"""Tests for the paper's aggregation script (docs/paper/data/summarise.py)."""

import importlib.util
import json
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "docs" / "paper" / "data" / "summarise.py"
_spec = importlib.util.spec_from_file_location("paper_summarise", _PATH)
summarise_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(summarise_mod)

STAGES = summarise_mod.STAGES


def _exec(eid, repeat, tokens_in, cost, criteria, llm_calls="", platform="langgraph"):
    return {
        "label": "m/US-001", "execution_id": eid, "platform_id": platform, "story_id": "US-001",
        "repeat_index": str(repeat), "tokens_input": str(tokens_in), "tokens_output": "100",
        "cost_usd": str(cost), "wall_clock_seconds": "10.0", "llm_calls": str(llm_calls),
        "criteria_results": json.dumps(criteria), "tests_run": "5", "tests_failed": "0",
        "deploy_healthy": "True", "stages_passed": "True",
    }


def _stage(eid, name, tokens_in, calls, success=True, cause=""):
    return {
        "execution_id": eid, "stage_name": name, "tokens_input": str(tokens_in),
        "tokens_output": "25", "cost_usd": "0.01", "wall_clock_seconds": "2.5",
        "llm_calls": "" if calls is None else str(calls), "failure_cause": cause,
        "success": str(success),
    }


class TestStat:
    def test_median_and_range_skip_unknown(self):
        s = summarise_mod.stat([3.0, None, 1.0, 10.0])
        assert s == {"n": 3, "values": [3.0, None, 1.0, 10.0], "median": 3.0, "min": 1.0, "max": 10.0}

    def test_all_unknown(self):
        assert summarise_mod.stat([None])["median"] is None


class TestFailureCause:
    def test_precedence(self):
        fc = summarise_mod.failure_cause
        assert fc(True, True, True) is None
        assert fc(False, True, True) == "timeout"
        assert fc(False, False, True) == "budget"
        assert fc(False, False, False) == "task"
        assert fc(False, None, None) == "task"


class TestSummarise:
    def _data(self):
        execs = [
            _exec("a", 0, 1000, 0.10, {"AC-1": True, "AC-2": True}, 8),
            _exec("b", 1, 3000, 0.30, {"AC-1": True, "AC-2": False}, ""),
            _exec("c", 2, 2000, 0.20, {"AC-1": True, "AC-2": True}, 8),
        ]
        stages = []
        for eid in "ac":
            stages += [_stage(eid, st, 100, 2) for st in STAGES]
        stages += [_stage("b", st, 100, 2) for st in STAGES[:2]]
        stages += [_stage("b", "testing", 5000, None, False, "timeout"),
                   _stage("b", "deploy", 100, 2, False, "task")]
        return execs, stages, {"m/US-001": {"model": "x/model"}}

    def test_cell_statistics(self):
        cell = summarise_mod.summarise(*self._data())["cells"][0]
        assert cell["model"] == "x/model"
        assert cell["repeats"] == 3
        assert cell["tokens_total"]["values"] == [1100, 3100, 2100]
        assert cell["tokens_total"]["median"] == 2100
        assert cell["llm_calls"]["n"] == 2

    def test_correctness_and_cost_efficiency(self):
        cell = summarise_mod.summarise(*self._data())["cells"][0]
        c = cell["correctness"]
        assert (c["criteria_met"], c["criteria_total"], c["passing_executions"]) == (5, 6, 2)
        assert c["per_criterion"] == {"AC-1": 3, "AC-2": 2}
        assert abs(cell["cost_efficiency"]["cost_per_criterion_met"] - 0.6 / 5) < 1e-9
        assert abs(cell["cost_efficiency"]["cost_per_passing_execution"] - 0.3) < 1e-9

    def test_failures_and_prompt_tokens_per_call(self):
        cell = summarise_mod.summarise(*self._data())["cells"][0]
        assert cell["failures"] == {"timeout": 1, "budget": 0, "task": 1}
        assert cell["stages"]["testing"]["failures"]["timeout"] == 1
        # The timed-out stage's unknown call count leaves it out of per-call tokens.
        assert cell["stages"]["testing"]["prompt_tokens_per_call"]["values"] == [50.0, None, 50.0]
        assert cell["prompt_tokens_per_call"]["values"] == [50.0, 50.0, 50.0]

    def test_cells_split_by_platform(self):
        execs, stages, runs = self._data()
        execs.append(_exec("d", 0, 500, 0.05, {"AC-1": False}, platform="crewai"))
        cells = summarise_mod.summarise(execs, stages, runs)["cells"]
        assert [c["platform_id"] for c in cells] == ["crewai", "langgraph"]
        assert cells[0]["stages"]["requirements"]["tokens_total"]["values"] == [None]
