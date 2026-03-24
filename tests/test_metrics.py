"""Tests for per-stage metrics tracking."""

from desmet.harness.metrics import MetricsCollector, StageMetrics


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
