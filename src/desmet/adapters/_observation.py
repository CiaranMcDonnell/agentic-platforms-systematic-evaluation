"""Observation data collection with completeness validation.

Wraps ``AgentTrace`` to provide a typed recording interface that handles
normalization internally and validates that all required observation types
were recorded before the trace is finalized.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from desmet.adapters._tracing import (
    finish_trace,
    normalize_usage,
    record_llm_duration,
    record_message as _record_message,
    record_tool_call,
    record_usage,
)
from desmet.harness.trace import AgentTrace


@dataclass
class ObservationRequirements:
    """Declares which observation types an adapter is expected to record.

    All default to ``True``.  Adapters override
    ``ToolAgentAdapter.observation_requirements()`` to relax specific ones.
    """

    usage: bool = True
    tool_calls: bool = True
    llm_duration: bool = True
    messages: bool = True
    iterations: bool = True
    custom: dict[str, bool] = field(default_factory=dict)


class ObservationCollector:
    """Thread-safe sealed accumulator for observation data.

    Wraps an ``AgentTrace``, provides typed recording methods that handle
    normalization internally, and validates completeness when sealed.
    """

    def __init__(
        self,
        trace: AgentTrace,
        *,
        model: str | None = None,
        requirements: ObservationRequirements | None = None,
    ) -> None:
        self._trace = trace
        self._model = model
        self._requirements = requirements or ObservationRequirements()
        self._lock = threading.Lock()
        self._sealed = False
        self._usage_count = 0
        self._tool_call_count = 0
        self._llm_duration_total_ms = 0.0
        self._message_count = 0
        self._iteration_count = 0
        self._custom_counts: dict[str, int] = {}

    # ── Recording methods ──────────────────────────────────────────

    def record_llm_response(
        self,
        raw_usage: Any = None,
        duration_ms: float = 0.0,
        *,
        model: str | None = None,
        cost_usd: float = 0.0,
    ) -> None:
        """Record one LLM API call — usage + duration in a single call."""
        with self._lock:
            if self._sealed:
                raise RuntimeError("Cannot record after seal()")
            resolved_model = model or self._model
            inp, out = normalize_usage(raw_usage)
            if inp or out:
                record_usage(
                    self._trace,
                    input_tokens=inp,
                    output_tokens=out,
                    cost_usd=cost_usd,
                    model=resolved_model,
                )
                self._usage_count += 1
            if duration_ms > 0:
                record_llm_duration(self._trace, duration_ms)
                self._llm_duration_total_ms += duration_ms

    def record_tool_execution(
        self,
        name: str,
        args: dict,
        result: Any,
        *,
        duration_ms: float = 0.0,
        success: bool = True,
    ) -> None:
        """Record one tool call."""
        with self._lock:
            if self._sealed:
                raise RuntimeError("Cannot record after seal()")
            record_tool_call(
                self._trace,
                name=name,
                args=args,
                result=result,
                duration_ms=duration_ms,
                success=success,
            )
            self._tool_call_count += 1

    def record_message(
        self,
        role: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a conversation message."""
        with self._lock:
            if self._sealed:
                raise RuntimeError("Cannot record after seal()")
            _record_message(self._trace, role, content, metadata=metadata)
            self._message_count += 1

    def mark_iterations(self, count: int) -> None:
        """Add *count* to the iteration counter."""
        with self._lock:
            if self._sealed:
                raise RuntimeError("Cannot record after seal()")
            self._iteration_count += count
            self._trace.total_iterations = self._iteration_count

    def record_custom(self, key: str, value: Any) -> None:
        """Record a named custom observation."""
        with self._lock:
            if self._sealed:
                raise RuntimeError("Cannot record after seal()")
            self._custom_counts[key] = self._custom_counts.get(key, 0) + 1

    # ── Lifecycle ──────────────────────────────────────────────────

    def seal(self) -> list[str]:
        """Finalize collection.  Returns list of warnings for missing data."""
        with self._lock:
            self._sealed = True

        if self._trace.end_time is None:
            finish_trace(self._trace)

        warnings: list[str] = []
        req = self._requirements

        if req.usage and self._usage_count == 0:
            warnings.append(
                "No token usage recorded (expected at least 1 LLM response)"
            )
        if req.tool_calls and self._tool_call_count == 0:
            warnings.append("No tool calls recorded")
        if req.llm_duration and self._llm_duration_total_ms == 0.0:
            warnings.append("No LLM duration recorded")
        if req.messages and self._message_count == 0:
            warnings.append("No messages recorded")
        if req.iterations and self._iteration_count == 0:
            warnings.append("No iterations recorded")

        for key, required in req.custom.items():
            if required and self._custom_counts.get(key, 0) == 0:
                warnings.append(f"No custom observation '{key}' recorded")

        return warnings

    # ── Accessors ──────────────────────────────────────────────────

    @property
    def trace(self) -> AgentTrace:
        """Direct trace access for framework-specific operations."""
        return self._trace

    @property
    def usage_count(self) -> int:
        """Number of LLM responses with non-zero usage recorded."""
        return self._usage_count

    @property
    def tool_call_count(self) -> int:
        """Number of tool executions recorded."""
        return self._tool_call_count
