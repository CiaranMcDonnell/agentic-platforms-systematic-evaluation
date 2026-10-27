"""Tests for per-stage metrics tracking."""

from desmet.harness.metrics import EvaluationMetrics, MetricsCollector, StageMetrics, StoryMetrics
from desmet.harness.story import StoryResult, StoryStatus


class TestStageMetrics:
    def test_create_stage_metrics(self):
        m = StageMetrics(
            story_id="US-001",
            platform_id="langgraph",
            stage_name="requirements",
            success=True,
            wall_clock_seconds=15.3,
            iterations=5,
        )
        assert m.stage_name == "requirements"
        assert m.success is True

    def test_default_values(self):
        m = StageMetrics(
            story_id="US-001",
            platform_id="langgraph",
            stage_name="codegen",
        )
        assert m.success is False
        assert m.wall_clock_seconds == 0.0
        assert m.tokens_input == 0


class TestStoryMetricsFacade:
    def test_story_metrics_reads_from_story_result(self):
        result = StoryResult(
            story_id="US-001",
            platform_id="langgraph",
            execution_id="test_001",
            status=StoryStatus.COMPLETED,
            iterations=10,
            tool_calls=5,
            tokens_input=1000,
            tokens_output=500,
            api_cost_usd=0.05,
            wall_clock_seconds=12.5,
            human_interventions=0,
        )
        metrics = StoryMetrics.from_story_result(result, time_budget_seconds=600.0)
        assert metrics.story_id == "US-001"
        assert metrics.platform_id == "langgraph"
        assert metrics.execution_id == "test_001"
        assert metrics.iterations == 10
        assert metrics.tool_calls == 5
        assert metrics.tokens_input == 1000
        assert metrics.tokens_output == 500
        assert metrics.api_cost_usd == 0.05
        assert metrics.success is True
        assert metrics.completed is True
        assert metrics.time_budget_seconds == 600.0
        assert metrics.wall_clock_seconds == 12.5
        assert metrics.langfuse_trace_id is None


class TestEvaluationMetricsToDict:
    def test_evaluation_metrics_to_dict_includes_cost(self):
        """to_dict should include api_cost_usd from the StoryResult facade."""
        result = StoryResult(
            story_id="US-001", platform_id="test", execution_id="e1",
            status=StoryStatus.COMPLETED,
            tokens_input=500, tokens_output=200, api_cost_usd=0.03,
        )
        em = EvaluationMetrics(platform_id="test", platform_name="Test")
        em.add_story_metrics(StoryMetrics.from_story_result(result, time_budget_seconds=300))
        d = em.to_dict()
        sm = d["story_metrics"][0]
        assert sm["api_cost_usd"] == 0.03
        assert sm["tokens_input"] == 500
        assert sm["tokens_output"] == 200
        assert sm["story_id"] == "US-001"
        assert sm["success"] is True


class TestMetricsCollectorStages:
    def test_collector_records_stage_metrics(self, tmp_path):
        collector = MetricsCollector(tmp_path)
        collector.get_or_create_platform_metrics("langgraph", "LangGraph")
        m = StageMetrics(
            story_id="US-001",
            platform_id="langgraph",
            stage_name="requirements",
            success=True,
            wall_clock_seconds=15.3,
            iterations=5,
        )
        collector.record_stage_metrics("langgraph", m)
        platform_metrics = collector.platform_metrics["langgraph"]
        assert len(platform_metrics.stage_metrics) == 1

    def test_records_multiple_stages(self, tmp_path):
        collector = MetricsCollector(tmp_path)
        collector.get_or_create_platform_metrics("langgraph", "LangGraph")
        for stage in ["requirements", "codegen", "testing", "deploy"]:
            m = StageMetrics(
                story_id="US-001",
                platform_id="langgraph",
                stage_name=stage,
                success=True,
            )
            collector.record_stage_metrics("langgraph", m)
        assert len(collector.platform_metrics["langgraph"].stage_metrics) == 4


def _platform_with(scores: dict[str, float], **kwargs) -> EvaluationMetrics:
    result = StoryResult(
        story_id="US-001",
        platform_id="p",
        execution_id="e1",
        status=StoryStatus.COMPLETED,
        wall_clock_seconds=kwargs.get("wall_clock_seconds", 300.0),
        tokens_input=kwargs.get("tokens_input", 50_000),
        tokens_output=0,
        api_cost_usd=kwargs.get("api_cost_usd", 0.0),
    )
    for dim, value in scores.items():
        result.add_score(dim, value)
    result.resource_metrics = kwargs.get("resource_metrics", {})
    em = EvaluationMetrics(platform_id="p", platform_name="p")
    em.add_story_metrics(StoryMetrics.from_story_result(result, time_budget_seconds=600.0))
    em.calculate_dimension_scores()
    return em


def _dim(em: EvaluationMetrics, name: str):
    return next(d for d in em.dimension_scores if d.dimension.value == name)


class TestUnscoredRubrics:
    def test_from_story_result_tracks_scored_dimensions(self):
        em = _platform_with({"tool_integration": 0.0})
        assert em.story_metrics[0].scored_dimensions == {"tool_integration"}

    def test_unscored_pipeline_rubric_uses_completion_only(self):
        em = _platform_with({})
        pc = _dim(em, "pipeline_completeness")
        assert pc.score == 5.0
        assert pc.metrics["avg_pipeline_completeness_rubric"] is None

    def test_scored_zero_pipeline_rubric_still_counts(self):
        em = _platform_with({"pipeline_completeness": 0.0})
        assert _dim(em, "pipeline_completeness").score == 3.0

    def test_orchestration_averages_only_scored_fields(self):
        em = _platform_with({"tool_integration": 3.0})
        orch = _dim(em, "orchestration")
        assert orch.score == 5.0
        assert orch.metrics["rubric_samples"] == 1

    def test_scored_zero_autonomy_is_blended(self):
        em = _platform_with({"autonomy": 0.0})
        aut = _dim(em, "autonomy")
        assert aut.metrics["blended_with_interventions"] is True
        assert aut.score == 3.0


class TestEfficiencyComponents:
    def test_missing_cost_and_memory_are_imputed_neutral(self):
        # time ratio 0.5 and tokens 0.5x budget both clamp to 5.0
        eff = _dim(_platform_with({}), "efficiency")
        assert eff.metrics["missing_components"] == ["cost", "memory"]
        assert eff.score == (5.0 + 5.0 + 3.0 + 3.0) / 4

    def test_all_components_present(self):
        eff = _dim(
            _platform_with(
                {},
                api_cost_usd=0.10,
                resource_metrics={"peak_memory_bytes": 256 * 1024 * 1024},
            ),
            "efficiency",
        )
        assert eff.metrics["missing_components"] == []
        assert eff.score == 5.0
