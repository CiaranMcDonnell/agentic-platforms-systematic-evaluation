"""Tests for the run reproducibility manifest."""
from pathlib import Path

import pytest

from desmet import cost_calculator
from desmet.harness import manifest
from desmet.harness.manifest import collect_manifest
from desmet.harness.runner import RunnerConfig

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(cost_calculator, "get_pricing", lambda: {})


def test_collect_manifest_keys():
    m = collect_manifest(RunnerConfig(execution_mode="container", deploy_mode="remote"), REPO_ROOT)
    assert set(m) == {"git_sha", "git_dirty", "provider", "deploy_mode", "execution_mode",
                      "stage_timeout_seconds", "prompts_sha256", "pricing_snapshot"}
    assert m["deploy_mode"] == "remote" and len(m["prompts_sha256"]) == 64
    assert m["execution_mode"] == "container"
    assert m["stage_timeout_seconds"] is None
    assert m["pricing_snapshot"] is None


def test_git_unavailable_gives_none(tmp_path):
    m = collect_manifest(RunnerConfig(), tmp_path)  # not a git repository
    assert m["git_sha"] is None and m["git_dirty"] is None


def test_execution_mode_mixed_when_platforms_differ():
    cfg = RunnerConfig(execution_mode="container", platform_execution_modes={"b": "in_process"})
    assert collect_manifest(cfg, REPO_ROOT, ["a", "b"])["execution_mode"] == "mixed"
    assert collect_manifest(cfg, REPO_ROOT, ["a"])["execution_mode"] == "container"
    assert collect_manifest(cfg, REPO_ROOT, ["b"])["execution_mode"] == "in_process"


def test_pricing_snapshot_none_when_unavailable(monkeypatch):
    monkeypatch.setattr(cost_calculator, "get_pricing", lambda: {})
    assert cost_calculator.pricing_snapshot("gpt-x") is None


def test_pricing_snapshot_resolves_model(monkeypatch):
    monkeypatch.setattr(cost_calculator, "get_pricing", lambda: {"openai/gpt-x": (1e-6, 2e-6)})
    monkeypatch.setattr(cost_calculator, "_pricing_fetched_at", "2026-10-27T00:00:00+00:00")
    assert cost_calculator.pricing_snapshot("gpt-x") == {
        "resolved_model_id": "openai/gpt-x",
        "input_per_token": 1e-6,
        "output_per_token": 2e-6,
        "fetched_at": "2026-10-27T00:00:00+00:00",
    }
    assert cost_calculator.pricing_snapshot("unknown") is None
