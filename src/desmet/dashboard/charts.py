"""DESMET Dashboard - reusable ECharts option builders.

Every public function returns a plain ``dict`` that can be serialised to
JSON and consumed directly by the ECharts frontend component.  No
browser-side library imports are needed on the Python side.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .data import get_platform_colour, get_platform_name

# ---------------------------------------------------------------------------
# Shared theme — designed for dark UI
# ---------------------------------------------------------------------------

_BG = "transparent"
_GRID = "rgba(255,255,255,0.08)"
_TEXT = "#e0e0e0"
_AXIS_TEXT = "#b0b0b0"
_FONT = "Inter, -apple-system, sans-serif"

_TOOLTIP_DEFAULTS: dict[str, Any] = dict(
    backgroundColor="#1e1e2e",
    borderColor="rgba(255,255,255,0.1)",
    textStyle=dict(color="#e0e0e0", fontFamily=_FONT, fontSize=12),
)

_LEGEND_DEFAULTS: dict[str, Any] = dict(
    textStyle=dict(color=_TEXT, fontFamily=_FONT, fontSize=12),
    bottom=0,
)

_TITLE_DEFAULTS: dict[str, Any] = dict(
    textStyle=dict(color="#ffffff", fontFamily=_FONT, fontSize=14, fontWeight="bold"),
    left=12,
    top=10,
)


def _base_option(title: str = "") -> dict[str, Any]:
    """Return a base ECharts option dict with shared theme defaults."""
    opt: dict[str, Any] = dict(
        backgroundColor=_BG,
        tooltip={**_TOOLTIP_DEFAULTS, "trigger": "axis"},
        legend={**_LEGEND_DEFAULTS},
        textStyle=dict(fontFamily=_FONT, color=_TEXT),
    )
    if title:
        opt["title"] = {**_TITLE_DEFAULTS, "text": title}
    return opt


def _axis_defaults() -> dict[str, Any]:
    """Shared axis styling for cartesian charts."""
    return dict(
        axisLine=dict(lineStyle=dict(color="rgba(255,255,255,0.15)")),
        splitLine=dict(lineStyle=dict(color=_GRID)),
        axisLabel=dict(color=_AXIS_TEXT, fontFamily=_FONT, fontSize=12),
        nameTextStyle=dict(color=_AXIS_TEXT, fontFamily=_FONT, fontSize=12),
        nameGap=25,
    )


def _hex_to_rgba(hex_colour: str, alpha: float) -> str:
    """Convert #RRGGBB to rgba() string."""
    r = int(hex_colour[1:3], 16)
    g = int(hex_colour[3:5], 16)
    b = int(hex_colour[5:7], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ---------------------------------------------------------------------------
# 1. Radar — DESMET dimension scores
# ---------------------------------------------------------------------------


def radar_dimensions(
    dimension_scores: dict[str, dict[str, float]],
    title: str = "DESMET Dimension Comparison",
) -> dict[str, Any]:
    """Polar radar chart of dimension scores per platform."""
    all_dims: list[str] = []
    for scores in dimension_scores.values():
        for dim in scores:
            if dim not in all_dims:
                all_dims.append(dim)

    indicators = [
        dict(name=d.replace("_", " ").title(), max=5) for d in all_dims
    ]

    series_data = []
    legend_data = []

    for platform_id, scores in dimension_scores.items():
        values = [scores.get(d, 0.0) for d in all_dims]
        colour = get_platform_colour(platform_id)
        name = get_platform_name(platform_id)
        legend_data.append(name)

        series_data.append(dict(
            value=values,
            name=name,
            symbol="circle",
            symbolSize=6,
            lineStyle=dict(color=colour, width=2.5),
            itemStyle=dict(color=colour),
            areaStyle=dict(color=_hex_to_rgba(colour, 0.15)),
        ))

    opt = _base_option(title)
    opt["tooltip"] = {**_TOOLTIP_DEFAULTS, "trigger": "item"}
    opt["legend"] = {
        **_LEGEND_DEFAULTS,
        "data": legend_data,
        "right": 10,
        "top": "middle",
        "bottom": "auto",
        "orient": "vertical",
    }
    opt["radar"] = dict(
        indicator=indicators,
        shape="polygon",
        center=["40%", "55%"],
        radius="65%",
        splitNumber=5,
        axisName=dict(color=_TEXT, fontFamily=_FONT, fontSize=12),
        splitLine=dict(lineStyle=dict(color="rgba(255,255,255,0.1)")),
        splitArea=dict(show=False),
        axisLine=dict(lineStyle=dict(color="rgba(255,255,255,0.1)")),
    )
    opt["series"] = [dict(type="radar", data=series_data)]

    return opt


# ---------------------------------------------------------------------------
# 2. Horizontal bar — platform overall rankings
# ---------------------------------------------------------------------------


def bar_platform_rankings(
    summary_df: pd.DataFrame,
    title: str = "Platform Rankings",
) -> dict[str, Any]:
    """Horizontal bar chart of platforms ranked by ``overall_score``."""
    df = summary_df.sort_values("overall_score", ascending=True).reset_index(drop=True)
    colours = [get_platform_colour(pid) for pid in df["platform_id"]]
    names = list(df["platform_name"])
    values = list(df["overall_score"])

    opt = _base_option(title)
    opt["tooltip"] = {**_TOOLTIP_DEFAULTS, "trigger": "axis", "axisPointer": dict(type="shadow")}
    opt["legend"] = {"show": False}
    opt["grid"] = dict(left="30%", right="18%", top=45, bottom=25)
    opt["xAxis"] = {
        **_axis_defaults(),
        "type": "value",
        "max": 5.5,
        "name": "Score (0–5)",
        "nameLocation": "middle",
        "nameGap": 30,
    }
    opt["yAxis"] = {
        **_axis_defaults(),
        "type": "category",
        "data": names,
    }
    opt["series"] = [dict(
        type="bar",
        data=[
            dict(value=round(v, 2), itemStyle=dict(color=c, borderRadius=[0, 4, 4, 0]))
            for v, c in zip(values, colours)
        ],
        label=dict(
            show=True, position="right", color=_TEXT,
            fontFamily=_FONT, fontSize=13,
            formatter="{c}",
        ),
        barMaxWidth=30,
    )]

    return opt


# ---------------------------------------------------------------------------
# 3. Horizontal bar — completion rates
# ---------------------------------------------------------------------------


def bar_completion_rates(
    summary_df: pd.DataFrame,
    title: str = "Completion Rates",
) -> dict[str, Any]:
    """Horizontal bar chart of story completion rates per platform."""
    df = summary_df.sort_values("completion_rate", ascending=True).reset_index(drop=True)
    pct = (df["completion_rate"] * 100).tolist()
    colours = [get_platform_colour(pid) for pid in df["platform_id"]]
    names = list(df["platform_name"])

    opt = _base_option(title)
    opt["tooltip"] = {
        **_TOOLTIP_DEFAULTS,
        "trigger": "axis",
        "axisPointer": dict(type="shadow"),
    }
    opt["legend"] = {"show": False}
    opt["grid"] = dict(left="30%", right="18%", top=45, bottom=25)
    opt["xAxis"] = {
        **_axis_defaults(),
        "type": "value",
        "max": 115,
        "name": "Completion (%)",
        "nameLocation": "middle",
        "nameGap": 30,
    }
    opt["yAxis"] = {
        **_axis_defaults(),
        "type": "category",
        "data": names,
    }
    opt["series"] = [dict(
        type="bar",
        data=[
            dict(value=round(v, 1), itemStyle=dict(color=c, borderRadius=[0, 4, 4, 0]))
            for v, c in zip(pct, colours)
        ],
        label=dict(
            show=True, position="right", color=_TEXT,
            fontFamily=_FONT, fontSize=13,
            formatter="{c}%",
        ),
        barMaxWidth=30,
    )]

    return opt


# ---------------------------------------------------------------------------
# 4. Grouped bar — story-level metric comparison
# ---------------------------------------------------------------------------


def bar_story_comparison(
    metrics_df: pd.DataFrame,
    metric: str,
    title: str = "",
) -> dict[str, Any]:
    """Grouped bar chart comparing a single *metric* across stories and platforms."""
    story_ids = list(metrics_df["story_id"].unique())
    y_label = metric.replace("_", " ").title()

    series = []
    for pid in metrics_df["platform_id"].unique():
        pdf = metrics_df[metrics_df["platform_id"] == pid]
        val_map = dict(zip(pdf["story_id"], pdf[metric]))
        values = [val_map.get(sid, 0) for sid in story_ids]

        series.append(dict(
            type="bar",
            name=get_platform_name(pid),
            data=values,
            itemStyle=dict(color=get_platform_colour(pid), borderRadius=[4, 4, 0, 0]),
            barMaxWidth=24,
        ))

    opt = _base_option(title or f"{y_label} by Story")
    opt["tooltip"] = {**_TOOLTIP_DEFAULTS, "trigger": "axis", "axisPointer": dict(type="shadow")}
    opt["legend"] = {**_LEGEND_DEFAULTS, "bottom": 0}
    opt["grid"] = dict(left=80, right=20, top=45, bottom=40)
    opt["xAxis"] = {
        **_axis_defaults(),
        "type": "category",
        "data": story_ids,
        "axisLabel": {**_axis_defaults()["axisLabel"], "rotate": 30, "fontSize": 10},
    }
    opt["yAxis"] = {
        **_axis_defaults(),
        "type": "value",
        "name": y_label,
        "nameLocation": "middle",
        "nameGap": 50,
    }
    opt["series"] = series

    return opt


# ---------------------------------------------------------------------------
# 5. Grouped bar — efficiency breakdown (wall_clock, iterations, tool_calls)
# ---------------------------------------------------------------------------


def bar_efficiency_breakdown(
    metrics_df: pd.DataFrame,
    title: str = "Efficiency Breakdown",
) -> dict[str, Any]:
    """Grouped bar chart of averaged efficiency metrics per platform."""
    efficiency_cols = ["wall_clock_seconds", "iterations", "tool_calls"]
    agg = (
        metrics_df.groupby(["platform_id", "platform_name"])[efficiency_cols]
        .mean()
        .reset_index()
    )

    metric_config = [
        ("wall_clock_seconds", "Avg Time (s)", "#6366f1"),
        ("iterations", "Avg Iterations", "#22d3ee"),
        ("tool_calls", "Avg Tool Calls", "#f472b6"),
    ]

    platform_names = list(agg["platform_name"])

    series = []
    for col, label, colour in metric_config:
        series.append(dict(
            type="bar",
            name=label,
            data=[round(v, 1) for v in agg[col]],
            itemStyle=dict(color=colour, borderRadius=[4, 4, 0, 0]),
            barMaxWidth=24,
        ))

    opt = _base_option(title)
    opt["tooltip"] = {**_TOOLTIP_DEFAULTS, "trigger": "axis", "axisPointer": dict(type="shadow")}
    opt["legend"] = {**_LEGEND_DEFAULTS, "bottom": 0}
    opt["grid"] = dict(left=80, right=20, top=45, bottom=40)
    opt["xAxis"] = {
        **_axis_defaults(),
        "type": "category",
        "data": platform_names,
    }
    opt["yAxis"] = {
        **_axis_defaults(),
        "type": "value",
        "name": "Average Value",
        "nameLocation": "middle",
        "nameGap": 50,
    }
    opt["series"] = series

    return opt


# ---------------------------------------------------------------------------
# 6. Heatmap — criteria pass / fail / N/A
# ---------------------------------------------------------------------------


def heatmap_criteria(
    criteria_data: dict[str, dict[str, bool | None]],
    title: str = "Acceptance Criteria",
) -> dict[str, Any]:
    """Heatmap showing pass/fail/N-A for every platform-criterion pair."""
    platform_ids = list(criteria_data.keys())
    platform_names = [get_platform_name(pid) for pid in platform_ids]

    all_criteria: list[str] = []
    for crit_dict in criteria_data.values():
        for cid in crit_dict:
            if cid not in all_criteria:
                all_criteria.append(cid)

    criteria_labels = [c.replace("_", " ").title() for c in all_criteria]

    # ECharts heatmap data: [x_index, y_index, value]
    data = []
    for xi, pid in enumerate(platform_ids):
        for yi, cid in enumerate(all_criteria):
            val = criteria_data[pid].get(cid)
            if val is True:
                data.append([xi, yi, 1])
            elif val is False:
                data.append([xi, yi, 0])
            else:
                data.append([xi, yi, 0.5])

    opt = _base_option(title)
    opt["tooltip"] = {
        **_TOOLTIP_DEFAULTS,
        "trigger": "item",
    }
    opt["grid"] = dict(left="30%", right=20, top=45, bottom=30)
    opt["xAxis"] = dict(
        type="category",
        data=platform_names,
        splitArea=dict(show=True),
        axisLabel=dict(color=_AXIS_TEXT, fontFamily=_FONT, fontSize=11, rotate=30),
    )
    opt["yAxis"] = dict(
        type="category",
        data=criteria_labels,
        axisLabel=dict(color=_AXIS_TEXT, fontFamily=_FONT, fontSize=11),
    )
    opt["visualMap"] = dict(
        min=0, max=1,
        show=False,
        inRange=dict(color=["#ef4444", "#4b5563", "#22c55e"]),
    )
    opt["series"] = [dict(
        type="heatmap",
        data=data,
        label=dict(show=True, color="white", fontSize=11),
        itemStyle=dict(borderWidth=2, borderColor="#0a0a0a"),
    )]

    return opt


# ---------------------------------------------------------------------------
# 7. Horizontal bar — single dimension comparison
# ---------------------------------------------------------------------------


def bar_dimension_comparison(
    dimension_df: pd.DataFrame,
    dimension: str,
    title: str = "",
) -> dict[str, Any]:
    """Horizontal bar chart for a single DESMET dimension."""
    df = dimension_df[dimension_df["dimension"] == dimension].copy()
    df = df.sort_values("score", ascending=True).reset_index(drop=True)

    dim_title = dimension.replace("_", " ").title()
    colours = [get_platform_colour(pid) for pid in df["platform_id"]]
    names = list(df["platform_name"])
    values = list(df["score"])

    opt = _base_option(title or dim_title)
    opt["tooltip"] = {**_TOOLTIP_DEFAULTS, "trigger": "axis", "axisPointer": dict(type="shadow")}
    opt["legend"] = {"show": False}
    opt["grid"] = dict(left="30%", right="18%", top=45, bottom=25)
    opt["xAxis"] = {
        **_axis_defaults(),
        "type": "value",
        "max": 5.5,
        "name": dim_title,
        "nameLocation": "middle",
        "nameGap": 30,
    }
    opt["yAxis"] = {
        **_axis_defaults(),
        "type": "category",
        "data": names,
    }
    opt["series"] = [dict(
        type="bar",
        data=[
            dict(value=round(v, 2), itemStyle=dict(color=c, borderRadius=[0, 4, 4, 0]))
            for v, c in zip(values, colours)
        ],
        label=dict(
            show=True, position="right", color=_TEXT,
            fontFamily=_FONT, fontSize=13,
            formatter="{c}",
        ),
        barMaxWidth=30,
    )]

    return opt
