"""Tests for the shared per-stage LLM-call budget."""

from desmet.adapters._shared.budget import (
    budget_exhausted,
    llm_calls_used,
    mark_budget_exhausted,
    remaining_llm_calls,
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
