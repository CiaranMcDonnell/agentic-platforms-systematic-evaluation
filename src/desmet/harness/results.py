"""Pipeline stage result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar

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

    # Automated framework metrics (computed from trace data)
    framework_metrics: dict[str, float | None] = field(default_factory=dict)

    # Container resource usage (from ResourceMonitor)
    resource_metrics: dict[str, float | int | None] = field(default_factory=dict)

    # Timestamps
    start_time: datetime | None = None
    end_time: datetime | None = None

    # Raw platform output
    raw_output: Any = None

    # LangSmith run ID (LangGraph only; None for all other adapters)
    langsmith_run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict for container IPC.

        Includes a ``_type`` field so ``from_dict`` can reconstruct
        the correct subclass.
        """
        d: dict[str, Any] = {
            "_type": type(self).__name__,
            "platform_id": self.platform_id,
            "stage_name": self.stage_name,
            "success": self.success,
            "completed": self.completed,
            "error_message": self.error_message,
            "trace": self.trace.to_dict(),
            "wall_clock_seconds": self.wall_clock_seconds,
            "iterations": self.iterations,
            "tool_calls_count": self.tool_calls_count,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "cost_usd": self.cost_usd,
            "human_interventions": self.human_interventions,
            "framework_metrics": self.framework_metrics,
            "resource_metrics": self.resource_metrics,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "langsmith_run_id": self.langsmith_run_id,
        }
        # Append subclass-specific fields (serialize nested dataclasses to dicts)
        import dataclasses

        base_fields = {f.name for f in dataclasses.fields(StageResult)}
        for f in dataclasses.fields(self):
            if f.name not in base_fields and f.name != "raw_output":
                val = getattr(self, f.name)
                if isinstance(val, list) and val and dataclasses.is_dataclass(val[0]):
                    val = [dataclasses.asdict(item) for item in val]
                elif dataclasses.is_dataclass(val):
                    val = dataclasses.asdict(val)
                d[f.name] = val
        return d

    _SUBCLASS_MAP: ClassVar[dict[str, type]] = {}

    @classmethod
    def _register_subclasses(cls) -> None:
        if cls._SUBCLASS_MAP:
            return
        for sub in [RequirementsResult, CodeResult, TestResult, DeployResult]:
            cls._SUBCLASS_MAP[sub.__name__] = sub

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StageResult:
        """Deserialize from a dict produced by ``to_dict()``.

        Reconstructs the correct subclass based on ``_type``.
        """
        from datetime import datetime as _dt

        cls._register_subclasses()

        data = dict(data)  # shallow copy to avoid mutating caller's dict
        type_name = data.pop("_type", "StageResult")
        target_cls = cls._SUBCLASS_MAP.get(type_name, StageResult)

        trace = AgentTrace.from_dict(data.pop("trace", {}))
        start_time_raw = data.pop("start_time", None)
        start_time = _dt.fromisoformat(start_time_raw) if start_time_raw else None
        end_time_raw = data.pop("end_time", None)
        end_time = _dt.fromisoformat(end_time_raw) if end_time_raw else None
        resource_metrics = data.pop("resource_metrics", {})

        # Remove fields not in the target dataclass
        import dataclasses

        valid_fields = {f.name for f in dataclasses.fields(target_cls)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}

        return target_cls(
            trace=trace,
            start_time=start_time,
            end_time=end_time,
            resource_metrics=resource_metrics,
            **filtered,
        )


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
