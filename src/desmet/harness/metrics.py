"""
Metrics Collection for DESMET Evaluation

Collects, aggregates, and exports evaluation metrics across all dimensions.
"""

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from desmet.harness.story import StoryResult, StoryStatus


class EvaluationDimension(Enum):
    """DESMET Layer 3 cross-cutting evaluation dimensions.

    Four primary dimensions measure **framework capability** for building
    SE pipelines, not LLM output quality.  Each is normalised to a 1-5
    Likert scale and aggregated from the per-story 0-3 rubric scores.
    """

    PIPELINE_COMPLETENESS = "pipeline_completeness"
    EFFICIENCY = "efficiency"
    ORCHESTRATION = "orchestration"
    AUTONOMY = "autonomy"


@dataclass
class DimensionScore:
    """Score for a single evaluation dimension."""

    dimension: EvaluationDimension
    score: float  # 1-5 Likert scale
    confidence: float = 1.0  # 0-1, how confident we are in this score
    metrics: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    evidence: list[str] = field(default_factory=list)


@dataclass
class SetupMetrics:
    """Metrics from Stage 0: Framework Setup & Onboarding."""

    platform_id: str

    # Timing
    time_to_environment_ready_minutes: float = 0.0
    time_to_first_agent_minutes: float = 0.0
    time_to_meaningful_agent_minutes: float = 0.0

    # Complexity
    manual_steps_count: int = 0
    dependencies_count: int = 0
    required_services_count: int = 0
    config_files_count: int = 0

    # Quality
    documentation_clarity_score: int = 3  # 1-5
    errors_during_setup: int = 0
    error_resolution_time_minutes: float = 0.0

    # Notes
    hidden_assumptions: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class StageMetrics:
    """Metrics for a single stage execution.

    All score fields measure **framework capability**, not LLM output quality.

    Wired into the runner: each stage result is automatically converted to a
    StageMetrics entry and recorded via ``MetricsCollector.record_stage_metrics``
    (see ``runner.py`` stage execution loop).
    """

    story_id: str
    platform_id: str
    stage_name: str  # "requirements", "codegen", "testing", "deploy"

    success: bool = False
    wall_clock_seconds: float = 0.0
    iterations: int = 0
    tool_calls: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    human_interventions: int = 0

    # Framework-centric scores (0-3)
    pipeline_completeness_score: float = 0.0
    tool_integration_score: float = 0.0
    error_recovery_score: float = 0.0


@dataclass
class StoryMetrics:
    """Facade over StoryResult that adds metrics-only fields.

    Delegates all StoryResult fields as properties to avoid duplication.
    Use ``StoryMetrics.from_story_result`` to construct an instance.
    """

    _result: StoryResult

    # Metrics-only fields (not present on StoryResult)
    time_budget_seconds: float = 0.0

    # Framework-centric rubric scores (0-3); extracted from result.scores
    pipeline_completeness_score: float = 0.0
    tool_integration_score: float = 0.0
    error_recovery_score: float = 0.0
    trace_quality_score: float = 0.0
    time_efficiency_score: float = 0.0
    autonomy_score: float = 0.0

    # Automated framework metrics (from StoryResult.framework_metrics)
    framework_metrics: dict[str, float | None] = field(default_factory=dict)

    @classmethod
    def from_story_result(
        cls,
        result: StoryResult,
        time_budget_seconds: float = 0.0,
    ) -> "StoryMetrics":
        """Create a StoryMetrics facade from a StoryResult."""
        instance = cls(
            _result=result,
            time_budget_seconds=time_budget_seconds,
        )
        # Extract rubric scores from result.scores by dimension name
        score_map = {s.dimension: s.score for s in result.scores}
        for attr, dimension in (
            ("pipeline_completeness_score", "pipeline_completeness"),
            ("tool_integration_score", "tool_integration"),
            ("error_recovery_score", "error_recovery"),
            ("trace_quality_score", "trace_quality"),
            ("time_efficiency_score", "time_efficiency"),
            ("autonomy_score", "autonomy"),
        ):
            if dimension in score_map:
                setattr(instance, attr, score_map[dimension])
        instance.framework_metrics = getattr(result, "framework_metrics", {}) or {}
        return instance

    # ------------------------------------------------------------------
    # Delegating properties — read directly from the wrapped StoryResult
    # ------------------------------------------------------------------

    @property
    def story_id(self) -> str:
        return self._result.story_id

    @property
    def platform_id(self) -> str:
        return self._result.platform_id

    @property
    def execution_id(self) -> str:
        return self._result.execution_id

    @property
    def success(self) -> bool:
        return self._result.success

    @property
    def completed(self) -> bool:
        return self._result.status == StoryStatus.COMPLETED

    @property
    def wall_clock_seconds(self) -> float:
        return self._result.wall_clock_seconds

    @property
    def iterations(self) -> int:
        return self._result.iterations

    @property
    def tool_calls(self) -> int:
        return self._result.tool_calls

    @property
    def tokens_input(self) -> int:
        return self._result.tokens_input

    @property
    def tokens_output(self) -> int:
        return self._result.tokens_output

    @property
    def api_cost_usd(self) -> float:
        return self._result.api_cost_usd

    @property
    def human_interventions(self) -> int:
        return self._result.human_interventions

    @property
    def tests_run(self) -> int:
        return self._result.tests_run

    @property
    def tests_passed(self) -> int:
        return self._result.tests_passed

    @property
    def coverage_delta(self) -> float:
        return self._result.coverage_delta

    @property
    def criteria_total(self) -> int:
        return len(self._result.criteria_results)

    @property
    def criteria_passed(self) -> int:
        return sum(1 for v in self._result.criteria_results.values() if v)

    @property
    def langfuse_trace_id(self) -> str | None:
        return self._result.langfuse_trace_id


@dataclass
class VarianceMetrics:
    """Statistical variance across repeated runs of the same story."""

    repeats: int
    wall_clock_mean: float
    wall_clock_std: float
    tokens_mean: float
    tokens_std: float
    cost_mean: float
    cost_std: float
    success_rate: float
    tool_calls_mean: float
    tool_calls_std: float
    iterations_mean: float
    iterations_std: float

    def to_dict(self) -> dict[str, float]:
        return {
            "repeats": self.repeats,
            "wall_clock_mean": round(self.wall_clock_mean, 2),
            "wall_clock_std": round(self.wall_clock_std, 2),
            "tokens_mean": round(self.tokens_mean, 1),
            "tokens_std": round(self.tokens_std, 1),
            "cost_mean": round(self.cost_mean, 4),
            "cost_std": round(self.cost_std, 4),
            "success_rate": round(self.success_rate, 4),
            "tool_calls_mean": round(self.tool_calls_mean, 1),
            "tool_calls_std": round(self.tool_calls_std, 1),
            "iterations_mean": round(self.iterations_mean, 1),
            "iterations_std": round(self.iterations_std, 1),
        }


def compute_variance_metrics(results: list) -> VarianceMetrics:
    """Compute variance statistics from repeated StoryResult runs."""
    n = len(results)
    if n == 0:
        return VarianceMetrics(
            repeats=0,
            wall_clock_mean=0,
            wall_clock_std=0,
            tokens_mean=0,
            tokens_std=0,
            cost_mean=0,
            cost_std=0,
            success_rate=0,
            tool_calls_mean=0,
            tool_calls_std=0,
            iterations_mean=0,
            iterations_std=0,
        )

    from desmet.harness.story import StoryStatus

    wc = [r.wall_clock_seconds for r in results]
    tk = [float(r.tokens_input + r.tokens_output) for r in results]
    co = [r.api_cost_usd for r in results]
    tc = [float(r.tool_calls) for r in results]
    it = [float(r.iterations) for r in results]
    completed = sum(1 for r in results if r.status == StoryStatus.COMPLETED)

    return VarianceMetrics(
        repeats=n,
        wall_clock_mean=mean(wc),
        wall_clock_std=pstdev(wc),
        tokens_mean=mean(tk),
        tokens_std=pstdev(tk),
        cost_mean=mean(co),
        cost_std=pstdev(co),
        success_rate=completed / n,
        tool_calls_mean=mean(tc),
        tool_calls_std=pstdev(tc),
        iterations_mean=mean(it),
        iterations_std=pstdev(it),
    )


@dataclass
class EvaluationMetrics:
    """
    Complete metrics for a platform evaluation.
    """

    platform_id: str
    platform_name: str
    evaluation_date: datetime = field(default_factory=datetime.now)
    evaluator: str = ""

    # Setup metrics
    setup_metrics: SetupMetrics | None = None

    # Story metrics
    story_metrics: list[StoryMetrics] = field(default_factory=list)

    # Stage metrics
    stage_metrics: list[StageMetrics] = field(default_factory=list)

    # Variance metrics (populated when repeats > 1)
    variance_metrics: dict[str, VarianceMetrics] = field(default_factory=dict)

    # Dimension scores
    dimension_scores: list[DimensionScore] = field(default_factory=list)

    # Aggregate metrics
    stories_total: int = 0
    stories_completed: int = 0
    stories_failed: int = 0

    # Overall score
    overall_score: float = 0.0

    def add_story_metrics(self, metrics: StoryMetrics):
        """Add metrics from a story execution."""
        self.story_metrics.append(metrics)
        self.stories_total += 1
        if metrics.success:
            self.stories_completed += 1
        else:
            self.stories_failed += 1

    def calculate_dimension_scores(self):
        """Calculate Layer 3 benchmarking dimension scores from collected metrics.

        All primary dimensions measure **framework capability** for building
        SE pipelines, not LLM output quality.  The four primary dimensions
        are: Pipeline Completeness, Efficiency, Orchestration, and Autonomy.
        All scores are on a 1-5 Likert scale.

        Note: REPRODUCIBILITY, OBSERVABILITY, and FAILURE_HANDLING are Layer 2
        assessments (qualitative platform capability reviews) and are NOT
        computed here from benchmarking data.  They are populated separately
        by manual evaluation and stored as DimensionScore entries with
        confidence < 1.0 to distinguish them from benchmarked scores.
        """
        if not self.story_metrics:
            return

        self.dimension_scores = []

        n = len(self.story_metrics)

        # ------------------------------------------------------------------
        # Pipeline Completeness
        # Measures: can the framework run all SDLC stages end-to-end?
        # Formula: completion_ratio * 0.5
        #          + avg(pipeline_completeness_score) / 3 * 0.5
        # Scaled to 1-5.
        # ------------------------------------------------------------------
        completion_ratio = (
            self.stories_completed / self.stories_total if self.stories_total > 0 else 0.0
        )
        avg_pipeline_score = sum(m.pipeline_completeness_score for m in self.story_metrics) / n
        pipeline_raw = completion_ratio * 0.5 + (avg_pipeline_score / 3.0) * 0.5
        pipeline_completeness_score = 1.0 + pipeline_raw * 4.0

        self.dimension_scores.append(
            DimensionScore(
                dimension=EvaluationDimension.PIPELINE_COMPLETENESS,
                score=min(5.0, max(1.0, pipeline_completeness_score)),
                metrics={
                    "completion_ratio": completion_ratio,
                    "avg_pipeline_completeness_rubric": avg_pipeline_score,
                },
            )
        )

        # ------------------------------------------------------------------
        # Efficiency
        # Measures: framework orchestration overhead (time + tokens + cost).
        #   time_component  = max(1, 5 - (avg_time_ratio - 1) * 2)
        #   token_component = max(1, 5 - (avg_tokens / token_budget - 1) * 2)
        #   cost_component  = max(1, 5 - (avg_cost / cost_budget - 1) * 2)
        # When cost data is unavailable (all zeros), cost_component is omitted
        # and efficiency is the average of time + token components only.
        # ------------------------------------------------------------------
        token_budget = 100_000
        cost_budget = 0.50  # USD per story

        timed_metrics = [m for m in self.story_metrics if m.time_budget_seconds > 0]
        if timed_metrics:
            avg_time_ratio = sum(
                m.wall_clock_seconds / m.time_budget_seconds for m in timed_metrics
            ) / len(timed_metrics)
        else:
            avg_time_ratio = 1.0  # neutral assumption when no budget is set

        avg_tokens_per_story = sum(m.tokens_input + m.tokens_output for m in self.story_metrics) / n

        total_cost = sum(m.api_cost_usd for m in self.story_metrics)
        avg_cost_per_story = total_cost / n if total_cost > 0 else 0.0

        time_component = max(1.0, 5.0 - (avg_time_ratio - 1.0) * 2.0)
        token_component = max(1.0, 5.0 - (avg_tokens_per_story / token_budget - 1.0) * 2.0)

        # Resource component (from container monitoring)
        memory_budget_mb = 512.0
        resource_values = [
            m._result.resource_metrics.get("peak_memory_bytes")
            for m in self.story_metrics
            if m._result.resource_metrics
        ]
        resource_values = [v for v in resource_values if v is not None and v > 0]
        if resource_values:
            avg_peak_mb = (sum(resource_values) / len(resource_values)) / (1024 * 1024)
            resource_component = max(1.0, 5.0 - (avg_peak_mb / memory_budget_mb - 1.0) * 2.0)
        else:
            resource_component = None

        components = [time_component, token_component]
        if avg_cost_per_story > 0:
            cost_component = max(1.0, 5.0 - (avg_cost_per_story / cost_budget - 1.0) * 2.0)
            components.append(cost_component)
        else:
            cost_component = None

        if resource_component is not None:
            components.append(resource_component)

        efficiency_score = sum(components) / len(components)

        self.dimension_scores.append(
            DimensionScore(
                dimension=EvaluationDimension.EFFICIENCY,
                score=min(5.0, max(1.0, efficiency_score)),
                metrics={
                    "avg_time_ratio": avg_time_ratio,
                    "avg_tokens_per_story": avg_tokens_per_story,
                    "token_budget": token_budget,
                    "avg_cost_per_story": avg_cost_per_story,
                    "cost_budget": cost_budget,
                    "time_component": time_component,
                    "token_component": token_component,
                    "cost_component": cost_component,
                    "resource_component": resource_component,
                    "memory_budget_mb": memory_budget_mb,
                },
            )
        )

        # ------------------------------------------------------------------
        # Orchestration
        # Measures: how well the framework handles tool integration, error
        # recovery, and trace production — pure framework concerns.
        # Formula: avg(tool_integration, error_recovery, trace_quality) * 5/3
        # ------------------------------------------------------------------
        all_orchestration_scores: list[float] = []
        for m in self.story_metrics:
            all_orchestration_scores.extend(
                [
                    m.tool_integration_score,
                    m.error_recovery_score,
                    m.trace_quality_score,
                ]
            )

        avg_orchestration = (
            sum(all_orchestration_scores) / len(all_orchestration_scores)
            if all_orchestration_scores
            else 0.0
        )
        orchestration_score = avg_orchestration * (5.0 / 3.0)

        self.dimension_scores.append(
            DimensionScore(
                dimension=EvaluationDimension.ORCHESTRATION,
                score=min(5.0, max(1.0, orchestration_score)),
                metrics={
                    "avg_orchestration_rubric": avg_orchestration,
                    "rubric_fields_used": [
                        "tool_integration",
                        "error_recovery",
                        "trace_quality",
                    ],
                    "rubric_samples": len(all_orchestration_scores),
                },
            )
        )

        # ------------------------------------------------------------------
        # Autonomy
        # Primary source: rubric_autonomy (manual 0-3) — the evaluator's
        # judgement after reviewing the trace.
        # Optional augment: avg_interventions_per_stage (automatic) — only
        # blended in when adapters actually logged interventions > 0.
        # Formula: rubric alone, scaled 0-3 → 1-5; or 50/50 blend with the
        # intervention counter when it has signal.
        # ------------------------------------------------------------------
        avg_autonomy_rubric = sum(m.autonomy_score for m in self.story_metrics) / n
        rubric_normalized = avg_autonomy_rubric / 3.0  # 0-1

        if self.stage_metrics:
            avg_interventions_per_stage = sum(
                sm.human_interventions for sm in self.stage_metrics
            ) / len(self.stage_metrics)
            intervention_source = "stage_metrics"
        else:
            avg_story_interventions = sum(m.human_interventions for m in self.story_metrics) / n
            avg_interventions_per_stage = avg_story_interventions / 4.0
            intervention_source = "story_metrics_fallback"

        if avg_interventions_per_stage > 0:
            auto_normalized = (4.0 - min(4.0, avg_interventions_per_stage)) / 4.0
            autonomy_raw = rubric_normalized * 0.5 + auto_normalized * 0.5
            blended = True
        else:
            autonomy_raw = rubric_normalized
            blended = False

        autonomy_score = 1.0 + autonomy_raw * 4.0

        self.dimension_scores.append(
            DimensionScore(
                dimension=EvaluationDimension.AUTONOMY,
                score=min(5.0, max(1.0, autonomy_score)),
                metrics={
                    "avg_autonomy_rubric": avg_autonomy_rubric,
                    "avg_interventions_per_stage": avg_interventions_per_stage,
                    "intervention_source": intervention_source,
                    "blended_with_interventions": blended,
                },
            )
        )

        # Overall score: average of the four Layer 3 dimensions
        if self.dimension_scores:
            self.overall_score = sum(d.score for d in self.dimension_scores) / len(
                self.dimension_scores
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "platform_id": self.platform_id,
            "platform_name": self.platform_name,
            "evaluation_date": self.evaluation_date.isoformat(),
            "evaluator": self.evaluator,
            "setup_metrics": {
                "time_to_first_agent_minutes": self.setup_metrics.time_to_first_agent_minutes,
                "manual_steps_count": self.setup_metrics.manual_steps_count,
                "documentation_clarity_score": self.setup_metrics.documentation_clarity_score,
            }
            if self.setup_metrics
            else None,
            "stories_total": self.stories_total,
            "stories_completed": self.stories_completed,
            "stories_failed": self.stories_failed,
            "dimension_scores": [
                {
                    "dimension": d.dimension.value,
                    "score": d.score,
                    "metrics": d.metrics,
                }
                for d in self.dimension_scores
            ],
            "overall_score": self.overall_score,
            "story_metrics": [
                {
                    "story_id": m.story_id,
                    "success": m.success,
                    "wall_clock_seconds": m.wall_clock_seconds,
                    "iterations": m.iterations,
                    "tool_calls": m.tool_calls,
                    "tokens_input": m.tokens_input,
                    "tokens_output": m.tokens_output,
                    "api_cost_usd": m.api_cost_usd,
                    "pipeline_completeness_score": m.pipeline_completeness_score,
                    "tool_integration_score": m.tool_integration_score,
                    "error_recovery_score": m.error_recovery_score,
                    "trace_quality_score": m.trace_quality_score,
                    "time_efficiency_score": m.time_efficiency_score,
                    "autonomy_score": m.autonomy_score,
                    "framework_metrics": m.framework_metrics,
                    "resource_metrics": m._result.resource_metrics,
                }
                for m in self.story_metrics
            ],
            "variance_metrics": {sid: vm.to_dict() for sid, vm in self.variance_metrics.items()}
            if self.variance_metrics
            else {},
        }


def recompute_platform_likert_from_store(
    store: Any,
    run_id: str,
    platform_id: str,
    story_budgets: dict[str, float],
) -> dict[str, float]:
    """Rebuild Likert dimension scores for one platform from persisted data.

    Reads executions from DuckDB, synthesises ``StoryResult`` +
    ``StoryMetrics`` objects, calls ``calculate_dimension_scores`` and
    persists the resulting 1-5 scores via ``store.update_platform_scores``.

    Needed because ``submit_score`` writes only rubric columns;
    ``score_*`` / ``overall_score`` stay stale until this runs.

    *story_budgets* maps ``story_id`` to ``time_budget_seconds``.
    Stories not in the map use 600s (the harness default).
    """
    import pandas as _pd

    from desmet.harness.story import StoryResult, StoryStatus

    exec_df = store.get_executions(run_id)
    group = exec_df[exec_df["platform_id"] == platform_id]
    if group.empty:
        return {}

    em = EvaluationMetrics(platform_id=platform_id, platform_name=platform_id)

    for _, row in group.iterrows():
        story_id = str(row["story_id"])
        try:
            status = StoryStatus(row["status"])
        except (KeyError, ValueError):
            status = StoryStatus.PENDING

        result = StoryResult(
            story_id=story_id,
            platform_id=platform_id,
            execution_id=str(row["execution_id"]),
            status=status,
            wall_clock_seconds=float(row["wall_clock_seconds"] or 0),
            iterations=int(row["iterations"] or 0),
            tool_calls=int(row["tool_calls"] or 0),
            tokens_input=int(row["tokens_input"] or 0),
            tokens_output=int(row["tokens_output"] or 0),
            api_cost_usd=float(row["cost_usd"] or 0),
            human_interventions=int(row["human_interventions"] or 0),
        )

        for dim in (
            "pipeline_completeness",
            "tool_integration",
            "error_recovery",
            "trace_quality",
            "time_efficiency",
            "autonomy",
        ):
            val = row.get(f"rubric_{dim}")
            if val is not None and not _pd.isna(val):
                result.add_score(dim, float(val))

        resource: dict[str, Any] = {}
        if _pd.notna(row.get("resource_peak_memory_bytes")):
            resource["peak_memory_bytes"] = int(row["resource_peak_memory_bytes"])
        if _pd.notna(row.get("resource_avg_cpu_percent")):
            resource["avg_cpu_percent"] = float(row["resource_avg_cpu_percent"])
        if _pd.notna(row.get("resource_net_tx_bytes")):
            resource["net_tx_total_bytes"] = int(row["resource_net_tx_bytes"])
        result.resource_metrics = resource

        budget = float(story_budgets.get(story_id, 600))
        em.add_story_metrics(
            StoryMetrics.from_story_result(result, time_budget_seconds=budget)
        )

    em.calculate_dimension_scores()

    scores: dict[str, float] = {"overall_score": em.overall_score}
    for ds in em.dimension_scores:
        scores[f"score_{ds.dimension.value}"] = ds.score
    store.update_platform_scores(run_id, platform_id, scores)
    return scores


class MetricsCollector:
    """
    Collects and manages metrics across the evaluation.
    """

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.platform_metrics: dict[str, EvaluationMetrics] = {}

    def get_or_create_platform_metrics(
        self,
        platform_id: str,
        platform_name: str,
    ) -> EvaluationMetrics:
        """Get or create metrics for a platform."""
        if platform_id not in self.platform_metrics:
            self.platform_metrics[platform_id] = EvaluationMetrics(
                platform_id=platform_id,
                platform_name=platform_name,
            )
        return self.platform_metrics[platform_id]

    def record_setup_metrics(
        self,
        platform_id: str,
        metrics: SetupMetrics,
    ):
        """Record setup metrics for a platform."""
        if platform_id in self.platform_metrics:
            self.platform_metrics[platform_id].setup_metrics = metrics

    def record_stage_metrics(
        self,
        platform_id: str,
        metrics: StageMetrics,
    ):
        """Record metrics for a single stage execution."""
        if platform_id in self.platform_metrics:
            self.platform_metrics[platform_id].stage_metrics.append(metrics)

    def record_story_metrics(
        self,
        platform_id: str,
        metrics: StoryMetrics,
    ):
        """Record metrics from a story execution."""
        if platform_id in self.platform_metrics:
            self.platform_metrics[platform_id].add_story_metrics(metrics)

    def record_variance_metrics(
        self,
        platform_id: str,
        story_id: str,
        metrics: VarianceMetrics,
    ):
        """Record variance metrics for repeated runs of a story."""
        if platform_id in self.platform_metrics:
            self.platform_metrics[platform_id].variance_metrics[story_id] = metrics

    def finalize_platform(self, platform_id: str):
        """Calculate final scores for a platform."""
        if platform_id in self.platform_metrics:
            self.platform_metrics[platform_id].calculate_dimension_scores()

    def export_json(self, filename: str = "evaluation_results.json"):
        """Export all metrics to JSON."""
        output_path = self.output_dir / filename
        data = {
            "evaluation_date": datetime.now().isoformat(),
            "platforms": {pid: metrics.to_dict() for pid, metrics in self.platform_metrics.items()},
        }
        from desmet.harness.dev_metrics import compute_all_dev_metrics, get_shared_loc

        all_dev = compute_all_dev_metrics()
        data["dev_metrics"] = {
            "platforms": {pid: dm.to_dict() for pid, dm in all_dev.items()},
            "shared_adapter_loc": get_shared_loc(),
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return output_path

    def export_csv(self, filename: str = "evaluation_summary.csv"):
        """Export summary metrics to CSV."""
        output_path = self.output_dir / filename

        rows = []
        for pid, metrics in self.platform_metrics.items():
            row = {
                "platform_id": pid,
                "platform_name": metrics.platform_name,
                "stories_total": metrics.stories_total,
                "stories_completed": metrics.stories_completed,
                "completion_rate": metrics.stories_completed / metrics.stories_total
                if metrics.stories_total > 0
                else 0,
                "overall_score": metrics.overall_score,
            }
            for dim_score in metrics.dimension_scores:
                row[f"score_{dim_score.dimension.value}"] = dim_score.score
            resource_stories = [
                sm
                for sm in metrics.story_metrics
                if sm._result.resource_metrics
                and sm._result.resource_metrics.get("peak_memory_bytes")
            ]
            if resource_stories:
                row["resource_peak_memory_mb"] = round(
                    max(sm._result.resource_metrics["peak_memory_bytes"] for sm in resource_stories)
                    / (1024 * 1024),
                    1,
                )
                row["resource_avg_cpu_pct"] = round(
                    sum(
                        sm._result.resource_metrics.get("avg_cpu_percent", 0)
                        for sm in resource_stories
                    )
                    / len(resource_stories),
                    1,
                )
            rows.append(row)

        if rows:
            all_keys: list[str] = []
            seen: set[str] = set()
            for row in rows:
                for k in row:
                    if k not in seen:
                        all_keys.append(k)
                        seen.add(k)
            with open(output_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)

        return output_path

    def generate_comparison_report(self) -> str:
        """Generate a text-based comparison report."""
        lines = [
            "=" * 70,
            "DESMET AGENTIC PLATFORMS EVALUATION REPORT",
            "=" * 70,
            f"Generated: {datetime.now().isoformat()}",
            "",
        ]

        for pid, metrics in sorted(
            self.platform_metrics.items(), key=lambda x: x[1].overall_score, reverse=True
        ):
            lines.append(f"\n{'─' * 70}")
            lines.append(f"Platform: {metrics.platform_name} ({pid})")
            lines.append(f"{'─' * 70}")
            lines.append(f"Overall Score: {metrics.overall_score:.2f}/5.0")
            lines.append(f"Stories: {metrics.stories_completed}/{metrics.stories_total} completed")
            lines.append("")
            lines.append("Dimension Scores:")
            for dim in metrics.dimension_scores:
                bar = "█" * int(dim.score) + "░" * (5 - int(dim.score))
                lines.append(f"  {dim.dimension.value:20} {bar} {dim.score:.1f}/5")

            resource_stories = [
                sm
                for sm in metrics.story_metrics
                if sm._result.resource_metrics
                and sm._result.resource_metrics.get("peak_memory_bytes")
            ]
            if resource_stories:
                peak_mem = max(
                    sm._result.resource_metrics["peak_memory_bytes"] for sm in resource_stories
                )
                avg_cpu = sum(
                    sm._result.resource_metrics.get("avg_cpu_percent", 0) for sm in resource_stories
                ) / len(resource_stories)
                lines.append(f"\nResource Consumption:")
                lines.append(f"  Peak Memory: {peak_mem / (1024 * 1024):.0f} MB")
                lines.append(f"  Avg CPU:     {avg_cpu:.1f}%")

            if metrics.variance_metrics:
                lines.append(
                    f"\nRun Variance ({next(iter(metrics.variance_metrics.values())).repeats} repeats):"
                )
                for sid, vm in metrics.variance_metrics.items():
                    cv = vm.wall_clock_std / vm.wall_clock_mean if vm.wall_clock_mean > 0 else 0
                    lines.append(
                        f"  {sid}: {vm.wall_clock_mean:.1f}s ± {vm.wall_clock_std:.1f}s "
                        f"(CV={cv:.2f}), success={vm.success_rate:.0%}"
                    )

        from desmet.harness.dev_metrics import compute_all_dev_metrics, get_shared_loc

        all_dev = compute_all_dev_metrics()
        if all_dev:
            lines.append(f"\n{'─' * 70}")
            lines.append("Developer Experience")
            lines.append(f"{'─' * 70}")
            lines.append(f"{'Platform':<20} {'LOC':>6} {'SLOC':>6} {'Deps':>5} {'Size MB':>8}")
            lines.append(f"{'─' * 20} {'─' * 6} {'─' * 6} {'─' * 5} {'─' * 8}")
            for pid, dm in sorted(all_dev.items()):
                size_str = f"{dm.install_size_mb:.0f}" if dm.install_size_mb is not None else "—"
                lines.append(
                    f"{pid:<20} {dm.adapter_loc:>6} {dm.adapter_sloc:>6} "
                    f"{dm.dependency_count:>5} {size_str:>8}"
                )
            lines.append(f"{'Shared modules':<20} {get_shared_loc():>6}")

        lines.append("\n" + "=" * 70)
        return "\n".join(lines)
