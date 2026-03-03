"""
Stage 1: Story Loading and Context Preparation

Loads user stories from YAML and prepares StageContext for downstream stages.
This is a harness-only stage — no adapter call.
"""
from pathlib import Path
from typing import Optional

from desmet.harness.base import StageContext
from desmet.harness.story import UserStory


def prepare_stage_context(
    story: UserStory,
    workspace: Path,
    time_budget_seconds: Optional[int] = None,
    max_iterations: Optional[int] = None,
    timeout_multiplier: float = 1.0,
    model: str = "gpt-4.1",
) -> StageContext:
    """
    Prepare a StageContext from a UserStory for pipeline execution.

    Args:
        story: The user story to prepare context for
        workspace: Path to the isolated workspace for this execution
        time_budget_seconds: Override story time budget (None = use story's)
        max_iterations: Override story max iterations (None = use story's)
        timeout_multiplier: Multiply the time budget by this factor
        model: LLM model to use

    Returns:
        StageContext ready for pipeline stages 2-5
    """
    budget = time_budget_seconds if time_budget_seconds is not None else story.time_budget_seconds
    budget = int(budget * timeout_multiplier)

    iterations = max_iterations if max_iterations is not None else story.max_iterations

    return StageContext(
        story=story,
        workspace=workspace,
        time_budget_seconds=budget,
        max_iterations=iterations,
        model=model,
    )
