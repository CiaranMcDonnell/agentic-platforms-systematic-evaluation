"""Tests for the shared adapter tracing module."""

from __future__ import annotations

from datetime import datetime, timezone

from desmet.adapters._shared.tracing import (
    build_stage_result,
    finish_trace,
    format_tool_detail,
    normalize_usage,
    record_message,
    record_node_event,
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
        assert trace.node_events == []

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

    def test_error_message_defaults_from_trace_errors(self) -> None:
        """A swallowed exception stored on trace.errors must surface on the stage.

        Regression guard: the ADK adapter catches pipeline exceptions and
        appends them to ``trace.errors`` but was never propagating them to
        ``StageResult.error_message``, so failures looked like silent
        success-with-no-tools in the results JSON.
        """
        trace = start_trace()
        trace.errors.append("Context variable not found: `PORT`.")
        finish_trace(trace)

        result = build_stage_result(
            StageResult,
            platform_id="google_adk",
            stage_name="deploy",
            trace=trace,
            success=False,
            iterations=1,
        )

        assert result.error_message == "Context variable not found: `PORT`."

    def test_explicit_error_message_overrides_trace_errors(self) -> None:
        """If the caller passes error_message, it wins over trace.errors."""
        trace = start_trace()
        trace.errors.append("inner failure")
        finish_trace(trace)

        result = build_stage_result(
            StageResult,
            platform_id="x",
            stage_name="y",
            trace=trace,
            success=False,
            iterations=1,
            error_message="outer failure",
        )

        assert result.error_message == "outer failure"

    def test_empty_trace_errors_leaves_error_message_none(self) -> None:
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

        assert result.error_message is None


# ── TestRecordNodeEvent ─────────────────────────────────────────────────


class TestRecordNodeEvent:
    """record_node_event() appends a node-attributed event dict to the trace."""

    def test_appends_event(self) -> None:
        trace = start_trace()
        record_node_event(trace, "validator_node", validator_passed=True, retry_count=1)
        assert len(trace.node_events) == 1
        event = trace.node_events[0]
        assert event["node"] == "validator_node"
        assert event["validator_passed"] is True
        assert event["retry_count"] == 1

    def test_node_key_always_present(self) -> None:
        trace = start_trace()
        record_node_event(trace, "planner_node")
        assert trace.node_events[0]["node"] == "planner_node"

    def test_multiple_events_accumulate(self) -> None:
        trace = start_trace()
        record_node_event(trace, "validator_node", validator_passed=False, retry_count=1)
        record_node_event(trace, "validator_node", validator_passed=True, retry_count=2)
        assert len(trace.node_events) == 2
        assert trace.node_events[0]["validator_passed"] is False
        assert trace.node_events[1]["validator_passed"] is True

    def test_arbitrary_kwargs_stored(self) -> None:
        trace = start_trace()
        record_node_event(trace, "executor_node", step=3, tool="write_file")
        event = trace.node_events[0]
        assert event["step"] == 3
        assert event["tool"] == "write_file"

    def test_does_not_affect_other_collections(self) -> None:
        trace = start_trace()
        record_node_event(trace, "planner_node", plan="step 1")
        assert trace.messages == []
        assert trace.tool_calls == []
        assert trace.errors == []


# ── TestFormatToolDetail ───────────────────────────────────────────────


class TestFormatToolDetail:
    """format_tool_detail() formats a tool call into a compact string."""

    def test_read_file_with_path(self) -> None:
        assert format_tool_detail("read_file", {"path": "main.py"}) == "read_file \u2192 main.py"

    def test_write_file_with_path(self) -> None:
        assert format_tool_detail("write_file", {"path": "out.txt"}) == "write_file \u2192 out.txt"

    def test_execute_shell_truncates_long_command(self) -> None:
        result = format_tool_detail("execute_shell", {"command": "x" * 100})
        assert len(result) < 100
        assert "\u2026" in result

    def test_execute_shell_short_command(self) -> None:
        result = format_tool_detail("execute_shell", {"command": "echo hi"})
        assert result == "execute_shell \u2192 echo hi"

    def test_search_code_with_pattern(self) -> None:
        assert format_tool_detail("search_code", {"pattern": "TODO"}) == "search_code \u2192 /TODO/"

    def test_list_directory_with_path(self) -> None:
        assert format_tool_detail("list_directory", {"path": "src"}) == "list_directory \u2192 src"

    def test_list_directory_default_dot(self) -> None:
        assert format_tool_detail("list_directory", {}) == "list_directory \u2192 ."

    def test_deploy_remote_with_action(self) -> None:
        assert format_tool_detail("deploy_remote", {"action": "push"}) == "deploy_remote \u2192 push"

    def test_unknown_tool_returns_name(self) -> None:
        assert format_tool_detail("custom_tool", {"x": 1}) == "custom_tool"

    def test_json_string_args_parsed(self) -> None:
        import json

        result = format_tool_detail("read_file", json.dumps({"path": "file.py"}))
        assert result == "read_file \u2192 file.py"

    def test_invalid_json_string_returns_name(self) -> None:
        assert format_tool_detail("read_file", "not json") == "read_file"


# ── TestNormalizeUsage ─────────────────────────────────────────────────


class TestNormalizeUsage:
    """normalize_usage() extracts (input_tokens, output_tokens) from varied formats."""

    def test_attr_prompt_tokens(self) -> None:
        class U:
            prompt_tokens = 100
            completion_tokens = 50

        assert normalize_usage(U()) == (100, 50)

    def test_attr_input_tokens(self) -> None:
        class U:
            input_tokens = 200
            output_tokens = 80

        assert normalize_usage(U()) == (200, 80)

    def test_dict_prompt_tokens(self) -> None:
        assert normalize_usage({"prompt_tokens": 100, "completion_tokens": 50}) == (100, 50)

    def test_dict_input_tokens(self) -> None:
        assert normalize_usage({"input_tokens": 200, "output_tokens": 80}) == (200, 80)

    def test_dict_input_token_count(self) -> None:
        assert normalize_usage({"input_token_count": 300, "output_token_count": 120}) == (300, 120)

    def test_none_returns_zeros(self) -> None:
        assert normalize_usage(None) == (0, 0)

    def test_empty_dict_returns_zeros(self) -> None:
        assert normalize_usage({}) == (0, 0)

    def test_attr_zero_prompt_falls_back(self) -> None:
        class U:
            prompt_tokens = 0
            input_tokens = 150
            completion_tokens = 0
            output_tokens = 60

        assert normalize_usage(U()) == (150, 60)
