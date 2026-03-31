"""Integration tests for extended metrics features."""

from datetime import datetime, timezone

from desmet.harness.metrics import (
    EvaluationMetrics,
    MetricsCollector,
    StoryMetrics,
    VarianceMetrics,
    compute_variance_metrics,
)
from desmet.harness.resource_monitor import ResourceSummary
from desmet.harness.story import StoryResult, StoryStatus


def test_full_pipeline_with_resource_metrics():
    """Resource metrics flow from StoryResult through to EvaluationMetrics."""
    result = StoryResult(
        story_id="s1",
        platform_id="langgraph",
        execution_id="e1",
        status=StoryStatus.COMPLETED,
        wall_clock_seconds=120,
        tokens_input=30000,
        tokens_output=8000,
        api_cost_usd=0.15,
        resource_metrics={
            "peak_memory_bytes": 200 * 1024 * 1024,
            "avg_memory_bytes": 150 * 1024 * 1024,
            "avg_cpu_percent": 35.0,
            "peak_cpu_percent": 72.0,
            "net_rx_total_bytes": 50000,
            "net_tx_total_bytes": 120000,
            "startup_to_ready_ms": 800.0,
            "samples": 60,
        },
    )
    sm = StoryMetrics.from_story_result(result, time_budget_seconds=600)
    em = EvaluationMetrics(platform_id="langgraph", platform_name="LangGraph")
    em.add_story_metrics(sm)
    em.calculate_dimension_scores()

    # Verify resource component exists in efficiency
    eff = next(d for d in em.dimension_scores if d.dimension.value == "efficiency")
    assert eff.metrics["resource_component"] is not None
    assert eff.score >= 1.0

    # Verify serialization
    d = em.to_dict()
    assert d["story_metrics"][0]["resource_metrics"]["peak_memory_bytes"] == 200 * 1024 * 1024


def test_full_pipeline_with_variance():
    """Variance metrics computed from repeated runs."""
    results = [
        StoryResult(
            story_id="s1", platform_id="langgraph",
            execution_id=f"e{i}",
            status=StoryStatus.COMPLETED,
            wall_clock_seconds=100 + i * 10,
            tokens_input=20000 + i * 1000,
            tokens_output=5000,
            api_cost_usd=0.10 + i * 0.01,
            tool_calls=5 + i,
            iterations=3 + i,
        )
        for i in range(5)
    ]
    vm = compute_variance_metrics(results)
    assert vm.repeats == 5
    assert vm.success_rate == 1.0
    assert vm.wall_clock_std > 0

    # Verify it can be attached to EvaluationMetrics
    em = EvaluationMetrics(platform_id="langgraph", platform_name="LangGraph")
    em.variance_metrics["s1"] = vm
    d = em.to_dict()
    assert "s1" in d["variance_metrics"]
    assert d["variance_metrics"]["s1"]["repeats"] == 5


def test_resource_summary_round_trip():
    """ResourceSummary serializes and can be stored on StoryResult."""
    summary = ResourceSummary(
        samples=30,
        peak_memory_bytes=512 * 1024 * 1024,
        avg_memory_bytes=256 * 1024 * 1024,
        avg_cpu_percent=45.5,
        peak_cpu_percent=89.2,
        net_rx_total_bytes=1_000_000,
        net_tx_total_bytes=2_000_000,
        startup_to_ready_ms=1200.0,
    )
    d = summary.to_dict()

    result = StoryResult(
        story_id="s1", platform_id="test", execution_id="e1",
        resource_metrics=d,
    )
    assert result.resource_metrics["peak_memory_bytes"] == 512 * 1024 * 1024
    assert result.resource_metrics["avg_cpu_percent"] == 45.5
