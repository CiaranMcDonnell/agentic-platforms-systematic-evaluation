"""Tests for the shared per-stage LLM-call budget."""

from desmet.adapters._shared.budget import (
    budget_exhausted,
    llm_calls_used,
    mark_budget_exhausted,
    mark_usage_fallback,
    remaining_llm_calls,
    usage_fallback,
)
from desmet.adapters._shared.tracing import compute_framework_metrics, record_usage, start_trace


def test_each_model_response_with_tokens_is_one_call():
    trace = start_trace()
    record_usage(trace, input_tokens=100, output_tokens=20)
    record_usage(trace, input_tokens=50)
    record_usage(trace)  # no tokens: not a model response
    assert llm_calls_used(trace) == 2
    assert remaining_llm_calls(trace, 5) == 3
    assert remaining_llm_calls(trace, 1) == 0


def test_exhaustion_flag_reaches_framework_metrics():
    trace = start_trace()
    record_usage(trace, input_tokens=10)
    assert not budget_exhausted(trace)
    mark_budget_exhausted(trace)
    fm = compute_framework_metrics(trace, max_iterations=50)
    assert fm["llm_calls"] == 1.0
    assert fm["budget_exhausted"] == 1.0


def test_unexhausted_stage_reports_zero():
    fm = compute_framework_metrics(start_trace(), max_iterations=50)
    assert fm["budget_exhausted"] == 0.0


def test_usage_fallback_makes_call_count_unknown():
    # Aggregate usage recorded as one "call" must not read as one call.
    trace = start_trace()
    record_usage(trace, input_tokens=5000, output_tokens=900)
    assert not usage_fallback(trace)
    mark_usage_fallback(trace)
    assert usage_fallback(trace)
    fm = compute_framework_metrics(trace, max_iterations=50)
    assert fm["llm_calls"] is None
    assert fm["iteration_ratio"] is None
    assert fm["usage_fallback"] == 1.0
    assert fm["tokens_per_stage"] == 5900.0


def test_no_usage_fallback_key_by_default():
    assert "usage_fallback" not in compute_framework_metrics(start_trace(), max_iterations=50)
