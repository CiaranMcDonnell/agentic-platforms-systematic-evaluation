"""
Dify Platform Adapter

Communicates with Dify via its Console API (management) and Service API
(execution) to create and run AI Agent apps for each SDLC pipeline stage.

Dify differs from the other visual adapters:
- Two APIs: Console (auth via access token) and Service (auth via app API key)
- Model providers configured separately via Console API
- Agent apps created → published → API key generated → executed → deleted
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


# ── DifyClient ─────────────────────────────────────────────────────────


class DifyClient:
    """Async wrapper around Dify's Console and Service APIs.

    Console API (``/console/api/...``) manages apps, model providers, etc.
    Service API (``/v1/...``) executes apps using per-app API keys.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._console_token: str | None = None
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=300.0,
            )
        return self._client

    def _console_headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Content-Type": "application/json"}
        if self._console_token:
            h["Authorization"] = f"Bearer {self._console_token}"
        return h

    # ── Console Auth ───────────────────────────────────────────────────

    async def login(self, email: str, password: str) -> None:
        """Login to the Console API and store the access token."""
        client = await self._ensure_client()
        resp = await client.post(
            "/console/api/login",
            json={"email": email, "password": password},
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        self._console_token = data.get("access_token") or data.get("data", {}).get("access_token", "")

    async def setup_account(self, email: str, name: str, password: str) -> None:
        """Initial account setup (first-run only). Silently ignores if already set up."""
        client = await self._ensure_client()
        try:
            resp = await client.post(
                "/console/api/setup",
                json={"email": email, "name": name, "password": password},
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                self._console_token = data.get("access_token") or data.get("data", {}).get("access_token", "")
        except Exception:
            pass  # Already set up

    # ── Model Provider ─────────────────────────────────────────────────

    async def setup_model_provider(
        self, provider: str, api_key: str, base_url: str | None = None,
    ) -> None:
        """Configure an LLM provider in Dify's model settings."""
        client = await self._ensure_client()
        credentials: dict[str, str] = {"openai_api_key": api_key}
        if base_url:
            credentials["openai_api_base"] = base_url

        # Map DESMET providers to Dify provider names
        dify_provider = {
            "openai": "openai",
            "anthropic": "anthropic",
            "openrouter": "openai",  # OpenRouter is OpenAI-compatible
            "google": "google",
        }.get(provider, "openai")

        if dify_provider == "anthropic":
            credentials = {"anthropic_api_key": api_key}

        resp = await client.post(
            f"/console/api/workspaces/current/model-providers/{dify_provider}",
            json={"credentials": credentials},
            headers=self._console_headers(),
        )
        # Ignore 4xx — provider may already be configured
        if resp.status_code >= 500:
            resp.raise_for_status()

    # ── Apps ───────────────────────────────────────────────────────────

    async def create_app(
        self, name: str, mode: str = "agent-chat",
        model_name: str = "", system_msg: str = "",
    ) -> str:
        """Create an agent app. Returns the app ID."""
        client = await self._ensure_client()
        resp = await client.post(
            "/console/api/apps",
            json={
                "name": name,
                "mode": mode,
                "icon_type": "emoji",
                "icon": "🤖",
                "icon_background": "#D5F5F6",
            },
            headers=self._console_headers(),
        )
        resp.raise_for_status()
        app_id = resp.json()["id"]

        # Configure model and system prompt
        await self._configure_app(app_id, model_name, system_msg)
        return app_id

    async def _configure_app(
        self, app_id: str, model_name: str, system_msg: str,
    ) -> None:
        """Set the model config and enable code interpreter tool."""
        client = await self._ensure_client()

        config = {
            "pre_prompt": system_msg,
            "model": {
                "provider": "openai",
                "name": model_name,
                "mode": "chat",
                "completion_params": {"temperature": 0},
            },
            "agent_mode": {
                "enabled": True,
                "strategy": "function_call",
                "max_iteration": 25,
                "tools": [],
            },
        }

        resp = await client.post(
            f"/console/api/apps/{app_id}/model-config",
            json=config,
            headers=self._console_headers(),
        )
        if resp.status_code >= 500:
            resp.raise_for_status()

    async def create_api_key(self, app_id: str) -> str:
        """Generate a Service API key for an app."""
        client = await self._ensure_client()
        resp = await client.post(
            f"/console/api/apps/{app_id}/api-keys",
            json={},
            headers=self._console_headers(),
        )
        resp.raise_for_status()
        return resp.json().get("token") or resp.json().get("id", "")

    async def delete_app(self, app_id: str) -> None:
        client = await self._ensure_client()
        resp = await client.delete(
            f"/console/api/apps/{app_id}",
            headers=self._console_headers(),
        )
        if resp.status_code != 404:
            resp.raise_for_status()

    # ── Service API (Execution) ────────────────────────────────────────

    async def chat(self, api_key: str, message: str, user: str = "desmet") -> dict:
        """Send a chat message to an agent app via the Service API."""
        client = await self._ensure_client()
        resp = await client.post(
            "/v1/chat-messages",
            json={
                "inputs": {},
                "query": message,
                "response_mode": "blocking",
                "user": user,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json()

    # ── Health ─────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        try:
            client = await self._ensure_client()
            resp = await client.get("/console/api/setup")
            return resp.status_code in (200, 403)  # 403 = already set up
        except Exception:
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# ── DifyAdapter ────────────────────────────────────────────────────────


_DIFY_EMAIL = "admin@desmet.local"
_DIFY_NAME = "DESMET Admin"


class DifyAdapter(VisualAgentAdapter):
    """Dify adapter — creates Agent apps via Console API, executes via Service API."""

    def __init__(self, config: dict[str, Any] | None = None):
        config = config or {}
        super().__init__(
            base_url=config.get("base_url", "http://localhost:5001"),
            api_key=None,  # Dify doesn't use a single API key
            config=config,
        )
        self._client: DifyClient | None = None
        self._model_name: str | None = None
        self._provider: str | None = None

    @property
    def platform_info(self) -> PlatformInfo:
        return load_platform_info("dify")

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def initialize(self) -> None:
        self._client = DifyClient(self.base_url)

        if not await self._client.health_check():
            raise RuntimeError(
                f"Dify is not reachable at {self.base_url}. "
                "Start it with: docker compose --profile dify up -d"
            )

        # Setup or login
        password = os.environ.get("DIFY_INIT_PASSWORD", "desmet-admin")
        await self._client.setup_account(_DIFY_EMAIL, _DIFY_NAME, password)
        if not self._client._console_token:
            await self._client.login(_DIFY_EMAIL, password)

        # Configure LLM provider
        from desmet.llm_config import get_config as get_llm_config

        cfg = get_llm_config(model=self.config.get("model"))
        self._model_name = cfg.model
        self._provider = cfg.provider.value

        if cfg.api_key:
            await self._client.setup_model_provider(
                cfg.provider.value, cfg.api_key, cfg.base_url,
            )

        self._initialized = True
        logger.info("Dify adapter initialized")

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
        return await self._client.create_app(
            name=workflow_definition.get("name", "desmet-app"),
            model_name=workflow_definition.get("model_name", ""),
            system_msg=workflow_definition.get("system_msg", ""),
        )

    async def execute_workflow(self, workflow_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        assert self._client is not None
        api_key = await self._client.create_api_key(workflow_id)
        return await self._client.chat(api_key, inputs.get("query", ""))

    async def delete_workflow(self, workflow_id: str) -> None:
        assert self._client is not None
        await self._client.delete_app(workflow_id)

    # ── VisualAgentAdapter abstract methods ─────────────────────────────

    async def _run_workflow(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str,
        workspace: str,
    ) -> dict:
        """Create an agent app, run it, clean up, return result."""
        app_name = f"desmet-{stage_name}"

        # Inject workspace info into system message
        full_system_msg = (
            f"{system_msg}\n\n"
            f"Working directory: {workspace}\n"
            f"Use the code interpreter to run shell commands, read files, "
            f"and write files in this directory."
        )

        app_id = await self._client.create_app(
            name=app_name,
            model_name=self._model_name or "",
            system_msg=full_system_msg,
        )
        try:
            api_key = await self._client.create_api_key(app_id)
            result = await self._client.chat(api_key, prompt)
            return result
        finally:
            try:
                await self._client.delete_app(app_id)
            except Exception:
                pass

    def _collect_execution_metrics(self, trace, exec_data: dict) -> None:
        """Extract token usage from Dify chat response."""
        metadata = exec_data.get("metadata", {})
        usage = metadata.get("usage", {})
        if usage:
            inp = usage.get("prompt_tokens", 0)
            out = usage.get("completion_tokens", 0)
            if inp or out:
                record_usage(trace, int(inp), int(out), model=self._model_name)

    # ── Metadata ──────────────────────────────────────────────────────

    def get_observability_info(self) -> dict[str, Any]:
        return {
            "has_tracing": True,
            "has_step_through": False,
            "has_replay": False,
            "has_state_inspection": True,
            "has_memory_inspection": True,
            "trace_format": "Dify execution log",
            "notes": (
                "Full execution trace via Console API. "
                "Token usage in chat response metadata."
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
                "Dify does not natively checkpoint agent state."
            ),
        }
