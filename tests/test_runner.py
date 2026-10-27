"""Tests for the restructured evaluation runner.

Verifies that _run_story executes four sequential stages (requirements,
codegen, testing, deploy), accumulates artifacts on the StageContext,
tolerates individual stage failures, and respects dry_run.
"""
import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from desmet.harness.adapter import ContainerOnlyAdapter
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
def runner_setup(mock_adapter, sample_story, tmp_path, monkeypatch):
    """Create an EvaluationRunner wired with a mock adapter, a disposable
    baseline directory, and a temp results/logs directory."""
    # The run manifest snapshots pricing; never hit OpenRouter from tests.
    monkeypatch.setattr("desmet.cost_calculator.get_pricing", lambda: {})
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    (baseline / "README.md").write_text("baseline")

    config = RunnerConfig(
        results_dir=tmp_path / "results",
        logs_dir=tmp_path / "logs",
        execution_mode="in_process",
        verify_workspace=False,  # skip Docker verification and SSH health check
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

class TestRunManifest:
    async def test_run_row_has_manifest(self, runner_setup, fake_containers):
        runner, _ = runner_setup
        runner.config.execution_mode = "container"
        await runner.run_full_evaluation()
        run = runner.store.get_run(runner._current_run_id).iloc[0]
        assert run["execution_mode"] == "container"
        assert json.loads(run["image_digests"]) == {"test_platform": fake_containers.digest}

    async def test_shared_run_id_path_gets_manifest_and_resolved_model(
        self, runner_setup, monkeypatch
    ):
        """Web single-story runs create the run via runner.create_run, then
        pass run_id to run_single_story."""
        monkeypatch.setenv("DESMET_MODEL", "gpt-manifest-test")
        runner, _ = runner_setup
        run_id = runner.create_run(
            platforms_filter=["test_platform"],
            stories_filter=["US-001"],
            platform_ids=["test_platform"],
        )
        await runner.run_single_story("test_platform", "US-001", run_id=run_id)
        run = runner.store.get_run(run_id).iloc[0]
        assert run["model"] == "gpt-manifest-test"
        assert run["execution_mode"] == "in_process"
        assert run["deploy_mode"] == "remote"
        assert len(run["prompts_sha256"]) == 64
        assert run["provider"]

    async def test_in_process_run_has_no_image_digests(self, runner_setup):
        runner, _ = runner_setup
        await runner.run_full_evaluation()
        run = runner.store.get_run(runner._current_run_id).iloc[0]
        assert run["execution_mode"] == "in_process"
        assert pd.isna(run["image_digests"])
        assert len(run["prompts_sha256"]) == 64


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

    async def test_all_stages_raise_is_not_success(self, runner_setup):
        runner, adapter = runner_setup
        for m in ("generate_requirements", "generate_code", "generate_tests", "build_and_deploy"):
            getattr(adapter, m).side_effect = Exception("fail")
        await runner.run_full_evaluation()
        r = runner.results["test_platform"]["US-001"]
        assert r.status == StoryStatus.COMPLETED
        assert r.success is False
        assert set(r.raw_result) == {"requirements", "codegen", "testing", "deploy"}
        assert r.raw_result["codegen"].error_message == "Exception: fail"
        assert isinstance(r.raw_result["codegen"], CodeResult)

    async def test_post_stage_error_keeps_real_stage_result(self, runner_setup):
        """A crash in the progress/metrics code after a stage returned must
        not replace the paid stage result with a fabricated failure."""
        runner, adapter = runner_setup
        adapter.generate_code.return_value = CodeResult(
            platform_id="test_platform", stage_name="codegen",
            success=True, tokens_input=200, tokens_output=100,
        )

        def callback(msg):
            if "[CODEGEN] PASSED" in msg:
                raise RuntimeError("progress sink broke")

        runner.progress_callback = callback
        await runner.run_full_evaluation()
        cg = runner.results["test_platform"]["US-001"].raw_result["codegen"]
        assert cg.success is True
        assert (cg.tokens_input, cg.tokens_output) == (200, 100)

    async def test_single_stage_run_success_needs_only_that_stage(self, runner_setup):
        runner, _ = runner_setup
        runner.config.stage = "codegen"
        await runner.run_full_evaluation()
        r = runner.results["test_platform"]["US-001"]
        assert r.expected_stages == ["codegen"] and r.success is True

    async def test_in_process_stage_timeout(self, runner_setup):
        runner, adapter = runner_setup
        runner.config.stage_timeout_seconds = 1

        async def slow(ctx):
            await asyncio.sleep(5)

        adapter.generate_code.side_effect = slow
        await runner.run_full_evaluation()
        cg = runner.results["test_platform"]["US-001"].raw_result["codegen"]
        assert cg.success is False and cg.error_message == "Stage timed out after 1s"
        assert cg.iterations is None
        assert cg.framework_metrics["timed_out"] == 1.0
        assert cg.framework_metrics["llm_calls"] is None
        # One unknown stage count makes the execution totals unknown.
        r = runner.results["test_platform"]["US-001"]
        assert r.iterations is None
        assert r.framework_metrics["llm_calls"] is None

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

    async def test_run_single_story_creates_new_run_when_no_id_passed(
        self, runner_setup,
    ):
        """Backward compat: omitting run_id creates a fresh DuckDB run."""
        runner, _ = runner_setup
        await runner.run_single_story("test_platform", "US-001")
        # The runner picked up an internally-generated run id
        assert runner._current_run_id is not None
        assert runner._owns_current_run is True

    async def test_run_single_story_reuses_caller_run_id(self, runner_setup):
        """Passing an existing run_id must NOT call store.create_run again
        and must NOT call store.finish_run on exit — that's the caller's
        responsibility when sharing a run across multiple platforms.

        This is the contract that fixes the Scoring page bug where each
        platform created its own DuckDB run, leaving the latest-run view
        with only the last platform that finished.
        """
        runner, _ = runner_setup
        # Caller creates the run first (the contract: shared runs are
        # owned by the caller, not by run_single_story).
        shared_id = runner.store.create_run(
            model="test", temperature=0.0,
            platforms_filter=["test_platform"], stories_filter=["US-001"],
        )

        from unittest.mock import patch
        with patch.object(runner.store, "create_run") as mock_create, \
             patch.object(runner.store, "finish_run") as mock_finish:
            await runner.run_single_story(
                "test_platform", "US-001", run_id=shared_id,
            )
            mock_create.assert_not_called()
            mock_finish.assert_not_called()

        assert runner._current_run_id == shared_id
        assert runner._owns_current_run is False
        # Foreign-key constraint would have raised by now if save_execution
        # was called with an invalid run_id, so reaching here proves the
        # row was actually inserted under the shared run.


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


class TestExecutionMode:
    """One explicit execution path per run; image built once per platform."""

    async def test_build_failure_fails_platform_stories(self, runner_setup, fake_containers):
        runner, adapter = runner_setup
        runner.config.execution_mode = "container"
        fake_containers.build_ok = False
        progress: list[str] = []
        runner.progress_callback = progress.append
        await runner.run_full_evaluation()
        r = runner.results["test_platform"]["US-001"]
        assert r.status == StoryStatus.FAILED
        assert "image build failed" in r.error_message.lower()
        # Loud: the build failure reaches the run log, not just structlog.
        assert any("[ERROR] Docker image build failed for test_platform" in m for m in progress)
        assert r.execution_mode == "container"
        assert fake_containers.run_stage_calls == []
        adapter.generate_requirements.assert_not_called()

    async def test_image_built_once_per_platform(self, runner_setup, fake_containers):
        runner, _ = runner_setup
        runner.config.execution_mode = "container"
        runner.config.repeats = 3
        await runner.run_full_evaluation()
        assert fake_containers.build_calls == ["test_platform"]
        assert len(fake_containers.run_stage_calls) == 3 * 4

    async def test_container_mode_does_not_call_adapter_stages(self, runner_setup, fake_containers):
        runner, adapter = runner_setup
        runner.config.execution_mode = "container"
        await runner.run_full_evaluation()
        adapter.generate_code.assert_not_called()
        assert runner.results["test_platform"]["US-001"].execution_mode == "container"

    async def test_single_story_builds_once(self, runner_setup, fake_containers):
        runner, _ = runner_setup
        runner.config.execution_mode = "container"
        runner.config.repeats = 2
        await runner.run_single_story("test_platform", "US-001")
        assert fake_containers.build_calls == ["test_platform"]

    async def test_in_process_never_touches_docker(self, runner_setup, fake_containers):
        runner, _ = runner_setup
        await runner.run_full_evaluation()
        assert fake_containers.build_calls == [] and fake_containers.run_stage_calls == []
        assert fake_containers.stop_calls == []
        assert runner.results["test_platform"]["US-001"].execution_mode == "in_process"

    def test_in_process_rejects_container_only_adapter(self, tmp_path, sample_story):
        with pytest.raises(ValueError):
            EvaluationRunner(
                RunnerConfig(
                    results_dir=tmp_path,
                    logs_dir=tmp_path / "l",
                    execution_mode="in_process",
                ),
                {"p": ContainerOnlyAdapter("langgraph")},
                [sample_story],
                tmp_path,
            )

    async def test_mode_is_decided_per_platform(self, runner_setup, fake_containers, sample_story):
        runner, adapter = runner_setup
        runner.platforms["box"] = ContainerOnlyAdapter("langgraph")
        runner.config.platform_execution_modes = {
            "box": "container",
            "test_platform": "in_process",
        }
        fake_containers.build_ok = False
        await runner.run_full_evaluation()
        ok = runner.results["test_platform"]["US-001"]
        assert ok.status == StoryStatus.COMPLETED
        assert ok.execution_mode == "in_process"
        bad = runner.results["box"]["US-001"]
        assert bad.status == StoryStatus.FAILED
        assert bad.execution_mode == "container"
        assert fake_containers.build_calls == ["box"]


class TestDeployMode:
    def test_deploy_mode_defaults_remote(self, sample_story, tmp_path):
        assert RunnerConfig().deploy_mode == "remote"
        ctx = StageContext(story=sample_story, workspace=tmp_path)
        assert ctx.deploy_mode == "remote"
        data = ctx.to_dict()
        assert data["deploy_mode"] == "remote"
        data["deploy_mode"] = "local"
        assert StageContext.from_dict(data).deploy_mode == "local"

    async def test_runner_leaves_env_untouched(self, runner_setup, monkeypatch):
        monkeypatch.delenv("DESMET_DEPLOY_MODE", raising=False)
        runner, _ = runner_setup
        await runner.run_full_evaluation()
        assert "DESMET_DEPLOY_MODE" not in os.environ

    async def test_in_process_stage_sees_mode_only_during_call(
        self, runner_setup, monkeypatch
    ):
        monkeypatch.delenv("DESMET_DEPLOY_MODE", raising=False)
        runner, adapter = runner_setup
        runner.config.deploy_mode = "local"
        seen = []
        result = adapter.build_and_deploy.return_value

        async def spy(ctx):
            seen.append((ctx.deploy_mode, os.environ.get("DESMET_DEPLOY_MODE")))
            return result

        adapter.build_and_deploy = spy
        await runner.run_full_evaluation()
        assert seen == [("local", "local")]
        assert "DESMET_DEPLOY_MODE" not in os.environ


class TestTestCounts:
    async def test_reported_tests_do_not_overwrite_verified(self, runner_setup, monkeypatch):
        runner, adapter = runner_setup
        adapter.generate_tests.return_value = TestResult(
            platform_id="test_platform", stage_name="testing",
            success=True, tests_run=10, tests_passed=10,
        )
        runner.config.verify_workspace = True
        monkeypatch.setattr(
            "desmet.adapters._shared.tools.harness_health_check",
            lambda *a, **k: None,
        )
        # runner.py imports it lazily, so patch the source module
        monkeypatch.setattr(
            "desmet.harness.verification.verify_execution",
            lambda *a, **k: SimpleNamespace(
                artifact_path="a.tar", tests_run=4, tests_passed=1,
                tests_failed=3, pytest_exit_code=1, criteria_results={},
            ),
        )
        await runner.run_full_evaluation()
        r = runner.results["test_platform"]["US-001"]
        assert (r.tests_run, r.tests_passed, r.tests_failed) == (4, 1, 3)
        assert (r.reported_tests_run, r.reported_tests_passed) == (10, 10)


async def test_repeat_index_reaches_result(runner_setup):
    runner, _ = runner_setup
    runner.config.repeats = 2
    await runner.run_full_evaluation()
    df = runner.store.get_executions(runner._current_run_id)
    assert sorted(df["repeat_index"]) == [0, 1]
