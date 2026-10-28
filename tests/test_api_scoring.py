"""Scoring submission API: repeats must be scored individually."""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from desmet.harness.metrics import StoryMetrics
from desmet.harness.store import ResultStore
from desmet.harness.story import StoryResult, StoryStatus
from desmet.webui import api


def _save(store: ResultStore, run_id: str, repeat_index: int) -> None:
    # Distinct wall clock per repeat so tests can tell the rows apart.
    result = StoryResult(
        story_id="US-001",
        platform_id="p",
        execution_id=f"p_US-001_r{repeat_index}",
        status=StoryStatus.COMPLETED,
        start_time=datetime(2026, 3, 28, 9, 19, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 3, 28, 9, 22, 0, tzinfo=timezone.utc),
        wall_clock_seconds=10.0 + repeat_index,
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


@pytest.fixture
def real_loader(client_with_two_repeats, monkeypatch):
    """Route load_results_raw through the temp store and capture the JSON mirror."""
    from desmet.dashboard import data as dash_data

    client, store, run_id = client_with_two_repeats
    monkeypatch.setattr(dash_data, "_get_store", lambda: store)
    monkeypatch.setattr(api, "load_results_raw", dash_data.load_results_raw)
    monkeypatch.setattr(api, "list_trace_files", lambda p, s: [])
    saved: list[dict] = []
    monkeypatch.setattr(api, "save_results", lambda data: saved.append(data))
    return client, store, run_id, saved


def test_story_score_returns_selected_repeat_evidence(real_loader):
    client, _, _, _ = real_loader
    r0 = client.get("/api/dashboard/scoring/p/US-001", params={"repeat_index": 0}).json()
    r1 = client.get("/api/dashboard/scoring/p/US-001", params={"repeat_index": 1}).json()
    assert r0["wall_clock_seconds"] == 10.0
    assert r1["wall_clock_seconds"] == 11.0
    assert r1["repeat_indices"] == [0, 1]


def test_story_score_returns_selected_repeat_rubric(real_loader):
    client, store, run_id, _ = real_loader
    store.update_rubric_scores_by_story(
        run_id, "p", "US-001", {"autonomy": 3.0}, repeat_index=1
    )
    r0 = client.get("/api/dashboard/scoring/p/US-001", params={"repeat_index": 0}).json()
    r1 = client.get("/api/dashboard/scoring/p/US-001", params={"repeat_index": 1}).json()
    assert r0["scored"] is False
    assert r1["scored"] is True and r1["scores"]["autonomy"] == 3.0


def test_json_mirror_written_to_submitted_repeat_only(real_loader):
    client, _, _, saved = real_loader
    resp = client.post(
        "/api/dashboard/scoring/submit",
        json=_body(repeat_index=1, notes={"autonomy": "good"}),
    )
    assert resp.status_code == 200
    by_repeat = {sm["repeat_index"]: sm for sm in saved[-1]["platforms"]["p"]["story_metrics"]}
    assert by_repeat[1]["scoring_notes"] == {"autonomy": "good"}
    assert "scoring_notes" not in by_repeat[0]


def test_update_story_scores_defaults_to_repeat_zero_for_legacy_records():
    from desmet.dashboard.data import update_story_scores

    data = {"platforms": {"p": {"story_metrics": [{"story_id": "US-001"}]}}}
    update_story_scores(data, "p", "US-001", {"autonomy": 2}, {}, repeat_index=1)
    assert "autonomy_score" not in data["platforms"]["p"]["story_metrics"][0]
    update_story_scores(data, "p", "US-001", {"autonomy": 2}, {})
    assert data["platforms"]["p"]["story_metrics"][0]["autonomy_score"] == 2


def test_availability_endpoint_merges_run_rows_and_traces(monkeypatch):
    data = {
        "run_id": "r1",
        "platforms": {"p": {"story_metrics": [{"story_id": "US-001", "success": True, "scored": False}]}},
    }
    monkeypatch.setattr(api, "load_results_raw", lambda run_id=None: data)
    monkeypatch.setattr(api, "list_traced_pairs", lambda: {("p", "US-001"), ("q", "US-002")})

    body = TestClient(api.app).get("/api/dashboard/scoring/availability").json()

    assert body["run_id"] == "r1"
    assert body["platforms"]["p"]["US-001"]["passed"] == 1
    assert body["platforms"]["p"]["US-001"]["has_trace"] is True
    assert body["platforms"]["q"]["US-002"]["repeats"] == 0


def test_story_score_prefers_the_rows_langfuse_id_and_flags_unmatched_trace(monkeypatch):
    row = {"story_id": "US-001", "repeat_index": 0, "langfuse_trace_id": "row-trace"}
    monkeypatch.setattr(api, "load_results_raw", lambda run_id=None: {"platforms": {"p": {"story_metrics": [row]}}})
    monkeypatch.setattr(api, "_story_repeat_indices", lambda *a: [0])
    monkeypatch.setattr(api, "list_trace_files", lambda p, s: [Path("other_stages.json")])
    newest = {"langfuse_trace_id": "other-run", "stages": {"codegen": {"messages": [{"role": "assistant", "content": "x"}]}}}
    monkeypatch.setattr(api, "load_trace", lambda path: newest)

    body = TestClient(api.app).get("/api/dashboard/scoring/p/US-001").json()

    assert body["langfuse_trace_id"] == "row-trace"
    assert body["trace_matched"] is False
    assert body["trace"]["messages"]
