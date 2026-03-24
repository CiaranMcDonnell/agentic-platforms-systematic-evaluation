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
from typing import Any


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

    TODO: Wire StageMetrics into the runner so that each stage result
    (RequirementsResult, CodeResult, TestResult, DeployResult) is
    automatically converted to a StageMetrics entry and appended to
    EvaluationMetrics.stage_metrics.  The dimension-score formulas in
    calculate_dimension_scores() are designed to consume this list.
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
    """Metrics from a single story execution."""
    story_id: str
    platform_id: str
    execution_id: str

    # Outcome
    success: bool = False
    completed: bool = False

    # Timing
    wall_clock_seconds: float = 0.0
    time_budget_seconds: float = 0.0

    # Efficiency
    iterations: int = 0
    tool_calls: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    api_cost_usd: float = 0.0

    # Autonomy
    human_interventions: int = 0
    clarifying_questions: int = 0
    self_corrections: int = 0

    # Framework-centric scores (0-3)
    pipeline_completeness_score: float = 0.0
    tool_integration_score: float = 0.0
    error_recovery_score: float = 0.0
    trace_quality_score: float = 0.0

    # Test metrics
    tests_run: int = 0
    tests_passed: int = 0
    coverage_delta: float = 0.0

    # Acceptance criteria
    criteria_total: int = 0
    criteria_passed: int = 0

    # Langfuse trace linkage
    langfuse_trace_id: str | None = None


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
        if metrics.completed:
            self.stories_completed += 1
        if not metrics.completed and not metrics.success:
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
        avg_pipeline_score = (
            sum(m.pipeline_completeness_score for m in self.story_metrics) / n
        )
        pipeline_raw = (
            completion_ratio * 0.5
            + (avg_pipeline_score / 3.0) * 0.5
        )
        pipeline_completeness_score = 1.0 + pipeline_raw * 4.0

        self.dimension_scores.append(DimensionScore(
            dimension=EvaluationDimension.PIPELINE_COMPLETENESS,
            score=min(5.0, max(1.0, pipeline_completeness_score)),
            metrics={
                "completion_ratio": completion_ratio,
                "avg_pipeline_completeness_rubric": avg_pipeline_score,
            }
        ))

        # ------------------------------------------------------------------
        # Efficiency
        # Measures: framework orchestration overhead (time + tokens).
        #   time_component = max(1, 5 - (avg_time_ratio - 1) * 2)
        #   token_component = max(1, 5 - (avg_tokens / token_budget - 1) * 2)
        #   efficiency_score = (time_component + token_component) / 2
        # token_budget: 100,000 tokens per story (adjust as evaluation matures).
        # ------------------------------------------------------------------
        token_budget = 100_000

        timed_metrics = [m for m in self.story_metrics if m.time_budget_seconds > 0]
        if timed_metrics:
            avg_time_ratio = sum(
                m.wall_clock_seconds / m.time_budget_seconds for m in timed_metrics
            ) / len(timed_metrics)
        else:
            avg_time_ratio = 1.0  # neutral assumption when no budget is set

        avg_tokens_per_story = sum(
            m.tokens_input + m.tokens_output for m in self.story_metrics
        ) / n

        time_component = max(1.0, 5.0 - (avg_time_ratio - 1.0) * 2.0)
        token_component = max(
            1.0, 5.0 - (avg_tokens_per_story / token_budget - 1.0) * 2.0
        )
        efficiency_score = (time_component + token_component) / 2.0

        self.dimension_scores.append(DimensionScore(
            dimension=EvaluationDimension.EFFICIENCY,
            score=min(5.0, max(1.0, efficiency_score)),
            metrics={
                "avg_time_ratio": avg_time_ratio,
                "avg_tokens_per_story": avg_tokens_per_story,
                "token_budget": token_budget,
                "time_component": time_component,
                "token_component": token_component,
            }
        ))

        # ------------------------------------------------------------------
        # Orchestration
        # Measures: how well the framework handles tool integration, error
        # recovery, and trace production — pure framework concerns.
        # Formula: avg(tool_integration, error_recovery, trace_quality) * 5/3
        # ------------------------------------------------------------------
        all_orchestration_scores: list[float] = []
        for m in self.story_metrics:
            all_orchestration_scores.extend([
                m.tool_integration_score,
                m.error_recovery_score,
                m.trace_quality_score,
            ])

        avg_orchestration = (
            sum(all_orchestration_scores) / len(all_orchestration_scores)
            if all_orchestration_scores else 0.0
        )
        orchestration_score = avg_orchestration * (5.0 / 3.0)

        self.dimension_scores.append(DimensionScore(
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
            }
        ))

        # ------------------------------------------------------------------
        # Autonomy
        # Measures: how much human intervention the framework requires.
        # Formula: 5 - min(4, avg(interventions_per_stage))
        # ------------------------------------------------------------------
        if self.stage_metrics:
            avg_interventions_per_stage = (
                sum(sm.human_interventions for sm in self.stage_metrics) / len(self.stage_metrics)
            )
        else:
            avg_story_interventions = (
                sum(m.human_interventions for m in self.story_metrics) / n
            )
            avg_interventions_per_stage = avg_story_interventions / 4.0

        autonomy_score = 5.0 - min(4.0, avg_interventions_per_stage)

        self.dimension_scores.append(DimensionScore(
            dimension=EvaluationDimension.AUTONOMY,
            score=min(5.0, max(1.0, autonomy_score)),
            metrics={
                "avg_interventions_per_stage": avg_interventions_per_stage,
                "source": "stage_metrics" if self.stage_metrics else "story_metrics_fallback",
            }
        ))

        # Overall score: average of the four Layer 3 dimensions
        if self.dimension_scores:
            self.overall_score = (
                sum(d.score for d in self.dimension_scores) / len(self.dimension_scores)
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
            } if self.setup_metrics else None,
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
                    "pipeline_completeness_score": m.pipeline_completeness_score,
                    "tool_integration_score": m.tool_integration_score,
                    "error_recovery_score": m.error_recovery_score,
                    "trace_quality_score": m.trace_quality_score,
                }
                for m in self.story_metrics
            ],
        }


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

    def finalize_platform(self, platform_id: str):
        """Calculate final scores for a platform."""
        if platform_id in self.platform_metrics:
            self.platform_metrics[platform_id].calculate_dimension_scores()

    def export_json(self, filename: str = "evaluation_results.json"):
        """Export all metrics to JSON."""
        output_path = self.output_dir / filename
        data = {
            "evaluation_date": datetime.now().isoformat(),
            "platforms": {
                pid: metrics.to_dict()
                for pid, metrics in self.platform_metrics.items()
            }
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
                "completion_rate": metrics.stories_completed / metrics.stories_total if metrics.stories_total > 0 else 0,
                "overall_score": metrics.overall_score,
            }
            for dim_score in metrics.dimension_scores:
                row[f"score_{dim_score.dimension.value}"] = dim_score.score
            rows.append(row)

        if rows:
            with open(output_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
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
            self.platform_metrics.items(),
            key=lambda x: x[1].overall_score,
            reverse=True
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

        lines.append("\n" + "=" * 70)
        return "\n".join(lines)
