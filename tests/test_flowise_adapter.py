"""Tests for the Flowise adapter."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestFlowiseClientInit:
    def test_client_sets_base_url(self):
        from desmet.adapters.visual.flowise import FlowiseClient

        client = FlowiseClient("http://localhost:3000")
        assert client.base_url == "http://localhost:3000"

    def test_client_strips_trailing_slash(self):
        from desmet.adapters.visual.flowise import FlowiseClient

        client = FlowiseClient("http://localhost:3000/")
        assert client.base_url == "http://localhost:3000"

    def test_auth_header_set_when_api_key_provided(self):
        from desmet.adapters.visual.flowise import FlowiseClient

        client = FlowiseClient("http://localhost:3000", api_key="my-key")
        assert client._headers["Authorization"] == "Bearer my-key"

    def test_no_auth_header_when_no_api_key(self):
        from desmet.adapters.visual.flowise import FlowiseClient

        client = FlowiseClient("http://localhost:3000")
        assert "Authorization" not in client._headers


# NOTE: the old ``TestChatflowTemplates`` class tested a removed
# ``STAGE_TEMPLATES`` module-level dict and an earlier
# ``build_chatflow`` signature that took a ``prompt`` kwarg.  Flowise
# templates are now assembled per-call by
# ``flowise_templates.build_chatflow`` from live node specs fetched
# from ``GET /api/v1/nodes/{name}``, so there is no static dict to
# introspect.  End-to-end assembly is covered by the live Flowise
# integration run; the unit-test surface no longer has anything
# meaningful to assert about the template shape.


class TestFlowiseAdapterStructure:
    def test_imports(self):
        from desmet.adapters.visual.flowise import FlowiseAdapter

        adapter = FlowiseAdapter(config={"base_url": "http://localhost:3000"})
        assert adapter.platform_info.id == "flowise"

    def test_platform_info_category(self):
        from desmet.adapters.visual.flowise import FlowiseAdapter
        from desmet.harness.models import PlatformCategory

        adapter = FlowiseAdapter()
        assert adapter.platform_info.category == PlatformCategory.VISUAL_WORKFLOW_PLATFORM

    def test_platform_info_runtime_is_docker(self):
        from desmet.adapters.visual.flowise import FlowiseAdapter
        from desmet.harness.models import PlatformRuntime

        adapter = FlowiseAdapter()
        assert adapter.platform_info.runtime == PlatformRuntime.DOCKER

    def test_observability_info(self):
        from desmet.adapters.visual.flowise import FlowiseAdapter

        adapter = FlowiseAdapter()
        info = adapter.get_observability_info()
        assert isinstance(info, dict)
        assert "has_tracing" in info


class TestFlowiseStageExecution:
    @pytest.fixture
    def adapter(self):
        from desmet.adapters.visual.flowise import FlowiseAdapter

        a = FlowiseAdapter(config={"base_url": "http://localhost:3000"})
        a._initialized = True
        a._model_name = "gpt-5.4-2026-03-05"
        a._client = MagicMock()
        # ``_run_workflow`` expects the adapter's post-``initialize()``
        # state: a credential id (created from the LLM config), the
        # chat-model node alias that the template builder should use,
        # and the pre-fetched node specs dict.  The specs themselves
        # are irrelevant here because we patch ``build_chatflow`` to
        # return a canned chatflow definition — the point of the test
        # is the create→predict→delete sequencing around that call.
        a._credential_id = "cred-1"
        a._chat_model_node = "chatOpenRouter"
        a._node_specs = {
            "chatOpenRouter": {},
            "customTool": {},
            "bufferMemory": {},
            "toolAgent": {},
        }
        return a

    @pytest.mark.asyncio
    async def test_run_workflow_creates_and_deletes_chatflow(self, adapter):
        adapter._client.create_tool = AsyncMock(side_effect=["t1", "t2", "t3"])
        adapter._client.delete_tool = AsyncMock()
        adapter._client.create_chatflow = AsyncMock(return_value="cf-1")
        adapter._client.predict = AsyncMock(return_value={
            "text": "Done",
            "chatMessageId": "msg-1",
        })
        adapter._client.delete_chatflow = AsyncMock()

        with patch(
            "desmet.adapters.visual.flowise_templates.build_chatflow",
            return_value={"nodes": [], "edges": []},
        ):
            result = await adapter._run_workflow(
                "requirements",
                "Analyse this story",
                "You are a requirements analyst",
                "/desmet-results/flowise/story_01/workspace",
            )

        assert isinstance(result, dict)
        # Three workspace tools: execute_shell, read_file, write_file.
        assert adapter._client.create_tool.await_count == 3
        adapter._client.create_chatflow.assert_awaited_once()
        adapter._client.predict.assert_awaited_once_with(
            "cf-1", "Analyse this story"
        )
        adapter._client.delete_chatflow.assert_awaited_once_with("cf-1")
        # Tools are cleaned up even after a successful run.
        assert adapter._client.delete_tool.await_count == 3

    @pytest.mark.asyncio
    async def test_execute_visual_stage_end_to_end(self, adapter):
        from desmet.harness.story import UserStory, DifficultyLevel
        from desmet.harness.results import RequirementsResult

        adapter._client.create_tool = AsyncMock(side_effect=["t1", "t2", "t3"])
        adapter._client.delete_tool = AsyncMock()
        adapter._client.create_chatflow = AsyncMock(return_value="cf-1")
        adapter._client.predict = AsyncMock(return_value={
            "text": "Requirements complete",
        })
        adapter._client.delete_chatflow = AsyncMock()

        story = UserStory(
            id="test_01", title="Test", description="Test story",
            difficulty=DifficultyLevel.BASIC, category="test",
            prompt="Build a hello world app",
        )
        context = MagicMock()
        context.story = story
        context.workspace = "/tmp/results/flowise/test_01/workspace"
        context.platform_id = "flowise"
        context.max_iterations = 25
        context.metadata = {}

        with (
            patch(
                "desmet.adapters._shared.visual_base.audit_workspace",
                return_value=[],
            ),
            patch(
                "desmet.adapters.visual.flowise_templates.build_chatflow",
                return_value={"nodes": [], "edges": []},
            ),
        ):
            result = await adapter._execute_visual_stage(
                "requirements",
                lambda s, **kw: "Analyse: " + s.prompt,
                RequirementsResult,
                context,
            )

        assert result.platform_id == "flowise"
        assert result.stage_name == "requirements"
        assert result.success is True
