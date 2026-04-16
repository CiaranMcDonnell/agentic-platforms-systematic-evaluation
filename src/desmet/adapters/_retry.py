"""Retry policy and progress reporting for platform adapters.

Centralizes retry parameters (``RetryPolicy``) and progress callback
formatting (``ProgressReporter``) so that adapters use shared policy
and formatting while keeping their idiomatic retry mechanisms.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from desmet.adapters._observation import ObservationCollector
from desmet.adapters._tracing import format_tool_detail


@dataclass
class RetryPolicy:
    """Single source of truth for retry parameters and validation.

    Created by the base class, passed to adapters.  Adapters call
    ``validate()`` inside their idiomatic retry mechanisms instead of
    importing ``validate_workspace`` / ``_check_completion`` directly.
    """

    max_retries: int = 3
    stage_name: str = ""
    workspace: Path = Path(".")

    def total_attempts(self) -> int:
        """Max retries + 1 initial attempt."""
        return self.max_retries + 1

    def validate(self) -> tuple[bool, str]:
        """Run workspace validation for the current stage.

        Returns ``(passed, feedback)`` where *feedback* is a human-readable
        string from ``_check_completion`` (success message when passed,
        failure hint when not).
        """
        from desmet.adapters._tools import _check_completion

        return _check_completion(self.workspace, self.stage_name)


class ProgressReporter:
    """Standardized progress formatting for adapter execution.

    Owns elapsed time tracking, tool call counting, and token reads.
    All methods are no-ops when the callback is ``None``.
    """

    def __init__(
        self,
        callback: Callable[[str], None] | None,
        collector: ObservationCollector,
    ) -> None:
        self._cb = callback
        self._collector = collector
        self._t0 = time.monotonic()
        self._tool_count = 0

    def _tokens(self) -> int:
        t = self._collector.trace
        return t.total_tokens_input + t.total_tokens_output

    def _elapsed(self) -> float:
        return time.monotonic() - self._t0

    def tool_call(self, name: str, args: Any) -> None:
        """Emit standardized tool call progress."""
        if self._cb is None:
            return
        self._tool_count += 1
        detail = format_tool_detail(name, args)
        self._cb(
            f"    tool {self._tool_count} — {detail}"
            f"  ({self._elapsed():.0f}s, {self._tokens():,} tokens)"
        )

    def validation_passed(self) -> None:
        """Emit validation success."""
        if self._cb is None:
            return
        self._cb("    validator: PASSED")

    def validation_failed(
        self,
        attempt: int,
        max_attempts: int,
        feedback: str,
    ) -> None:
        """Emit validation failure with attempt count and feedback."""
        if self._cb is None:
            return
        self._cb(
            f"    validator: FAILED (attempt {attempt}/{max_attempts})"
            f" — {feedback}  ({self._elapsed():.0f}s)"
        )

    def agent_status(self, agent: str, status: str) -> None:
        """Emit agent lifecycle status."""
        if self._cb is None:
            return
        self._cb(f"    [{agent}] {status}  ({self._elapsed():.0f}s, {self._tokens():,} tokens)")

    def heartbeat(self, step: int, label: str = "") -> None:
        """Emit periodic progress during long-running execution.

        *label* is the agent/node name shown in brackets.
        """
        if self._cb is None:
            return
        prefix = f"[{label}] " if label else ""
        self._cb(f"    {prefix}step {step}  ({self._elapsed():.0f}s, {self._tokens():,} tokens)")

    def waiting(self, label: str, seconds: int) -> None:
        """Emit a wall-clock heartbeat while a stage is blocked on an LLM call.

        Used by streaming wrappers (e.g. langgraph's ``executor_sg.astream``)
        to break the silence when a single LLM call is taking long enough
        that no chunk has been yielded yet.  Without this the UI looks
        frozen during 60+ second LLM calls or rate-limit retries.
        """
        if self._cb is None:
            return
        self._cb(
            f"    [{label}] waiting on LLM ({seconds}s)..."
            f"  ({self._elapsed():.0f}s, {self._tokens():,} tokens)"
        )
