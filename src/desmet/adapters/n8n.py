"""
n8n Platform Adapter

Communicates with n8n via its REST API v1 to create and execute
AI Agent workflows for each SDLC pipeline stage.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

from desmet.adapters._shared.tracing import (
    record_llm_duration,
    record_node_event,
    record_tool_call,
    record_usage,
)
from desmet.adapters._shared.visual_base import VisualAgentAdapter
from desmet.adapters.registry import load_platform_info
from desmet.harness.models import PlatformInfo
from desmet.llm_config import get_config as get_llm_config

logger = logging.getLogger(__name__)


# ── N8nClient ──────────────────────────────────────────────────────────


class N8nClient:
    """Async wrapper around the n8n REST API v1."""

    def __init__(self, base_url: str, api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            self._headers["X-N8N-API-KEY"] = api_key
        self._client: httpx.AsyncClient | None = None
        self._owns_api_key = False  # True if we created the key ourselves

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._headers,
                timeout=60.0,
            )
        return self._client

    async def auto_provision(self) -> None:
        """Set up n8n owner account + API key if not already configured."""
        if self._api_key:
            return
        client = await self._ensure_client()
        email = "desmet@local.dev"
        password = "Desmet123!"
        # 1. Create owner account (idempotent — 400 if already exists)
        setup_resp = await client.post(
            "/rest/owner/setup",
            json={
                "email": email,
                "firstName": "DESMET",
                "lastName": "Harness",
                "password": password,
            },
        )
        # 2. Login to get session cookie
        resp = await client.post(
            "/rest/login",
            json={"emailOrLdapLoginId": email, "password": password},
        )
        if resp.status_code != 200:
            if setup_resp.status_code == 400:
                raise RuntimeError(
                    f"n8n login failed ({resp.status_code}): owner was set up "
                    f"previously with different credentials. Reset with: "
                    f"docker exec desmet-n8n n8n user-management:reset"
                )
            raise RuntimeError(f"n8n login failed ({resp.status_code}): {resp.text[:200]}")
        # Capture the session cookie — httpx may not auto-forward it
        # due to domain matching rules with localhost base_url.
        auth_cookie = client.cookies.get("n8n-auth", "")
        session_cookies = {"n8n-auth": auth_cookie} if auth_cookie else None
        # 3. Create API key via /rest/api-keys (n8n ≥1.x)
        #    First delete any existing "desmet-eval" key (rawApiKey is
        #    only returned on creation, so we can't reuse a stale one).
        import time

        list_resp = await client.get("/rest/api-keys", cookies=session_cookies)
        if list_resp.status_code == 200:
            for key in list_resp.json().get("data", []):
                if key.get("label") == "desmet-eval":
                    await client.delete(
                        f"/rest/api-keys/{key['id']}", cookies=session_cookies
                    )

        expires_at = int((time.time() + 365 * 86400) * 1000)  # 1 year
        resp = await client.post(
            "/rest/api-keys",
            json={
                "label": "desmet-eval",
                "scopes": [
                    "workflow:create",
                    "workflow:read",
                    "workflow:update",
                    "workflow:delete",
                    "workflow:execute",
                    "credential:create",
                    "credential:read",
                    "credential:delete",
                    "execution:read",
                ],
                "expiresAt": expires_at,
            },
            cookies=session_cookies,
        )
        if resp.status_code in (200, 201):
            api_key = resp.json().get("data", {}).get("rawApiKey")
            if api_key:
                self._api_key = api_key
                self._headers["X-N8N-API-KEY"] = api_key
                self._client.headers["X-N8N-API-KEY"] = api_key
                self._owns_api_key = True
                return
        raise RuntimeError(
            f"Failed to create n8n API key ({resp.status_code}): {resp.text[:200]}"
        )

    # ── Credentials ────────────────────────────────────────────────────

    async def create_credential(self, cred_type: str, name: str, data: dict) -> str:
        """Create a credential in n8n. Returns the credential ID."""
        client = await self._ensure_client()
        resp = await client.post(
            "/api/v1/credentials",
            json={"type": cred_type, "name": name, "data": data},
        )
        resp.raise_for_status()
        return resp.json()["id"]

    async def delete_credential(self, credential_id: str) -> None:
        client = await self._ensure_client()
        resp = await client.delete(f"/api/v1/credentials/{credential_id}")
        if resp.status_code != 404:
            resp.raise_for_status()

    # ── Workflows ──────────────────────────────────────────────────────

    async def create_workflow(self, definition: dict) -> str:
        """Create a workflow. Returns the workflow ID."""
        client = await self._ensure_client()
        resp = await client.post("/api/v1/workflows", json=definition)
        resp.raise_for_status()
        return resp.json()["id"]

    async def activate_workflow(self, workflow_id: str) -> None:
        client = await self._ensure_client()
        resp = await client.patch(
            f"/api/v1/workflows/{workflow_id}",
            json={"active": True},
        )
        resp.raise_for_status()

    async def execute_workflow(self, workflow_id: str, data: dict) -> str:
        """Execute a workflow via the test webhook. Returns execution ID."""
        client = await self._ensure_client()
        resp = await client.post(
            f"/api/v1/workflows/{workflow_id}/run",
            json=data,
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("id") or body.get("executionId", "")

    async def delete_workflow(self, workflow_id: str) -> None:
        client = await self._ensure_client()
        resp = await client.delete(f"/api/v1/workflows/{workflow_id}")
        if resp.status_code != 404:
            resp.raise_for_status()

    # ── Executions ─────────────────────────────────────────────────────

    async def get_execution(self, execution_id: str) -> dict:
        client = await self._ensure_client()
        resp = await client.get(f"/api/v1/executions/{execution_id}")
        resp.raise_for_status()
        return resp.json()

    async def wait_for_execution(
        self,
        execution_id: str,
        timeout: int = 600,
    ) -> dict:
        """Poll until execution completes or timeout (seconds)."""
        deadline = asyncio.get_event_loop().time() + timeout
        delay = 1.0
        while asyncio.get_event_loop().time() < deadline:
            data = await self.get_execution(execution_id)
            status = data.get("status") or data.get("finished")
            if status in ("success", "error", "crashed", True):
                return data
            await asyncio.sleep(min(delay, 5.0))
            delay *= 1.5
        raise TimeoutError(f"n8n execution {execution_id} did not complete within {timeout}s")

    # ── Health ─────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        try:
            client = await self._ensure_client()
            resp = await client.get("/healthz")
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# ── Credential mapping ────────────────────────────────────────────────


def _map_credential(
    provider: str,
    model: str,
    api_key: str | None,
    base_url: str | None,
) -> tuple[str, dict[str, str]]:
    """Map DESMET LLM config to n8n credential type and data.

    Returns ``(n8n_credential_type, credential_data_dict)``.
    Raises ``ValueError`` if the API key is missing.

    n8n's ``@n8n/n8n-nodes-langchain`` package ships provider-specific
    credential types (e.g. ``openRouterApi``, ``anthropicApi``).  The
    generic ``openAiApi`` type in the public API has stricter ``allOf``
    schema validation than the UI, so prefer provider-specific types
    where available.
    """
    if not api_key:
        raise ValueError(f"API key required for provider '{provider}'")

    if provider == "anthropic":
        return "anthropicApi", {"apiKey": api_key}

    if provider == "openrouter":
        # openRouterApi has a hidden ``url`` field defaulting to
        # https://openrouter.ai/api/v1 — only ``apiKey`` is accepted.
        return "openRouterApi", {"apiKey": api_key}

    # OpenAI and OpenAI-compatible providers.  Field name is ``url``,
    # not ``baseUrl``.  The public API schema also requires the
    # conditional header fields even when ``header=False``.
    data: dict[str, Any] = {
        "apiKey": api_key,
        "organizationId": "",
        "header": False,
        "headerName": "",
        "headerValue": "",
    }
    if base_url:
        data["url"] = base_url
    return "openAiApi", data


class N8nAdapter(VisualAgentAdapter):
    """n8n adapter — creates AI Agent workflows via the REST API."""

    def __init__(self, config: dict[str, Any] | None = None):
        config = config or {}
        super().__init__(
            base_url=config.get("base_url", "http://localhost:5678"),
            api_key=config.get("api_key") or os.environ.get("N8N_API_KEY"),
            config=config,
        )
        self._client: N8nClient | None = None
        self._credential_id: str | None = None
        self._model_name: str | None = None

    @property
    def platform_info(self) -> PlatformInfo:
        return load_platform_info("n8n")

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def initialize(self) -> None:
        api_key = self.api_key or os.environ.get("N8N_API_KEY")
        self._client = N8nClient(self.base_url, api_key=api_key)
        await self._client.auto_provision()
        if not await self._client.health_check():
            raise RuntimeError(
                f"n8n is not reachable at {self.base_url}. "
                "Start it with: docker compose --profile n8n up -d"
            )
        cfg = get_llm_config(model=self.config.get("model"))
        self._model_name = cfg.model
        cred_type, cred_data = _map_credential(
            cfg.provider.value,
            cfg.model,
            cfg.api_key,
            cfg.base_url,
        )
        self._credential_id = await self._client.create_credential(
            cred_type,
            "desmet-llm",
            cred_data,
        )
        self._initialized = True
        logger.info("n8n adapter initialized (credential=%s)", self._credential_id)

    async def shutdown(self) -> None:
        if self._client:
            if self._credential_id:
                try:
                    await self._client.delete_credential(self._credential_id)
                except Exception:
                    logger.warning("Failed to delete n8n credential %s", self._credential_id)
                self._credential_id = None
            await self._client.close()
            self._client = None
        self._initialized = False

    async def health_check(self) -> bool:
        if self._client is None:
            return False
        return await self._client.health_check()

    # ── VisualPlatformAdapter contract ─────────────────────────────────

    async def create_workflow(self, workflow_definition: dict) -> str:
        assert self._client is not None
        return await self._client.create_workflow(workflow_definition)

    async def execute_workflow(self, workflow_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        assert self._client is not None
        exec_id = await self._client.execute_workflow(workflow_id, inputs)
        return await self._client.wait_for_execution(exec_id)

    async def delete_workflow(self, workflow_id: str) -> None:
        assert self._client is not None
        await self._client.delete_workflow(workflow_id)

    # ── Platform-specific workflow execution ───────────────────────────

    async def _run_workflow(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str,
        workspace: str,
    ) -> dict:
        """Create, execute, poll, and clean up one n8n workflow."""
        from desmet.adapters.n8n_templates import build_workflow

        wf_def = build_workflow(
            stage_name=stage_name,
            prompt=prompt,
            system_msg=system_msg,
            workspace=workspace,
            model_name=self._model_name or "",
            credential_id=self._credential_id or "",
        )
        workflow_id = await self._client.create_workflow(wf_def)
        try:
            try:
                await self._client.activate_workflow(workflow_id)
            except Exception:
                pass

            exec_id = await self._client.execute_workflow(
                workflow_id,
                {
                    "prompt": prompt,
                    "workspace": workspace,
                },
            )
            exec_data = await self._client.wait_for_execution(exec_id)
            return exec_data
        finally:
            try:
                await self._client.delete_workflow(workflow_id)
            except Exception:
                pass

    def _collect_execution_metrics(self, trace, exec_data: dict) -> None:
        """Extract timing, tokens, tool calls, and node events from n8n.

        n8n's execution response is the richest of the visual platforms:
        ``runData`` is keyed by node name, each entry carries timing
        (startedAt/executionTime), inputs/outputs, and per-node status.
        We record:
          * overall LLM wall-clock duration (aggregate)
          * token usage (per AI-node output)
          * one ``record_tool_call`` per tool-node invocation
          * one ``record_node_event`` per node run, so graph-level
            orchestration can be reconstructed in analysis
        """
        from datetime import datetime

        started = exec_data.get("startedAt")
        stopped = exec_data.get("stoppedAt")
        if started and stopped:
            try:
                t0 = datetime.fromisoformat(started.replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(stopped.replace("Z", "+00:00"))
                duration_ms = (t1 - t0).total_seconds() * 1000
                record_llm_duration(trace, duration_ms)
            except (ValueError, TypeError):
                pass

        run_data = exec_data.get("data", {}).get("resultData", {}).get("runData", {})
        for node_name, node_runs in run_data.items():
            if not isinstance(node_runs, list):
                continue
            for run in node_runs:
                exec_time_ms = run.get("executionTime") or 0
                success = (run.get("executionStatus") or "success") == "success"

                # Per-node event — lets the analyser reconstruct the
                # graph execution order across iterations.
                record_node_event(
                    trace,
                    node=node_name,
                    duration_ms=exec_time_ms,
                    success=success,
                )

                # Treat anything whose name hints at a tool as a tool
                # call.  n8n's AI Agent surfaces per-tool invocations as
                # separate nodes in runData (one per call).
                canonical = None
                for tool in ("execute_shell", "read_file", "write_file"):
                    if tool in node_name:
                        canonical = tool
                        break
                if canonical:
                    # Args come in on the input side of the run.
                    in_main = run.get("data", {}).get("main") or [[]]
                    args: dict = {}
                    if in_main and isinstance(in_main[0], list) and in_main[0]:
                        first = in_main[0][0]
                        if isinstance(first, dict):
                            args = first.get("json", {}) or {}
                    result = None
                    out_main = run.get("data", {}).get("main") or [[]]
                    if out_main and isinstance(out_main[-1], list) and out_main[-1]:
                        result = out_main[-1][0]
                    record_tool_call(
                        trace,
                        name=canonical,
                        args=args,
                        result=result,
                        duration_ms=float(exec_time_ms),
                        success=success,
                    )

                output_data = run.get("data", {}).get("main", [[]])
                for items in output_data:
                    if not isinstance(items, list):
                        continue
                    for item in items:
                        usage = item.get("json", {}).get("tokenUsage") or item.get("json", {}).get(
                            "usage"
                        )
                        if usage and isinstance(usage, dict):
                            inp = usage.get("promptTokens", 0) or usage.get("prompt_tokens", 0)
                            out = usage.get("completionTokens", 0) or usage.get(
                                "completion_tokens", 0
                            )
                            if inp or out:
                                record_usage(trace, int(inp), int(out), model=self._model_name)

    # ── Metadata ──────────────────────────────────────────────────────

    def get_observability_info(self) -> dict[str, Any]:
        return {
            "has_tracing": True,
            "has_step_through": False,
            "has_replay": False,
            "has_state_inspection": True,
            "has_memory_inspection": False,
            "trace_format": "n8n execution log",
            "exposes_per_tool_call": True,
            "exposes_tool_timing": True,
            "exposes_token_usage": True,
            "exposes_node_events": True,
            "notes": (
                "Richest trace of the visual platforms: runData keyed "
                "by node, per-node startedAt/executionTime, and tool "
                "inputs/outputs all surface via the REST API. The "
                "harness records per-tool-call ToolCall entries plus "
                "per-node record_node_event for graph reconstruction."
            ),
        }

    def get_failure_handling_info(self) -> dict[str, Any]:
        return {
            "has_checkpointing": False,
            "has_auto_recovery": False,
            "has_graceful_degradation": False,
            "supports_human_handoff": False,
            "is_idempotent": True,
            "notes": (
                "Adapter-side retry loop with workspace validation. "
                "n8n does not natively checkpoint AI Agent state."
            ),
        }
