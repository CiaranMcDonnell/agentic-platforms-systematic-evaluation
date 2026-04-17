"""Tests for the Flowise adapter."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestFlowiseClientInit:
    def test_client_sets_base_url(self):
        from desmet.adapters.flowise import FlowiseClient

        client = FlowiseClient("http://localhost:3000")
        assert client.base_url == "http://localhost:3000"

    def test_client_strips_trailing_slash(self):
        from desmet.adapters.flowise import FlowiseClient

        client = FlowiseClient("http://localhost:3000/")
        assert client.base_url == "http://localhost:3000"

    def test_auth_header_set_when_api_key_provided(self):
        from desmet.adapters.flowise import FlowiseClient

        client = FlowiseClient("http://localhost:3000", api_key="my-key")
        assert client._headers["Authorization"] == "Bearer my-key"

    def test_no_auth_header_when_no_api_key(self):
        from desmet.adapters.flowise import FlowiseClient

        client = FlowiseClient("http://localhost:3000")
        assert "Authorization" not in client._headers


class TestChatflowTemplates:
    def test_all_four_stages_have_templates(self):
        from desmet.adapters.flowise_templates import STAGE_TEMPLATES

        assert set(STAGE_TEMPLATES.keys()) == {
            "requirements", "codegen", "testing", "deploy",
        }

    def test_template_has_agent_node(self):
        from desmet.adapters.flowise_templates import STAGE_TEMPLATES

        for stage, template in STAGE_TEMPLATES.items():
            nodes = template["nodes"]
            agent_nodes = [
                n for n in nodes
                if "agent" in n.get("data", {}).get("category", "").lower()
                or "agent" in n.get("data", {}).get("name", "").lower()
            ]
            assert len(agent_nodes) >= 1, f"Stage {stage} missing agent node"

    def test_template_has_tool_nodes(self):
        from desmet.adapters.flowise_templates import STAGE_TEMPLATES

        for stage, template in STAGE_TEMPLATES.items():
            nodes = template["nodes"]
            assert len(nodes) >= 3, f"Stage {stage} has too few nodes"

    def test_build_chatflow_injects_parameters(self):
        from desmet.adapters.flowise_templates import build_chatflow

        cf = build_chatflow(
            stage_name="requirements",
            prompt="Analyse this story",
            system_msg="You are a requirements analyst",
            workspace="/desmet-results/flowise/story_01/workspace",
            model_name="gpt-5.4-2026-03-05",
        )
        cf_str = str(cf)
        assert "You are a requirements analyst" in cf_str
        assert "/desmet-results/flowise/story_01/workspace" in cf_str
        assert "gpt-5.4" in cf_str


class TestFlowiseAdapterStructure:
    def test_imports(self):
        from desmet.adapters.flowise import FlowiseAdapter

        adapter = FlowiseAdapter(config={"base_url": "http://localhost:3000"})
        assert adapter.platform_info.id == "flowise"

    def test_platform_info_category(self):
        from desmet.adapters.flowise import FlowiseAdapter
        from desmet.harness.models import PlatformCategory

        adapter = FlowiseAdapter()
        assert adapter.platform_info.category == PlatformCategory.VISUAL_WORKFLOW_PLATFORM

    def test_platform_info_runtime_is_docker(self):
        from desmet.adapters.flowise import FlowiseAdapter
        from desmet.harness.models import PlatformRuntime

        adapter = FlowiseAdapter()
        assert adapter.platform_info.runtime == PlatformRuntime.DOCKER

    def test_observability_info(self):
        from desmet.adapters.flowise import FlowiseAdapter

        adapter = FlowiseAdapter()
        info = adapter.get_observability_info()
        assert isinstance(info, dict)
        assert "has_tracing" in info


class TestFlowiseStageExecution:
    @pytest.fixture
    def adapter(self):
        from desmet.adapters.flowise import FlowiseAdapter

        a = FlowiseAdapter(config={"base_url": "http://localhost:3000"})
        a._initialized = True
        a._model_name = "gpt-5.4-2026-03-05"
        a._client = MagicMock()
        return a

    @pytest.mark.asyncio
    async def test_run_workflow_creates_and_deletes_chatflow(self, adapter):
        adapter._client.create_chatflow = AsyncMock(return_value="cf-1")
        adapter._client.predict = AsyncMock(return_value={
            "text": "Done",
            "chatMessageId": "msg-1",
        })
        adapter._client.delete_chatflow = AsyncMock()

        result = await adapter._run_workflow(
            "requirements",
            "Analyse this story",
            "You are a requirements analyst",
            "/desmet-results/flowise/story_01/workspace",
        )

        assert isinstance(result, dict)
        adapter._client.create_chatflow.assert_awaited_once()
        adapter._client.predict.assert_awaited_once()
        adapter._client.delete_chatflow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_visual_stage_end_to_end(self, adapter):
        from desmet.harness.story import UserStory, DifficultyLevel
        from desmet.harness.results import RequirementsResult

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

        with patch("desmet.adapters._shared.visual_base.audit_workspace", return_value=[]):
            result = await adapter._execute_visual_stage(
                "requirements",
                lambda s, **kw: "Analyse: " + s.prompt,
                RequirementsResult,
                context,
            )

        assert result.platform_id == "flowise"
        assert result.stage_name == "requirements"
        assert result.success is True
