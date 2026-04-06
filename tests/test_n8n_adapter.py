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
