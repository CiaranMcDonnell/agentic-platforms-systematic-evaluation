"""Async client for querying the Langfuse public REST API.

Proxies requests server-side so API keys stay out of the browser.
Degrades gracefully when Langfuse is not configured or unreachable.
"""

from __future__ import annotations

import ast
import json
import os
from datetime import datetime, timezone
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
        params["tags"] = tags  # httpx sends list values as repeated params
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
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("fetch_traces failed: %s", exc)
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
                "latency_ms": _latency_ms(o),
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
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("fetch_trace failed: %s", exc)
        return None


def _latency_ms(obs: dict[str, Any]) -> float:
    """Return latency in milliseconds for an observation.

    Langfuse's `latency` field is populated for SDK spans but is often None
    for OTEL-instrumented spans (e.g. LangGraph). Fall back to computing from
    startTime / endTime in that case.
    """
    raw = obs.get("latency")
    if raw is not None and raw > 0:
        return float(raw)
    start = obs.get("startTime")
    end = obs.get("endTime")
    if start and end:
        try:
            s = datetime.fromisoformat(start.replace("Z", "+00:00"))
            e = datetime.fromisoformat(end.replace("Z", "+00:00"))
            return max(0.0, (e - s).total_seconds() * 1000)
        except (ValueError, TypeError):
            pass
    return 0.0


def _truncate(value: Any, max_len: int = 4000) -> str | None:
    """Truncate a value to a readable string.

    dict/list values are serialised as JSON so the browser receives valid JSON
    rather than Python repr. String values that look like Python literals
    (e.g. LangGraph message lists stored as str) are similarly converted.
    """
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        s = json.dumps(value, ensure_ascii=False)
    else:
        s = str(value)
        stripped = s.strip()
        if stripped and stripped[0] in ("{", "["):
            try:
                parsed = ast.literal_eval(stripped)
                s = json.dumps(parsed, ensure_ascii=False)
            except (ValueError, SyntaxError):
                pass
    if len(s) > max_len:
        return s[:max_len] + "... [truncated]"
    return s
