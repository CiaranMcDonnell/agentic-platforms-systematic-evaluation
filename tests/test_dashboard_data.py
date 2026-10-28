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


def test_framework_metrics_includes_cost_and_total_tokens():
    """Endpoint averages cost_usd and (tokens_input + tokens_output) per platform."""
    from desmet.webui.api import app
    client = TestClient(app)

    fake_data = {
        "platforms": {
            "langgraph": {
                "platform_name": "LangGraph",
                "story_metrics": [
                    {
                        "story_id": "s1",
                        "api_cost_usd": 0.10,
                        "tokens_input": 1000,
                        "tokens_output": 500,
                        "framework_metrics": {"tokens_per_stage": 300},
                    },
                    {
                        "story_id": "s2",
                        "api_cost_usd": 0.30,
                        "tokens_input": 2000,
                        "tokens_output": 1000,
                        "framework_metrics": {"tokens_per_stage": 500},
                    },
                ],
            }
        }
    }
    with patch("desmet.webui.api.load_results_raw", return_value=fake_data):
        resp = client.get("/api/dashboard/framework-metrics")

    assert resp.status_code == 200
    platforms = resp.json()["platforms"]
    assert len(platforms) == 1
    metrics = platforms[0]["metrics"]
    assert metrics["cost_usd"] == 0.2        # (0.10 + 0.30) / 2
    assert metrics["total_tokens"] == 2250.0  # ((1000+500) + (2000+1000)) / 2


def test_framework_metrics_cost_skips_missing():
    """Stories missing api_cost_usd are skipped when averaging cost."""
    from desmet.webui.api import app
    client = TestClient(app)

    fake_data = {
        "platforms": {
            "crewai": {
                "platform_name": "CrewAI",
                "story_metrics": [
                    {
                        "story_id": "s1",
                        "api_cost_usd": 0.20,
                        "tokens_input": 100,
                        "tokens_output": 50,
                        "framework_metrics": {"tokens_per_stage": 100},
                    },
                    {
                        "story_id": "s2",
                        # no api_cost_usd, no tokens
                        "framework_metrics": {"tokens_per_stage": 200},
                    },
                ],
            }
        }
    }
    with patch("desmet.webui.api.load_results_raw", return_value=fake_data):
        resp = client.get("/api/dashboard/framework-metrics")

    metrics = resp.json()["platforms"][0]["metrics"]
    assert metrics["cost_usd"] == 0.2      # only s1 contributed
    assert metrics["total_tokens"] == 150.0  # only s1 contributed


def test_framework_metrics_none_when_no_cost_data():
    """When no story has cost/token data, endpoint returns None for those keys."""
    from desmet.webui.api import app
    client = TestClient(app)

    fake_data = {
        "platforms": {
            "flowise": {
                "platform_name": "Flowise",
                "story_metrics": [
                    {
                        "story_id": "s1",
                        "framework_metrics": {"tokens_per_stage": 100},
                    }
                ],
            }
        }
    }
    with patch("desmet.webui.api.load_results_raw", return_value=fake_data):
        resp = client.get("/api/dashboard/framework-metrics")

    metrics = resp.json()["platforms"][0]["metrics"]
    assert metrics["cost_usd"] is None
    assert metrics["total_tokens"] is None


def test_story_availability_counts_repeats_and_trace_only_pairs():
    from desmet.dashboard.data import get_story_availability

    data = {
        "platforms": {
            "p": {
                "story_metrics": [
                    {"story_id": "US-001", "success": True, "scored": True, "wall_clock_seconds": 10,
                     "tokens_input": 100, "tokens_output": 50, "api_cost_usd": 0.2},
                    {"story_id": "US-001", "success": False, "scored": False, "wall_clock_seconds": 30,
                     "tokens_input": 300, "tokens_output": 150, "api_cost_usd": None},
                ]
            }
        }
    }
    out = get_story_availability(data, {("p", "US-001"), ("q", "US-002")})

    a = out["p"]["US-001"]
    assert (a["repeats"], a["passed"], a["scored"]) == (2, 1, 1)
    assert a["wall_clock_seconds"] == 20
    assert a["tokens"] == 300
    assert a["cost_usd"] == 0.2
    assert a["has_trace"] is True
    # Trace on disk but no row in this run.
    assert out["q"]["US-002"]["repeats"] == 0
    assert out["q"]["US-002"]["has_trace"] is True


def test_own_trace_file_resolves_foreign_paths_and_execution_ids(tmp_path, monkeypatch):
    from desmet.dashboard import data

    monkeypatch.setattr(data, "LOGS_DIR", tmp_path)
    pair = tmp_path / "p" / "US-001"
    pair.mkdir(parents=True)
    (pair / "p_US-001_r0_stages.json").write_text("{}", encoding="utf-8")
    (pair / "exec-7_stages.json").write_text("{}", encoding="utf-8")

    # Absolute path written inside a container: found by file name.
    sm = {"trace_path": "/app/results/logs/p/US-001/p_US-001_r0_stages.json"}
    assert data.own_trace_file(sm, "p", "US-001") == pair / "p_US-001_r0_stages.json"
    # No recorded path: found by the runner's execution-id file name.
    assert data.own_trace_file({"execution_id": "exec-7"}, "p", "US-001") == pair / "exec-7_stages.json"
    assert data.own_trace_file({"execution_id": "missing"}, "p", "US-001") is None


def test_story_availability_reports_unmatched_traces(tmp_path, monkeypatch):
    from desmet.dashboard import data

    monkeypatch.setattr(data, "LOGS_DIR", tmp_path)
    rows = {"platforms": {"p": {"story_metrics": [{"story_id": "US-001", "execution_id": "gone"}]}}}

    out = data.get_story_availability(rows, {("p", "US-001")})

    assert out["p"]["US-001"]["has_trace"] is True
    assert out["p"]["US-001"]["trace_matched"] is False
