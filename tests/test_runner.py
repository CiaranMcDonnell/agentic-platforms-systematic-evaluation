"""Tests for the restructured evaluation runner.

Verifies that _run_story executes four sequential stages (requirements,
codegen, testing, deploy), accumulates artifacts on the StageContext,
tolerates individual stage failures, and respects dry_run.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from desmet.harness.context import StageContext
from desmet.harness.results import (
    CodeResult,
    DeployResult,
    RequirementsResult,
    TestResult,
)
from desmet.harness.runner import EvaluationRunner, RunnerConfig
from desmet.harness.story import DifficultyLevel, StoryStatus, UserStory

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_adapter():
    """Build an AsyncMock adapter with all four stage methods returning
    successful StageResults."""
    adapter = AsyncMock()

    # platform_info must behave like a real PlatformInfo
    adapter.platform_info = MagicMock()
    adapter.platform_info.id = "test_platform"
    adapter.platform_info.name = "Test Platform"

    adapter.generate_requirements.return_value = RequirementsResult(
        platform_id="test_platform",
        stage_name="requirements",
        success=True,
    )
    adapter.generate_code.return_value = CodeResult(
        platform_id="test_platform",
        stage_name="codegen",
        success=True,
    )
    adapter.generate_tests.return_value = TestResult(
        platform_id="test_platform",
        stage_name="testing",
        success=True,
    )
    adapter.build_and_deploy.return_value = DeployResult(
        platform_id="test_platform",
        stage_name="deploy",
        success=True,
        build_success=True,
        deployment_ready=True,
    )
    return adapter


@pytest.fixture
def sample_story():
    return UserStory(
        id="US-001",
        title="Test Story",
        description="A test story",
        difficulty=DifficultyLevel.BASIC,
        category="code_generation",
        prompt="Implement something",
        time_budget_seconds=300,
        max_iterations=25,
    )


@pytest.fixture
def runner_setup(mock_adapter, sample_story, tmp_path):
    """Create an EvaluationRunner wired with a mock adapter, a disposable
    baseline directory, and a temp results/logs directory."""
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    (baseline / "README.md").write_text("baseline")

    config = RunnerConfig(
        results_dir=tmp_path / "results",
        logs_dir=tmp_path / "logs",
    )
    runner = EvaluationRunner(
        config=config,
        platforms={"test_platform": mock_adapter},
        stories=[sample_story],
        baseline_repo=baseline,
    )
    return runner, mock_adapter


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestRunnerStageExecution:
    """Test that _run_story drives four stages sequentially."""

    async def test_runs_all_four_stages(self, runner_setup):
        """Each adapter stage method must be called exactly once."""
        runner, adapter = runner_setup
        await runner.run_full_evaluation()

        adapter.generate_requirements.assert_called_once()
        adapter.generate_code.assert_called_once()
        adapter.generate_tests.assert_called_once()
        adapter.build_and_deploy.assert_called_once()

    async def test_stage_context_passed_to_all_stages(self, runner_setup):
        """Every stage method receives a StageContext as the first positional arg."""
        runner, adapter = runner_setup
        await runner.run_full_evaluation()

        for method in (
            adapter.generate_requirements,
            adapter.generate_code,
            adapter.generate_tests,
            adapter.build_and_deploy,
        ):
            ctx_arg = method.call_args[0][0]
            assert isinstance(ctx_arg, StageContext)

    async def test_stage_context_accumulates_artifacts(self, runner_setup):
        """After requirements runs, the context passed to generate_code
        must contain the requirements result in its artifacts dict."""
        runner, adapter = runner_setup
        await runner.run_full_evaluation()

        # The context passed to generate_code (second stage) should already
        # have requirements artifacts
        code_call_ctx = adapter.generate_code.call_args[0][0]
        assert isinstance(code_call_ctx, StageContext)
        assert "requirements" in code_call_ctx.artifacts

    async def test_all_four_artifacts_accumulated(self, runner_setup):
        """After all stages run, the context passed to build_and_deploy
        should contain requirements, codegen, and testing artifacts."""
        runner, adapter = runner_setup
        await runner.run_full_evaluation()

        deploy_ctx = adapter.build_and_deploy.call_args[0][0]
        assert "requirements" in deploy_ctx.artifacts
        assert "codegen" in deploy_ctx.artifacts
        assert "testing" in deploy_ctx.artifacts

    async def test_stage_failure_doesnt_block_later_stages(self, runner_setup):
        """If generate_requirements raises, the remaining three stages
        must still be attempted."""
        runner, adapter = runner_setup
        adapter.generate_requirements.side_effect = Exception("Requirements failed")

        await runner.run_full_evaluation()

        # All later stages should still be called
        adapter.generate_code.assert_called_once()
        adapter.generate_tests.assert_called_once()
        adapter.build_and_deploy.assert_called_once()

    async def test_middle_stage_failure_doesnt_block(self, runner_setup):
        """If generate_code raises, testing and deploy must still run."""
        runner, adapter = runner_setup
        adapter.generate_code.side_effect = Exception("Codegen failed")

        await runner.run_full_evaluation()

        adapter.generate_requirements.assert_called_once()
        adapter.generate_tests.assert_called_once()
        adapter.build_and_deploy.assert_called_once()

    async def test_failed_stage_not_in_artifacts(self, runner_setup):
        """When a stage fails, its key should NOT appear in artifacts."""
        runner, adapter = runner_setup
        adapter.generate_requirements.side_effect = Exception("Requirements failed")

        await runner.run_full_evaluation()

        code_call_ctx = adapter.generate_code.call_args[0][0]
        assert "requirements" not in code_call_ctx.artifacts

    async def test_dry_run_skips_stages(self, runner_setup):
        """When dry_run=True, no stage methods should be called."""
        runner, adapter = runner_setup
        runner.config.dry_run = True

        await runner.run_full_evaluation()

        adapter.generate_requirements.assert_not_called()
        adapter.generate_code.assert_not_called()
        adapter.generate_tests.assert_not_called()
        adapter.build_and_deploy.assert_not_called()

    async def test_story_result_status_completed(self, runner_setup):
        """When all stages succeed, the StoryResult should be COMPLETED."""
        runner, adapter = runner_setup
        await runner.run_full_evaluation()

        result = runner.results["test_platform"]["US-001"]
        assert result.status == StoryStatus.COMPLETED

    async def test_story_result_status_on_all_fail(self, runner_setup):
        """When all stages fail, the story should still complete (stages are
        non-blocking) but result should reflect partial failure."""
        runner, adapter = runner_setup
        adapter.generate_requirements.side_effect = Exception("fail")
        adapter.generate_code.side_effect = Exception("fail")
        adapter.generate_tests.side_effect = Exception("fail")
        adapter.build_and_deploy.side_effect = Exception("fail")

        await runner.run_full_evaluation()

        result = runner.results["test_platform"]["US-001"]
        # Story still completes (stage failures are non-blocking)
        assert result.status == StoryStatus.COMPLETED

    async def test_workspace_created(self, runner_setup, sample_story, tmp_path):
        """The runner should create a workspace directory from baseline."""
        runner, adapter = runner_setup
        await runner.run_full_evaluation()

        workspace = runner.config.results_dir / "test_platform" / "US-001" / "workspace"
        assert workspace.exists()
        assert (workspace / "README.md").exists()

    async def test_story_result_aggregates_metrics(self, runner_setup):
        """StoryResult should aggregate token counts from stage results."""
        runner, adapter = runner_setup

        # Set up stage results with token counts
        adapter.generate_requirements.return_value = RequirementsResult(
            platform_id="test_platform",
            stage_name="requirements",
            success=True,
            tokens_input=100,
            tokens_output=50,
            iterations=2,
            tool_calls_count=3,
        )
        adapter.generate_code.return_value = CodeResult(
            platform_id="test_platform",
            stage_name="codegen",
            success=True,
            tokens_input=200,
            tokens_output=100,
            iterations=5,
            tool_calls_count=7,
        )
        adapter.generate_tests.return_value = TestResult(
            platform_id="test_platform",
            stage_name="testing",
            success=True,
            tokens_input=150,
            tokens_output=75,
            iterations=3,
            tool_calls_count=4,
        )
        adapter.build_and_deploy.return_value = DeployResult(
            platform_id="test_platform",
            stage_name="deploy",
            success=True,
            build_success=True,
            deployment_ready=True,
            tokens_input=50,
            tokens_output=25,
            iterations=1,
            tool_calls_count=2,
        )

        await runner.run_full_evaluation()

        result = runner.results["test_platform"]["US-001"]
        assert result.tokens_input == 500   # 100+200+150+50
        assert result.tokens_output == 250  # 50+100+75+25
        assert result.iterations == 11      # 2+5+3+1
        assert result.tool_calls == 16      # 3+7+4+2

    async def test_run_single_story_uses_stages(self, runner_setup, sample_story):
        """run_single_story should also use the stage-by-stage flow."""
        runner, adapter = runner_setup
        result = await runner.run_single_story("test_platform", "US-001")

        adapter.generate_requirements.assert_called_once()
        adapter.generate_code.assert_called_once()
        adapter.generate_tests.assert_called_once()
        adapter.build_and_deploy.assert_called_once()
        assert result.status == StoryStatus.COMPLETED


def test_stage_result_has_langsmith_run_id():
    from desmet.harness.results import StageResult
    result = StageResult(platform_id="langgraph", stage_name="requirements")
    assert result.langsmith_run_id is None  # field exists, defaults to None


def test_stage_result_langsmith_run_id_can_be_set():
    from desmet.harness.results import StageResult
    result = StageResult(platform_id="langgraph", stage_name="requirements")
    result.langsmith_run_id = "abc-123"
    assert result.langsmith_run_id == "abc-123"


def test_save_stage_traces_includes_langsmith_run_id(tmp_path):
    """langsmith_run_id written per-stage into the JSON trace file."""
    import json
    from desmet.harness.runner import EvaluationRunner, RunnerConfig
    from desmet.harness.results import RequirementsResult
    from desmet.harness.story import StoryResult, StoryStatus

    cfg = RunnerConfig(results_dir=tmp_path, logs_dir=tmp_path / "logs")
    # Bypass __init__ (requires platforms/stories/baseline_repo) — only config is needed
    runner = object.__new__(EvaluationRunner)
    runner.config = cfg
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)

    story_result = StoryResult(
        story_id="US001", platform_id="langgraph", execution_id="exec-1",
        status=StoryStatus.COMPLETED,
    )

    req_result = RequirementsResult(platform_id="langgraph", stage_name="requirements")
    req_result.langsmith_run_id = "ls-run-abc"

    runner._save_stage_traces(story_result, {"requirements": req_result})

    trace_files = list((tmp_path / "logs" / "langgraph" / "US001").glob("*_stages.json"))
    assert trace_files, "No trace file written"
    data = json.loads(trace_files[0].read_text())
    assert data["stages"]["requirements"]["langsmith_run_id"] == "ls-run-abc"
