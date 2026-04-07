"""Dynamic model discovery from provider APIs.

Queries OpenAI, Anthropic, OpenRouter, and Google for their available
models, grouped by provider.  Only providers with a configured API key
are queried.  Results are cached in-process with a 1-hour TTL.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 3600  # 1 hour
_CACHE: dict[str, Any] = {
    "timestamp": 0.0,
    "data": {},
}
_HTTP_TIMEOUT = 10.0


def _clear_cache() -> None:
    """Reset the in-process cache (used by tests)."""
    _CACHE["timestamp"] = 0.0
    _CACHE["data"] = {}


def _log_fetch_error(provider: str, status_code: int) -> None:
    """Log a non-200 response at the appropriate severity.

    401/403 means the user's key is wrong, expired, or lacks permission —
    treat this as expected (info level) so the log doesn't fill with
    warnings when a user has a placeholder value or a stale key.
    5xx and other unexpected codes stay at warning level.
    """
    if status_code in (401, 403):
        logger.info(
            "%s models fetch returned %s — check your API key",
            provider, status_code,
        )
    else:
        logger.warning("%s models fetch returned %s", provider, status_code)


# ── Per-provider fetchers ─────────────────────────────────────────────


def _read_api_key(env_var: str) -> str | None:
    """Read an API key from the environment, stripping whitespace.

    Returns ``None`` when the variable is unset, empty, or obviously a
    placeholder value (contains ``your-*-key-here``) — these would fail
    with 401 and just pollute the logs.
    """
    raw = os.environ.get(env_var)
    if not raw:
        return None
    key = raw.strip()
    if not key:
        return None
    if "your-" in key and "-key-here" in key:
        logger.info(
            "%s looks like a placeholder (%s...) — treating as unset",
            env_var, key[:16],
        )
        return None
    return key


def fetch_openai_models() -> list[str]:
    """Fetch available OpenAI models. Returns empty list on error or no key."""
    api_key = _read_api_key("OPENAI_API_KEY")
    if not api_key:
        return []
    try:
        resp = httpx.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=_HTTP_TIMEOUT,
        )
        if resp.status_code != 200:
            _log_fetch_error("OpenAI", resp.status_code)
            return []
        data = resp.json().get("data", [])
        return sorted([m["id"] for m in data if "id" in m])
    except Exception as e:
        logger.warning("OpenAI models fetch failed: %s", e)
        return []


def fetch_anthropic_models() -> list[str]:
    """Fetch available Anthropic models. Returns empty list on error or no key."""
    api_key = _read_api_key("ANTHROPIC_API_KEY")
    if not api_key:
        return []
    try:
        resp = httpx.get(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            timeout=_HTTP_TIMEOUT,
        )
        if resp.status_code != 200:
            _log_fetch_error("Anthropic", resp.status_code)
            return []
        data = resp.json().get("data", [])
        return sorted([m["id"] for m in data if "id" in m])
    except Exception as e:
        logger.warning("Anthropic models fetch failed: %s", e)
        return []


def fetch_openrouter_models() -> list[str]:
    """Fetch available OpenRouter models. Returns empty list on error or no key."""
    api_key = _read_api_key("OPENROUTER_API_KEY")
    if not api_key:
        return []
    try:
        resp = httpx.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=_HTTP_TIMEOUT,
        )
        if resp.status_code != 200:
            _log_fetch_error("OpenRouter", resp.status_code)
            return []
        data = resp.json().get("data", [])
        return sorted([m["id"] for m in data if "id" in m])
    except Exception as e:
        logger.warning("OpenRouter models fetch failed: %s", e)
        return []


def fetch_google_models() -> list[str]:
    """Fetch available Google models. Returns empty list on error or no key.

    The Google API returns names like ``models/gemini-2.0-pro`` — strip
    the ``models/`` prefix.
    """
    api_key = _read_api_key("GOOGLE_API_KEY")
    if not api_key:
        return []
    try:
        resp = httpx.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
            timeout=_HTTP_TIMEOUT,
        )
        if resp.status_code != 200:
            _log_fetch_error("Google", resp.status_code)
            return []
        models = resp.json().get("models", [])
        ids: list[str] = []
        for m in models:
            name = m.get("name", "")
            if name.startswith("models/"):
                ids.append(name[len("models/"):])
            elif name:
                ids.append(name)
        return sorted(ids)
    except Exception as e:
        logger.warning("Google models fetch failed: %s", e)
        return []


# ── Aggregated fetch with cache ───────────────────────────────────────


def get_available_models() -> dict[str, list[str]]:
    """Return available models grouped by provider.

    Only providers whose API key env var is set are included in the
    result dict.  Results are cached in-process for ``_CACHE_TTL_SECONDS``.
    """
    now = time.time()
    if _CACHE["data"] and (now - _CACHE["timestamp"]) < _CACHE_TTL_SECONDS:
        return _CACHE["data"]

    result: dict[str, list[str]] = {}
    if _read_api_key("OPENAI_API_KEY"):
        models = fetch_openai_models()
        if models:
            result["openai"] = models
    if _read_api_key("ANTHROPIC_API_KEY"):
        models = fetch_anthropic_models()
        if models:
            result["anthropic"] = models
    if _read_api_key("OPENROUTER_API_KEY"):
        models = fetch_openrouter_models()
        if models:
            result["openrouter"] = models
    if _read_api_key("GOOGLE_API_KEY"):
        models = fetch_google_models()
        if models:
            result["google"] = models

    _CACHE["timestamp"] = now
    _CACHE["data"] = result
    return result
