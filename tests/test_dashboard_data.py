"""Unit tests for desmet.dashboard.data helper functions."""
import pytest
from desmet.dashboard.data import get_rubric_dim_averages, SCORING_DIMENSIONS


def _make_data(platform_scored_stories: dict) -> dict:
    platforms = {}
    for pid, stories in platform_scored_stories.items():
        metrics = []
        for s in stories:
            sm: dict = {"story_id": f"story_{len(metrics)}", "scored": s.get("scored", True)}
            for dim in SCORING_DIMENSIONS:
                if dim in s:
                    sm[f"{dim}_score"] = s[dim]
            metrics.append(sm)
        platforms[pid] = {"platform_name": pid, "story_metrics": metrics}
    return {"platforms": platforms}


def test_all_scored_returns_averages():
    data = _make_data({
        "langgraph": [
            {"pipeline_completeness": 3, "tool_integration": 2, "error_recovery": 3,
             "time_efficiency": 2, "autonomy": 3, "trace_quality": 2},
            {"pipeline_completeness": 1, "tool_integration": 2, "error_recovery": 1,
             "time_efficiency": 2, "autonomy": 1, "trace_quality": 2},
        ]
    })
    result = get_rubric_dim_averages(data)
    assert "langgraph" in result
    assert result["langgraph"]["pipeline_completeness"] == 2.0
    assert result["langgraph"]["tool_integration"] == 2.0
    assert result["langgraph"]["autonomy"] == 2.0


def test_unscored_stories_excluded():
    data = _make_data({
        "crewai": [
            {"pipeline_completeness": 3, "scored": True},
            {"pipeline_completeness": 1, "scored": False},
        ]
    })
    result = get_rubric_dim_averages(data)
    assert result["crewai"]["pipeline_completeness"] == 3.0
    assert result["crewai"]["tool_integration"] is None


def test_no_scored_stories_returns_none():
    data = _make_data({
        "flowise": [{"pipeline_completeness": 2, "scored": False}]
    })
    result = get_rubric_dim_averages(data)
    assert result["flowise"]["pipeline_completeness"] is None


def test_empty_platforms():
    result = get_rubric_dim_averages({"platforms": {}})
    assert result == {}


def test_all_six_dims_present():
    data = _make_data({
        "test": [{dim: 2 for dim in SCORING_DIMENSIONS}]
    })
    result = get_rubric_dim_averages(data)
    for dim in SCORING_DIMENSIONS:
        assert dim in result["test"]
        assert result["test"][dim] == 2.0


from fastapi.testclient import TestClient
from unittest.mock import patch


def test_scoring_matrix_endpoint_empty():
    """Matrix endpoint returns empty list when no results exist."""
    from desmet.webui.api import app
    client = TestClient(app)
    with patch("desmet.webui.api.load_results_raw", return_value={"platforms": {}}):
        resp = client.get("/api/dashboard/scoring/matrix")
    assert resp.status_code == 200
    body = resp.json()
    assert body["platforms"] == []
    assert "dimensions" in body


def test_scoring_matrix_endpoint_with_data():
    """Matrix endpoint returns correct structure and sorted order."""
    from desmet.dashboard.data import SCORING_DIMENSIONS
    from desmet.webui.api import app
    client = TestClient(app)

    fake_data = _make_data({
        "langgraph": [{dim: 3 for dim in SCORING_DIMENSIONS}],
        "crewai": [{dim: 1 for dim in SCORING_DIMENSIONS}],
    })
    with patch("desmet.webui.api.load_results_raw", return_value=fake_data):
        resp = client.get("/api/dashboard/scoring/matrix")
    assert resp.status_code == 200
    body = resp.json()
    # langgraph has higher total score, should come first
    assert body["platforms"][0]["platform_id"] == "langgraph"
    assert body["platforms"][0]["scores"]["pipeline_completeness"] == 3.0
    assert body["platforms"][0]["scored_count"] == 1
    assert body["dimensions"] == SCORING_DIMENSIONS
