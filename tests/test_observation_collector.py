"""Unit tests for ObservationCollector."""

from __future__ import annotations

import threading

import pytest

from desmet.adapters._shared.observation import ObservationCollector, ObservationRequirements
from desmet.harness.trace import AgentTrace


# ── Completeness validation ────────────────────────────────────────────


def test_seal_all_missing_gives_five_warnings():
    trace = AgentTrace()
    collector = ObservationCollector(trace)
    warnings = collector.seal()
    assert len(warnings) == 5
    assert any("token usage" in w for w in warnings)
    assert any("tool calls" in w for w in warnings)
    assert any("LLM duration" in w for w in warnings)
    assert any("messages" in w for w in warnings)
    assert any("iterations" in w for w in warnings)


def test_seal_all_recorded_gives_no_warnings():
    trace = AgentTrace()
    collector = ObservationCollector(trace, model="test-model")
    collector.record_llm_response(
        raw_usage={"prompt_tokens": 10, "completion_tokens": 5},
        duration_ms=100.0,
    )
    collector.record_tool_execution("read_file", {"path": "x"}, "content")
    collector.record_message("user", "hello")
    collector.mark_iterations(3)
    warnings = collector.seal()
    assert warnings == []


def test_seal_relaxed_requirement_no_warning():
    trace = AgentTrace()
    reqs = ObservationRequirements(llm_duration=False)
    collector = ObservationCollector(trace, requirements=reqs, model="m")
    collector.record_llm_response(raw_usage={"prompt_tokens": 1, "completion_tokens": 1})
    collector.record_tool_execution("t", {}, "")
    collector.record_message("user", "hi")
    collector.mark_iterations(1)
    warnings = collector.seal()
    assert warnings == []


def test_seal_custom_requirement_missing():
    trace = AgentTrace()
    reqs = ObservationRequirements(
        usage=False, tool_calls=False, llm_duration=False,
        messages=False, iterations=False,
        custom={"stall_count": True},
    )
    collector = ObservationCollector(trace, requirements=reqs)
    warnings = collector.seal()
    assert len(warnings) == 1
    assert "stall_count" in warnings[0]


def test_seal_custom_requirement_recorded():
    trace = AgentTrace()
    reqs = ObservationRequirements(
        usage=False, tool_calls=False, llm_duration=False,
        messages=False, iterations=False,
        custom={"stall_count": True},
    )
    collector = ObservationCollector(trace, requirements=reqs)
    collector.record_custom("stall_count", 2)
    warnings = collector.seal()
    assert warnings == []


# ── Normalization ──────────────────────────────────────────────────────


def test_normalize_prompt_tokens_keys():
    trace = AgentTrace()
    collector = ObservationCollector(trace, model="m")
    collector.record_llm_response(
        raw_usage={"prompt_tokens": 10, "completion_tokens": 20},
    )
    assert trace.total_tokens_input == 10
    assert trace.total_tokens_output == 20
    assert collector.usage_count == 1


def test_normalize_input_tokens_keys():
    trace = AgentTrace()
    collector = ObservationCollector(trace, model="m")
    collector.record_llm_response(
        raw_usage={"input_tokens": 10, "output_tokens": 20},
    )
    assert trace.total_tokens_input == 10
    assert trace.total_tokens_output == 20
    assert collector.usage_count == 1


def test_null_usage_not_counted():
    trace = AgentTrace()
    collector = ObservationCollector(trace, model="m")
    collector.record_llm_response(raw_usage=None)
    assert collector.usage_count == 0
    assert trace.total_tokens_input == 0


def test_null_usage_with_duration_records_duration_only():
    trace = AgentTrace()
    collector = ObservationCollector(trace, model="m")
    collector.record_llm_response(raw_usage=None, duration_ms=150.0)
    assert collector.usage_count == 0
    assert trace.total_llm_duration_ms == 150.0


# ── Thread safety ──────────────────────────────────────────────────────


def test_concurrent_recording():
    trace = AgentTrace()
    collector = ObservationCollector(
        trace, model="m",
        requirements=ObservationRequirements(
            tool_calls=False, messages=False, iterations=False,
        ),
    )

    def record_batch():
        for _ in range(100):
            collector.record_llm_response(
                raw_usage={"prompt_tokens": 1, "completion_tokens": 1},
                duration_ms=1.0,
            )

    threads = [threading.Thread(target=record_batch) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert collector.usage_count == 1000
    assert trace.total_tokens_input == 1000
    assert trace.total_tokens_output == 1000


def test_record_after_seal_raises():
    trace = AgentTrace()
    collector = ObservationCollector(trace)
    collector.seal()
    with pytest.raises(RuntimeError, match="Cannot record after seal"):
        collector.record_llm_response(raw_usage={"prompt_tokens": 1, "completion_tokens": 1})
    with pytest.raises(RuntimeError, match="Cannot record after seal"):
        collector.record_tool_execution("t", {}, "")
    with pytest.raises(RuntimeError, match="Cannot record after seal"):
        collector.record_message("user", "hi")
    with pytest.raises(RuntimeError, match="Cannot record after seal"):
        collector.mark_iterations(1)
    with pytest.raises(RuntimeError, match="Cannot record after seal"):
        collector.record_custom("k", "v")


# ── Model fallback ─────────────────────────────────────────────────────


def test_constructor_model_used_by_default(mocker):
    trace = AgentTrace()
    spy = mocker.patch("desmet.adapters._shared.observation.record_usage")
    collector = ObservationCollector(trace, model="gpt-4o")
    collector.record_llm_response(raw_usage={"prompt_tokens": 5, "completion_tokens": 5})
    spy.assert_called_once()
    assert spy.call_args.kwargs["model"] == "gpt-4o"


def test_per_call_model_overrides_constructor(mocker):
    trace = AgentTrace()
    spy = mocker.patch("desmet.adapters._shared.observation.record_usage")
    collector = ObservationCollector(trace, model="gpt-4o")
    collector.record_llm_response(
        raw_usage={"prompt_tokens": 5, "completion_tokens": 5},
        model="claude-sonnet",
    )
    spy.assert_called_once()
    assert spy.call_args.kwargs["model"] == "claude-sonnet"


# ── seal() calls finish_trace ──────────────────────────────────────────


def test_seal_sets_end_time():
    trace = AgentTrace()
    collector = ObservationCollector(
        trace,
        requirements=ObservationRequirements(
            usage=False, tool_calls=False, llm_duration=False,
            messages=False, iterations=False,
        ),
    )
    assert trace.end_time is None
    collector.seal()
    assert trace.end_time is not None


def test_seal_idempotent_end_time():
    from datetime import datetime, timezone

    trace = AgentTrace()
    trace.end_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    collector = ObservationCollector(
        trace,
        requirements=ObservationRequirements(
            usage=False, tool_calls=False, llm_duration=False,
            messages=False, iterations=False,
        ),
    )
    collector.seal()
    assert trace.end_time == datetime(2026, 1, 1, tzinfo=timezone.utc)
