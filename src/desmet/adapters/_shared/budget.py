"""Per-stage LLM-call budget, the same for every adapter.

Each stage may make at most ``StageContext.max_iterations`` LLM calls in
total, across every agent that runs in it (planner, executor, reviewer,
manager).  One LLM call is one model response, counted in
``tracing.record_usage`` — the single place every adapter's token usage
passes through — so the unit is identical across frameworks.

Adapters enforce the budget through their framework's own limit
(LangGraph recursion_limit, CrewAI max_iter, OpenAI max_turns, ADK
RunConfig.max_llm_calls, MAF chat middleware), set from
``remaining_llm_calls``.  When a stage stops because the budget ran out
the adapter calls ``mark_budget_exhausted``; the flag is reported in the
stage's framework metrics so "ran out of budget" can be told apart from
"failed the task".  How much of the budget a platform *uses* is still
measured and scored.
"""

from __future__ import annotations

from desmet.harness.trace import AgentTrace

LLM_CALLS_KEY = "llm_calls"
BUDGET_EXHAUSTED_KEY = "budget_exhausted"


def llm_calls_used(trace: AgentTrace) -> int:
    """LLM calls recorded on *trace* so far."""
    return int(trace.metadata.get(LLM_CALLS_KEY, 0))


def remaining_llm_calls(trace: AgentTrace, budget: int) -> int:
    """Calls left in a *budget*-call stage (never negative)."""
    return max(0, budget - llm_calls_used(trace))


def mark_budget_exhausted(trace: AgentTrace) -> None:
    """Record that the stage stopped because its LLM-call budget ran out."""
    trace.metadata[BUDGET_EXHAUSTED_KEY] = True


def budget_exhausted(trace: AgentTrace) -> bool:
    return bool(trace.metadata.get(BUDGET_EXHAUSTED_KEY, False))
