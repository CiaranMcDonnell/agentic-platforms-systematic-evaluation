"""Tests for llm_config default behavior."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest


class TestGetConfig:
    def test_empty_model_when_nothing_set(self):
        from desmet.llm_config import get_config

        with patch.dict(os.environ, {}, clear=True):
            cfg = get_config()
            assert cfg.model == ""

    def test_uses_explicit_model_argument(self):
        from desmet.llm_config import get_config

        with patch.dict(os.environ, {}, clear=True):
            cfg = get_config(model="my-custom-model")
            assert cfg.model == "my-custom-model"

    def test_uses_desmet_model_env_var(self):
        from desmet.llm_config import get_config

        with patch.dict(os.environ, {"DESMET_MODEL": "env-model"}, clear=True):
            cfg = get_config()
            assert cfg.model == "env-model"

    def test_explicit_overrides_env(self):
        from desmet.llm_config import get_config

        with patch.dict(os.environ, {"DESMET_MODEL": "env-model"}, clear=True):
            cfg = get_config(model="explicit-model")
            assert cfg.model == "explicit-model"

    def test_no_default_model_constant(self):
        """DEFAULT_MODEL should no longer exist in llm_config."""
        import desmet.llm_config as llm_config
        assert not hasattr(llm_config, "DEFAULT_MODEL")


class TestTimeoutAndRetries:
    """LLMConfig must expose per-call HTTP timeout and SDK-retry knobs.

    Defaults convert silent provider hangs into ReadTimeout (so the stage
    retry loop can react) and disable SDK-level retries (so our retry
    loop is the single source of truth).
    """

    def test_defaults_are_safe(self):
        from desmet.llm_config import (
            DEFAULT_LLM_MAX_RETRIES, DEFAULT_LLM_TIMEOUT, get_config,
        )
        with patch.dict(os.environ, {}, clear=True):
            cfg = get_config()
            assert cfg.timeout_seconds == DEFAULT_LLM_TIMEOUT
            assert cfg.max_retries == DEFAULT_LLM_MAX_RETRIES
            # Defaults must not be "wait forever, retry forever".
            assert cfg.timeout_seconds > 0
            assert cfg.max_retries == 0

    def test_timeout_env_override(self):
        from desmet.llm_config import get_config

        with patch.dict(os.environ, {"DESMET_LLM_TIMEOUT": "45"}, clear=True):
            cfg = get_config()
            assert cfg.timeout_seconds == 45.0

    def test_max_retries_env_override(self):
        from desmet.llm_config import get_config

        with patch.dict(os.environ, {"DESMET_LLM_MAX_RETRIES": "3"}, clear=True):
            cfg = get_config()
            assert cfg.max_retries == 3

    def test_invalid_env_falls_back_to_default(self):
        from desmet.llm_config import (
            DEFAULT_LLM_MAX_RETRIES, DEFAULT_LLM_TIMEOUT, get_config,
        )
        with patch.dict(os.environ, {
            "DESMET_LLM_TIMEOUT": "not-a-number",
            "DESMET_LLM_MAX_RETRIES": "also-bogus",
        }, clear=True):
            cfg = get_config()
            assert cfg.timeout_seconds == DEFAULT_LLM_TIMEOUT
            assert cfg.max_retries == DEFAULT_LLM_MAX_RETRIES
