"""Stage context model."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
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

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict for container IPC.

        Excludes ``progress_callback`` (not serializable).
        Converts ``workspace`` to string, ``story`` and ``artifacts``
        to dicts via ``dataclasses.asdict`` with datetime handling.
        """
        import dataclasses

        def _convert(obj: Any) -> Any:
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, Path):
                return str(obj)
            if isinstance(obj, Enum):
                return obj.value
            return obj

        def _asdict(obj: Any) -> Any:
            if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
                return {
                    k: _asdict(v)
                    for k, v in dataclasses.asdict(obj).items()
                }
            if isinstance(obj, list):
                return [_asdict(i) for i in obj]
            if isinstance(obj, dict):
                return {k: _asdict(v) for k, v in obj.items()}
            return _convert(obj)

        return {
            "story": _asdict(self.story),
            "workspace": str(self.workspace),
            "platform_id": self.platform_id,
            "time_budget_seconds": self.time_budget_seconds,
            "max_iterations": self.max_iterations,
            "max_tool_calls": self.max_tool_calls,
            "allowed_tools": list(self.allowed_tools),
            "model": self.model,
            "temperature": self.temperature,
            "artifacts": {k: _asdict(v) for k, v in self.artifacts.items()},
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StageContext:
        """Deserialize from a dict produced by ``to_dict()``.

        Reconstructs ``UserStory`` from dict, sets ``workspace`` as Path,
        and leaves ``artifacts`` as plain dicts (sufficient for prompt
        building inside the container).
        """
        from .story import UserStory, DifficultyLevel, AcceptanceCriterion

        story_data = data["story"]
        story_data["difficulty"] = DifficultyLevel(story_data["difficulty"])
        if "acceptance_criteria" in story_data:
            story_data["acceptance_criteria"] = [
                AcceptanceCriterion(**ac) for ac in story_data["acceptance_criteria"]
            ]
        if isinstance(story_data.get("created_at"), str):
            story_data["created_at"] = datetime.fromisoformat(story_data["created_at"])
        story = UserStory(**story_data)

        return cls(
            story=story,
            workspace=Path(data["workspace"]),
            platform_id=data.get("platform_id", ""),
            time_budget_seconds=data.get("time_budget_seconds", 600),
            max_iterations=data.get("max_iterations", 50),
            max_tool_calls=data.get("max_tool_calls", 100),
            allowed_tools=data.get("allowed_tools", []),
            model=data.get("model", ""),
            temperature=data.get("temperature", 0.0),
            artifacts=data.get("artifacts", {}),
            metadata=data.get("metadata", {}),
        )
