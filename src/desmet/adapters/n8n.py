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

from desmet.adapters._prompts import (
    build_codegen_prompt,
    build_deploy_prompt,
    build_requirements_prompt,
    build_system_message,
    build_testing_prompt,
)
from desmet.adapters._tracing import (
    build_stage_result,
    finish_trace,
    record_message,
    record_usage,
    record_llm_duration,
    start_trace,
)
from desmet.adapters._validation import audit_workspace
from desmet.adapters.registry import load_platform_info
from desmet.harness.adapter import VisualPlatformAdapter
from desmet.harness.context import StageContext
from desmet.harness.models import PlatformInfo
from desmet.harness.results import (
    CodeResult,
    DeployResult,
    RequirementsResult,
    StageResult,
    TestResult,
)
from desmet.llm_config import get_config as get_llm_config

logger = logging.getLogger(__name__)


# ── N8nClient ──────────────────────────────────────────────────────────


class N8nClient:
    """Async wrapper around the n8n REST API v1."""

    def __init__(self, base_url: str, api_key: str | None = None):
        if not api_key:
            raise ValueError("n8n api_key is required (set N8N_API_KEY env var)")
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "X-N8N-API-KEY": api_key,
            "Content-Type": "application/json",
        }
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._headers,
                timeout=60.0,
            )
        return self._client

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
        self, execution_id: str, timeout: int = 600,
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
        raise TimeoutError(
            f"n8n execution {execution_id} did not complete within {timeout}s"
        )

    # ── Health ─────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        try:
            client = await self._ensure_client()
            resp = await client.get("/api/v1/workflows", params={"limit": 1})
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
    """
    if not api_key:
        raise ValueError(f"API key required for provider '{provider}'")

    if provider == "anthropic":
        return "anthropicApi", {"apiKey": api_key}

    # OpenAI, OpenRouter, and any OpenAI-compatible provider
    data: dict[str, str] = {"apiKey": api_key}
    if base_url:
        data["baseUrl"] = base_url
    return "openAiApi", data


_CONTAINER_RESULTS_ROOT = "/desmet-results"


class N8nAdapter(VisualPlatformAdapter):
    """n8n adapter — creates AI Agent workflows via the REST API."""

    max_retries: int = 3

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
        if not await self._client.health_check():
            raise RuntimeError(
                f"n8n is not reachable at {self.base_url}. "
                "Start it with: docker compose --profile n8n up -d"
            )
        cfg = get_llm_config(model=self.config.get("model"))
        self._model_name = cfg.model
        cred_type, cred_data = _map_credential(
            cfg.provider.value, cfg.model, cfg.api_key, cfg.base_url,
        )
        self._credential_id = await self._client.create_credential(
            cred_type, "desmet-llm", cred_data,
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

    # ── Workspace path translation ─────────────────────────────────────

    def _translate_workspace(self, host_path: str) -> str:
        """Translate a host workspace path to the container-side path."""
        import re
        normalised = host_path.replace("\\", "/")
        match = re.search(r"results/(.+)$", normalised)
        if match:
            return f"{_CONTAINER_RESULTS_ROOT}/{match.group(1)}"
        return normalised

    # ── Stage executor ─────────────────────────────────────────────────

    async def _execute_n8n_stage(
        self,
        stage_name: str,
        prompt_fn,
        result_cls: type[StageResult],
        context: StageContext,
    ) -> StageResult:
        """Create, execute, and clean up an n8n workflow for one SDLC stage."""
        from desmet.adapters.n8n_templates import build_workflow

        trace = start_trace()
        workflow_id: str | None = None
        try:
            if stage_name == "codegen":
                prior = context.get_prior_result("requirements")
                prompt = prompt_fn(context.story, prior_requirements=prior)
            else:
                prompt = prompt_fn(context.story)
            system_msg = build_system_message(context.story)
            workspace = self._translate_workspace(str(context.workspace))

            record_message(trace, "user", prompt)

            iterations = 0
            success = False

            for attempt in range(self.max_retries + 1):
                wf_def = build_workflow(
                    stage_name=stage_name,
                    prompt=prompt,
                    system_msg=system_msg or "",
                    workspace=workspace,
                    model_name=self._model_name or "",
                    credential_id=self._credential_id or "",
                )
                workflow_id = await self._client.create_workflow(wf_def)

                try:
                    await self._client.activate_workflow(workflow_id)
                except Exception:
                    pass

                exec_id = await self._client.execute_workflow(workflow_id, {
                    "prompt": prompt,
                    "workspace": workspace,
                })
                exec_data = await self._client.wait_for_execution(
                    exec_id,
                    timeout=context.metadata.get("time_budget", 600),
                )

                iterations += 1
                self._collect_execution_metrics(trace, exec_data)

                scope_warnings = audit_workspace(
                    stage_name, str(context.workspace),
                    set(context.metadata.get("baseline_files", [])),
                )

                if not scope_warnings:
                    success = True
                    break

                feedback = "; ".join(scope_warnings)
                logger.info(
                    "n8n stage %s attempt %d/%d failed validation: %s",
                    stage_name, attempt + 1, self.max_retries + 1, feedback,
                )
                record_message(
                    trace, "system",
                    f"Validation failed (attempt {attempt + 1}): {feedback}",
                )

                await self._client.delete_workflow(workflow_id)
                workflow_id = None

                prompt = (
                    f"{prompt}\n\n"
                    f"PREVIOUS ATTEMPT FAILED VALIDATION:\n{feedback}\n"
                    f"Please fix these issues."
                )

            return build_stage_result(
                result_cls, "n8n", stage_name, trace,
                success=success, iterations=iterations,
            )

        except Exception as e:
            finish_trace(trace, error=str(e))
            return build_stage_result(
                result_cls, "n8n", stage_name, trace,
                success=False, iterations=0, error_message=str(e),
            )
        finally:
            if workflow_id:
                try:
                    await self._client.delete_workflow(workflow_id)
                except Exception:
                    pass

    def _collect_execution_metrics(self, trace, exec_data: dict) -> None:
        """Extract timing and token usage from n8n execution response."""
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

        run_data = (
            exec_data.get("data", {})
            .get("resultData", {})
            .get("runData", {})
        )
        for node_name, node_runs in run_data.items():
            if not isinstance(node_runs, list):
                continue
            for run in node_runs:
                output_data = run.get("data", {}).get("main", [[]])
                for items in output_data:
                    if not isinstance(items, list):
                        continue
                    for item in items:
                        usage = (
                            item.get("json", {}).get("tokenUsage")
                            or item.get("json", {}).get("usage")
                        )
                        if usage and isinstance(usage, dict):
                            inp = usage.get("promptTokens", 0) or usage.get("prompt_tokens", 0)
                            out = usage.get("completionTokens", 0) or usage.get("completion_tokens", 0)
                            if inp or out:
                                record_usage(trace, int(inp), int(out), model=self._model_name)

    # ── SDLC stage methods ─────────────────────────────────────────────

    async def generate_requirements(self, context: StageContext) -> RequirementsResult:
        return await self._execute_n8n_stage(
            "requirements", build_requirements_prompt, RequirementsResult, context,
        )

    async def generate_code(self, context: StageContext) -> CodeResult:
        return await self._execute_n8n_stage(
            "codegen", build_codegen_prompt, CodeResult, context,
        )

    async def generate_tests(self, context: StageContext) -> TestResult:
        return await self._execute_n8n_stage(
            "testing", build_testing_prompt, TestResult, context,
        )

    async def build_and_deploy(self, context: StageContext) -> DeployResult:
        return await self._execute_n8n_stage(
            "deploy", build_deploy_prompt, DeployResult, context,
        )

    # ── Metadata ──────────────────────────────────────────────────────

    def get_observability_info(self) -> dict[str, Any]:
        return {
            "has_tracing": True,
            "has_step_through": False,
            "has_replay": False,
            "has_state_inspection": True,
            "has_memory_inspection": False,
            "trace_format": "n8n execution log",
            "notes": (
                "Execution data captured via n8n REST API. "
                "Per-node timing and output available from execution details."
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
