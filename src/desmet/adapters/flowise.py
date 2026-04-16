"""
Flowise Platform Adapter

Communicates with Flowise via its REST API to create and execute
AI Agent chatflows for each SDLC pipeline stage.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import json

import httpx

from desmet.adapters._tracing import record_tool_call, record_usage
from desmet.adapters._visual_base import VisualAgentAdapter
from desmet.adapters.registry import load_platform_info
from desmet.harness.models import PlatformInfo

logger = logging.getLogger(__name__)


# ── Provider → Flowise node/credential mapping ────────────────────────
#
# Each DESMET provider maps to a (chat-model node name, credential type,
# credential field name) triple.  ``chat-model node name`` is the key
# used against ``/api/v1/nodes/{name}``; ``credential type`` is the one
# required by ``POST /api/v1/credentials``.
_PROVIDER_TO_FLOWISE: dict[str, tuple[str, str, str]] = {
    "openrouter": ("chatOpenRouter", "openRouterApi", "openRouterApiKey"),
    "openai": ("chatOpenAI", "openAIApi", "openAIApiKey"),
    "anthropic": ("chatAnthropic", "anthropicApi", "anthropicApiKey"),
}


def _provider_mapping(provider: str) -> tuple[str, str, str]:
    if provider not in _PROVIDER_TO_FLOWISE:
        raise ValueError(
            f"Flowise adapter does not yet support provider '{provider}'. "
            f"Supported: {sorted(_PROVIDER_TO_FLOWISE)}"
        )
    return _PROVIDER_TO_FLOWISE[provider]


# ── FlowiseClient ─────────────────────────────────────────────────────


class FlowiseClient:
    """Async wrapper around the Flowise REST API."""

    def __init__(self, base_url: str, api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self._headers: dict[str, str] = {
            "Content-Type": "application/json",
            "x-request-from": "internal",
        }
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._headers,
                timeout=300.0,  # longer timeout — predict is synchronous
            )
        return self._client

    # ── Chatflows ──────────────────────────────────────────────────────

    async def create_chatflow(self, definition: dict) -> str:
        """Create a chatflow. Returns the chatflow ID.

        Flowise expects ``flowData`` as a serialised JSON string
        containing nodes and edges, not as top-level dict keys.
        """
        client = await self._ensure_client()
        payload = {
            "name": definition.get("name", "desmet"),
            "type": definition.get("type", "CHATFLOW"),
            "deployed": definition.get("deployed", False),
            "isPublic": definition.get("isPublic", False),
            "flowData": json.dumps(
                {
                    "nodes": definition.get("nodes", []),
                    "edges": definition.get("edges", []),
                }
            ),
        }
        resp = await client.post("/api/v1/chatflows", json=payload)
        resp.raise_for_status()
        return resp.json()["id"]

    async def delete_chatflow(self, chatflow_id: str) -> None:
        client = await self._ensure_client()
        resp = await client.delete(f"/api/v1/chatflows/{chatflow_id}")
        if resp.status_code != 404:
            resp.raise_for_status()

    # ── Node specs (for template building) ─────────────────────────────

    async def get_node_spec(self, name: str) -> dict:
        """Fetch a node spec from ``/api/v1/nodes/{name}``."""
        client = await self._ensure_client()
        resp = await client.get(f"/api/v1/nodes/{name}")
        resp.raise_for_status()
        return resp.json()

    # ── Tools ──────────────────────────────────────────────────────────

    async def create_tool(
        self,
        name: str,
        description: str,
        func: str,
        schema_json: str = "[]",
    ) -> str:
        """Register a custom tool. Returns the tool ID."""
        client = await self._ensure_client()
        resp = await client.post(
            "/api/v1/tools",
            json={
                "name": name,
                "description": description,
                "color": "#1E88E5",
                "iconSrc": "",
                "schema": schema_json,
                "func": func,
            },
        )
        resp.raise_for_status()
        return resp.json()["id"]

    async def delete_tool(self, tool_id: str) -> None:
        client = await self._ensure_client()
        resp = await client.delete(f"/api/v1/tools/{tool_id}")
        if resp.status_code != 404:
            resp.raise_for_status()

    # ── Credentials ────────────────────────────────────────────────────

    async def create_credential(
        self, name: str, credential_name: str, plain_data: dict
    ) -> str:
        """Create a credential. Returns the credential ID."""
        client = await self._ensure_client()
        resp = await client.post(
            "/api/v1/credentials",
            json={
                "name": name,
                "credentialName": credential_name,
                "plainDataObj": plain_data,
            },
        )
        resp.raise_for_status()
        return resp.json()["id"]

    async def delete_credential(self, credential_id: str) -> None:
        client = await self._ensure_client()
        resp = await client.delete(f"/api/v1/credentials/{credential_id}")
        if resp.status_code != 404:
            resp.raise_for_status()

    # ── Execution ──────────────────────────────────────────────────────

    async def predict(self, chatflow_id: str, question: str) -> dict:
        """Send a prediction request. Returns result synchronously."""
        client = await self._ensure_client()
        resp = await client.post(
            f"/api/v1/prediction/{chatflow_id}",
            json={"question": question},
        )
        resp.raise_for_status()
        return resp.json()

    # ── Health ─────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        try:
            client = await self._ensure_client()
            resp = await client.get("/api/v1/ping")
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# ── FlowiseAdapter ─────────────────────────────────────────────────────


class FlowiseAdapter(VisualAgentAdapter):
    """Flowise adapter — creates AI Agent chatflows via the REST API."""

    def __init__(self, config: dict[str, Any] | None = None):
        config = config or {}
        super().__init__(
            base_url=config.get("base_url", "http://localhost:3200"),
            api_key=config.get("api_key") or os.environ.get("FLOWISE_API_KEY"),
            config=config,
        )
        self._client: FlowiseClient | None = None
        self._model_name: str | None = None
        self._chat_model_node: str | None = None  # e.g. "chatOpenRouter"
        self._credential_id: str | None = None
        self._node_specs: dict[str, dict[str, Any]] = {}

    @property
    def platform_info(self) -> PlatformInfo:
        return load_platform_info("flowise")

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def initialize(self) -> None:
        self._client = FlowiseClient(
            self.base_url,
            api_key=self.api_key or os.environ.get("FLOWISE_API_KEY"),
        )
        if not await self._client.health_check():
            raise RuntimeError(
                f"Flowise is not reachable at {self.base_url}. "
                "Start it with: docker compose --profile flowise up -d"
            )
        from desmet.llm_config import get_config as get_llm_config

        cfg = get_llm_config(model=self.config.get("model"))
        self._model_name = cfg.model

        # Provider → Flowise chat model node + credential wiring
        chat_node, cred_type, cred_field = _provider_mapping(cfg.provider.value)
        self._chat_model_node = chat_node

        if not cfg.api_key:
            raise RuntimeError(
                f"API key required for provider '{cfg.provider.value}' "
                f"(env var: {cfg.api_key_env_var})"
            )

        # Cache the node specs we'll reuse on every stage.
        for name in (chat_node, "customTool", "bufferMemory", "toolAgent"):
            self._node_specs[name] = await self._client.get_node_spec(name)

        # Create the LLM credential once for the lifetime of this adapter.
        self._credential_id = await self._client.create_credential(
            name=f"desmet-{cfg.provider.value}",
            credential_name=cred_type,
            plain_data={cred_field: cfg.api_key},
        )

        self._initialized = True
        logger.info(
            "Flowise adapter initialized (provider=%s, credential=%s)",
            cfg.provider.value,
            self._credential_id,
        )

    async def shutdown(self) -> None:
        if self._client:
            if self._credential_id:
                try:
                    await self._client.delete_credential(self._credential_id)
                except Exception:
                    logger.warning(
                        "Failed to delete Flowise credential %s", self._credential_id
                    )
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
        return await self._client.create_chatflow(workflow_definition)

    async def execute_workflow(self, workflow_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        assert self._client is not None
        return await self._client.predict(workflow_id, inputs.get("question", ""))

    async def delete_workflow(self, workflow_id: str) -> None:
        assert self._client is not None
        await self._client.delete_chatflow(workflow_id)

    # ── VisualAgentAdapter abstract methods ─────────────────────────────

    async def _run_workflow(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str,
        workspace: str,
    ) -> dict:
        """Create workspace tools + chatflow, execute, clean up, return result."""
        from desmet.adapters.flowise_templates import (
            TOOL_DEFS,
            build_chatflow,
            tool_js_execute,
            tool_js_read,
            tool_js_write,
        )

        assert self._client is not None
        assert self._credential_id is not None
        assert self._chat_model_node is not None

        js_by_name = {
            "execute_shell": tool_js_execute(workspace),
            "read_file": tool_js_read(workspace),
            "write_file": tool_js_write(workspace),
        }
        # Use stage-scoped tool names to avoid collisions between
        # concurrent stages and to keep cleanup unambiguous.
        tool_id_by_name: dict[str, str] = {}
        created_tool_ids: list[str] = []
        try:
            for td in TOOL_DEFS:
                tool_id = await self._client.create_tool(
                    name=f"desmet_{stage_name}_{td['name']}",
                    description=td["description"],
                    func=js_by_name[td["name"]],
                    schema_json=td["schema_json"],
                )
                tool_id_by_name[td["name"]] = tool_id
                created_tool_ids.append(tool_id)

            # Remap specs so the chatflow builder finds the right chat
            # model node under the canonical key.
            specs_for_builder = {
                "chatOpenRouter": self._node_specs[self._chat_model_node],
                "customTool": self._node_specs["customTool"],
                "bufferMemory": self._node_specs["bufferMemory"],
                "toolAgent": self._node_specs["toolAgent"],
            }

            cf_def = build_chatflow(
                stage_name=stage_name,
                system_msg=system_msg,
                model_name=self._model_name or "",
                credential_id=self._credential_id,
                tool_id_by_name=tool_id_by_name,
                specs=specs_for_builder,
            )
            chatflow_id = await self._client.create_chatflow(cf_def)
            try:
                return await self._client.predict(chatflow_id, prompt)
            finally:
                try:
                    await self._client.delete_chatflow(chatflow_id)
                except Exception:
                    pass
        finally:
            for tid in created_tool_ids:
                try:
                    await self._client.delete_tool(tid)
                except Exception:
                    pass

    def _collect_execution_metrics(self, trace, exec_data: dict) -> None:
        """Extract token usage and tool calls from a Flowise prediction.

        Flowise's ``/api/v1/prediction/{id}`` response carries a
        ``usedTools`` list for ToolAgent flows — one entry per call the
        agent made during this run, including the stripped tool name,
        parsed args, raw output, and an ``error`` field.  We fan that
        into per-call ``ToolCall`` trace entries so framework metrics
        (tool_calls_count, redundant_tool_call_rate, tool_failure_rate)
        can be computed from it.

        Platform limitation: Flowise does not surface ``tokenUsage`` in
        ToolAgent responses regardless of streaming mode, so token
        counts will be zero for this platform.
        """
        token_usage = exec_data.get("tokenUsage") or exec_data.get("usage")
        if token_usage and isinstance(token_usage, dict):
            inp = token_usage.get("promptTokens", 0) or token_usage.get("prompt_tokens", 0)
            out = token_usage.get("completionTokens", 0) or token_usage.get("completion_tokens", 0)
            if inp or out:
                record_usage(trace, int(inp), int(out), model=self._model_name)

        for entry in exec_data.get("usedTools") or []:
            if not isinstance(entry, dict):
                continue
            # Tool names are prefixed ``desmet_<stage>_<name>`` at
            # registration time — strip the prefix for comparability
            # with other platforms' canonical ``read_file`` / ``write_file``
            # / ``execute_shell`` names.
            raw_name = entry.get("tool") or ""
            name = raw_name
            for canonical in ("execute_shell", "read_file", "write_file"):
                if raw_name.endswith(canonical):
                    name = canonical
                    break
            args = entry.get("toolInput") or {}
            if not isinstance(args, dict):
                args = {"input": args}
            err = entry.get("error") or ""
            record_tool_call(
                trace,
                name=name,
                args=args,
                result=entry.get("toolOutput"),
                success=not err,
            )

    # ── Metadata ──────────────────────────────────────────────────────

    def get_observability_info(self) -> dict[str, Any]:
        return {
            "has_tracing": False,
            "has_step_through": False,
            "has_replay": False,
            "has_state_inspection": False,
            "has_memory_inspection": False,
            "trace_format": "Flowise predict response (usedTools array)",
            "exposes_per_tool_call": True,
            "exposes_tool_timing": False,
            "exposes_token_usage": False,  # dropped by ToolAgent
            "exposes_node_events": False,
            "notes": (
                "Minimal trace: the /api/v1/prediction response carries "
                "a usedTools array with input/output/error per call, but "
                "no per-call timestamps, no token usage for ToolAgent, "
                "and no per-node execution log. first_action_latency_ms "
                "and framework_overhead_ms are therefore unavailable."
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
                "Flowise does not natively checkpoint agent state."
            ),
        }
