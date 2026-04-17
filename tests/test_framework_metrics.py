"""Tests for compute_framework_metrics()."""

import json
from datetime import datetime, timedelta, timezone

from desmet.adapters._shared.tracing import compute_framework_metrics, record_llm_duration
from desmet.harness.trace import AgentTrace, ToolCall


def _make_trace(
    *,
    tool_calls: list[ToolCall] | None = None,
    iterations: int = 10,
    tokens_in: int = 5000,
    tokens_out: int = 3000,
    duration_seconds: float = 60.0,
    llm_duration_ms: float = 0.0,
) -> AgentTrace:
    now = datetime.now(timezone.utc)
    trace = AgentTrace(
        start_time=now,
        end_time=now + timedelta(seconds=duration_seconds),
        total_iterations=iterations,
        total_tokens_input=tokens_in,
        total_tokens_output=tokens_out,
        total_llm_duration_ms=llm_duration_ms,
    )
    if tool_calls:
        trace.tool_calls = tool_calls
    return trace


def _tool(name: str, args: dict, success: bool = True, offset_s: float = 1.0) -> ToolCall:
    return ToolCall(
        tool_name=name,
        arguments=args,
        result="ok",
        timestamp=datetime.now(timezone.utc) + timedelta(seconds=offset_s),
        duration_ms=10.0,
        success=success,
    )


class TestComputeFrameworkMetrics:
    def test_basic_metrics(self):
        trace = _make_trace(
            tool_calls=[
                _tool("read_file", {"path": "a.py"}, offset_s=2.0),
                _tool("write_file", {"path": "b.py"}, offset_s=5.0),
            ],
            iterations=10,
            tokens_in=5000,
            tokens_out=3000,
            llm_duration_ms=40000.0,
            duration_seconds=60.0,
        )
        m = compute_framework_metrics(trace, max_iterations=50)
        assert m["tokens_per_stage"] == 8000
        assert m["iteration_ratio"] == 10 / 50
        assert m["first_action_latency_ms"] is not None
        assert m["first_action_latency_ms"] > 0
        assert m["redundant_tool_call_rate"] == 0.0
        assert m["tool_failure_rate"] == 0.0
        assert m["framework_overhead_ms"] == 20000.0

    def test_no_tool_calls(self):
        trace = _make_trace(tool_calls=[], iterations=5)
        m = compute_framework_metrics(trace, max_iterations=50)
        assert m["first_action_latency_ms"] is None
        assert m["redundant_tool_call_rate"] == 0.0
        assert m["tool_failure_rate"] == 0.0

    def test_division_by_zero_max_iterations(self):
        trace = _make_trace(iterations=5)
        m = compute_framework_metrics(trace, max_iterations=0)
        assert m["iteration_ratio"] == 0.0

    def test_redundant_calls_detected(self):
        trace = _make_trace(tool_calls=[
            _tool("read_file", {"path": "a.py"}, offset_s=1.0),
            _tool("read_file", {"path": "a.py"}, offset_s=2.0),
            _tool("read_file", {"path": "b.py"}, offset_s=3.0),
        ])
        m = compute_framework_metrics(trace, max_iterations=50)
        assert m["redundant_tool_call_rate"] == round(1 / 3, 4)

    def test_write_tools_excluded_from_duplicates(self):
        trace = _make_trace(tool_calls=[
            _tool("write_file", {"path": "a.py"}, offset_s=1.0),
            _tool("write_file", {"path": "a.py"}, offset_s=2.0),
        ])
        m = compute_framework_metrics(trace, max_iterations=50)
        assert m["redundant_tool_call_rate"] == 0.0

    def test_check_completion_excluded_from_duplicates(self):
        trace = _make_trace(tool_calls=[
            _tool("check_completion", {"stage": "codegen"}, offset_s=1.0),
            _tool("check_completion", {"stage": "codegen"}, offset_s=2.0),
        ])
        m = compute_framework_metrics(trace, max_iterations=50)
        assert m["redundant_tool_call_rate"] == 0.0

    def test_tool_failure_rate(self):
        trace = _make_trace(tool_calls=[
            _tool("read_file", {"path": "a.py"}, success=True),
            _tool("read_file", {"path": "b.py"}, success=False),
            _tool("write_file", {"path": "c.py"}, success=True),
            _tool("execute_shell", {"command": "ls"}, success=False),
        ])
        m = compute_framework_metrics(trace, max_iterations=50)
        assert m["tool_failure_rate"] == 2 / 4

    def test_negative_framework_overhead_clamped(self):
        trace = _make_trace(
            llm_duration_ms=100000.0,
            duration_seconds=60.0,
        )
        m = compute_framework_metrics(trace, max_iterations=50)
        assert m["framework_overhead_ms"] == 0.0

    def test_llm_duration_none_when_zero(self):
        trace = _make_trace(llm_duration_ms=0.0, duration_seconds=60.0)
        m = compute_framework_metrics(trace, max_iterations=50)
        assert m["framework_overhead_ms"] is None


class TestRecordLlmDuration:
    def test_accumulates(self):
        trace = AgentTrace()
        record_llm_duration(trace, 100.0)
        record_llm_duration(trace, 200.0)
        assert trace.total_llm_duration_ms == 300.0
