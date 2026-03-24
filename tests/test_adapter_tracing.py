"""Tests for the shared adapter tracing module."""

from __future__ import annotations

from datetime import datetime, timezone

from desmet.adapters._tracing import (
    build_stage_result,
    finish_trace,
    record_message,
    record_tool_call,
    record_usage,
    start_trace,
)
from desmet.harness.results import (
    DeployResult,
    RequirementsResult,
    StageResult,
)
from desmet.harness.trace import (
    AgentMessage,
    AgentTrace,
    ToolCall,
)

# ── TestStartTrace ──────────────────────────────────────────────────────


class TestStartTrace:
    """start_trace() returns a fresh AgentTrace with start_time set."""

    def test_returns_agent_trace(self) -> None:
        trace = start_trace()
        assert isinstance(trace, AgentTrace)

    def test_start_time_is_utc(self) -> None:
        before = datetime.now(timezone.utc)
        trace = start_trace()
        after = datetime.now(timezone.utc)
        assert trace.start_time is not None
        assert before <= trace.start_time <= after
        assert trace.start_time.tzinfo is not None

    def test_collections_are_empty(self) -> None:
        trace = start_trace()
        assert trace.messages == []
        assert trace.tool_calls == []
        assert trace.errors == []
        assert trace.final_state == {}

    def test_counters_are_zero(self) -> None:
        trace = start_trace()
        assert trace.total_iterations == 0
        assert trace.total_tokens_input == 0
        assert trace.total_tokens_output == 0

    def test_end_time_is_none(self) -> None:
        trace = start_trace()
        assert trace.end_time is None


# ── TestRecordMessage ───────────────────────────────────────────────────


class TestRecordMessage:
    """record_message() appends an AgentMessage to the trace."""

    def test_appends_message(self) -> None:
        trace = start_trace()
        record_message(trace, "user", "Hello")
        assert len(trace.messages) == 1
        msg = trace.messages[0]
        assert isinstance(msg, AgentMessage)
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_message_has_timestamp(self) -> None:
        trace = start_trace()
        before = datetime.now(timezone.utc)
        record_message(trace, "assistant", "Hi")
        after = datetime.now(timezone.utc)
        msg = trace.messages[0]
        assert before <= msg.timestamp <= after

    def test_metadata_kwarg(self) -> None:
        trace = start_trace()
        record_message(trace, "system", "init", metadata={"key": "value"})
        assert trace.messages[0].metadata == {"key": "value"}

    def test_default_metadata_is_empty(self) -> None:
        trace = start_trace()
        record_message(trace, "user", "x")
        assert trace.messages[0].metadata == {}

    def test_multiple_messages(self) -> None:
        trace = start_trace()
        record_message(trace, "user", "one")
        record_message(trace, "assistant", "two")
        assert len(trace.messages) == 2
        assert trace.messages[0].role == "user"
        assert trace.messages[1].role == "assistant"


# ── TestRecordToolCall ──────────────────────────────────────────────────


class TestRecordToolCall:
    """record_tool_call() appends a ToolCall to the trace."""

    def test_appends_tool_call(self) -> None:
        trace = start_trace()
        record_tool_call(trace, "read_file", {"path": "a.py"}, "contents")
        assert len(trace.tool_calls) == 1
        tc = trace.tool_calls[0]
        assert isinstance(tc, ToolCall)
        assert tc.tool_name == "read_file"
        assert tc.arguments == {"path": "a.py"}
        assert tc.result == "contents"
        assert tc.success is True

    def test_failed_tool_call(self) -> None:
        trace = start_trace()
        record_tool_call(
            trace, "execute_shell", {"cmd": "rm -rf /"}, None, success=False
        )
        tc = trace.tool_calls[0]
        assert tc.success is False

    def test_duration_ms(self) -> None:
        trace = start_trace()
        record_tool_call(trace, "search", {}, [], duration_ms=42.5)
        assert trace.tool_calls[0].duration_ms == 42.5

    def test_tool_call_has_timestamp(self) -> None:
        trace = start_trace()
        before = datetime.now(timezone.utc)
        record_tool_call(trace, "list_dir", {}, [])
        after = datetime.now(timezone.utc)
        assert before <= trace.tool_calls[0].timestamp <= after


# ── TestRecordUsage ─────────────────────────────────────────────────────


class TestRecordUsage:
    """record_usage() accumulates token counts."""

    def test_single_call(self) -> None:
        trace = start_trace()
        record_usage(trace, input_tokens=100, output_tokens=50)
        assert trace.total_tokens_input == 100
        assert trace.total_tokens_output == 50

    def test_accumulates_across_calls(self) -> None:
        trace = start_trace()
        record_usage(trace, input_tokens=100, output_tokens=50)
        record_usage(trace, input_tokens=200, output_tokens=75)
        assert trace.total_tokens_input == 300
        assert trace.total_tokens_output == 125

    def test_defaults_to_zero(self) -> None:
        trace = start_trace()
        record_usage(trace)
        assert trace.total_tokens_input == 0
        assert trace.total_tokens_output == 0

    def test_input_only(self) -> None:
        trace = start_trace()
        record_usage(trace, input_tokens=500)
        assert trace.total_tokens_input == 500
        assert trace.total_tokens_output == 0


# ── TestFinishTrace ─────────────────────────────────────────────────────


class TestFinishTrace:
    """finish_trace() finalizes a trace."""

    def test_sets_end_time(self) -> None:
        trace = start_trace()
        before = datetime.now(timezone.utc)
        finish_trace(trace)
        after = datetime.now(timezone.utc)
        assert trace.end_time is not None
        assert before <= trace.end_time <= after

    def test_sets_final_state(self) -> None:
        trace = start_trace()
        finish_trace(trace, final_state={"status": "done"})
        assert trace.final_state == {"status": "done"}

    def test_appends_error(self) -> None:
        trace = start_trace()
        finish_trace(trace, error="something broke")
        assert "something broke" in trace.errors

    def test_no_error_no_append(self) -> None:
        trace = start_trace()
        finish_trace(trace)
        assert trace.errors == []

    def test_idempotent_end_time(self) -> None:
        """Calling finish_trace twice should not overwrite the first end_time."""
        trace = start_trace()
        finish_trace(trace)
        first_end = trace.end_time
        finish_trace(trace)
        assert trace.end_time == first_end

    def test_none_final_state_preserves_existing(self) -> None:
        trace = start_trace()
        trace.final_state = {"existing": True}
        finish_trace(trace, final_state=None)
        assert trace.final_state == {"existing": True}


# ── TestBuildStageResult ────────────────────────────────────────────────


class TestBuildStageResult:
    """build_stage_result() constructs a StageResult subclass from trace data."""

    def test_basic_requirements_result(self) -> None:
        trace = start_trace()
        record_usage(trace, input_tokens=500, output_tokens=200)
        record_tool_call(trace, "read_file", {}, "data")
        record_tool_call(trace, "search", {}, [])
        finish_trace(trace, final_state={"ok": True})

        result = build_stage_result(
            RequirementsResult,
            platform_id="langgraph",
            stage_name="requirements",
            trace=trace,
            success=True,
            iterations=3,
        )

        assert isinstance(result, RequirementsResult)
        assert result.platform_id == "langgraph"
        assert result.stage_name == "requirements"
        assert result.success is True
        assert result.completed is True
        assert result.iterations == 3
        assert result.tokens_input == 500
        assert result.tokens_output == 200
        assert result.tool_calls_count == 2
        assert result.trace is trace
        assert result.start_time == trace.start_time
        assert result.end_time == trace.end_time

    def test_failed_result_with_error(self) -> None:
        trace = start_trace()
        finish_trace(trace)

        result = build_stage_result(
            StageResult,
            platform_id="crewai",
            stage_name="codegen",
            trace=trace,
            success=False,
            iterations=1,
            error_message="LLM timeout",
        )

        assert result.success is False
        assert result.completed is False
        assert result.error_message == "LLM timeout"

    def test_auto_finishes_trace(self) -> None:
        """If the trace has no end_time yet, build_stage_result should call finish_trace."""
        trace = start_trace()
        assert trace.end_time is None

        result = build_stage_result(
            StageResult,
            platform_id="test",
            stage_name="testing",
            trace=trace,
            success=True,
            iterations=1,
        )

        assert trace.end_time is not None
        assert result.end_time is not None

    def test_extra_fields_passthrough(self) -> None:
        """Extra keyword arguments should be forwarded to the result constructor."""
        trace = start_trace()
        finish_trace(trace)

        result = build_stage_result(
            DeployResult,
            platform_id="agent_framework",
            stage_name="deploy",
            trace=trace,
            success=True,
            iterations=1,
            build_success=True,
            deployment_ready=True,
            build_log="all good",
        )

        assert isinstance(result, DeployResult)
        assert result.build_success is True
        assert result.deployment_ready is True
        assert result.build_log == "all good"

    def test_token_counts_from_trace(self) -> None:
        trace = start_trace()
        record_usage(trace, input_tokens=1000, output_tokens=400)
        record_usage(trace, input_tokens=500, output_tokens=100)
        finish_trace(trace)

        result = build_stage_result(
            StageResult,
            platform_id="x",
            stage_name="y",
            trace=trace,
            success=True,
            iterations=2,
        )

        assert result.tokens_input == 1500
        assert result.tokens_output == 500

    def test_wall_clock_seconds_from_trace(self) -> None:
        trace = start_trace()
        finish_trace(trace)

        result = build_stage_result(
            StageResult,
            platform_id="x",
            stage_name="y",
            trace=trace,
            success=True,
            iterations=1,
        )

        assert result.wall_clock_seconds == trace.duration_seconds

    def test_completed_can_be_overridden(self) -> None:
        """If completed is passed in extra_fields, it should override the default."""
        trace = start_trace()
        finish_trace(trace)

        result = build_stage_result(
            StageResult,
            platform_id="x",
            stage_name="y",
            trace=trace,
            success=True,
            iterations=1,
            completed=False,
        )

        assert result.completed is False
