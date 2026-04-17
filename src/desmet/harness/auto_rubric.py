"""Automated rubric scoring from trace-derived signals.

DESMET uses 0-3 rubric scores per dimension, aggregated to a 1-5 Likert
at the platform level.  Three rubric dimensions are reducible to trace
telemetry:

* ``tool_integration``  — framework's tool-dispatch reliability.
* ``error_recovery``    — framework recovers from tool failures.
* ``trace_quality``     — trace carries enough signal to analyse.

The remaining two (``pipeline_completeness`` and ``autonomy``) continue
to be filled in by the human evaluator via the web UI, because they
require artifact inspection and judgement of agency quality.

All scoring functions are pure and side-effect free.
"""

from __future__ import annotations

from typing import Any

from desmet.harness.trace import AgentTrace


def score_tool_integration(framework_metrics: dict[str, Any]) -> float:
    """Score tool-dispatch quality on a 0-3 scale.

    Formula: ``3 * (0.7 * (1 - tool_failure_rate) + 0.3 * (1 - redundant_tool_call_rate))``.

    Weighting rationale: tool failure is a stronger negative signal than
    redundancy (a failed call is broken dispatch; a redundant call is
    wasted dispatch).  Missing metrics are treated as 0 (no evidence of
    problems) so that platforms with no tool calls at all don't get
    penalised — they just score the default 3.0.
    """
    failure = float(framework_metrics.get("tool_failure_rate") or 0.0)
    redundant = float(framework_metrics.get("redundant_tool_call_rate") or 0.0)
    health = 0.7 * (1.0 - failure) + 0.3 * (1.0 - redundant)
    return round(max(0.0, min(3.0, 3.0 * health)), 2)


def score_error_recovery(
    success: bool,
    framework_metrics: dict[str, Any],
) -> float:
    """Score error recovery on a 0-3 scale.

    * Stage failed: 0.0 (the framework did not recover).
    * Stage succeeded with no tool failures: 2.0 (nothing to recover
      from; credit withheld because recovery capability was not
      exercised).
    * Stage succeeded with non-zero tool failures: 3.0 (framework
      recovered from observable failures).
    """
    if not success:
        return 0.0
    failure = float(framework_metrics.get("tool_failure_rate") or 0.0)
    return 2.0 if failure == 0.0 else 3.0


def score_trace_quality(
    trace: AgentTrace,
    framework_metrics: dict[str, Any],
) -> float:
    """Score trace completeness on a 0-3 scale.

    Three binary signals, each worth 1.0:

    1. first-action latency is populated.
    2. framework-overhead is populated.
    3. every recorded tool call has a duration.

    An empty tool-call list counts as signal 3 present (nothing to
    fail to record).
    """
    signals = 0
    if framework_metrics.get("first_action_latency_ms") is not None:
        signals += 1
    if framework_metrics.get("framework_overhead_ms") is not None:
        signals += 1
    if not trace.tool_calls or all(tc.duration_ms is not None for tc in trace.tool_calls):
        signals += 1
    return round((signals / 3.0) * 3.0, 2)


def compute_auto_rubric_scores(
    success: bool,
    framework_metrics: dict[str, Any],
    trace: AgentTrace,
) -> dict[str, float]:
    """Return the three auto-derivable rubric scores as a dict.

    Keys match the ``StoryMetrics.*_score`` / DB ``rubric_*`` columns.
    """
    return {
        "tool_integration": score_tool_integration(framework_metrics),
        "error_recovery": score_error_recovery(success, framework_metrics),
        "trace_quality": score_trace_quality(trace, framework_metrics),
    }
