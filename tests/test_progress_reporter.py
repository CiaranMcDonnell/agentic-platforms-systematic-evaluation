"""Unit tests for ProgressReporter."""

from __future__ import annotations

import time

from desmet.adapters._shared.observation import ObservationCollector, ObservationRequirements
from desmet.adapters._shared.retry import ProgressReporter
from desmet.harness.trace import AgentTrace


def _make_reporter(messages: list[str]) -> ProgressReporter:
    """Create a reporter that appends to *messages*."""
    trace = AgentTrace()
    collector = ObservationCollector(
        trace,
        requirements=ObservationRequirements(
            usage=False, tool_calls=False, llm_duration=False,
            messages=False, iterations=False,
        ),
    )
    return ProgressReporter(callback=messages.append, collector=collector)


def test_tool_call_format():
    msgs: list[str] = []
    reporter = _make_reporter(msgs)
    reporter.tool_call("read_file", {"path": "src/main.py"})
    assert len(msgs) == 1
    assert "tool 1" in msgs[0]
    assert "read_file" in msgs[0]
    assert "src/main.py" in msgs[0]


def test_tool_call_increments_counter():
    msgs: list[str] = []
    reporter = _make_reporter(msgs)
    reporter.tool_call("read_file", {"path": "a.py"})
    reporter.tool_call("write_file", {"path": "b.py", "content": "x"})
    assert "tool 1" in msgs[0]
    assert "tool 2" in msgs[1]


def test_validation_passed():
    msgs: list[str] = []
    reporter = _make_reporter(msgs)
    reporter.validation_passed()
    assert msgs == ["    validator: PASSED"]


def test_validation_failed():
    msgs: list[str] = []
    reporter = _make_reporter(msgs)
    reporter.validation_failed(2, 4, "Missing artifacts")
    assert len(msgs) == 1
    assert "validator: FAILED" in msgs[0]
    assert "(attempt 2/4)" in msgs[0]
    assert "Missing artifacts" in msgs[0]


def test_agent_status():
    msgs: list[str] = []
    reporter = _make_reporter(msgs)
    reporter.agent_status("planner", "done — 5 steps planned")
    assert len(msgs) == 1
    assert "[planner]" in msgs[0]
    assert "done — 5 steps planned" in msgs[0]


def test_heartbeat():
    msgs: list[str] = []
    reporter = _make_reporter(msgs)
    reporter.heartbeat(7, "executor")
    assert len(msgs) == 1
    assert "[executor]" in msgs[0]
    assert "step 7" in msgs[0]


def test_heartbeat_no_label():
    msgs: list[str] = []
    reporter = _make_reporter(msgs)
    reporter.heartbeat(3)
    assert len(msgs) == 1
    assert "step 3" in msgs[0]
    assert "[" not in msgs[0]  # no brackets when no label


def test_waiting_emits_seconds_and_label():
    """The waiting() helper is what stops slow LLM calls from looking
    like a freeze in the UI — used by the langgraph stream wrapper."""
    msgs: list[str] = []
    reporter = _make_reporter(msgs)
    reporter.waiting("executor", 15)
    assert len(msgs) == 1
    assert "[executor]" in msgs[0]
    assert "waiting on LLM" in msgs[0]
    assert "(15s)" in msgs[0]


def test_waiting_is_noop_when_callback_none():
    trace = AgentTrace()
    collector = ObservationCollector(
        trace,
        requirements=ObservationRequirements(
            usage=False, tool_calls=False, llm_duration=False,
            messages=False, iterations=False,
        ),
    )
    reporter = ProgressReporter(callback=None, collector=collector)
    reporter.waiting("executor", 5)  # must not raise


def test_none_callback_is_noop():
    trace = AgentTrace()
    collector = ObservationCollector(
        trace,
        requirements=ObservationRequirements(
            usage=False, tool_calls=False, llm_duration=False,
            messages=False, iterations=False,
        ),
    )
    reporter = ProgressReporter(callback=None, collector=collector)
    # None of these should raise
    reporter.tool_call("read_file", {"path": "x"})
    reporter.validation_passed()
    reporter.validation_failed(1, 4, "hint")
    reporter.agent_status("planner", "done")
    reporter.heartbeat(1, "executor")


def test_elapsed_and_tokens_in_output():
    msgs: list[str] = []
    reporter = _make_reporter(msgs)
    reporter.tool_call("read_file", {"path": "x"})
    # Should contain elapsed time and token count
    assert "s," in msgs[0]  # elapsed seconds
    assert "tokens" in msgs[0]
