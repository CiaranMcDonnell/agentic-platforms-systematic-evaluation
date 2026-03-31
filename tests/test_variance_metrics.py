from datetime import datetime, timezone
from desmet.harness.metrics import VarianceMetrics, compute_variance_metrics
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
