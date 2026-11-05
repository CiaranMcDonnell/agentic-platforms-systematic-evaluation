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


def _spread_df():
    return pd.DataFrame(
        {
            "platform_id": ["langgraph"] * 3 + ["crewai"] * 3 + ["langgraph"] * 3,
            "series": ["m1"] * 6 + ["m2"] * 3,
            "repeat_index": [0, 1, 2] * 3,
            "cost_usd": [1.0, 2.0, 9.0, 0.5, None, 0.7, 3.0, 3.0, 3.0],
        }
    )


def test_spread_shows_median_range_and_each_repeat():
    from desmet.dashboard.charts import spread_by_platform

    chart = spread_by_platform(_spread_df(), "cost_usd", "Cost (USD)")
    json.dumps(chart, allow_nan=False)
    m1 = [s for s in chart["series"] if s["name"] == "m1"]
    ranges, repeats, medians = m1
    # Platforms sorted: crewai (x=0), langgraph (x=1); m1 sits left of centre.
    lg = next(d for d in medians["data"] if d["value"][0] > 0.5)
    assert lg["value"][1] == 2.0  # median, not the 4.0 mean the outlier would give
    assert "1.00–9.00" in lg["tooltip"]["formatter"]
    # The unknown CrewAI repeat is left out, not plotted as 0.
    assert len(repeats["data"]) == 5
    cr = next(d for d in medians["data"] if d["value"][0] < 0.5)
    assert "2 of 3 repeats known" in cr["tooltip"]["formatter"]
    # Series are offset so they don't overlap within a platform.
    m2_median = next(s for s in chart["series"] if s["name"] == "m2" and s.get("symbolSize") == 12)
    assert m2_median["data"][0]["value"][0] > lg["value"][0]
    assert ranges["data"].count("-") == 2


def test_spread_log_scale_drops_non_positive():
    from desmet.dashboard.charts import spread_by_platform

    df = _spread_df()
    df.loc[0, "cost_usd"] = 0.0
    chart = spread_by_platform(df, "cost_usd", "Cost (USD)", log=True)
    assert chart["yAxis"]["type"] == "log"
    values = [d["value"][1] for s in chart["series"] if s["type"] == "scatter" for d in s["data"]]
    assert min(values) > 0


def test_criteria_heatmap_labels_met_over_executions():
    from desmet.dashboard.charts import heatmap_criteria

    chart = heatmap_criteria({"crewai": {"AC-1": (2, 3)}, "langgraph": {"AC-1": (0, 3), "AC-2": (3, 3)}})
    data = chart["series"][0]["data"]
    assert len(data) == 3  # crewai has no AC-2 result: no cell, not a fail
    assert {d["label"]["formatter"] for d in data} == {"2/3", "0/3", "3/3"}
    assert next(d for d in data if d["label"]["formatter"] == "2/3")["value"][2] == 0.667
