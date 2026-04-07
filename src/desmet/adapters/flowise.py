"""
Flowise Platform Adapter

Communicates with Flowise via its REST API to create and execute
AI Agent chatflows for each SDLC pipeline stage.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from desmet.adapters._tracing import record_usage
from desmet.adapters._visual_base import VisualAgentAdapter
from desmet.adapters.registry import load_platform_info
from desmet.harness.models import PlatformInfo

logger = logging.getLogger(__name__)


# ── FlowiseClient ─────────────────────────────────────────────────────


class FlowiseClient:
    """Async wrapper around the Flowise REST API."""

    def __init__(self, base_url: str, api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self._headers: dict[str, str] = {"Content-Type": "application/json"}
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
        """Create a chatflow. Returns the chatflow ID."""
        client = await self._ensure_client()
        resp = await client.post("/api/v1/chatflows", json=definition)
        resp.raise_for_status()
        return resp.json()["id"]

    async def delete_chatflow(self, chatflow_id: str) -> None:
        client = await self._ensure_client()
        resp = await client.delete(f"/api/v1/chatflows/{chatflow_id}")
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
            resp = await client.get("/api/v1/chatflows", params={"limit": 1})
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
            base_url=config.get("base_url", "http://localhost:3000"),
            api_key=config.get("api_key") or os.environ.get("FLOWISE_API_KEY"),
            config=config,
        )
        self._client: FlowiseClient | None = None
        self._model_name: str | None = None

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
        self._initialized = True
        logger.info("Flowise adapter initialized")

    async def shutdown(self) -> None:
        if self._client:
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
        """Create a chatflow, execute it, clean up, return result."""
        from desmet.adapters.flowise_templates import build_chatflow

        cf_def = build_chatflow(
            stage_name=stage_name,
            prompt=prompt,
            system_msg=system_msg,
            workspace=workspace,
            model_name=self._model_name or "",
        )
        chatflow_id = await self._client.create_chatflow(cf_def)
        try:
            result = await self._client.predict(chatflow_id, prompt)
            return result
        finally:
            try:
                await self._client.delete_chatflow(chatflow_id)
            except Exception:
                pass

    def _collect_execution_metrics(self, trace, exec_data: dict) -> None:
        """Extract token usage from Flowise prediction response."""
        token_usage = exec_data.get("tokenUsage") or exec_data.get("usage")
        if token_usage and isinstance(token_usage, dict):
            inp = token_usage.get("promptTokens", 0) or token_usage.get("prompt_tokens", 0)
            out = token_usage.get("completionTokens", 0) or token_usage.get("completion_tokens", 0)
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
            "trace_format": "Flowise chatflow log",
            "notes": (
                "Execution data from prediction API. "
                "Chatflow logs available via Flowise UI."
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
