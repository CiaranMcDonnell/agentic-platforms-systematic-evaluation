"""
Stage 1: Story Loading and Context Preparation

Loads user stories from YAML and prepares StageContext for downstream stages.
This is a harness-only stage — no adapter call.
"""
from pathlib import Path

from desmet.harness.context import StageContext
from desmet.harness.story import UserStory
from desmet.llm_config import get_config as _get_llm_config


def prepare_stage_context(
    story: UserStory,
    workspace: Path,
    time_budget_seconds: int | None = None,
    max_iterations: int | None = None,
    timeout_multiplier: float = 1.0,
    model: str | None = None,
    platform_id: str = "",
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

    resolved_model = model or _get_llm_config().model

    return StageContext(
        story=story,
        workspace=workspace,
        platform_id=platform_id,
        time_budget_seconds=budget,
        max_iterations=iterations,
        model=resolved_model,
    )
