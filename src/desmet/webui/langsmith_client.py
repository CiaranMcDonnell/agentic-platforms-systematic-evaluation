"""Async client for querying the LangSmith REST API.

Proxies requests server-side so API keys stay out of the browser.
Degrades gracefully when LangSmith is not configured or unreachable.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

_TIMEOUT = 10.0


def _get_api_key() -> str | None:
    return os.environ.get("LANGSMITH_API_KEY") or None


def _base_url() -> str:
    return os.environ.get("LANGSMITH_BASE_URL", "https://api.smith.langchain.com").rstrip("/")


def _headers() -> dict[str, str]:
    return {"X-API-Key": _get_api_key() or ""}


async def check_status() -> dict[str, Any]:
    """Quick health check — can we reach LangSmith?"""
    key = _get_api_key()
    if not key:
        return {"available": False, "project": None}
    project = os.environ.get("LANGCHAIN_PROJECT")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(
                f"{_base_url()}/runs",
                headers=_headers(),
                params={"limit": 1},
            )
            return {"available": r.status_code == 200, "project": project}
    except Exception:
        return {"available": False, "project": project}


def _truncate(value: Any, max_len: int = 500) -> str | None:
    if value is None:
        return None
    s = str(value)
    return s[:max_len] + "... [truncated]" if len(s) > max_len else s


def _latency_ms(start: str | None, end: str | None) -> int:
    if not start or not end:
        return 0
    from datetime import datetime, timezone
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            s = datetime.strptime(start, fmt).replace(tzinfo=timezone.utc)
            e = datetime.strptime(end, fmt).replace(tzinfo=timezone.utc)
            return max(0, int((e - s).total_seconds() * 1000))
        except ValueError:
            continue
    return 0


def _normalise_run(raw: dict) -> dict:
    """Normalise a raw LangSmith run dict into the DESMET LangSmithRun shape."""
    extra = raw.get("extra") or {}
    token_usage = extra.get("token_usage") or {}
    total = extra.get("total_tokens") or token_usage.get("total_tokens", 0)
    start = raw.get("start_time")
    end = raw.get("end_time")
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "run_type": raw.get("run_type", "chain"),
        "start_time": start,
        "end_time": end,
        "latency_ms": _latency_ms(start, end),
        "model": (extra.get("invocation_params") or {}).get("model_name"),
        "tokens": {
            "input": token_usage.get("prompt_tokens", 0),
            "output": token_usage.get("completion_tokens", 0),
            "total": total,
        },
        "error": raw.get("error"),
        "inputs": _truncate(raw.get("inputs")),
        "outputs": _truncate(raw.get("outputs")),
        "children": [],
    }


async def fetch_run_tree(run_id: str) -> dict[str, Any] | None:
    """Fetch a LangSmith run and its full child-run tree."""
    key = _get_api_key()
    if not key:
        return None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            # Fetch root run
            r = await client.get(
                f"{_base_url()}/runs/{run_id}",
                headers=_headers(),
            )
            r.raise_for_status()
            root_raw = r.json()

            # Fetch child runs
            cr = await client.get(
                f"{_base_url()}/runs",
                headers=_headers(),
                params={"parent_run_id": run_id, "limit": 100},
            )
            cr.raise_for_status()
            children_raw = cr.json().get("runs", [])

        # Normalise and assemble tree
        children_by_id: dict[str, dict] = {}
        for c in children_raw:
            node = _normalise_run(c)
            children_by_id[node["id"]] = node

        # Build nested tree from flat list
        roots: list[dict] = []
        for c_raw in children_raw:
            node = children_by_id[c_raw["id"]]
            parent_id = c_raw.get("parent_run_id")
            if parent_id and parent_id in children_by_id:
                children_by_id[parent_id]["children"].append(node)
            elif parent_id == run_id or parent_id is None:
                roots.append(node)

        roots.sort(key=lambda n: n.get("start_time") or "")

        start = root_raw.get("start_time")
        end = root_raw.get("end_time")
        extra = root_raw.get("extra") or {}
        total_tokens = extra.get("total_tokens", 0)

        return {
            "run": {
                "id": root_raw.get("id"),
                "name": root_raw.get("name"),
                "run_type": root_raw.get("run_type", "chain"),
                "start_time": start,
                "end_time": end,
                "latency_ms": _latency_ms(start, end),
                "total_tokens": total_tokens,
                "error": root_raw.get("error"),
                "tags": root_raw.get("tags", []),
            },
            "children": roots,
        }
    except Exception:
        return None
