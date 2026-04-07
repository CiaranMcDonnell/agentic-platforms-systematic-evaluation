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
