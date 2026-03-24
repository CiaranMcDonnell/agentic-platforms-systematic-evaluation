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
) -> None:
    """Accumulate token usage and cost into the trace."""
    trace.total_tokens_input += input_tokens
    trace.total_tokens_output += output_tokens
    trace.total_cost_usd += cost_usd


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
