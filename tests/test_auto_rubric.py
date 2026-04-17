"""Tests for auto-derived rubric scores."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from desmet.harness.auto_rubric import (
    compute_auto_rubric_scores,
    score_error_recovery,
    score_tool_integration,
    score_trace_quality,
)
from desmet.harness.trace import AgentTrace, ToolCall


def _make_trace(tool_calls: list[ToolCall] | None = None) -> AgentTrace:
    # AgentTrace has no stage_name field; all fields have defaults.
    t = AgentTrace(
        start_time=datetime.now(timezone.utc),
    )
    t.tool_calls = tool_calls or []
    t.total_llm_duration_ms = 1000.0
    return t


def _tc(name: str, ok: bool = True, dur: float | None = 100.0) -> ToolCall:
    # ToolCall field order: tool_name, arguments, result, timestamp, duration_ms, success
    return ToolCall(
        tool_name=name,
        arguments={},
        result="",
        timestamp=datetime.now(timezone.utc),
        duration_ms=dur,
        success=ok,
    )


class TestToolIntegration:
    def test_zero_calls_scores_full(self):
        assert score_tool_integration({"tool_failure_rate": 0.0, "redundant_tool_call_rate": 0.0}) == 3.0

    def test_half_fail_half_redundant(self):
        fm = {"tool_failure_rate": 0.5, "redundant_tool_call_rate": 0.5}
        score = score_tool_integration(fm)
        # 0.5*0.7 + 0.5*0.3 = 0.5 ; *3 = 1.5
        assert score == pytest.approx(1.5, abs=0.01)

    def test_missing_metrics_default_conservatively(self):
        # None/missing → treat as 0 failures (no evidence of problems)
        assert score_tool_integration({}) == 3.0


class TestErrorRecovery:
    def test_failure_scores_zero(self):
        assert score_error_recovery(success=False, framework_metrics={"tool_failure_rate": 0.0}) == 0.0

    def test_success_no_errors_scores_mid(self):
        # Nothing to prove — neutral-high, not full marks.
        assert score_error_recovery(success=True, framework_metrics={"tool_failure_rate": 0.0}) == 2.0

    def test_success_with_errors_scores_full(self):
        assert score_error_recovery(success=True, framework_metrics={"tool_failure_rate": 0.3}) == 3.0

    def test_success_with_missing_metric_treated_as_no_failures(self):
        # Missing key → `or 0.0` path → 2.0 (conservative default).
        assert score_error_recovery(success=True, framework_metrics={}) == 2.0


class TestTraceQuality:
    def test_full_signals_scores_full(self):
        trace = _make_trace([_tc("write_file", dur=12.5), _tc("execute_shell", dur=33.1)])
        fm = {"first_action_latency_ms": 400.0, "framework_overhead_ms": 120.0}
        assert score_trace_quality(trace, fm) == 3.0

    def test_missing_latency_docks_one_third(self):
        trace = _make_trace([_tc("write_file", dur=12.5)])
        fm = {"first_action_latency_ms": None, "framework_overhead_ms": 120.0}
        assert score_trace_quality(trace, fm) == pytest.approx(2.0, abs=0.01)

    def test_tool_call_without_duration_docks(self):
        trace = _make_trace([_tc("write_file", dur=None)])
        fm = {"first_action_latency_ms": 400.0, "framework_overhead_ms": 120.0}
        assert score_trace_quality(trace, fm) == pytest.approx(2.0, abs=0.01)


class TestCompose:
    def test_compose_returns_all_three_dimensions(self):
        trace = _make_trace([_tc("write_file", dur=12.5)])
        fm = {
            "tool_failure_rate": 0.0,
            "redundant_tool_call_rate": 0.0,
            "first_action_latency_ms": 400.0,
            "framework_overhead_ms": 120.0,
        }
        scores = compute_auto_rubric_scores(success=True, framework_metrics=fm, trace=trace)
        assert set(scores) == {"tool_integration", "error_recovery", "trace_quality"}
        for v in scores.values():
            assert 0.0 <= v <= 3.0


class TestRunnerIntegration:
    def test_all_three_dimensions_present_for_successful_run(self):
        trace = _make_trace([_tc("write_file"), _tc("execute_shell")])
        fm = {
            "tool_failure_rate": 0.0,
            "redundant_tool_call_rate": 0.0,
            "first_action_latency_ms": 400.0,
            "framework_overhead_ms": 120.0,
        }
        scores = compute_auto_rubric_scores(success=True, framework_metrics=fm, trace=trace)
        assert set(scores) == {"tool_integration", "error_recovery", "trace_quality"}
        assert scores["tool_integration"] == 3.0
        assert scores["error_recovery"] == 2.0
        assert scores["trace_quality"] == 3.0

    def test_failed_run_zeroes_error_recovery_but_keeps_other_signals(self):
        trace = _make_trace([_tc("write_file", ok=False)])
        fm = {
            "tool_failure_rate": 1.0,
            "redundant_tool_call_rate": 0.0,
            "first_action_latency_ms": 400.0,
            "framework_overhead_ms": 120.0,
        }
        scores = compute_auto_rubric_scores(success=False, framework_metrics=fm, trace=trace)
        assert scores["error_recovery"] == 0.0
        assert scores["tool_integration"] < 1.0  # 0.3 * 3 = 0.9
        assert scores["trace_quality"] == 3.0
