"""
User Story Definitions for Evaluation

Defines the structure of user stories and their results.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from datetime import datetime


class DifficultyLevel(Enum):
    """Story difficulty levels for graduated evaluation."""
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class StoryStatus(Enum):
    """Execution status of a story."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class AcceptanceCriterion:
    """A single acceptance criterion for a story."""
    id: str
    description: str
    gherkin: Optional[str] = None  # Given/When/Then format
    verification_method: str = "manual"  # manual, automated, test
    passed: Optional[bool] = None
    notes: Optional[str] = None


@dataclass
class UserStory:
    """
    A user story for evaluation.

    Each story represents a task that the agentic platform must complete.
    """
    # Identification
    id: str
    title: str
    description: str

    # Classification
    difficulty: DifficultyLevel
    category: str  # e.g., "code_generation", "debugging", "refactoring"

    # Prompt and context
    prompt: str  # The main instruction given to the agent
    tags: list[str] = field(default_factory=list)
    context: str = ""  # Additional context (file contents, requirements)
    system_prompt: Optional[str] = None  # Optional system prompt override

    # Acceptance criteria
    acceptance_criteria: list[AcceptanceCriterion] = field(default_factory=list)

    # Constraints
    time_budget_seconds: int = 600
    max_iterations: int = 50
    target_files: list[str] = field(default_factory=list)

    # Prerequisites
    requires_setup: bool = False
    setup_script: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)  # Other story IDs

    # Expected outcomes
    expected_files_created: list[str] = field(default_factory=list)
    expected_files_modified: list[str] = field(default_factory=list)
    expected_test_pass: bool = True

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    version: str = "1.0"
    author: str = ""
    notes: str = ""

    def to_evaluation_context(self, repo_path) -> dict:
        """Convert to EvaluationContext parameters."""
        return {
            "story_id": self.id,
            "story_prompt": self.prompt,
            "story_context": self.context,
            "repo_path": repo_path,
            "target_files": self.target_files,
            "time_budget_seconds": self.time_budget_seconds,
            "max_iterations": self.max_iterations,
        }


@dataclass
class StoryScore:
    """
    Scoring for a single dimension of story execution.
    """
    dimension: str
    score: float  # 0-3 scale
    max_score: float = 3.0
    notes: str = ""
    evidence: list[str] = field(default_factory=list)

    @property
    def percentage(self) -> float:
        return (self.score / self.max_score) * 100 if self.max_score > 0 else 0


@dataclass
class StoryResult:
    """
    Complete result of executing a story on a platform.
    """
    # Identification
    story_id: str
    platform_id: str
    execution_id: str

    # Status
    status: StoryStatus = StoryStatus.PENDING
    error_message: Optional[str] = None

    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    wall_clock_seconds: float = 0.0

    # Execution metrics
    iterations: int = 0
    tool_calls: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    human_interventions: int = 0

    # Acceptance criteria
    criteria_results: dict[str, bool] = field(default_factory=dict)

    # Scoring (0-3 scale for each dimension)
    scores: list[StoryScore] = field(default_factory=list)

    # Test results
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    coverage_delta: float = 0.0

    # Artifacts
    output_files: list[str] = field(default_factory=list)
    git_diff: Optional[str] = None
    trace_file: Optional[str] = None
    log_file: Optional[str] = None

    # Raw data
    raw_result: Any = None

    @property
    def success(self) -> bool:
        """Whether the story was successfully completed."""
        return self.status == StoryStatus.COMPLETED

    @property
    def criteria_pass_rate(self) -> float:
        """Percentage of acceptance criteria passed."""
        if not self.criteria_results:
            return 0.0
        passed = sum(1 for v in self.criteria_results.values() if v)
        return (passed / len(self.criteria_results)) * 100

    @property
    def overall_score(self) -> float:
        """Average of all dimension scores."""
        if not self.scores:
            return 0.0
        return sum(s.score for s in self.scores) / len(self.scores)

    @property
    def tokens_total(self) -> int:
        return self.tokens_input + self.tokens_output

    def add_score(
        self,
        dimension: str,
        score: float,
        notes: str = "",
        evidence: list[str] | None = None,
    ):
        """Add a dimension score."""
        self.scores.append(StoryScore(
            dimension=dimension,
            score=score,
            notes=notes,
            evidence=evidence or [],
        ))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "story_id": self.story_id,
            "platform_id": self.platform_id,
            "execution_id": self.execution_id,
            "status": self.status.value,
            "success": self.success,
            "error_message": self.error_message,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "wall_clock_seconds": self.wall_clock_seconds,
            "iterations": self.iterations,
            "tool_calls": self.tool_calls,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "tokens_total": self.tokens_total,
            "human_interventions": self.human_interventions,
            "criteria_results": self.criteria_results,
            "criteria_pass_rate": self.criteria_pass_rate,
            "scores": [
                {
                    "dimension": s.dimension,
                    "score": s.score,
                    "percentage": s.percentage,
                    "notes": s.notes,
                }
                for s in self.scores
            ],
            "overall_score": self.overall_score,
            "tests_run": self.tests_run,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "coverage_delta": self.coverage_delta,
            "output_files": self.output_files,
        }


# Scoring dimensions
SCORING_DIMENSIONS = [
    "correctness",
    "completeness",
    "code_quality",
    "test_quality",
    "time_efficiency",
    "autonomy",
]

# Scoring rubric
SCORING_RUBRIC = {
    "correctness": {
        0: "Does not compile/run",
        1: "Runs but wrong behavior",
        2: "Mostly correct, minor issues",
        3: "Fully correct",
    },
    "completeness": {
        0: "No meaningful output",
        1: "Partial implementation",
        2: "Most requirements met",
        3: "All requirements met",
    },
    "code_quality": {
        0: "Unreadable/unmaintainable",
        1: "Poor style, no structure",
        2: "Acceptable quality",
        3: "Clean, idiomatic code",
    },
    "test_quality": {
        0: "No tests",
        1: "Tests exist but trivial",
        2: "Tests cover main paths",
        3: "Comprehensive tests",
    },
    "time_efficiency": {
        0: "Exceeded budget by 2x+",
        1: "Exceeded budget",
        2: "Met budget",
        3: "Under budget",
    },
    "autonomy": {
        0: "Required constant intervention",
        1: "Frequent intervention",
        2: "Occasional intervention",
        3: "Fully autonomous",
    },
}
