"""Tests for the Dify adapter."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestDifyClientInit:
    def test_client_sets_base_url(self):
        from desmet.adapters.dify import DifyClient

        client = DifyClient("http://localhost:5001")
        assert client.base_url == "http://localhost:5001"

    def test_client_strips_trailing_slash(self):
        from desmet.adapters.dify import DifyClient

        client = DifyClient("http://localhost:5001/")
        assert client.base_url == "http://localhost:5001"

    def test_console_headers_without_token(self):
        from desmet.adapters.dify import DifyClient

        client = DifyClient("http://localhost:5001")
        headers = client._console_headers()
        assert "Authorization" not in headers

    def test_console_headers_with_token(self):
        from desmet.adapters.dify import DifyClient

        client = DifyClient("http://localhost:5001")
        client._console_token = "test-token"
        headers = client._console_headers()
        assert headers["Authorization"] == "Bearer test-token"


class TestDifyAdapterStructure:
    def test_imports(self):
        from desmet.adapters.dify import DifyAdapter

        adapter = DifyAdapter(config={"base_url": "http://localhost:5001"})
        assert adapter.platform_info.id == "dify"

    def test_platform_info_category(self):
        from desmet.adapters.dify import DifyAdapter
        from desmet.harness.models import PlatformCategory

        adapter = DifyAdapter()
        assert adapter.platform_info.category == PlatformCategory.VISUAL_WORKFLOW_PLATFORM

    def test_platform_info_runtime_is_docker(self):
        from desmet.adapters.dify import DifyAdapter
        from desmet.harness.models import PlatformRuntime

        adapter = DifyAdapter()
        assert adapter.platform_info.runtime == PlatformRuntime.DOCKER

    def test_observability_info(self):
        from desmet.adapters.dify import DifyAdapter

        adapter = DifyAdapter()
        info = adapter.get_observability_info()
        assert isinstance(info, dict)
        assert info["has_tracing"] is True
        assert info["has_memory_inspection"] is True


class TestDifyStageExecution:
    @pytest.fixture
    def adapter(self):
        from desmet.adapters.dify import DifyAdapter

        a = DifyAdapter(config={"base_url": "http://localhost:5001"})
        a._initialized = True
        a._model_name = "gpt-5.4-2026-03-05"
        a._provider = "openai"
        a._client = MagicMock()
        return a

    @pytest.mark.asyncio
    async def test_run_workflow_creates_and_deletes_app(self, adapter):
        adapter._client.create_app = AsyncMock(return_value="app-1")
        adapter._client.create_api_key = AsyncMock(return_value="sk-app-1")
        adapter._client.chat = AsyncMock(return_value={
            "answer": "Done",
            "metadata": {"usage": {"prompt_tokens": 100, "completion_tokens": 50}},
        })
        adapter._client.delete_app = AsyncMock()

        result = await adapter._run_workflow(
            "requirements",
            "Analyse this story",
            "You are a requirements analyst",
            "/desmet-results/dify/story_01/workspace",
        )

        assert isinstance(result, dict)
        assert result["answer"] == "Done"
        adapter._client.create_app.assert_awaited_once()
        adapter._client.create_api_key.assert_awaited_once()
        adapter._client.chat.assert_awaited_once()
        adapter._client.delete_app.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_visual_stage_end_to_end(self, adapter):
        from desmet.harness.story import UserStory, DifficultyLevel
        from desmet.harness.results import RequirementsResult

        adapter._client.create_app = AsyncMock(return_value="app-1")
        adapter._client.create_api_key = AsyncMock(return_value="sk-app-1")
        adapter._client.chat = AsyncMock(return_value={
            "answer": "Requirements complete",
            "metadata": {"usage": {"prompt_tokens": 200, "completion_tokens": 100}},
        })
        adapter._client.delete_app = AsyncMock()

        story = UserStory(
            id="test_01", title="Test", description="Test story",
            difficulty=DifficultyLevel.BASIC, category="test",
            prompt="Build a hello world app",
        )
        context = MagicMock()
        context.story = story
        context.workspace = "/tmp/results/dify/test_01/workspace"
        context.platform_id = "dify"
        context.max_iterations = 25
        context.metadata = {}

        with patch("desmet.adapters._shared.visual_base.audit_workspace", return_value=[]):
            result = await adapter._execute_visual_stage(
                "requirements",
                lambda s, **kw: "Analyse: " + s.prompt,
                RequirementsResult,
                context,
            )

        assert result.platform_id == "dify"
        assert result.stage_name == "requirements"
        assert result.success is True

    def test_collect_execution_metrics_extracts_usage(self, adapter):
        from desmet.adapters._shared.tracing import start_trace

        trace = start_trace()
        exec_data = {
            "answer": "Done",
            "metadata": {
                "usage": {
                    "prompt_tokens": 150,
                    "completion_tokens": 75,
                },
            },
        }
        adapter._collect_execution_metrics(trace, exec_data)
        assert trace.total_tokens_input == 150
        assert trace.total_tokens_output == 75
