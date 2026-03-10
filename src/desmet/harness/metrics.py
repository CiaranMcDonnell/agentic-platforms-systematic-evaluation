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
    """DESMET cross-cutting evaluation dimensions."""
    EFFECTIVENESS = "effectiveness"
    EFFICIENCY = "efficiency"
    QUALITY = "quality"
    AUTONOMY = "autonomy"
    REPRODUCIBILITY = "reproducibility"
    USABILITY = "usability"
    OBSERVABILITY = "observability"
    FAILURE_HANDLING = "failure_handling"


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

    correctness_score: float = 0.0
    completeness_score: float = 0.0
    quality_score: float = 0.0


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

    # Quality scores (0-3)
    correctness_score: float = 0.0
    completeness_score: float = 0.0
    code_quality_score: float = 0.0
    test_quality_score: float = 0.0

    # Test metrics
    tests_run: int = 0
    tests_passed: int = 0
    coverage_delta: float = 0.0

    # Acceptance criteria
    criteria_total: int = 0
    criteria_passed: int = 0


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
        elif not metrics.success:
            self.stories_failed += 1

    def calculate_dimension_scores(self):
        """Calculate Layer 3 benchmarking dimension scores from collected metrics.

        Implements the formulas defined in the DESMET report for the four
        primary cross-cutting dimensions: Effectiveness, Efficiency, Quality,
        and Autonomy.  All scores are on a 1-5 Likert scale.

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
        # Effectiveness
        # Formula: (stages_supported/total_stages)*0.4
        #          + avg(correctness_scores)*0.3
        #          + avg(completeness_scores)*0.3
        # Scaled to 1-5.
        # stages_supported is approximated here by the story completion rate;
        # the runner should replace this with a per-stage support ratio once
        # StageMetrics wiring is in place.
        # ------------------------------------------------------------------
        stages_supported_ratio = (
            self.stories_completed / self.stories_total if self.stories_total > 0 else 0.0
        )
        avg_correctness = sum(m.correctness_score for m in self.story_metrics) / n
        avg_completeness = sum(m.completeness_score for m in self.story_metrics) / n
        # correctness_score and completeness_score are on 0-3; normalise to 0-1
        effectiveness_raw = (
            stages_supported_ratio * 0.4
            + (avg_correctness / 3.0) * 0.3
            + (avg_completeness / 3.0) * 0.3
        )
        # Raw is 0-1; scale to 1-5
        effectiveness_score = 1.0 + effectiveness_raw * 4.0

        self.dimension_scores.append(DimensionScore(
            dimension=EvaluationDimension.EFFECTIVENESS,
            score=min(5.0, max(1.0, effectiveness_score)),
            metrics={
                "stages_supported_ratio": stages_supported_ratio,
                "avg_correctness": avg_correctness,
                "avg_completeness": avg_completeness,
            }
        ))

        # ------------------------------------------------------------------
        # Efficiency
        # Single-platform approximation (rank normalisation is cross-platform
        # and applied at comparison time):
        #   time_component = max(1, 5 - (avg_time_ratio - 1) * 2)
        #   token_component = max(1, 5 - (avg_tokens_per_story / TOKEN_BUDGET - 1) * 2)
        #   efficiency_score = (time_component + token_component) / 2
        # TOKEN_BUDGET: 100,000 tokens per story (adjust as evaluation matures).
        # ------------------------------------------------------------------
        TOKEN_BUDGET = 100_000

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
            1.0, 5.0 - (avg_tokens_per_story / TOKEN_BUDGET - 1.0) * 2.0
        )
        efficiency_score = (time_component + token_component) / 2.0

        self.dimension_scores.append(DimensionScore(
            dimension=EvaluationDimension.EFFICIENCY,
            score=min(5.0, max(1.0, efficiency_score)),
            metrics={
                "avg_time_ratio": avg_time_ratio,
                "avg_tokens_per_story": avg_tokens_per_story,
                "token_budget": TOKEN_BUDGET,
                "time_component": time_component,
                "token_component": token_component,
            }
        ))

        # ------------------------------------------------------------------
        # Quality
        # Formula: avg(all 0-3 rubric scores) * 5/3
        # Uses ALL available rubric scores: correctness, completeness,
        # code_quality, test_quality.  Additional rubric fields (e.g.
        # requirement quality) should be added to StageMetrics and averaged
        # in here once the runner wiring is complete.
        # ------------------------------------------------------------------
        all_rubric_scores: list[float] = []
        for m in self.story_metrics:
            all_rubric_scores.extend([
                m.correctness_score,
                m.completeness_score,
                m.code_quality_score,
                m.test_quality_score,
            ])

        avg_rubric = sum(all_rubric_scores) / len(all_rubric_scores) if all_rubric_scores else 0.0
        quality_score = avg_rubric * (5.0 / 3.0)

        self.dimension_scores.append(DimensionScore(
            dimension=EvaluationDimension.QUALITY,
            score=min(5.0, max(1.0, quality_score)),
            metrics={
                "avg_rubric_score": avg_rubric,
                "rubric_fields_used": ["correctness", "completeness", "code_quality", "test_quality"],
                "rubric_samples": len(all_rubric_scores),
            }
        ))

        # ------------------------------------------------------------------
        # Autonomy
        # Formula: 5 - min(4, avg(interventions_per_stage))
        # interventions_per_stage is sourced from StageMetrics.human_interventions
        # when available; falls back to StoryMetrics.human_interventions
        # divided by the number of stages (4) as an approximation.
        # ------------------------------------------------------------------
        if self.stage_metrics:
            # Preferred path: per-stage granularity
            avg_interventions_per_stage = (
                sum(sm.human_interventions for sm in self.stage_metrics) / len(self.stage_metrics)
            )
        else:
            # Fallback: story-level human_interventions spread across 4 stages
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

        # ------------------------------------------------------------------
        # Usability (secondary / Layer 2-adjacent)
        # Kept because SetupMetrics data is already collected; deprioritised
        # in the overall score.  REPRODUCIBILITY, OBSERVABILITY, and
        # FAILURE_HANDLING are NOT computed here — they are Layer 2
        # assessments populated by manual evaluation outside this method.
        # ------------------------------------------------------------------
        if self.setup_metrics:
            usability_score = float(self.setup_metrics.documentation_clarity_score)
            time_penalty = min(2.0, self.setup_metrics.time_to_first_agent_minutes / 30.0)
            usability_score = max(1.0, usability_score - time_penalty)

            self.dimension_scores.append(DimensionScore(
                dimension=EvaluationDimension.USABILITY,
                score=usability_score,
                confidence=0.7,  # lower confidence — single observer, setup only
                metrics={
                    "documentation_score": self.setup_metrics.documentation_clarity_score,
                    "time_to_first_agent": self.setup_metrics.time_to_first_agent_minutes,
                },
                notes="Layer 2 / setup-phase indicator; not derived from benchmarking runs.",
            ))

        # Overall score: average the four primary Layer 3 dimensions only
        primary_dimensions = {
            EvaluationDimension.EFFECTIVENESS,
            EvaluationDimension.EFFICIENCY,
            EvaluationDimension.QUALITY,
            EvaluationDimension.AUTONOMY,
        }
        primary_scores = [
            d.score for d in self.dimension_scores if d.dimension in primary_dimensions
        ]
        if primary_scores:
            self.overall_score = sum(primary_scores) / len(primary_scores)

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
                    "correctness_score": m.correctness_score,
                    "completeness_score": m.completeness_score,
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
