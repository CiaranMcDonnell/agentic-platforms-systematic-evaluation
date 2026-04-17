"""Shared planning utilities for all platform adapters.

Consolidates the structured-planning logic (plan model, formatting,
instruction assembly, and plan parsing) that was previously duplicated
across the concrete adapter modules.
"""

from __future__ import annotations

import re
from typing import overload

from pydantic import BaseModel

from desmet.adapters._shared.prompts import AgentPersona

# =========================================================================
# Plan Model
# =========================================================================


class ImplementationPlan(BaseModel):
    """Structured output from the planner agent."""

    steps: list[str]
    files_to_create: list[str]
    files_to_modify: list[str]


# =========================================================================
# Format helpers
# =========================================================================


def format_plan_text(plan: ImplementationPlan) -> tuple[str, str]:
    """Return ``(plan_text, files_text)`` from *plan*.

    *plan_text* is a numbered list of steps.  *files_text* is a
    comma-separated list of all files (create + modify), or
    ``"(none specified)"`` when both lists are empty.
    """
    plan_text = "\n".join(f"{i}. {step}" for i, step in enumerate(plan.steps, 1))

    all_files = plan.files_to_create + plan.files_to_modify
    files_text = ", ".join(all_files) if all_files else "(none specified)"

    return plan_text, files_text


def build_executor_instructions(
    persona: AgentPersona,
    plan: ImplementationPlan,
    system_msg: str | None = None,
    *,
    stage: str = "",
    workspace: str = "",
) -> str:
    """Assemble executor instructions from persona, plan, and optional context."""
    plan_text, files_text = format_plan_text(plan)

    parts: list[str] = [
        persona.backstory,
        "",
        "## Implementation Plan",
        plan_text,
        "",
        "## Files",
        files_text,
    ]

    if system_msg:
        parts.extend(["", "## Additional Context", system_msg])

    if stage or workspace:
        parts.append("")
        if stage:
            parts.append(f"Stage: {stage}")
        if workspace:
            parts.append(f"Working directory: {workspace}")

    return "\n".join(parts)


# =========================================================================
# Plan parsing
# =========================================================================

_STEP_RE = re.compile(r"^\s*(?:\d+\.\s+|-\s+)(.*)", re.MULTILINE)
_PARALLEL_TAG = "[PARALLEL]"


@overload
def parse_plan_text(text: str, include_parallel: bool = False) -> ImplementationPlan: ...


@overload
def parse_plan_text(
    text: str, include_parallel: bool = True
) -> tuple[ImplementationPlan, list[bool]]: ...


def parse_plan_text(
    text: str, include_parallel: bool = False
) -> ImplementationPlan | tuple[ImplementationPlan, list[bool]]:
    """Parse numbered/dashed steps from free *text*.

    When *include_parallel* is ``False`` (default), returns an
    :class:`ImplementationPlan`.  When ``True``, returns a
    ``(plan, parallel_flags)`` tuple where each flag indicates whether the
    corresponding step was marked ``[PARALLEL]``.
    """
    matches = _STEP_RE.findall(text)

    if not matches:
        # Fallback: treat the whole text as a single step.
        step = text.strip() or text
        plan = ImplementationPlan(steps=[step], files_to_create=[], files_to_modify=[])
        if include_parallel:
            return plan, [False]
        return plan

    steps: list[str] = []
    parallel_flags: list[bool] = []

    for raw in matches:
        is_parallel = _PARALLEL_TAG in raw
        cleaned = raw.replace(_PARALLEL_TAG, "").strip()
        steps.append(cleaned)
        parallel_flags.append(is_parallel)

    plan = ImplementationPlan(steps=steps, files_to_create=[], files_to_modify=[])

    if include_parallel:
        return plan, parallel_flags
    return plan
