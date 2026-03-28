"""Stage context model."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from desmet.llm_config import DEFAULT_MODEL, DEFAULT_TEMPERATURE

from .results import StageResult

if TYPE_CHECKING:
    from .story import UserStory


@dataclass
class StageContext:
    """
    Context provided to each pipeline stage.

    Replaces EvaluationContext for the new multi-stage pipeline.
    Carries the user story, workspace, constraints, and accumulated
    artifacts from prior stages.
    """

    # Story information
    story: UserStory
    workspace: Path

    # Platform identification (for deploy path derivation)
    platform_id: str = ""

    # Constraints
    time_budget_seconds: int = 600
    max_iterations: int = 50
    max_tool_calls: int = 100

    # Available tools
    allowed_tools: list[str] = field(
        default_factory=lambda: [
            "read_file",
            "write_file",
            "list_directory",
            "execute_shell",
            "search_code",
            "check_completion",
        ]
    )

    # Model configuration
    model: str = DEFAULT_MODEL
    temperature: float = DEFAULT_TEMPERATURE

    # Accumulated stage results
    artifacts: dict[str, StageResult] = field(default_factory=dict)

    # Progress reporting (sync callable, safe from any thread)
    progress_callback: Callable[[str], None] | None = None

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_artifacts(self, stage_name: str, result: StageResult) -> None:
        """Store the result of a completed stage."""
        self.artifacts[stage_name] = result

    def get_prior_result(self, stage_name: str) -> StageResult | None:
        """Retrieve the result of a previously completed stage."""
        return self.artifacts.get(stage_name)
