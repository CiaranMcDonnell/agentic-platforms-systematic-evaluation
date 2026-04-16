"""
LangFlow Platform Adapter

Communicates with LangFlow via its REST API to create and execute
AI Agent flows for each SDLC pipeline stage.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from desmet.adapters._tracing import record_tool_call, record_usage
from desmet.adapters._visual_base import VisualAgentAdapter
from desmet.adapters.registry import load_platform_info
from desmet.harness.models import PlatformInfo

logger = logging.getLogger(__name__)


# ── LangFlowClient ────────────────────────────────────────────────────


class LangFlowClient:
    """Async wrapper around the LangFlow REST API."""

    def __init__(self, base_url: str, api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            self._headers["x-api-key"] = api_key
        self._client: httpx.AsyncClient | None = None
        self._authenticated = False

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            # Accept gzip so ``/api/v1/all`` (hefty JSON) streams efficiently.
            headers = {**self._headers, "Accept-Encoding": "gzip"}
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=300.0,
            )
        if not self._authenticated and not self._api_key:
            await self._auto_login()
        return self._client

    async def _auto_login(self) -> None:
        """Obtain a token via LangFlow's auto-login endpoint."""
        assert self._client is not None
        resp = await self._client.get("/api/v1/auto_login")
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            if token:
                self._client.headers["Authorization"] = f"Bearer {token}"
        self._authenticated = True

    # ── Component catalog ──────────────────────────────────────────────

    async def get_catalog(self) -> dict:
        """Fetch the full component catalog (``/api/v1/all``)."""
        client = await self._ensure_client()
        resp = await client.get("/api/v1/all")
        resp.raise_for_status()
        return resp.json()

    # ── API keys ───────────────────────────────────────────────────────
    #
    # Session Bearer tokens from ``/api/v1/auto_login`` can't authorise
    # the ``/api/v1/run/...`` endpoint (which requires an explicit API
    # key).  We mint one at init, remember the id, and delete it on
    # shutdown.

    async def create_api_key(self, name: str) -> tuple[str, str]:
        """Create a LangFlow API key. Returns ``(key_id, api_key)``."""
        client = await self._ensure_client()
        resp = await client.post("/api/v1/api_key/", json={"name": name})
        resp.raise_for_status()
        body = resp.json()
        return body["id"], body["api_key"]

    async def delete_api_key(self, key_id: str) -> None:
        client = await self._ensure_client()
        resp = await client.delete(f"/api/v1/api_key/{key_id}")
        if resp.status_code != 404:
            resp.raise_for_status()

    # ── Flows ──────────────────────────────────────────────────────────

    async def create_flow(self, definition: dict) -> str:
        """Create a flow. Returns the flow ID."""
        client = await self._ensure_client()
        # LangFlow ≥1.8 requires a trailing slash on collection endpoints
        resp = await client.post("/api/v1/flows/", json=definition)
        resp.raise_for_status()
        return resp.json()["id"]

    async def delete_flow(self, flow_id: str) -> None:
        client = await self._ensure_client()
        resp = await client.delete(f"/api/v1/flows/{flow_id}")
        if resp.status_code != 404:
            resp.raise_for_status()

    # ── Execution ──────────────────────────────────────────────────────

    async def run_flow(
        self,
        flow_id: str,
        input_value: str,
        api_key: str | None = None,
    ) -> dict:
        """Run a flow synchronously. Returns the result.

        The ``/api/v1/run/...`` endpoint is not accessible with a
        session Bearer token — it requires an ``x-api-key`` header
        (or ``?x-api-key=`` query arg).
        """
        client = await self._ensure_client()
        headers = {}
        if api_key:
            headers["x-api-key"] = api_key
        resp = await client.post(
            f"/api/v1/run/{flow_id}",
            json={"input_value": input_value, "output_type": "chat"},
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Health ─────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        try:
            client = await self._ensure_client()
            resp = await client.get("/health")
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# ── LangFlowAdapter ───────────────────────────────────────────────────


class LangFlowAdapter(VisualAgentAdapter):
    """LangFlow adapter — creates AI Agent flows via the REST API."""

    def __init__(self, config: dict[str, Any] | None = None):
        config = config or {}
        super().__init__(
            base_url=config.get("base_url", "http://localhost:7960"),
            api_key=config.get("api_key") or os.environ.get("LANGFLOW_API_KEY"),
            config=config,
        )
        self._client: LangFlowClient | None = None
        self._model_name: str | None = None
        self._llm_api_key: str | None = None
        self._catalog: dict[str, Any] | None = None
        self._run_api_key: str | None = None
        self._run_api_key_id: str | None = None

    @property
    def platform_info(self) -> PlatformInfo:
        return load_platform_info("langflow")

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def initialize(self) -> None:
        self._client = LangFlowClient(
            self.base_url,
            api_key=self.api_key or os.environ.get("LANGFLOW_API_KEY"),
        )
        if not await self._client.health_check():
            raise RuntimeError(
                f"LangFlow is not reachable at {self.base_url}. "
                "Start it with: docker compose --profile langflow up -d"
            )
        from desmet.llm_config import get_config as get_llm_config

        cfg = get_llm_config(model=self.config.get("model"))
        if cfg.provider.value != "openrouter":
            # The current flow template hardcodes OpenRouterComponent.
            # Add more providers by extending the template to accept
            # other chat model components (OpenAIModel, AnthropicModel).
            raise RuntimeError(
                f"LangFlow adapter currently only supports the 'openrouter' "
                f"provider; got {cfg.provider.value!r}"
            )
        if not cfg.api_key:
            raise RuntimeError(
                f"API key required for LangFlow (env var: {cfg.api_key_env_var})"
            )
        self._model_name = cfg.model
        self._llm_api_key = cfg.api_key
        self._catalog = await self._client.get_catalog()
        # Mint the run API key once — session tokens can't drive the
        # ``/api/v1/run/{flow_id}`` endpoint.
        self._run_api_key_id, self._run_api_key = await self._client.create_api_key(
            "desmet-eval-run"
        )
        self._initialized = True
        logger.info(
            "LangFlow adapter initialized (provider=%s, components=%d)",
            cfg.provider.value,
            sum(len(v) for v in self._catalog.values() if isinstance(v, dict)),
        )

    async def shutdown(self) -> None:
        if self._client:
            if self._run_api_key_id:
                try:
                    await self._client.delete_api_key(self._run_api_key_id)
                except Exception:
                    logger.warning(
                        "Failed to delete LangFlow API key %s", self._run_api_key_id
                    )
                self._run_api_key_id = None
                self._run_api_key = None
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
        return await self._client.create_flow(workflow_definition)

    async def execute_workflow(self, workflow_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        assert self._client is not None
        return await self._client.run_flow(workflow_id, inputs.get("input_value", ""))

    async def delete_workflow(self, workflow_id: str) -> None:
        assert self._client is not None
        await self._client.delete_flow(workflow_id)

    # ── VisualAgentAdapter abstract methods ─────────────────────────────

    async def _run_workflow(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str,
        workspace: str,
    ) -> dict:
        """Create a flow, run it, clean up, return result."""
        from desmet.adapters.langflow_templates import build_flow

        assert self._client is not None
        assert self._catalog is not None
        assert self._llm_api_key is not None

        flow_def = build_flow(
            stage_name=stage_name,
            system_msg=system_msg,
            model_name=self._model_name or "",
            api_key=self._llm_api_key,
            workspace=workspace,
            catalog=self._catalog,
        )
        flow_id = await self._client.create_flow(flow_def)
        try:
            result = await self._client.run_flow(
                flow_id, prompt, api_key=self._run_api_key
            )
            return result
        finally:
            try:
                await self._client.delete_flow(flow_id)
            except Exception:
                pass

    def _collect_execution_metrics(self, trace, exec_data: dict) -> None:
        """Extract tokens and tool calls from a LangFlow run response.

        LangFlow returns a nested envelope:
        ``{session_id, outputs: [{inputs, outputs: [{results: {message}, artifacts, ...}]}]}``.

        Tool invocations surface in a few places depending on version:
          * ``message.properties.source`` — the component that emitted
            each sub-message.  PythonCodeStructuredTool outputs appear
            as separate results entries and are our primary signal.
          * ``message.data.content_blocks`` — newer LangFlow builds
            include structured tool-call blocks with ``type: "tool_use"``
            and the tool input/output.
          * ``message.additional_kwargs.tool_calls`` — LangChain-style
            pass-through used for some model backends.

        The parser walks all three defensively — whichever it finds
        first gets recorded.  Usage data is also extracted from the
        agent's final ``message.data.usage_metadata`` when present.
        """
        outputs = exec_data.get("outputs") or []
        for output_frame in outputs:
            inner = output_frame.get("outputs") or []
            for entry in inner:
                # 1) Token usage on the agent's message.
                msg = (entry.get("results") or {}).get("message") or {}
                data = msg.get("data") or {}
                usage = (
                    data.get("usage_metadata")
                    or entry.get("token_usage")
                    or entry.get("usage")
                )
                if isinstance(usage, dict):
                    inp = (
                        usage.get("input_tokens")
                        or usage.get("prompt_tokens")
                        or usage.get("prompt_token_count", 0)
                    )
                    out = (
                        usage.get("output_tokens")
                        or usage.get("completion_tokens")
                        or usage.get("candidates_token_count", 0)
                    )
                    if inp or out:
                        record_usage(trace, int(inp), int(out), model=self._model_name)

                # 2) Structured content blocks (newer LangFlow shape).
                for block in data.get("content_blocks") or []:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") in ("tool_use", "tool_call"):
                        name = block.get("name") or block.get("tool") or "unknown"
                        record_tool_call(
                            trace,
                            name=name,
                            args=block.get("input") or block.get("args") or {},
                            result=block.get("output") or block.get("result"),
                            success=not block.get("error"),
                        )

                # 3) LangChain-style tool calls on additional_kwargs.
                for tc in (msg.get("additional_kwargs") or {}).get("tool_calls") or []:
                    if not isinstance(tc, dict):
                        continue
                    fn = tc.get("function") or {}
                    name = fn.get("name") or tc.get("name") or "unknown"
                    args = fn.get("arguments") or tc.get("args") or {}
                    record_tool_call(trace, name=name, args=args, result=None, success=True)

                # 4) Fall-through: if this message came from a
                # PythonCodeStructuredTool component, treat it as a
                # tool invocation even without structured metadata.
                source = ((msg.get("properties") or {}).get("source") or {})
                if source.get("source") == "PythonCodeStructuredTool":
                    display = source.get("display_name") or "PythonCodeStructuredTool"
                    record_tool_call(
                        trace,
                        name=display,
                        args={},
                        result=msg.get("text"),
                        success=not msg.get("error"),
                    )

    # ── Metadata ──────────────────────────────────────────────────────

    def get_observability_info(self) -> dict[str, Any]:
        return {
            "has_tracing": True,
            "has_step_through": False,
            "has_replay": False,
            "has_state_inspection": True,
            "has_memory_inspection": False,
            "trace_format": "LangFlow nested outputs + content_blocks",
            "exposes_per_tool_call": True,
            "exposes_tool_timing": False,
            "exposes_token_usage": True,  # on message.data.usage_metadata
            "exposes_node_events": False,
            "notes": (
                "Tool calls surface via three paths depending on version: "
                "message.data.content_blocks[type=tool_use], "
                "message.additional_kwargs.tool_calls, or component "
                "source attribution. Per-call timing is not in the "
                "response, so first_action_latency_ms stays None. "
                "Token usage is available on message.data.usage_metadata."
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
                "LangFlow does not natively checkpoint agent state."
            ),
        }
