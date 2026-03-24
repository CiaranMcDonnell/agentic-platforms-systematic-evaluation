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
