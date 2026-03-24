"""Pipeline stage result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .trace import AgentTrace


@dataclass
class UMLDiagram:
    """A UML diagram produced during requirements analysis."""

    diagram_type: str  # e.g., "class", "sequence", "activity", "use_case"
    title: str
    content: str  # Raw diagram source (Mermaid syntax)
    format: str = "mermaid"


@dataclass
class StageResult:
    """
    Base result for all pipeline stage executions.

    Every stage (requirements, codegen, testing, deploy) returns
    a subclass of this with additional stage-specific fields.
    """

    # Identification
    platform_id: str
    stage_name: str

    # Outcome
    success: bool = False
    completed: bool = False
    error_message: str | None = None

    # Execution trace
    trace: AgentTrace = field(default_factory=AgentTrace)

    # Timing & resource usage
    wall_clock_seconds: float = 0.0
    iterations: int = 0
    tool_calls_count: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    human_interventions: int = 0

    # Timestamps
    start_time: datetime | None = None
    end_time: datetime | None = None

    # Raw platform output
    raw_output: Any = None

    # LangSmith run ID (LangGraph only; None for all other adapters)
    langsmith_run_id: str | None = None


@dataclass
class RequirementsResult(StageResult):
    """Result of the requirements-analysis stage."""

    functional_requirements: list[dict[str, Any]] = field(default_factory=list)
    non_functional_requirements: list[dict[str, Any]] = field(default_factory=list)
    use_cases: list[dict[str, Any]] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    api_endpoints: list[dict[str, Any]] = field(default_factory=list)
    uml_diagrams: list[UMLDiagram] = field(default_factory=list)


@dataclass
class CodeResult(StageResult):
    """Result of the code-generation stage."""

    output_files: list[str] = field(default_factory=list)
    git_diff: str | None = None


@dataclass
class TestResult(StageResult):
    """Result of the testing stage."""

    test_files: list[str] = field(default_factory=list)
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    coverage_percentage: float = 0.0

    @property
    def test_pass_rate(self) -> float:
        """Percentage of tests that passed."""
        if self.tests_run == 0:
            return 0.0
        return (self.tests_passed / self.tests_run) * 100


@dataclass
class DeployResult(StageResult):
    """Result of the deployment stage."""

    build_success: bool = False
    deployment_ready: bool = False
    build_log: str = ""
    dependency_issues: list[str] = field(default_factory=list)


