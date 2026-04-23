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

    def test_api_key_header_set_when_api_key_provided(self):
        # LangFlow's ``/api/v1/run/...`` endpoint authenticates via
        # ``x-api-key`` (not ``Authorization: Bearer ...``).  Session
        # tokens obtained via ``/api/v1/auto_login`` are Bearer tokens
        # but cannot drive ``/run``, so the client keeps them in the
        # ``httpx`` default headers for /flows/ calls and sets
        # ``x-api-key`` up front when the caller supplies one.
        from desmet.adapters.visual.langflow import LangFlowClient

        client = LangFlowClient("http://localhost:7860", api_key="my-key")
        assert client._headers["x-api-key"] == "my-key"

    def test_no_api_key_header_when_no_api_key(self):
        from desmet.adapters.visual.langflow import LangFlowClient

        client = LangFlowClient("http://localhost:7860")
        assert "x-api-key" not in client._headers


# NOTE: the old ``TestFlowTemplates`` class tested a removed
# ``STAGE_TEMPLATES`` module-level dict and an earlier ``build_flow``
# signature that took a ``prompt`` kwarg.  LangFlow flows are now
# assembled per-call by ``langflow_templates.build_flow`` from the
# live component catalogue fetched via ``GET /api/v1/all``, so there
# is no static dict to introspect.  Assembly is covered by the live
# LangFlow integration run.


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
        # ``_run_workflow`` expects the adapter's post-``initialize()``
        # state: the component catalogue from ``/api/v1/all``, the
        # provider API key embedded in the flow, and the run-scoped
        # API key minted for ``/api/v1/run/{flow_id}``.  The catalogue
        # is irrelevant here because we patch ``build_flow`` — the
        # test targets the create→run→delete sequencing.
        a._catalog = {}
        a._llm_api_key = "sk-llm-test"
        a._run_api_key_id = "runkey-id"
        a._run_api_key = "sk-run-test"
        return a

    @pytest.mark.asyncio
    async def test_run_workflow_creates_and_deletes_flow(self, adapter):
        adapter._client.create_flow = AsyncMock(return_value="flow-1")
        adapter._client.run_flow = AsyncMock(return_value={
            "outputs": [{"outputs": [{"results": {"text": "Done"}}]}],
        })
        adapter._client.delete_flow = AsyncMock()

        with patch(
            "desmet.adapters.visual.langflow_templates.build_flow",
            return_value={"nodes": [], "edges": []},
        ):
            result = await adapter._run_workflow(
                "requirements",
                "Analyse this story",
                "You are a requirements analyst",
                "/desmet-results/langflow/story_01/workspace",
            )

        assert isinstance(result, dict)
        adapter._client.create_flow.assert_awaited_once()
        adapter._client.run_flow.assert_awaited_once_with(
            "flow-1", "Analyse this story", api_key="sk-run-test",
        )
        adapter._client.delete_flow.assert_awaited_once_with("flow-1")

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

        with (
            patch(
                "desmet.adapters._shared.visual_base.audit_workspace",
                return_value=[],
            ),
            patch(
                "desmet.adapters.visual.langflow_templates.build_flow",
                return_value={"nodes": [], "edges": []},
            ),
        ):
            result = await adapter._execute_visual_stage(
                "requirements",
                lambda s, **kw: "Analyse: " + s.prompt,
                RequirementsResult,
                context,
            )

        assert result.platform_id == "langflow"
        assert result.stage_name == "requirements"
        assert result.success is True
