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


# Keep stub adapter so registry imports don't break until N8nAdapter is added
from desmet.adapters._stub import create_visual_stub_adapter as _create_stub

N8nAdapter = _create_stub("n8n", default_url="http://localhost:5678")
