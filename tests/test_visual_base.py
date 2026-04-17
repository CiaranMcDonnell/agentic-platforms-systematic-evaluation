"""Tests for the shared VisualAgentAdapter base class."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _MockVisualAdapter:
    """Create a concrete subclass of VisualAgentAdapter for testing."""

    @staticmethod
    def create(run_workflow_return=None):
        from desmet.adapters._shared.visual_base import VisualAgentAdapter
        from desmet.harness.models import PlatformInfo, PlatformCategory, PlatformRuntime

        class ConcreteAdapter(VisualAgentAdapter):
            def __init__(self):
                super().__init__(
                    base_url="http://localhost:9999",
                    api_key="test",
                    config={},
                )
                self._run_workflow_return = run_workflow_return or {
                    "status": "success",
                }

            @property
            def platform_info(self) -> PlatformInfo:
                return PlatformInfo(
                    name="MockVisual", id="mock_visual",
                    category=PlatformCategory.VISUAL_WORKFLOW_PLATFORM,
                    runtime=PlatformRuntime.DOCKER, version="test",
                    vendor="Test", description="Test adapter",
                    documentation_url="https://example.com",
                    repository_url="https://github.com/example",
                )

            async def initialize(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

            async def health_check(self) -> bool:
                return True

            async def create_workflow(self, definition: dict) -> str:
                return "wf-1"

            async def execute_workflow(self, workflow_id: str, inputs: dict) -> dict:
                return {}

            async def delete_workflow(self, workflow_id: str) -> None:
                pass

            async def _run_workflow(self, stage_name, prompt, system_msg, workspace):
                return self._run_workflow_return

            def _collect_execution_metrics(self, trace, exec_data):
                pass

        return ConcreteAdapter()


class TestTranslateWorkspace:
    def test_linux_path(self):
        adapter = _MockVisualAdapter.create()
        result = adapter._translate_workspace("/home/user/project/results/n8n/story/workspace")
        assert result == "/desmet-results/n8n/story/workspace"

    def test_windows_path(self):
        adapter = _MockVisualAdapter.create()
        result = adapter._translate_workspace("C:\\Users\\user\\results\\n8n\\story\\workspace")
        assert result == "/desmet-results/n8n/story/workspace"

    def test_no_results_segment_returns_normalised(self):
        adapter = _MockVisualAdapter.create()
        result = adapter._translate_workspace("/tmp/workspace")
        assert result == "/tmp/workspace"


class TestExecuteVisualStage:
    @pytest.mark.asyncio
    async def test_successful_stage_returns_success(self):
        from desmet.harness.story import UserStory, DifficultyLevel
        from desmet.harness.results import RequirementsResult

        adapter = _MockVisualAdapter.create()
        story = UserStory(
            id="test_01", title="Test", description="Test",
            difficulty=DifficultyLevel.BASIC, category="test",
            prompt="Do the thing",
        )
        context = MagicMock()
        context.story = story
        context.workspace = "/tmp/results/mock_visual/test_01/workspace"
        context.platform_id = "mock_visual"
        context.max_iterations = 25
        context.metadata = {}

        with patch("desmet.adapters._shared.visual_base.audit_workspace", return_value=[]):
            result = await adapter._execute_visual_stage(
                "requirements",
                lambda s, **kw: "Analyse: " + s.prompt,
                RequirementsResult,
                context,
            )

        assert result.success is True
        assert result.platform_id == "mock_visual"
        assert result.stage_name == "requirements"

    @pytest.mark.asyncio
    async def test_failed_validation_retries(self):
        from desmet.harness.story import UserStory, DifficultyLevel
        from desmet.harness.results import CodeResult

        adapter = _MockVisualAdapter.create()
        adapter._run_workflow = AsyncMock(return_value={"status": "success"})

        story = UserStory(
            id="test_02", title="Test", description="Test",
            difficulty=DifficultyLevel.BASIC, category="test",
            prompt="Build it",
        )
        context = MagicMock()
        context.story = story
        context.workspace = "/tmp/results/mock_visual/test_02/workspace"
        context.platform_id = "mock_visual"
        context.max_iterations = 25
        context.metadata = {}

        call_count = 0
        def mock_audit(stage, ws, baseline):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return ["missing file: main.py"]
            return []

        with patch("desmet.adapters._shared.visual_base.audit_workspace", side_effect=mock_audit):
            result = await adapter._execute_visual_stage(
                "codegen",
                lambda s, **kw: "Build: " + s.prompt,
                CodeResult,
                context,
            )

        assert result.success is True
        assert adapter._run_workflow.await_count == 2

    @pytest.mark.asyncio
    async def test_exception_returns_failure(self):
        from desmet.harness.story import UserStory, DifficultyLevel
        from desmet.harness.results import TestResult

        adapter = _MockVisualAdapter.create()
        adapter._run_workflow = AsyncMock(side_effect=RuntimeError("connection failed"))

        story = UserStory(
            id="test_03", title="Test", description="Test",
            difficulty=DifficultyLevel.BASIC, category="test",
            prompt="Test it",
        )
        context = MagicMock()
        context.story = story
        context.workspace = "/tmp/workspace"
        context.platform_id = "mock_visual"
        context.max_iterations = 25
        context.metadata = {}

        result = await adapter._execute_visual_stage(
            "testing",
            lambda s, **kw: "Test: " + s.prompt,
            TestResult,
            context,
        )

        assert result.success is False
        assert "connection failed" in result.error_message
