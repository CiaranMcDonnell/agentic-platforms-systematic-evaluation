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
