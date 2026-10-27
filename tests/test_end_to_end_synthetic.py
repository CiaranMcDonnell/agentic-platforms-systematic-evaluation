"""Synthetic end-to-end check of the result store.

Runs the real EvaluationRunner with a fake adapter and a stubbed
verification step, then checks what lands in DuckDB: run manifest,
repeats, per-stage rows, verified vs reported test counts, criteria,
deploy health, per-stage LLM-call budget metrics and recompute parity.
"""
import json
from itertools import count
from types import SimpleNamespace

import pandas as pd
import pytest

from desmet import cost_calculator
from desmet.harness import manifest
from desmet.harness.metrics import recompute_platform_likert_from_store
from desmet.harness.results import (
    CodeResult,
    DeployResult,
    RequirementsResult,
    TestResult,
)

from test_runner import mock_adapter, runner_setup, sample_story  # noqa: F401

STAGES = ("requirements", "codegen", "testing", "deploy")
CRITERIA = {"AC-001-1": True, "AC-001-2": False}
PRICING = {"openai/gpt-synthetic": (1e-6, 2e-6)}


def _fm(llm_calls: int, budget_exhausted: float = 0.0) -> dict:
    return {
        "tokens_per_stage": 1200.0,
        "iteration_ratio": 0.4,
        "redundant_tool_call_rate": 0.1,
        "tool_failure_rate": 0.0,
        "first_action_latency_ms": 350.0,
        "framework_overhead_ms": 40.0,
        "llm_calls": llm_calls,
        "budget_exhausted": budget_exhausted,
    }


@pytest.fixture
def synthetic(runner_setup, monkeypatch):  # noqa: F811
    runner, adapter = runner_setup
    monkeypatch.setenv("DESMET_MODEL", "gpt-synthetic")
    monkeypatch.setattr(cost_calculator, "get_pricing", lambda: PRICING)
    monkeypatch.setattr(cost_calculator, "_pricing_fetched_at", "2026-10-27T00:00:00+00:00")
    monkeypatch.setattr(
        manifest, "_git",
        lambda repo_root, *args: "a" * 40 + "\n" if args[0] == "rev-parse" else "",
    )
    monkeypatch.setattr(
        "desmet.adapters._shared.tools.harness_health_check", lambda *a, **k: True
    )
    monkeypatch.setattr(
        "desmet.harness.verification.verify_execution",
        lambda *a, **k: SimpleNamespace(
            artifact_path="a.tar", tests_run=4, tests_passed=3, tests_failed=1,
            pytest_exit_code=1, criteria_results=dict(CRITERIA),
        ),
    )

    runner.config.repeats = 2
    runner.config.deploy_mode = "remote"
    runner.config.verify_workspace = True

    # Each repeat runs requirements/codegen/testing/deploy once; the
    # codegen stage of the second repeat runs out of LLM-call budget.
    codegen_calls = count()

    async def requirements(ctx):
        return RequirementsResult(
            platform_id="test_platform", stage_name="requirements", success=True,
            iterations=2, tokens_input=100, tokens_output=50,
            framework_metrics=_fm(2),
        )

    async def codegen(ctx):
        exhausted = 1.0 if next(codegen_calls) == 1 else 0.0
        return CodeResult(
            platform_id="test_platform", stage_name="codegen", success=True,
            iterations=5, tokens_input=300, tokens_output=200,
            framework_metrics=_fm(5, exhausted),
        )

    async def testing(ctx):
        return TestResult(
            platform_id="test_platform", stage_name="testing", success=True,
            tests_run=10, tests_passed=10, iterations=3,
            tokens_input=200, tokens_output=100, framework_metrics=_fm(3),
        )

    async def deploy(ctx):
        return DeployResult(
            platform_id="test_platform", stage_name="deploy", success=True,
            build_success=True, deployment_ready=True, iterations=1,
            tokens_input=50, tokens_output=20, framework_metrics=_fm(1),
        )

    adapter.generate_requirements = requirements
    adapter.generate_code = codegen
    adapter.generate_tests = testing
    adapter.build_and_deploy = deploy
    return runner


def _assert_manifest(run):
    assert run["model"] == "gpt-synthetic"
    assert run["provider"]
    assert run["deploy_mode"] == "remote"
    assert run["execution_mode"] == "in_process"
    assert len(run["prompts_sha256"]) == 64
    int(run["prompts_sha256"], 16)
    assert run["git_sha"] == "a" * 40
    assert bool(run["git_dirty"]) is False
    assert json.loads(run["pricing_snapshot"]) == {
        "resolved_model_id": "openai/gpt-synthetic",
        "input_per_token": 1e-6,
        "output_per_token": 2e-6,
        "fetched_at": "2026-10-27T00:00:00+00:00",
    }


async def test_full_evaluation_store_contents(synthetic):
    runner = synthetic
    await runner.run_full_evaluation()
    store, run_id = runner.store, runner._current_run_id

    _assert_manifest(store.get_run(run_id).iloc[0])

    execs = store.get_executions(run_id)
    assert len(execs) == 2
    assert set(zip(execs["platform_id"], execs["story_id"])) == {("test_platform", "US-001")}
    assert sorted(execs["repeat_index"]) == [0, 1]
    for _, row in execs.iterrows():
        assert bool(row["stages_passed"]) is True
        assert (row["tests_run"], row["tests_passed"], row["tests_failed"]) == (4, 3, 1)
        assert (row["reported_tests_run"], row["reported_tests_passed"]) == (10, 10)
        assert json.loads(row["criteria_results"]) == CRITERIA
        assert bool(row["deploy_healthy"]) is True

    stages = store.get_stage_executions(run_id)
    for eid in execs["execution_id"]:
        assert sorted(stages[stages["execution_id"] == eid]["stage_name"]) == sorted(STAGES)

    fm = {
        int(r["repeat_index"]): json.loads(r["framework_metrics"]) for _, r in execs.iterrows()
    }
    for fmetrics in fm.values():
        assert fmetrics["llm_calls"] == 2 + 5 + 3 + 1
    assert fm[0]["budget_exhausted_stages"] == 0
    assert "budget_exhausted_codegen" not in fm[0]
    assert fm[1]["budget_exhausted_stages"] == 1
    assert fm[1]["budget_exhausted_codegen"] == 1.0

    # Recompute parity: read the live scores before recompute rewrites them.
    live = execs.iloc[0]
    score_cols = [c for c in execs.columns if c.startswith("score_")]
    assert score_cols and all(pd.notna(live[c]) for c in score_cols)
    recomputed = recompute_platform_likert_from_store(
        store, run_id, "test_platform", {"US-001": 300}
    )
    for c in score_cols:
        assert recomputed[c] == pytest.approx(live[c])


async def test_web_single_story_path_store_contents(synthetic):
    runner = synthetic
    run_id = runner.create_run(
        platforms_filter=["test_platform"],
        stories_filter=["US-001"],
        platform_ids=["test_platform"],
    )
    await runner.run_single_story("test_platform", "US-001", run_id=run_id)
    store = runner.store

    _assert_manifest(store.get_run(run_id).iloc[0])

    execs = store.get_executions(run_id)
    assert sorted(execs["repeat_index"]) == [0, 1]
    for _, row in execs.iterrows():
        assert (row["tests_run"], row["reported_tests_run"]) == (4, 10)
        assert json.loads(row["criteria_results"]) == CRITERIA
        assert bool(row["deploy_healthy"]) is True
    assert len(store.get_stage_executions(run_id)) == 8
