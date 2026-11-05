"""Tests for the ``/api/dashboard/execution`` endpoint."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures" / "execution"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def client(monkeypatch):
    from desmet.webui import api

    stage_file = _fixture("langgraph_stages.json")
    monkeypatch.setattr(api, "list_trace_files", lambda p, s: [Path("fake_stages.json")])
    monkeypatch.setattr(api, "load_trace", lambda path: stage_file)
    # The run's row for the pair. It records no trace path, so the newest
    # file is matched to it through the shared Langfuse trace id.
    row = {"story_id": "US-001", "repeat_index": 0, "langfuse_trace_id": stage_file["langfuse_trace_id"]}
    monkeypatch.setattr(
        api, "load_results_raw", lambda run_id=None: {"platforms": {"langgraph": {"story_metrics": [row]}}}
    )

    async def fake_fetch_trace(trace_id: str):
        assert trace_id == stage_file["langfuse_trace_id"]
        return _fixture("langgraph_langfuse.json")

    monkeypatch.setattr(api, "langfuse_fetch_trace", fake_fetch_trace)
    return TestClient(api.app)


def test_execution_defaults_to_langfuse_when_trace_id_present(client):
    res = client.get("/api/dashboard/execution/langgraph/US-001")

    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "langfuse"
    assert [s["key"] for s in body["stages"]] == ["requirements", "codegen", "testing", "deploy"]
    assert body["summary"]["llm_calls"] > 0


def test_execution_overlays_stage_success_from_local_file(client):
    """Langfuse spans do not know whether a stage passed; the local file does."""
    res = client.get("/api/dashboard/execution/langgraph/US-001")

    body = res.json()
    assert all(s["success"] is True for s in body["stages"])


def test_execution_overlays_stage_cost_from_local_file(client):
    """Langfuse cannot price OpenRouter models; the harness stage cost wins."""
    body = client.get("/api/dashboard/execution/langgraph/US-001").json()
    local = _fixture("langgraph_stages.json")["stages"]

    for stage in body["stages"]:
        assert stage["cost_usd"] == pytest.approx(local[stage["key"]]["cost_usd"])
    assert body["summary"]["cost_usd"] == pytest.approx(sum(s["cost_usd"] for s in body["stages"]))


def test_execution_local_source_uses_stage_file(client):
    res = client.get("/api/dashboard/execution/langgraph/US-001", params={"source": "local"})

    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "local"
    assert body["stages"][0]["turns"][0]["role"] == "planner"


def test_execution_falls_back_to_local_when_langfuse_unavailable(client, monkeypatch):
    from desmet.webui import api

    async def unavailable(trace_id: str):
        return None

    monkeypatch.setattr(api, "langfuse_fetch_trace", unavailable)

    res = client.get("/api/dashboard/execution/langgraph/US-001")

    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "local"
    assert any("Langfuse" in n for n in body["notes"])


def test_execution_404_without_trace_files(client, monkeypatch):
    from desmet.webui import api

    monkeypatch.setattr(api, "list_trace_files", lambda p, s: [])
    monkeypatch.setattr(api, "load_results_raw", lambda run_id=None: {"platforms": {}})

    res = client.get("/api/dashboard/execution/langgraph/US-001")

    assert res.status_code == 404


def test_execution_without_trace_file_uses_the_rows_langfuse_trace(client, monkeypatch):
    """The row's Langfuse id alone is enough; stage results are flagged missing."""
    from desmet.webui import api

    monkeypatch.setattr(api, "list_trace_files", lambda p, s: [])

    body = client.get("/api/dashboard/execution/langgraph/US-001").json()

    assert body["source"] == "langfuse"
    assert any("pass/fail" in n for n in body["notes"])


def test_execution_does_not_overlay_another_runs_stage_file(client, monkeypatch):
    """A newest file whose Langfuse id is not the row's may be another run's."""
    from desmet.webui import api

    stage_file = _fixture("langgraph_stages.json")
    row = {"story_id": "US-001", "repeat_index": 0, "langfuse_trace_id": stage_file["langfuse_trace_id"]}
    other = {**stage_file, "langfuse_trace_id": "someone-else"}
    monkeypatch.setattr(api, "load_trace", lambda path: other)
    monkeypatch.setattr(
        api, "load_results_raw", lambda run_id=None: {"platforms": {"langgraph": {"story_metrics": [row]}}}
    )

    body = client.get("/api/dashboard/execution/langgraph/US-001").json()

    assert body["source"] == "langfuse"  # the row's own trace id is used
    assert body["trace_matched"] is False
    assert all(s["success"] is None for s in body["stages"])
    assert any("pass/fail" in n for n in body["notes"])


def test_execution_prefers_the_rows_own_trace_file(client, monkeypatch, tmp_path):
    from desmet.webui import api

    own = tmp_path / "langgraph_US-001_own_stages.json"
    own.write_text("{}", encoding="utf-8")
    loaded: list[Path] = []
    stage_file = _fixture("langgraph_stages.json")

    def load(path):
        loaded.append(Path(path))
        return stage_file

    row = {"story_id": "US-001", "repeat_index": 0, "trace_path": str(own)}
    monkeypatch.setattr(api, "load_trace", load)
    monkeypatch.setattr(
        api, "load_results_raw", lambda run_id=None: {"platforms": {"langgraph": {"story_metrics": [row]}}}
    )

    body = client.get("/api/dashboard/execution/langgraph/US-001", params={"source": "local"}).json()

    assert loaded == [own]
    assert body["trace_matched"] is True
