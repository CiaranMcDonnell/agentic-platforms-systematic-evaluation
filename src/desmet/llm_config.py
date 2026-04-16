"""
Centralised LLM configuration for the DESMET evaluation framework.

All model names, temperatures, and API key resolution live here.
To swap providers or models, change the defaults below or set the
corresponding environment variables.

Environment variables (all optional):
    DESMET_MODEL           – model identifier (default: gpt-5.4-2026-03-05)
    DESMET_TEMPERATURE     – sampling temperature (default: 0.0)
    DESMET_PROVIDER        – force a provider: openrouter | openai | anthropic
                             | google
                             (defaults to openrouter; auto-detected for claude/gemini)
    DESMET_BASE_URL        – custom API base URL (set automatically for
                             openrouter; override for any provider)
    DESMET_LLM_TIMEOUT     – per-call HTTP timeout in seconds (default: 120).
                             Converts silent provider hangs into ReadTimeout
                             so the stage retry loop can react.
    DESMET_LLM_MAX_RETRIES – per-call SDK-level retries (default: 0). The
                             stage retry loop is the source of truth for
                             retry semantics; SDK-level retries hide
                             failures and stack with our own.
    OPENAI_API_KEY         – OpenAI / Azure OpenAI key
    ANTHROPIC_API_KEY      – Anthropic key
    GOOGLE_API_KEY         – Google AI key
    OPENROUTER_API_KEY     – OpenRouter key
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

# ── defaults ────────────────────────────────────────────────────────────
DEFAULT_TEMPERATURE = 0.0
# 120s is generous for any single LLM call.  Beyond this we assume the
# provider is stuck (rate-limit retry storm, hung TCP read, slow path on
# large context) and want to surface a ReadTimeout instead of waiting
# indefinitely — see run 7da6614d testing stage stall.
DEFAULT_LLM_TIMEOUT = 120.0
# Disable SDK-level retries by default: our stage retry loop is the
# canonical retry source.  Stacking SDK retries on top hides failures
# and multiplies wall-clock time on stuck calls.
DEFAULT_LLM_MAX_RETRIES = 0
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# ────────────────────────────────────────────────────────────────────────


class Provider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OPENROUTER = "openrouter"


def detect_provider(model: str) -> Provider:
    """Infer the LLM provider from a model identifier string.

    Routing rules:
      - ``vendor/model`` (slash present) → OpenRouter
      - ``claude*``                      → Anthropic native
      - ``gpt-*``, ``o1*``, ``o3*``, ``o4*``, ``dall-e*`` → OpenAI native
      - ``gemini*``, ``palm*``           → Google native
      - anything else                    → OpenRouter
    """
    m = model.lower()
    # OpenRouter convention: "vendor/model" (e.g. "anthropic/claude-opus-4-6")
    if "/" in m:
        return Provider.OPENROUTER
    # Native Anthropic
    if "claude" in m:
        return Provider.ANTHROPIC
    # Native OpenAI
    if m.startswith(("gpt-", "o1-", "o3-", "o4-", "dall-e", "tts-", "whisper")) or m in (
        "o1",
        "o3",
        "o4",
    ):
        return Provider.OPENAI
    # Native Google
    if any(tok in m for tok in ("gemini", "palm")):
        return Provider.GOOGLE
    # Default to OpenRouter for maximum flexibility
    return Provider.OPENROUTER


_API_KEY_ENV: dict[Provider, str] = {
    Provider.OPENAI: "OPENAI_API_KEY",
    Provider.ANTHROPIC: "ANTHROPIC_API_KEY",
    Provider.GOOGLE: "GOOGLE_API_KEY",
    Provider.OPENROUTER: "OPENROUTER_API_KEY",
}

_BASE_URL: dict[Provider, str | None] = {
    Provider.OPENAI: None,  # SDK default
    Provider.ANTHROPIC: None,
    Provider.GOOGLE: None,
    Provider.OPENROUTER: OPENROUTER_BASE_URL,
}


@dataclass(frozen=True)
class LLMConfig:
    """Immutable snapshot of the active LLM settings."""

    model: str
    temperature: float
    provider: Provider
    api_key: str | None
    base_url: str | None = None
    timeout_seconds: float = DEFAULT_LLM_TIMEOUT
    max_retries: int = DEFAULT_LLM_MAX_RETRIES

    @property
    def api_key_env_var(self) -> str:
        """Name of the environment variable that holds the API key."""
        return _API_KEY_ENV[self.provider]

    @property
    def is_openai_compatible(self) -> bool:
        """Whether this provider speaks the OpenAI chat-completions API."""
        return self.provider in (Provider.OPENAI, Provider.OPENROUTER)

    @property
    def litellm_model(self) -> str:
        """Model string formatted for litellm routing.

        Litellm uses a ``provider/model`` prefix convention to decide which
        backend to call.  For OpenRouter models the prefix must be
        ``openrouter/`` so that litellm routes the request correctly
        instead of falling back to the OpenAI default.
        """
        if self.provider == Provider.OPENROUTER and not self.model.startswith("openrouter/"):
            return f"openrouter/{self.model}"
        return self.model


def get_config(
    *,
    model: str | None = None,
    temperature: float | None = None,
    provider: str | None = None,
) -> LLMConfig:
    """
    Build an ``LLMConfig`` by merging explicit arguments, environment
    variables, and compile-time defaults (in that priority order).

    This is the **single entry-point** that all adapters and stages should
    call to obtain LLM settings.
    """
    resolved_model = model or os.getenv("DESMET_MODEL") or os.getenv("DEFAULT_MODEL") or ""

    resolved_temp = (
        temperature
        if temperature is not None
        else _float_env("DESMET_TEMPERATURE", DEFAULT_TEMPERATURE)
    )

    if provider:
        resolved_provider = Provider(provider.lower())
    else:
        env_provider = os.getenv("DESMET_PROVIDER")
        resolved_provider = (
            Provider(env_provider.lower()) if env_provider else detect_provider(resolved_model)
        )

    api_key = os.getenv(_API_KEY_ENV[resolved_provider])

    base_url = os.getenv("DESMET_BASE_URL") or _BASE_URL.get(resolved_provider)

    timeout_seconds = _float_env("DESMET_LLM_TIMEOUT", DEFAULT_LLM_TIMEOUT)
    max_retries = _int_env("DESMET_LLM_MAX_RETRIES", DEFAULT_LLM_MAX_RETRIES)

    return LLMConfig(
        model=resolved_model,
        temperature=resolved_temp,
        provider=resolved_provider,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )


# ── helpers ─────────────────────────────────────────────────────────────


def _float_env(name: str, default: float) -> float:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default
