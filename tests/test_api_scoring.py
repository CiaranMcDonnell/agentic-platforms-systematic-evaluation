"""Scoring submission API: repeats must be scored individually."""

from datetime import datetime, timezone

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from desmet.harness.metrics import StoryMetrics
from desmet.harness.store import ResultStore
from desmet.harness.story import StoryResult, StoryStatus
from desmet.webui import api


def _save(store: ResultStore, run_id: str, repeat_index: int) -> None:
    result = StoryResult(
        story_id="US-001",
        platform_id="p",
        execution_id=f"p_US-001_r{repeat_index}",
        status=StoryStatus.COMPLETED,
        start_time=datetime(2026, 3, 28, 9, 19, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 3, 28, 9, 22, 0, tzinfo=timezone.utc),
        wall_clock_seconds=10.0,
        repeat_index=repeat_index,
    )
    store.save_execution(
        run_id, result, StoryMetrics.from_story_result(result, time_budget_seconds=300.0)
    )


@pytest.fixture
def client_with_two_repeats(tmp_path, monkeypatch):
    store = ResultStore(db_path=tmp_path / "test.duckdb")
    run_id = store.create_run()
    _save(store, run_id, 0)
    _save(store, run_id, 1)
    monkeypatch.setattr(api, "_get_result_store", lambda: store)
    # Keep the legacy JSON mirror out of the real results directory.
    monkeypatch.setattr(api, "load_results_raw", lambda run_id=None: {"platforms": {}})
    monkeypatch.setattr(api, "save_results", lambda data: None)
    yield TestClient(api.app), store, run_id
    store.close()


def _body(**extra):
    return {
        "platform_id": "p",
        "story_id": "US-001",
        "scores": {"autonomy": 2},
        "notes": {},
        **extra,
    }


def test_submit_without_repeat_index_rejected_when_ambiguous(client_with_two_repeats):
    client, store, run_id = client_with_two_repeats
    resp = client.post("/api/dashboard/scoring/submit", json=_body())
    assert resp.status_code == 400
    assert "repeat_index required: this story has 2 repeats" in resp.json()["detail"]
    assert store.get_executions(run_id)["rubric_autonomy"].isna().all()


def test_submit_with_repeat_index_scores_only_that_repeat(client_with_two_repeats):
    client, store, run_id = client_with_two_repeats
    resp = client.post("/api/dashboard/scoring/submit", json=_body(repeat_index=1))
    assert resp.status_code == 200
    df = store.get_executions(run_id).set_index("repeat_index")
    assert pd.isna(df.loc[0, "rubric_autonomy"])
    assert df.loc[1, "rubric_autonomy"] == 2.0
