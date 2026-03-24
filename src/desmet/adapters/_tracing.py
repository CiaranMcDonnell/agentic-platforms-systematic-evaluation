"""Shared trace lifecycle management and result construction for adapters.

Every platform adapter needs the same boilerplate to:
  1. Start / finish an ``AgentTrace``
  2. Record messages, tool calls, and token usage
  3. Build a ``StageResult`` subclass from a completed trace

This module provides small, composable helpers that all adapters can
reuse instead of duplicating the logic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from desmet.harness.results import StageResult
from desmet.harness.trace import AgentMessage, AgentTrace, ToolCall

# ── Trace lifecycle ─────────────────────────────────────────────────────


def start_trace() -> AgentTrace:
    """Create a new ``AgentTrace`` with *start_time* set to now (UTC)."""
    return AgentTrace(start_time=datetime.now(timezone.utc))


def finish_trace(
    trace: AgentTrace,
    final_state: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """Finalize a trace.

    * Sets *end_time* to now (UTC) **only if** it has not been set yet
      (idempotent).
    * Overwrites *final_state* if a non-``None`` value is provided.
    * Appends *error* to ``trace.errors`` when given.
    """
    if trace.end_time is None:
        trace.end_time = datetime.now(timezone.utc)
    if final_state is not None:
        trace.final_state = final_state
    if error is not None:
        trace.errors.append(error)


# ── Recording helpers ───────────────────────────────────────────────────


def record_message(
    trace: AgentTrace,
    role: str,
    content: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append an ``AgentMessage`` to *trace.messages*."""
    trace.messages.append(
        AgentMessage(
            role=role,
            content=content,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
    )


def record_usage(
    trace: AgentTrace,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float = 0.0,
    *,
    model: str | None = None,
) -> None:
    """Accumulate token usage and cost into the trace.

    When *cost_usd* is 0 and tokens are present, falls back to
    :func:`desmet.cost_calculator.estimate_cost` using live OpenRouter
    pricing data.  Pass *model* to enable the fallback.
    """
    trace.total_tokens_input += input_tokens
    trace.total_tokens_output += output_tokens
    if cost_usd > 0:
        trace.total_cost_usd += cost_usd
    elif model and (input_tokens or output_tokens):
        from desmet.cost_calculator import estimate_cost
        trace.total_cost_usd += estimate_cost(model, input_tokens, output_tokens)


def record_tool_call(
    trace: AgentTrace,
    name: str,
    args: dict,
    result: Any,
    *,
    duration_ms: float = 0.0,
    success: bool = True,
) -> None:
    """Append a ``ToolCall`` to *trace.tool_calls*."""
    trace.tool_calls.append(
        ToolCall(
            tool_name=name,
            arguments=args,
            result=result,
            timestamp=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            success=success,
        )
    )


def record_node_event(
    trace: AgentTrace,
    node: str,
    **data: Any,
) -> None:
    """Record a named graph-node event on the trace.

    Useful for capturing per-node state changes (e.g. validator retries,
    planner decisions) when streaming with ``stream_mode="updates"``.
    Each event is stored as a dict with at least a ``"node"`` key.
    """
    trace.node_events.append({"node": node, **data})


def record_llm_duration(trace: AgentTrace, duration_ms: float) -> None:
    """Accumulate LLM API call wall-clock time (ms) into the trace."""
    trace.total_llm_duration_ms += duration_ms


# ── Automated framework metrics ───────────────────────────────────────

_DUPLICATE_CHECK_TOOLS = frozenset({"read_file", "list_directory", "search_code"})


def compute_framework_metrics(
    trace: AgentTrace,
    max_iterations: int,
) -> dict[str, float | None]:
    """Compute automated framework metrics from a completed stage trace.

    All metrics measure framework orchestration quality, not LLM output.
    Returns a dict of metric_name -> value (or None when unavailable).
    """
    import json as _json

    total_tokens = trace.total_tokens_input + trace.total_tokens_output
    tool_calls = trace.tool_calls

    # Tokens per stage
    tokens_per_stage = float(total_tokens)

    # Iteration ratio
    iteration_ratio = (
        trace.total_iterations / max_iterations
        if max_iterations > 0 else 0.0
    )

    # First-action latency
    first_action_latency_ms: float | None = None
    if tool_calls and trace.start_time is not None:
        first_tc = min(tool_calls, key=lambda tc: tc.timestamp)
        delta = (first_tc.timestamp - trace.start_time).total_seconds()
        first_action_latency_ms = max(0.0, delta * 1000.0)

    # Redundant tool call rate
    checkable = [
        tc for tc in tool_calls
        if tc.tool_name in _DUPLICATE_CHECK_TOOLS
    ]
    if checkable:
        seen: set[str] = set()
        duplicates = 0
        for tc in checkable:
            key = tc.tool_name + "|" + _json.dumps(tc.arguments, sort_keys=True)
            if key in seen:
                duplicates += 1
            else:
                seen.add(key)
        redundant_tool_call_rate = duplicates / len(checkable)
    else:
        redundant_tool_call_rate = 0.0

    # Tool failure rate
    if tool_calls:
        failed = sum(1 for tc in tool_calls if not tc.success)
        tool_failure_rate = failed / len(tool_calls)
    else:
        tool_failure_rate = 0.0

    # Framework overhead
    if trace.total_llm_duration_ms > 0:
        wall_ms = trace.duration_seconds * 1000.0
        framework_overhead_ms: float | None = max(0.0, wall_ms - trace.total_llm_duration_ms)
    else:
        framework_overhead_ms = None

    return {
        "tokens_per_stage": tokens_per_stage,
        "iteration_ratio": round(iteration_ratio, 4),
        "first_action_latency_ms": (
            round(first_action_latency_ms, 1)
            if first_action_latency_ms is not None else None
        ),
        "redundant_tool_call_rate": round(redundant_tool_call_rate, 4),
        "tool_failure_rate": round(tool_failure_rate, 4),
        "framework_overhead_ms": (
            round(framework_overhead_ms, 1)
            if framework_overhead_ms is not None else None
        ),
    }


# ── Result construction ─────────────────────────────────────────────────


def build_stage_result(
    result_cls: type[StageResult],
    platform_id: str,
    stage_name: str,
    trace: AgentTrace,
    success: bool,
    iterations: int,
    error_message: str | None = None,
    **extra_fields: Any,
) -> StageResult:
    """Construct a ``StageResult`` subclass from trace data.

    Derives timing, token counts, and tool-call count directly from the
    trace so that callers never need to compute them manually.

    If *trace.end_time* has not been set, ``finish_trace()`` is called
    automatically so that ``wall_clock_seconds`` is meaningful.

    ``completed`` defaults to *success* but can be overridden via
    *extra_fields*.
    """
    # Auto-finish the trace if the caller forgot.
    if trace.end_time is None:
        finish_trace(trace)

    completed = extra_fields.pop("completed", success)

    return result_cls(
        platform_id=platform_id,
        stage_name=stage_name,
        success=success,
        completed=completed,
        error_message=error_message,
        trace=trace,
        wall_clock_seconds=trace.duration_seconds,
        iterations=iterations,
        tool_calls_count=len(trace.tool_calls),
        tokens_input=trace.total_tokens_input,
        tokens_output=trace.total_tokens_output,
        cost_usd=trace.total_cost_usd,
        start_time=trace.start_time,
        end_time=trace.end_time,
        **extra_fields,
    )
