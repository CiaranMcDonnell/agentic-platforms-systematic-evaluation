from datetime import datetime, timezone
from desmet.harness.metrics import EvaluationMetrics, StoryMetrics, VarianceMetrics, compute_variance_metrics
from desmet.harness.story import StoryResult, StoryStatus


def _make_result(wall_clock, tokens_in, tokens_out, cost, tool_calls, iterations, status=StoryStatus.COMPLETED):
    return StoryResult(
        story_id="s1", platform_id="langgraph",
        execution_id=f"exec_{wall_clock}",
        status=status,
        wall_clock_seconds=wall_clock,
        tokens_input=tokens_in, tokens_output=tokens_out,
        api_cost_usd=cost, tool_calls=tool_calls,
        iterations=iterations,
        start_time=datetime.now(timezone.utc),
    )


def test_variance_metrics_basic():
    results = [
        _make_result(10.0, 1000, 500, 0.10, 5, 3),
        _make_result(12.0, 1200, 600, 0.12, 7, 4),
        _make_result(11.0, 1100, 550, 0.11, 6, 3),
    ]
    vm = compute_variance_metrics(results)
    assert vm.repeats == 3
    assert abs(vm.wall_clock_mean - 11.0) < 0.01
    assert vm.wall_clock_std > 0
    assert vm.success_rate == 1.0


def test_variance_metrics_with_failures():
    results = [
        _make_result(10.0, 1000, 500, 0.10, 5, 3),
        _make_result(0.0, 0, 0, 0.0, 0, 0, status=StoryStatus.FAILED),
        _make_result(12.0, 1200, 600, 0.12, 7, 4),
    ]
    vm = compute_variance_metrics(results)
    assert vm.repeats == 3
    assert abs(vm.success_rate - 2/3) < 0.01
    assert vm.wall_clock_mean > 0


def test_variance_metrics_single_run():
    results = [_make_result(10.0, 1000, 500, 0.10, 5, 3)]
    vm = compute_variance_metrics(results)
    assert vm.repeats == 1
    assert vm.wall_clock_std == 0.0


def test_efficiency_includes_resource_component():
    em = EvaluationMetrics(platform_id="test", platform_name="Test")
    result = StoryResult(
        story_id="s1", platform_id="test", execution_id="e1",
        status=StoryStatus.COMPLETED,
        wall_clock_seconds=300, tokens_input=50000, tokens_output=10000,
        api_cost_usd=0.25,
        resource_metrics={"peak_memory_bytes": 256 * 1024 * 1024},
    )
    sm = StoryMetrics.from_story_result(result, time_budget_seconds=600)
    em.add_story_metrics(sm)
    em.calculate_dimension_scores()
    eff = next(d for d in em.dimension_scores if d.dimension.value == "efficiency")
    assert "resource_component" in eff.metrics
    assert eff.metrics["resource_component"] is not None


def test_efficiency_without_resource_falls_back():
    em = EvaluationMetrics(platform_id="test", platform_name="Test")
    result = StoryResult(
        story_id="s1", platform_id="test", execution_id="e1",
        status=StoryStatus.COMPLETED,
        wall_clock_seconds=300, tokens_input=50000, tokens_output=10000,
        api_cost_usd=0.25,
    )
    sm = StoryMetrics.from_story_result(result, time_budget_seconds=600)
    em.add_story_metrics(sm)
    em.calculate_dimension_scores()
    eff = next(d for d in em.dimension_scores if d.dimension.value == "efficiency")
    assert eff.metrics.get("resource_component") is None
