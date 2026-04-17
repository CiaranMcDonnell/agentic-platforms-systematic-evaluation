"""Tests for the LangFlow adapter."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestLangFlowClientInit:
    def test_client_sets_base_url(self):
        from desmet.adapters.visual.langflow import LangFlowClient

        client = LangFlowClient("http://localhost:7860")
        assert client.base_url == "http://localhost:7860"

    def test_client_strips_trailing_slash(self):
        from desmet.adapters.visual.langflow import LangFlowClient

        client = LangFlowClient("http://localhost:7860/")
        assert client.base_url == "http://localhost:7860"

    def test_auth_header_set_when_api_key_provided(self):
        from desmet.adapters.visual.langflow import LangFlowClient

        client = LangFlowClient("http://localhost:7860", api_key="my-key")
        assert client._headers["Authorization"] == "Bearer my-key"

    def test_no_auth_header_when_no_api_key(self):
        from desmet.adapters.visual.langflow import LangFlowClient

        client = LangFlowClient("http://localhost:7860")
        assert "Authorization" not in client._headers


class TestFlowTemplates:
    def test_all_four_stages_have_templates(self):
        from desmet.adapters.visual.langflow_templates import STAGE_TEMPLATES

        assert set(STAGE_TEMPLATES.keys()) == {
            "requirements", "codegen", "testing", "deploy",
        }

    def test_template_has_agent_node(self):
        from desmet.adapters.visual.langflow_templates import STAGE_TEMPLATES

        for stage, template in STAGE_TEMPLATES.items():
            nodes = template["nodes"]
            agent_nodes = [n for n in nodes if n["data"].get("type") == "Agent"]
            assert len(agent_nodes) >= 1, f"Stage {stage} missing Agent node"

    def test_template_has_tool_nodes(self):
        from desmet.adapters.visual.langflow_templates import STAGE_TEMPLATES

        for stage, template in STAGE_TEMPLATES.items():
            nodes = template["nodes"]
            assert len(nodes) >= 3, f"Stage {stage} has too few nodes"

    def test_build_flow_injects_parameters(self):
        from desmet.adapters.visual.langflow_templates import build_flow

        flow = build_flow(
            stage_name="requirements",
            prompt="Analyse this story",
            system_msg="You are a requirements analyst",
            workspace="/desmet-results/langflow/story_01/workspace",
            model_name="gpt-5.4-2026-03-05",
        )
        flow_str = str(flow)
        assert "You are a requirements analyst" in flow_str
        assert "/desmet-results/langflow/story_01/workspace" in flow_str
        assert "gpt-5.4" in flow_str


class TestLangFlowAdapterStructure:
    def test_imports(self):
        from desmet.adapters.visual.langflow import LangFlowAdapter

        adapter = LangFlowAdapter(config={"base_url": "http://localhost:7860"})
        assert adapter.platform_info.id == "langflow"

    def test_platform_info_category(self):
        from desmet.adapters.visual.langflow import LangFlowAdapter
        from desmet.harness.models import PlatformCategory

        adapter = LangFlowAdapter()
        assert adapter.platform_info.category == PlatformCategory.VISUAL_WORKFLOW_PLATFORM

    def test_observability_info(self):
        from desmet.adapters.visual.langflow import LangFlowAdapter

        adapter = LangFlowAdapter()
        info = adapter.get_observability_info()
        assert isinstance(info, dict)
        assert "has_tracing" in info


class TestLangFlowStageExecution:
    @pytest.fixture
    def adapter(self):
        from desmet.adapters.visual.langflow import LangFlowAdapter

        a = LangFlowAdapter(config={"base_url": "http://localhost:7860"})
        a._initialized = True
        a._model_name = "gpt-5.4-2026-03-05"
        a._client = MagicMock()
        return a

    @pytest.mark.asyncio
    async def test_run_workflow_creates_and_deletes_flow(self, adapter):
        adapter._client.create_flow = AsyncMock(return_value="flow-1")
        adapter._client.run_flow = AsyncMock(return_value={
            "outputs": [{"outputs": [{"results": {"text": "Done"}}]}],
        })
        adapter._client.delete_flow = AsyncMock()

        result = await adapter._run_workflow(
            "requirements",
            "Analyse this story",
            "You are a requirements analyst",
            "/desmet-results/langflow/story_01/workspace",
        )

        assert isinstance(result, dict)
        adapter._client.create_flow.assert_awaited_once()
        adapter._client.run_flow.assert_awaited_once()
        adapter._client.delete_flow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_visual_stage_end_to_end(self, adapter):
        from desmet.harness.story import UserStory, DifficultyLevel
        from desmet.harness.results import RequirementsResult

        adapter._client.create_flow = AsyncMock(return_value="flow-1")
        adapter._client.run_flow = AsyncMock(return_value={
            "outputs": [{"outputs": [{"results": {"text": "Requirements complete"}}]}],
        })
        adapter._client.delete_flow = AsyncMock()

        story = UserStory(
            id="test_01", title="Test", description="Test story",
            difficulty=DifficultyLevel.BASIC, category="test",
            prompt="Build a hello world app",
        )
        context = MagicMock()
        context.story = story
        context.workspace = "/tmp/results/langflow/test_01/workspace"
        context.platform_id = "langflow"
        context.max_iterations = 25
        context.metadata = {}

        with patch("desmet.adapters._shared.visual_base.audit_workspace", return_value=[]):
            result = await adapter._execute_visual_stage(
                "requirements",
                lambda s, **kw: "Analyse: " + s.prompt,
                RequirementsResult,
                context,
            )

        assert result.platform_id == "langflow"
        assert result.stage_name == "requirements"
        assert result.success is True
