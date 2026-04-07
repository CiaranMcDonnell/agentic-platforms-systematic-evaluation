"""Tests for the n8n adapter."""
from __future__ import annotations

import pytest


class TestN8nClientInit:
    def test_client_sets_base_url(self):
        from desmet.adapters.n8n import N8nClient

        client = N8nClient("http://localhost:5678", api_key="test-key")
        assert client.base_url == "http://localhost:5678"

    def test_client_strips_trailing_slash(self):
        from desmet.adapters.n8n import N8nClient

        client = N8nClient("http://localhost:5678/", api_key="test-key")
        assert client.base_url == "http://localhost:5678"


class TestN8nClientHeaders:
    def test_auth_header_set(self):
        from desmet.adapters.n8n import N8nClient

        client = N8nClient("http://localhost:5678", api_key="my-key")
        assert client._headers["X-N8N-API-KEY"] == "my-key"

    def test_no_api_key_raises(self):
        from desmet.adapters.n8n import N8nClient

        with pytest.raises(ValueError, match="api_key"):
            N8nClient("http://localhost:5678", api_key=None)


class TestWorkflowTemplates:
    def test_all_four_stages_have_templates(self):
        from desmet.adapters.n8n_templates import STAGE_TEMPLATES

        assert set(STAGE_TEMPLATES.keys()) == {
            "requirements", "codegen", "testing", "deploy",
        }

    def test_template_has_ai_agent_node(self):
        from desmet.adapters.n8n_templates import STAGE_TEMPLATES

        for stage, template in STAGE_TEMPLATES.items():
            nodes = template["nodes"]
            agent_nodes = [n for n in nodes if "agent" in n["type"].lower()]
            assert len(agent_nodes) >= 1, f"Stage {stage} missing AI Agent node"

    def test_template_has_tool_nodes(self):
        from desmet.adapters.n8n_templates import STAGE_TEMPLATES

        for stage, template in STAGE_TEMPLATES.items():
            nodes = template["nodes"]
            assert len(nodes) >= 3, f"Stage {stage} has too few nodes"

    def test_build_workflow_injects_parameters(self):
        from desmet.adapters.n8n_templates import build_workflow

        wf = build_workflow(
            stage_name="requirements",
            prompt="Analyse this story",
            system_msg="You are a requirements analyst",
            workspace="/desmet-results/n8n/story_01/workspace",
            model_name="gpt-5.4-2026-03-05",
            credential_id="cred-123",
        )
        wf_str = str(wf)
        assert "Analyse this story" in wf_str
        assert "You are a requirements analyst" in wf_str
        assert "/desmet-results/n8n/story_01/workspace" in wf_str
        assert "cred-123" in wf_str


class TestCredentialMapping:
    def test_openai_provider_maps_to_openAiApi(self):
        from desmet.adapters.n8n import _map_credential

        cred_type, data = _map_credential("openai", "gpt-5.4-2026-03-05", "sk-test", None)
        assert cred_type == "openAiApi"
        assert data["apiKey"] == "sk-test"

    def test_anthropic_provider_maps_to_anthropicApi(self):
        from desmet.adapters.n8n import _map_credential

        cred_type, data = _map_credential("anthropic", "claude-opus-4-6", "sk-ant-test", None)
        assert cred_type == "anthropicApi"
        assert data["apiKey"] == "sk-ant-test"

    def test_openrouter_uses_openai_with_base_url(self):
        from desmet.adapters.n8n import _map_credential

        cred_type, data = _map_credential(
            "openrouter", "meta-llama/llama-3", "sk-or-test",
            "https://openrouter.ai/api/v1",
        )
        assert cred_type == "openAiApi"
        assert data["apiKey"] == "sk-or-test"
        assert data["baseUrl"] == "https://openrouter.ai/api/v1"

    def test_missing_api_key_raises(self):
        from desmet.adapters.n8n import _map_credential

        with pytest.raises(ValueError, match="API key"):
            _map_credential("openai", "gpt-5.4", None, None)


class TestN8nAdapterStructure:
    def test_imports(self):
        from desmet.adapters.n8n import N8nAdapter
        adapter = N8nAdapter(config={"api_key": "test", "base_url": "http://localhost:5678"})
        assert adapter.platform_info.id == "n8n"

    def test_platform_info_category(self):
        from desmet.adapters.n8n import N8nAdapter
        from desmet.harness.models import PlatformCategory
        adapter = N8nAdapter(config={"api_key": "test"})
        assert adapter.platform_info.category == PlatformCategory.VISUAL_WORKFLOW_PLATFORM

    def test_platform_info_runtime_is_docker(self):
        from desmet.adapters.n8n import N8nAdapter
        from desmet.harness.models import PlatformRuntime
        adapter = N8nAdapter(config={"api_key": "test"})
        assert adapter.platform_info.runtime == PlatformRuntime.DOCKER

    def test_observability_info(self):
        from desmet.adapters.n8n import N8nAdapter
        adapter = N8nAdapter(config={"api_key": "test"})
        info = adapter.get_observability_info()
        assert isinstance(info, dict)
        assert "has_tracing" in info

    def test_workspace_path_translation(self):
        from desmet.adapters.n8n import N8nAdapter
        adapter = N8nAdapter(config={"api_key": "test"})
        host_path = "/home/user/project/results/n8n/story_01/workspace"
        container_path = adapter._translate_workspace(host_path)
        assert container_path.startswith("/desmet-results/")
        assert "workspace" in container_path

    def test_workspace_path_windows(self):
        from desmet.adapters.n8n import N8nAdapter
        adapter = N8nAdapter(config={"api_key": "test"})
        host_path = "C:\\Users\\user\\project\\results\\n8n\\story_01\\workspace"
        container_path = adapter._translate_workspace(host_path)
        assert container_path.startswith("/desmet-results/")


from unittest.mock import AsyncMock, MagicMock, patch


class TestN8nStageExecution:
    @pytest.fixture
    def adapter(self):
        from desmet.adapters.n8n import N8nAdapter
        a = N8nAdapter(config={"api_key": "test"})
        a._initialized = True
        a._credential_id = "cred-123"
        a._model_name = "gpt-5.4-2026-03-05"
        a._client = MagicMock()
        return a

    @pytest.mark.asyncio
    async def test_execute_n8n_stage_creates_and_deletes_workflow(self, adapter):
        from desmet.harness.story import UserStory, DifficultyLevel
        from desmet.harness.results import RequirementsResult

        adapter._client.create_workflow = AsyncMock(return_value="wf-1")
        adapter._client.activate_workflow = AsyncMock()
        adapter._client.execute_workflow = AsyncMock(return_value="exec-1")
        adapter._client.wait_for_execution = AsyncMock(return_value={
            "status": "success",
            "startedAt": "2026-04-06T10:00:00Z",
            "stoppedAt": "2026-04-06T10:01:00Z",
            "data": {"resultData": {"runData": {}}},
        })
        adapter._client.delete_workflow = AsyncMock()

        story = UserStory(
            id="test_01", title="Test", description="Test story",
            difficulty=DifficultyLevel.BASIC, category="test",
            prompt="Build a hello world app",
        )
        context = MagicMock()
        context.story = story
        context.workspace = "/tmp/test_workspace"
        context.platform_id = "n8n"
        context.max_iterations = 25
        context.progress_callback = None
        context.metadata = {}

        with patch("desmet.adapters._visual_base.audit_workspace", return_value=[]):
            result = await adapter._execute_visual_stage(
                "requirements",
                lambda s, **kw: "Analyse this story: " + s.prompt,
                RequirementsResult,
                context,
            )

        assert result.platform_id == "n8n"
        assert result.stage_name == "requirements"
        assert result.success is True
        adapter._client.create_workflow.assert_awaited_once()
        adapter._client.delete_workflow.assert_awaited()
