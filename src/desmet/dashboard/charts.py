"""DESMET Dashboard - reusable Plotly chart builders.

Every public function returns a ``plotly.graph_objects.Figure``.
No Streamlit imports - pure Plotly so charts can be embedded in any
front-end or exported to static images.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .data import get_platform_colour, get_platform_name

# ---------------------------------------------------------------------------
# Shared layout defaults
# ---------------------------------------------------------------------------

_LAYOUT_DEFAULTS: dict = dict(
    font=dict(size=12),
    plot_bgcolor="white",
    paper_bgcolor="white",
    margin=dict(l=60, r=30, t=50, b=50),
)


def _apply_defaults(fig: go.Figure, title: str = "") -> go.Figure:
    """Apply ``_LAYOUT_DEFAULTS`` and an optional title to *fig*."""
    layout_update: dict = {**_LAYOUT_DEFAULTS}
    if title:
        layout_update["title"] = dict(text=title, font=dict(size=14))
    fig.update_layout(**layout_update)
    return fig


# ---------------------------------------------------------------------------
# 1. Radar - DESMET dimension scores
# ---------------------------------------------------------------------------


def radar_dimensions(
    dimension_scores: dict[str, dict[str, float]],
    title: str = "",
) -> go.Figure:
    """Polar radar chart of dimension scores per platform.

    Parameters
    ----------
    dimension_scores:
        ``{platform_id: {dimension_name: score_0_to_5}}``
    title:
        Optional chart title.
    """
    fig = go.Figure()

    # Collect all dimension names from all platforms (stable order).
    all_dims: list[str] = []
    for scores in dimension_scores.values():
        for dim in scores:
            if dim not in all_dims:
                all_dims.append(dim)

    theta_labels = [d.replace("_", " ").title() for d in all_dims]

    for platform_id, scores in dimension_scores.items():
        values = [scores.get(d, 0.0) for d in all_dims]
        # Close the polygon by appending the first value.
        r = values + [values[0]]
        theta = theta_labels + [theta_labels[0]]

        fig.add_trace(
            go.Scatterpolar(
                r=r,
                theta=theta,
                fill="toself",
                opacity=0.3,
                name=get_platform_name(platform_id),
                marker=dict(color=get_platform_colour(platform_id)),
                line=dict(color=get_platform_colour(platform_id)),
            )
        )

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 5],
                tickvals=[1, 2, 3, 4, 5],
            ),
        ),
    )

    return _apply_defaults(fig, title)


# ---------------------------------------------------------------------------
# 2. Horizontal bar - platform overall rankings
# ---------------------------------------------------------------------------


def bar_platform_rankings(
    summary_df: pd.DataFrame,
    title: str = "",
) -> go.Figure:
    """Horizontal bar chart of platforms ranked by ``overall_score``.

    Parameters
    ----------
    summary_df:
        Must contain columns ``platform_id``, ``platform_name``,
        ``overall_score``.
    title:
        Optional chart title.
    """
    df = summary_df.sort_values("overall_score", ascending=True).reset_index(drop=True)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=df["platform_name"],
            x=df["overall_score"],
            orientation="h",
            marker_color=[get_platform_colour(pid) for pid in df["platform_id"]],
            text=[f"{v:.2f}" for v in df["overall_score"]],
            textposition="outside",
        )
    )
    fig.update_layout(xaxis=dict(range=[0, 5.5]), yaxis=dict(title=""))

    return _apply_defaults(fig, title)


# ---------------------------------------------------------------------------
# 3. Horizontal bar - completion rates
# ---------------------------------------------------------------------------


def bar_completion_rates(
    summary_df: pd.DataFrame,
    title: str = "",
) -> go.Figure:
    """Horizontal bar chart of story completion rates per platform.

    Parameters
    ----------
    summary_df:
        Must contain columns ``platform_id``, ``platform_name``,
        ``completion_rate`` (float 0-1).
    title:
        Optional chart title.
    """
    df = summary_df.sort_values("completion_rate", ascending=True).reset_index(drop=True)
    pct = df["completion_rate"] * 100

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=df["platform_name"],
            x=pct,
            orientation="h",
            marker_color=[get_platform_colour(pid) for pid in df["platform_id"]],
            text=[f"{v:.0f}%" for v in pct],
            textposition="outside",
        )
    )
    fig.update_layout(
        xaxis=dict(range=[0, 110], title="Completion Rate (%)"),
        yaxis=dict(title=""),
    )

    return _apply_defaults(fig, title)


# ---------------------------------------------------------------------------
# 4. Grouped bar - story-level metric comparison
# ---------------------------------------------------------------------------


def bar_story_comparison(
    metrics_df: pd.DataFrame,
    metric: str,
    title: str = "",
) -> go.Figure:
    """Grouped bar chart comparing a single *metric* across stories and platforms.

    Parameters
    ----------
    metrics_df:
        Must contain columns ``platform_id``, ``platform_name``,
        ``story_id``, and the column named by *metric*.
    metric:
        Column name of the metric to plot.
    title:
        Optional chart title.
    """
    fig = go.Figure()

    platform_ids = metrics_df["platform_id"].unique()

    for pid in platform_ids:
        pdf = metrics_df[metrics_df["platform_id"] == pid]
        fig.add_trace(
            go.Bar(
                x=pdf["story_id"],
                y=pdf[metric],
                name=get_platform_name(pid),
                marker_color=get_platform_colour(pid),
            )
        )

    fig.update_layout(barmode="group", xaxis=dict(title="Story"), yaxis=dict(title=metric))

    return _apply_defaults(fig, title)


# ---------------------------------------------------------------------------
# 5. Grouped bar - efficiency breakdown (wall_clock, iterations, tool_calls)
# ---------------------------------------------------------------------------


def bar_efficiency_breakdown(
    metrics_df: pd.DataFrame,
    title: str = "",
) -> go.Figure:
    """Grouped bar chart of averaged efficiency metrics per platform.

    Aggregates ``wall_clock_seconds``, ``iterations``, and ``tool_calls``
    as averages per platform, then plots three groups side by side.

    Parameters
    ----------
    metrics_df:
        Must contain columns ``platform_id``, ``platform_name``,
        ``wall_clock_seconds``, ``iterations``, ``tool_calls``.
    title:
        Optional chart title.
    """
    efficiency_cols = ["wall_clock_seconds", "iterations", "tool_calls"]
    agg = (
        metrics_df.groupby(["platform_id", "platform_name"])[efficiency_cols]
        .mean()
        .reset_index()
    )

    fig = go.Figure()

    metric_labels = {
        "wall_clock_seconds": "Wall Clock (s)",
        "iterations": "Iterations",
        "tool_calls": "Tool Calls",
    }

    for col in efficiency_cols:
        fig.add_trace(
            go.Bar(
                x=agg["platform_name"],
                y=agg[col],
                name=metric_labels[col],
            )
        )

    fig.update_layout(barmode="group", yaxis=dict(title="Average Value"))

    return _apply_defaults(fig, title)


# ---------------------------------------------------------------------------
# 6. Heatmap - criteria pass / fail / N/A
# ---------------------------------------------------------------------------


def heatmap_criteria(
    criteria_data: dict[str, dict[str, bool | None]],
    title: str = "",
) -> go.Figure:
    """Heatmap showing pass/fail/N-A for every platform-criterion pair.

    Parameters
    ----------
    criteria_data:
        ``{platform_id: {criterion_id: True | False | None}}``
    title:
        Optional chart title.
    """
    platform_ids = list(criteria_data.keys())
    platform_names = [get_platform_name(pid) for pid in platform_ids]

    # Collect all criterion IDs (stable order).
    all_criteria: list[str] = []
    for crit_dict in criteria_data.values():
        for cid in crit_dict:
            if cid not in all_criteria:
                all_criteria.append(cid)

    # Build numeric matrix and text matrix.
    # 1 = pass (green), 0 = fail (red), 0.5 = N/A (grey)
    z: list[list[float]] = []
    text: list[list[str]] = []

    for cid in all_criteria:
        row_z: list[float] = []
        row_t: list[str] = []
        for pid in platform_ids:
            val = criteria_data[pid].get(cid)
            if val is True:
                row_z.append(1.0)
                row_t.append("Pass")
            elif val is False:
                row_z.append(0.0)
                row_t.append("Fail")
            else:
                row_z.append(0.5)
                row_t.append("N/A")
        z.append(row_z)
        text.append(row_t)

    # Custom discrete colour scale: red -> grey -> green
    colorscale = [
        [0.0, "#e74c3c"],   # red  (fail)
        [0.25, "#e74c3c"],
        [0.25, "#bdc3c7"],  # grey (N/A)
        [0.75, "#bdc3c7"],
        [0.75, "#2ecc71"],  # green (pass)
        [1.0, "#2ecc71"],
    ]

    criteria_labels = [c.replace("_", " ").title() for c in all_criteria]

    fig = go.Figure()
    fig.add_trace(
        go.Heatmap(
            z=z,
            x=platform_names,
            y=criteria_labels,
            text=text,
            texttemplate="%{text}",
            colorscale=colorscale,
            showscale=False,
            zmin=0,
            zmax=1,
        )
    )
    fig.update_layout(yaxis=dict(autorange="reversed"))

    return _apply_defaults(fig, title)


# ---------------------------------------------------------------------------
# 7. Horizontal bar - single dimension comparison
# ---------------------------------------------------------------------------


def bar_dimension_comparison(
    dimension_df: pd.DataFrame,
    dimension: str,
    title: str = "",
) -> go.Figure:
    """Horizontal bar chart for a single DESMET dimension.

    Parameters
    ----------
    dimension_df:
        Must contain columns ``platform_id``, ``platform_name``,
        ``dimension``, ``score``.
    dimension:
        The dimension value to filter on.
    title:
        Optional chart title.
    """
    df = dimension_df[dimension_df["dimension"] == dimension].copy()
    df = df.sort_values("score", ascending=True).reset_index(drop=True)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=df["platform_name"],
            x=df["score"],
            orientation="h",
            marker_color=[get_platform_colour(pid) for pid in df["platform_id"]],
            text=[f"{v:.2f}" for v in df["score"]],
            textposition="outside",
        )
    )
    fig.update_layout(
        xaxis=dict(range=[0, 5.5], title=dimension.replace("_", " ").title()),
        yaxis=dict(title=""),
    )

    return _apply_defaults(fig, title)
