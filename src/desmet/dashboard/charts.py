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
    # Unknown values (None, e.g. iterations of a timed-out stage) become
    # NaN and are skipped by mean(); an all-unknown platform stays NaN and
    # is emitted as null below, since NaN is not valid JSON.
    numeric = metrics_df.assign(
        **{c: pd.to_numeric(metrics_df[c], errors="coerce") for c in efficiency_cols}
    )
    agg = (
        numeric.groupby(["platform_id", "platform_name"])[efficiency_cols]
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
            data=[None if pd.isna(v) else round(v, 1) for v in agg[col]],
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
    rates: dict[str, dict[str, tuple[int, int]]],
    title: str = "Hidden Acceptance Criteria",
) -> dict[str, Any]:
    """Pass rate over repeats for every platform x criterion; each cell is
    labelled met/executions.  Input from ``data.get_criteria_rates``."""
    platform_ids = sorted(rates)
    all_criteria = sorted({c for crit in rates.values() for c in crit})

    # ECharts heatmap data: [x_index, y_index, value]; per-item labels and
    # tooltips are plain strings (options must stay JSON).
    data = []
    for xi, pid in enumerate(platform_ids):
        for yi, cid in enumerate(all_criteria):
            if cid not in rates[pid]:
                continue
            met, n = rates[pid][cid]
            data.append(dict(
                value=[xi, yi, round(met / n, 3) if n else 0],
                label=dict(formatter=f"{met}/{n}", color="#0a0a0a" if n and met / n >= 0.6 else "#ffffff"),
                tooltip=dict(formatter=f"{get_platform_name(pid)} · {cid}<br/>{met} of {n} executions met it"),
            ))

    opt = _base_option(title)
    opt["tooltip"] = {**_TOOLTIP_DEFAULTS, "trigger": "item"}
    opt["grid"] = dict(left=90, right=20, top=45, bottom=60)
    opt["xAxis"] = dict(
        type="category",
        data=[get_platform_name(pid) for pid in platform_ids],
        axisLabel=dict(color=_AXIS_TEXT, fontFamily=_FONT, fontSize=11, interval=0, rotate=20),
    )
    opt["yAxis"] = dict(
        type="category",
        data=all_criteria,
        inverse=True,
        axisLabel=dict(color=_AXIS_TEXT, fontFamily=_FONT, fontSize=11),
    )
    # One hue, dark (none met) to light (all met) on the dark surface.
    opt["visualMap"] = dict(
        min=0, max=1, show=False,
        inRange=dict(color=["#1f2937", "#184f95", "#2a78d6", "#86b6ef"]),
    )
    opt["series"] = [dict(
        type="heatmap",
        data=data,
        label=dict(show=True, color="#ffffff", fontFamily=_FONT, fontSize=11),
        itemStyle=dict(borderWidth=2, borderColor="#0a0a0a"),
    )]
    return opt


# Model / run series: categorical slots tuned for the dark surface, in fixed
# order, each with its own marker so identity is never colour alone.
_SERIES_COLOURS = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
_SERIES_SYMBOLS = ["circle", "rect", "diamond", "triangle", "roundRect", "pin", "arrow", "circle"]


def _fmt(v: float) -> str:
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    if abs(v) >= 1:
        return f"{v:,.2f}"
    return f"{v:.4f}"


def spread_by_platform(
    df: pd.DataFrame,
    metric: str,
    metric_label: str,
    series_col: str = "series",
    log: bool = False,
    title: str = "",
) -> dict[str, Any]:
    """Median, range and every repeat of *metric* per platform, one series
    per value of *series_col* (a run or model).

    Averages hide a 2x outlier among three repeats; this shows each repeat.
    Unknown values (NaN) are left out and the tooltip says how many repeats
    the median covers.
    """
    platform_ids = sorted(df["platform_id"].unique())
    names = [get_platform_name(p) for p in platform_ids]
    series_keys = list(dict.fromkeys(df[series_col]))
    m = len(series_keys)
    width = min(0.6, 0.18 * m)

    series: list[dict[str, Any]] = []
    for j, key in enumerate(series_keys[: len(_SERIES_COLOURS)]):
        colour = _SERIES_COLOURS[j]
        symbol = _SERIES_SYMBOLS[j]
        offset = (j - (m - 1) / 2) * (width / max(m - 1, 1)) if m > 1 else 0.0
        ranges: list[Any] = []
        repeats: list[dict[str, Any]] = []
        medians: list[dict[str, Any]] = []
        for i, pid in enumerate(platform_ids):
            sub = df[(df[series_col] == key) & (df["platform_id"] == pid)]
            vals = [float(v) for v in sub[metric] if pd.notna(v) and (not log or v > 0)]
            if not vals:
                continue
            x = i + offset
            med = float(pd.Series(vals).median())
            ranges += [[x, min(vals)], [x, max(vals)], "-"]
            for r, v in zip(sub["repeat_index"], sub[metric]):
                if pd.notna(v) and (not log or v > 0):
                    repeats.append(dict(
                        value=[x, float(v)],
                        tooltip=dict(formatter=f"{key} · {names[i]}<br/>repeat {int(r or 0) + 1}: {_fmt(float(v))}"),
                    ))
            medians.append(dict(
                value=[x, med],
                tooltip=dict(formatter=(
                    f"{key} · {names[i]}<br/>median {_fmt(med)}"
                    f" (range {_fmt(min(vals))}–{_fmt(max(vals))}, {len(vals)} of {len(sub)} repeats known)"
                )),
            ))
        # Same name on all three series so the legend toggles them together.
        series += [
            dict(type="line", name=key, xAxisIndex=1, data=ranges, symbol="none", silent=True,
                 itemStyle=dict(color=colour), lineStyle=dict(color=colour, width=2),
                 tooltip=dict(show=False), connectNulls=False),
            dict(type="scatter", name=key, xAxisIndex=1, data=repeats, symbol="emptyCircle",
                 symbolSize=7, itemStyle=dict(color=colour)),
            dict(type="scatter", name=key, xAxisIndex=1, data=medians, symbol=symbol,
                 symbolSize=12, itemStyle=dict(color=colour, borderColor="#0a0a0a", borderWidth=1.5), z=3),
        ]

    opt = _base_option(title)
    opt["tooltip"] = {**_TOOLTIP_DEFAULTS, "trigger": "item"}
    opt["legend"] = {**_LEGEND_DEFAULTS, "data": [
        dict(name=k, icon=_SERIES_SYMBOLS[j]) for j, k in enumerate(series_keys[: len(_SERIES_COLOURS)])
    ]}
    opt["grid"] = dict(left=80, right=20, top=45, bottom=60)
    # A category axis for the labels and a hidden value axis on the same
    # span for the offset points: category i sits at value i.
    opt["xAxis"] = [
        {**_axis_defaults(), "type": "category", "data": names,
         "axisLabel": {**_axis_defaults()["axisLabel"], "interval": 0}},
        {"type": "value", "min": -0.5, "max": len(names) - 0.5, "show": False},
    ]
    opt["yAxis"] = {
        **_axis_defaults(),
        "type": "log" if log else "value",
        # Keep the axis at the plot edge, not at x = 0 of the hidden axis.
        "axisLine": {**_axis_defaults()["axisLine"], "onZero": False},
        "name": metric_label + (" (log)" if log else ""),
        "nameLocation": "middle",
        "nameGap": 60,
    }
    opt["series"] = series
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
