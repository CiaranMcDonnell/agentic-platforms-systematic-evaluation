"""Live model pricing via the OpenRouter ``/api/v1/models`` endpoint.

Fetches per-token pricing once per session and caches it in memory.
The endpoint requires no authentication and covers models from all
major providers (OpenAI, Anthropic, Google, Meta, Mistral, …).

Usage::

    from desmet.cost_calculator import estimate_cost

    usd = estimate_cost("gpt-5.4-2026-03-05", input_tokens=1000, output_tokens=500)
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import httpx

_log = logging.getLogger(__name__)

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# ── Session-level cache ────────────────────────────────────────────────

_pricing_cache: dict[str, tuple[float, float]] | None = None
_cache_lock = threading.Lock()


def _fetch_pricing() -> dict[str, tuple[float, float]]:
    """Fetch pricing from OpenRouter and return {model_id: (input_per_token, output_per_token)}."""
    try:
        resp = httpx.get(OPENROUTER_MODELS_URL, timeout=10)
        resp.raise_for_status()
        data: list[dict[str, Any]] = resp.json().get("data", [])
    except Exception as exc:
        _log.warning("Failed to fetch pricing from OpenRouter: %s", exc)
        return {}

    pricing: dict[str, tuple[float, float]] = {}
    for model in data:
        model_id: str = model.get("id", "")
        p = model.get("pricing") or {}
        try:
            inp = float(p.get("prompt", 0))
            out = float(p.get("completion", 0))
        except (TypeError, ValueError):
            continue
        if model_id:
            pricing[model_id] = (inp, out)
    _log.info("Loaded pricing for %d models from OpenRouter", len(pricing))
    return pricing


def get_pricing() -> dict[str, tuple[float, float]]:
    """Return the cached pricing dict, fetching on first call."""
    global _pricing_cache
    if _pricing_cache is not None:
        return _pricing_cache
    with _cache_lock:
        # Double-check after acquiring lock
        if _pricing_cache is not None:
            return _pricing_cache
        result = _fetch_pricing()
        if result:
            _pricing_cache = result
        return result


def refresh_pricing() -> None:
    """Force a re-fetch of pricing data."""
    global _pricing_cache
    with _cache_lock:
        _pricing_cache = _fetch_pricing()


# ── Model name resolution ──────────────────────────────────────────────

def _resolve_model_id(model: str, pricing: dict[str, tuple[float, float]]) -> str | None:
    """Resolve a model name to an OpenRouter model ID.

    Tries in order:
      1. Exact match (e.g. "openai/gpt-5.4")
      2. With "openai/" prefix (e.g. "gpt-5.4" → "openai/gpt-5.4")
      3. With "anthropic/" prefix (e.g. "claude-sonnet-4-6" → "anthropic/claude-sonnet-4-6")
      4. With "google/" prefix (e.g. "gemini-2.5-pro" → "google/gemini-2.5-pro")
      5. Prefix match — find the first key that starts with the model string
         after a "/" (handles versioned names like "gpt-5.4-2026-03-05")
    """
    if model in pricing:
        return model

    for prefix in ("openai/", "anthropic/", "google/"):
        candidate = prefix + model
        if candidate in pricing:
            return candidate

    # Prefix match: "gpt-5.4-2026-03-05" should match "openai/gpt-5.4"
    # by checking if the OpenRouter ID's suffix is a prefix of the input model.
    # Use the longest matching suffix to avoid "gpt-5.4" beating "gpt-5.4-pro".
    m_lower = model.lower()
    best_key: str | None = None
    best_len = 0
    for key in pricing:
        suffix = key.split("/", 1)[-1] if "/" in key else key
        s_lower = suffix.lower()
        if m_lower.startswith(s_lower) and len(s_lower) > best_len:
            best_key = key
            best_len = len(s_lower)

    return best_key


# ── Public API ─────────────────────────────────────────────────────────

def estimate_cost(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> float:
    """Estimate cost in USD using live OpenRouter pricing.

    Returns 0.0 if the model is not found or pricing is unavailable.
    """
    pricing = get_pricing()
    if not pricing:
        return 0.0

    resolved = _resolve_model_id(model, pricing)
    if resolved is None:
        return 0.0

    inp_rate, out_rate = pricing[resolved]
    return input_tokens * inp_rate + output_tokens * out_rate
