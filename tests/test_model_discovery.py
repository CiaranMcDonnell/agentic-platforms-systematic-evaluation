"""Tests for the model discovery module."""
from __future__ import annotations

import os
import time
from unittest.mock import MagicMock, patch

import pytest


class TestFetchOpenAI:
    def test_returns_model_ids(self):
        from desmet.webui.model_discovery import fetch_openai_models

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"id": "gpt-5.4-2026-03-05", "object": "model"},
                {"id": "gpt-5-turbo", "object": "model"},
                {"id": "dall-e-3", "object": "model"},
            ],
        }
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}), \
             patch("httpx.get", return_value=mock_resp) as mock_get:
            result = fetch_openai_models()
            assert "gpt-5.4-2026-03-05" in result
            assert "gpt-5-turbo" in result
            mock_get.assert_called_once()
            call_headers = mock_get.call_args[1].get("headers", {})
            assert call_headers.get("Authorization") == "Bearer sk-test"

    def test_returns_empty_on_error(self):
        from desmet.webui.model_discovery import fetch_openai_models

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}), \
             patch("httpx.get", side_effect=Exception("network down")):
            result = fetch_openai_models()
            assert result == []

    def test_returns_empty_without_api_key(self):
        from desmet.webui.model_discovery import fetch_openai_models

        with patch.dict(os.environ, {}, clear=True):
            result = fetch_openai_models()
            assert result == []


class TestFetchAnthropic:
    def test_returns_model_ids(self):
        from desmet.webui.model_discovery import fetch_anthropic_models

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"id": "claude-opus-4-6"},
                {"id": "claude-sonnet-4-6"},
            ],
        }
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant"}), \
             patch("httpx.get", return_value=mock_resp) as mock_get:
            result = fetch_anthropic_models()
            assert "claude-opus-4-6" in result
            assert "claude-sonnet-4-6" in result
            call_headers = mock_get.call_args[1].get("headers", {})
            assert call_headers.get("x-api-key") == "sk-ant"


class TestFetchOpenRouter:
    def test_returns_model_ids(self):
        from desmet.webui.model_discovery import fetch_openrouter_models

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": [
                {"id": "anthropic/claude-opus-4-6"},
                {"id": "openai/gpt-5.4"},
                {"id": "meta-llama/llama-3.1-70b"},
            ],
        }
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or"}), \
             patch("httpx.get", return_value=mock_resp):
            result = fetch_openrouter_models()
            assert "anthropic/claude-opus-4-6" in result
            assert "openai/gpt-5.4" in result


class TestFetchGoogle:
    def test_returns_model_ids(self):
        from desmet.webui.model_discovery import fetch_google_models

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [
                {"name": "models/gemini-2.0-pro"},
                {"name": "models/gemini-2.0-flash"},
            ],
        }
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "sk-goog"}), \
             patch("httpx.get", return_value=mock_resp):
            result = fetch_google_models()
            assert "gemini-2.0-pro" in result
            assert "gemini-2.0-flash" in result


class TestGetAvailableModels:
    def test_returns_only_configured_providers(self):
        from desmet.webui import model_discovery

        model_discovery._clear_cache()  # reset for test
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True), \
             patch.object(model_discovery, "fetch_openai_models", return_value=["gpt-5.4"]), \
             patch.object(model_discovery, "fetch_anthropic_models", return_value=[]), \
             patch.object(model_discovery, "fetch_openrouter_models", return_value=[]), \
             patch.object(model_discovery, "fetch_google_models", return_value=[]):
            result = model_discovery.get_available_models()
            assert "openai" in result
            assert result["openai"] == ["gpt-5.4"]
            # Providers without keys are omitted
            assert "anthropic" not in result
            assert "openrouter" not in result
            assert "google" not in result

    def test_cache_prevents_duplicate_calls(self):
        from desmet.webui import model_discovery

        model_discovery._clear_cache()
        call_count = {"n": 0}

        def fake_fetch():
            call_count["n"] += 1
            return ["gpt-5.4"]

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True), \
             patch.object(model_discovery, "fetch_openai_models", side_effect=fake_fetch), \
             patch.object(model_discovery, "fetch_anthropic_models", return_value=[]), \
             patch.object(model_discovery, "fetch_openrouter_models", return_value=[]), \
             patch.object(model_discovery, "fetch_google_models", return_value=[]):
            model_discovery.get_available_models()
            model_discovery.get_available_models()
            model_discovery.get_available_models()
            assert call_count["n"] == 1  # fetched once, then cached

    def test_cache_expires_after_ttl(self):
        from desmet.webui import model_discovery

        model_discovery._clear_cache()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True), \
             patch.object(model_discovery, "fetch_openai_models", return_value=["gpt-5.4"]), \
             patch.object(model_discovery, "fetch_anthropic_models", return_value=[]), \
             patch.object(model_discovery, "fetch_openrouter_models", return_value=[]), \
             patch.object(model_discovery, "fetch_google_models", return_value=[]):
            model_discovery.get_available_models()
            # Expire the cache by rewinding the stored timestamp
            model_discovery._CACHE["timestamp"] = time.time() - (model_discovery._CACHE_TTL_SECONDS + 10)
            model_discovery.get_available_models()
            assert model_discovery._CACHE["timestamp"] > time.time() - model_discovery._CACHE_TTL_SECONDS
