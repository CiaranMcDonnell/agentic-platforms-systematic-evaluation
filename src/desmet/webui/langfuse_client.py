"""Async client for querying the Langfuse public REST API.

Proxies requests server-side so API keys stay out of the browser.
Degrades gracefully when Langfuse is not configured or unreachable.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

_TIMEOUT = 10.0  # seconds


def _get_config() -> tuple[str, str, str] | None:
    """Return (host, public_key, secret_key) or None if not configured."""
    host = os.environ.get("LANGFUSE_HOST", "").rstrip("/")
    pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    sk = os.environ.get("LANGFUSE_SECRET_KEY", "")
    if not host or not pk or not sk:
        return None
    return host, pk, sk


async def check_status() -> dict[str, Any]:
    """Quick health check — can we reach Langfuse?"""
    cfg = _get_config()
    if cfg is None:
        return {"available": False, "host": None}
    host, pk, sk = cfg
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(
                f"{host}/api/public/traces",
                params={"limit": 1},
                auth=(pk, sk),
            )
            return {"available": r.status_code == 200, "host": host}
    except Exception:
        return {"available": False, "host": host}


async def fetch_traces(
    session_id: str | None = None,
    tags: list[str] | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List traces, optionally filtered by session or tags."""
    cfg = _get_config()
    if cfg is None:
        return []
    host, pk, sk = cfg
    params: dict[str, Any] = {"limit": limit}
    if session_id:
        params["sessionId"] = session_id
    if tags:
        for tag in tags:
            params["tags"] = tag  # Langfuse accepts repeated params
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(
                f"{host}/api/public/traces",
                params=params,
                auth=(pk, sk),
            )
            r.raise_for_status()
            data = r.json()
            return [
                {
                    "id": t.get("id"),
                    "name": t.get("name"),
                    "timestamp": t.get("timestamp"),
                    "latency_ms": t.get("latency", 0),
                    "total_tokens": (t.get("usage") or {}).get("totalTokens", 0),
                    "tags": t.get("tags", []),
                    "session_id": t.get("sessionId"),
                }
                for t in data.get("data", [])
            ]
    except Exception:
        return []


async def fetch_trace(trace_id: str) -> dict[str, Any] | None:
    """Fetch a single trace with its observations, structured as a span tree."""
    cfg = _get_config()
    if cfg is None:
        return None
    host, pk, sk = cfg
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            # Fetch trace metadata
            tr = await client.get(
                f"{host}/api/public/traces/{trace_id}",
                auth=(pk, sk),
            )
            tr.raise_for_status()
            trace_data = tr.json()

            # Fetch observations (spans + generations)
            obs_r = await client.get(
                f"{host}/api/public/observations",
                params={"traceId": trace_id, "limit": 100},
                auth=(pk, sk),
            )
            obs_r.raise_for_status()
            raw_obs = obs_r.json().get("data", [])

        # Normalise observations
        obs_by_id: dict[str, dict] = {}
        for o in raw_obs:
            usage = o.get("usage") or {}
            node: dict[str, Any] = {
                "id": o.get("id"),
                "name": o.get("name"),
                "type": o.get("type", "span").lower(),
                "start_time": o.get("startTime"),
                "end_time": o.get("endTime"),
                "latency_ms": o.get("latency", 0),
                "model": o.get("model"),
                "tokens": {
                    "input": usage.get("promptTokens") or usage.get("input", 0),
                    "output": usage.get("completionTokens") or usage.get("output", 0),
                    "total": usage.get("totalTokens") or usage.get("total", 0),
                },
                "level": o.get("level", "DEFAULT"),
                "status_message": o.get("statusMessage"),
                "input": _truncate(o.get("input")),
                "output": _truncate(o.get("output")),
                "cost": o.get("calculatedTotalCost") or o.get("totalCost") or 0,
                "metadata": o.get("metadata"),
                "parent_observation_id": o.get("parentObservationId"),
                "children": [],
            }
            obs_by_id[node["id"]] = node

        # Build parent-child tree
        roots: list[dict] = []
        for node in obs_by_id.values():
            parent_id = node.pop("parent_observation_id", None)
            if parent_id and parent_id in obs_by_id:
                obs_by_id[parent_id]["children"].append(node)
            else:
                roots.append(node)

        # Sort by start_time
        roots.sort(key=lambda n: n.get("start_time") or "")

        trace_usage = trace_data.get("usage") or {}
        return {
            "trace": {
                "id": trace_data.get("id"),
                "name": trace_data.get("name"),
                "timestamp": trace_data.get("timestamp"),
                "total_tokens": trace_usage.get("totalTokens", 0),
                "latency_ms": trace_data.get("latency", 0),
                "cost": trace_data.get("calculatedTotalCost") or trace_data.get("totalCost") or 0,
                "tags": trace_data.get("tags", []),
                "metadata": trace_data.get("metadata"),
            },
            "observations": roots,
        }
    except Exception:
        return None


def _truncate(value: Any, max_len: int = 500) -> str | None:
    """Truncate a value to a readable string."""
    if value is None:
        return None
    s = str(value)
    if len(s) > max_len:
        return s[:max_len] + "... [truncated]"
    return s
