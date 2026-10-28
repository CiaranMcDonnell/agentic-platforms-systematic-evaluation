"""Tests for dashboard chart builders."""

import json

import pandas as pd

from desmet.dashboard.charts import bar_efficiency_breakdown


def test_efficiency_breakdown_tolerates_unknown_iterations():
    """Timed-out or usage-fallback stages leave iterations unknown (None).

    A platform whose iterations are all unknown must not produce NaN —
    NaN is not valid JSON and made the chart endpoint return HTTP 500.
    Known values are averaged without the unknowns.
    """
    df = pd.DataFrame(
        {
            "platform_id": ["a", "a", "b"],
            "platform_name": ["A", "A", "B"],
            "wall_clock_seconds": [10.0, 20.0, 30.0],
            "iterations": [4, None, None],
            "tool_calls": [2, 6, 1],
        }
    )

    chart = bar_efficiency_breakdown(df)

    json.dumps(chart, allow_nan=False)  # raises on NaN/inf
    iterations = next(s for s in chart["series"] if s["name"] == "Avg Iterations")
    assert iterations["data"] == [4.0, None]
