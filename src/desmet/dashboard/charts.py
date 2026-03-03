"""DESMET Dashboard - reusable Plotly chart builders.

Every public function returns a ``plotly.graph_objects.Figure``.
No Streamlit imports - pure Plotly so charts can be embedded in any
front-end or exported to static images.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .data import get_platform_colour, get_platform_name

# ---------------------------------------------------------------------------
# Shared theme — designed for Streamlit dark mode
# ---------------------------------------------------------------------------

_BG = "rgba(0,0,0,0)"  # Transparent — inherits Streamlit's theme
_GRID = "rgba(255,255,255,0.08)"  # Subtle grid
_TEXT = "#e0e0e0"
_AXIS_TEXT = "#b0b0b0"

_LAYOUT_DEFAULTS: dict = dict(
    font=dict(family="Inter, -apple-system, sans-serif", size=13, color=_TEXT),
    plot_bgcolor=_BG,
    paper_bgcolor=_BG,
    margin=dict(l=10, r=10, t=60, b=10),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        borderwidth=0,
        font=dict(size=12, color=_TEXT),
    ),
    hoverlabel=dict(
        bgcolor="#1e1e2e",
        font_size=12,
        font_color="#e0e0e0",
        bordercolor="rgba(255,255,255,0.1)",
    ),
)


def _apply_defaults(fig: go.Figure, title: str = "") -> go.Figure:
    """Apply shared theme and optional title to *fig*."""
    layout_update: dict = {**_LAYOUT_DEFAULTS}
    if title:
        layout_update["title"] = dict(
            text=title,
            font=dict(size=16, color="#ffffff"),
            x=0.0,
            xanchor="left",
        )
    fig.update_layout(**layout_update)
    return fig


def _style_cartesian(fig: go.Figure) -> go.Figure:
    """Style x/y axes for cartesian charts."""
    axis_style = dict(
        gridcolor=_GRID,
        zerolinecolor="rgba(255,255,255,0.15)",
        tickfont=dict(size=12, color=_AXIS_TEXT),
        title=dict(font=dict(size=13, color=_TEXT)),
    )
    fig.update_xaxes(**axis_style)
    fig.update_yaxes(**axis_style)
    return fig


# ---------------------------------------------------------------------------
# 1. Radar - DESMET dimension scores
# ---------------------------------------------------------------------------


def radar_dimensions(
    dimension_scores: dict[str, dict[str, float]],
    title: str = "DESMET Dimension Comparison",
) -> go.Figure:
    """Polar radar chart of dimension scores per platform."""
    fig = go.Figure()

    all_dims: list[str] = []
    for scores in dimension_scores.values():
        for dim in scores:
            if dim not in all_dims:
                all_dims.append(dim)

    theta_labels = [d.replace("_", " ").title() for d in all_dims]

    for platform_id, scores in dimension_scores.items():
        values = [scores.get(d, 0.0) for d in all_dims]
        r = values + [values[0]]
        theta = theta_labels + [theta_labels[0]]
        colour = get_platform_colour(platform_id)
        # Convert hex to rgba for transparent fill
        r_val = int(colour[1:3], 16)
        g_val = int(colour[3:5], 16)
        b_val = int(colour[5:7], 16)
        fill_colour = f"rgba({r_val},{g_val},{b_val},0.15)"

        fig.add_trace(
            go.Scatterpolar(
                r=r,
                theta=theta,
                fill="toself",
                fillcolor=fill_colour,
                name=get_platform_name(platform_id),
                marker=dict(color=colour, size=6),
                line=dict(color=colour, width=2.5),
            )
        )

    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(
                visible=True,
                range=[0, 5],
                tickvals=[1, 2, 3, 4, 5],
                gridcolor="rgba(255,255,255,0.1)",
                tickfont=dict(size=10, color=_AXIS_TEXT),
                linecolor="rgba(255,255,255,0.05)",
            ),
            angularaxis=dict(
                gridcolor="rgba(255,255,255,0.1)",
                tickfont=dict(size=12, color=_TEXT),
                linecolor="rgba(255,255,255,0.05)",
            ),
        ),
        showlegend=True,
        legend=dict(x=1.15, y=1.0),
    )

    return _apply_defaults(fig, title)


# ---------------------------------------------------------------------------
# 2. Horizontal bar - platform overall rankings
# ---------------------------------------------------------------------------


def bar_platform_rankings(
    summary_df: pd.DataFrame,
    title: str = "Platform Rankings",
) -> go.Figure:
    """Horizontal bar chart of platforms ranked by ``overall_score``."""
    df = summary_df.sort_values("overall_score", ascending=True).reset_index(drop=True)
    colours = [get_platform_colour(pid) for pid in df["platform_id"]]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=df["platform_name"],
            x=df["overall_score"],
            orientation="h",
            marker=dict(
                color=colours,
                line=dict(width=0),
                cornerradius=4,
            ),
            text=[f"  {v:.1f}" for v in df["overall_score"]],
            textposition="outside",
            textfont=dict(size=13, color=_TEXT),
        )
    )
    fig.update_layout(
        xaxis=dict(range=[0, 5.5], title="Score (0–5)"),
        yaxis=dict(title="", automargin=True),
        height=max(200, len(df) * 60 + 80),
    )

    return _style_cartesian(_apply_defaults(fig, title))


# ---------------------------------------------------------------------------
# 3. Horizontal bar - completion rates
# ---------------------------------------------------------------------------


def bar_completion_rates(
    summary_df: pd.DataFrame,
    title: str = "Completion Rates",
) -> go.Figure:
    """Horizontal bar chart of story completion rates per platform."""
    df = summary_df.sort_values("completion_rate", ascending=True).reset_index(drop=True)
    pct = df["completion_rate"] * 100
    colours = [get_platform_colour(pid) for pid in df["platform_id"]]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=df["platform_name"],
            x=pct,
            orientation="h",
            marker=dict(
                color=colours,
                line=dict(width=0),
                cornerradius=4,
            ),
            text=[f"  {v:.0f}%" for v in pct],
            textposition="outside",
            textfont=dict(size=13, color=_TEXT),
        )
    )
    fig.update_layout(
        xaxis=dict(range=[0, 115], title="Completion (%)"),
        yaxis=dict(title="", automargin=True),
        height=max(200, len(df) * 60 + 80),
    )

    return _style_cartesian(_apply_defaults(fig, title))


# ---------------------------------------------------------------------------
# 4. Grouped bar - story-level metric comparison
# ---------------------------------------------------------------------------


def bar_story_comparison(
    metrics_df: pd.DataFrame,
    metric: str,
    title: str = "",
) -> go.Figure:
    """Grouped bar chart comparing a single *metric* across stories and platforms."""
    fig = go.Figure()

    for pid in metrics_df["platform_id"].unique():
        pdf = metrics_df[metrics_df["platform_id"] == pid]
        fig.add_trace(
            go.Bar(
                x=pdf["story_id"],
                y=pdf[metric],
                name=get_platform_name(pid),
                marker=dict(
                    color=get_platform_colour(pid),
                    cornerradius=4,
                ),
            )
        )

    y_label = metric.replace("_", " ").title()
    fig.update_layout(
        barmode="group",
        bargap=0.25,
        bargroupgap=0.1,
        xaxis=dict(title="Story"),
        yaxis=dict(title=y_label),
    )

    return _style_cartesian(_apply_defaults(fig, title or f"{y_label} by Story"))


# ---------------------------------------------------------------------------
# 5. Grouped bar - efficiency breakdown (wall_clock, iterations, tool_calls)
# ---------------------------------------------------------------------------


def bar_efficiency_breakdown(
    metrics_df: pd.DataFrame,
    title: str = "Efficiency Breakdown",
) -> go.Figure:
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

    fig = go.Figure()
    for col, label, colour in metric_config:
        fig.add_trace(
            go.Bar(
                x=agg["platform_name"],
                y=agg[col],
                name=label,
                marker=dict(color=colour, cornerradius=4),
            )
        )

    fig.update_layout(
        barmode="group",
        bargap=0.25,
        bargroupgap=0.1,
        yaxis=dict(title="Average Value"),
    )

    return _style_cartesian(_apply_defaults(fig, title))


# ---------------------------------------------------------------------------
# 6. Heatmap - criteria pass / fail / N/A
# ---------------------------------------------------------------------------


def heatmap_criteria(
    criteria_data: dict[str, dict[str, bool | None]],
    title: str = "Acceptance Criteria",
) -> go.Figure:
    """Heatmap showing pass/fail/N-A for every platform-criterion pair."""
    platform_ids = list(criteria_data.keys())
    platform_names = [get_platform_name(pid) for pid in platform_ids]

    all_criteria: list[str] = []
    for crit_dict in criteria_data.values():
        for cid in crit_dict:
            if cid not in all_criteria:
                all_criteria.append(cid)

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

    colorscale = [
        [0.0, "#ef4444"], [0.25, "#ef4444"],
        [0.25, "#4b5563"], [0.75, "#4b5563"],
        [0.75, "#22c55e"], [1.0, "#22c55e"],
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
            textfont=dict(size=12, color="white"),
            colorscale=colorscale,
            showscale=False,
            zmin=0,
            zmax=1,
            xgap=2,
            ygap=2,
        )
    )
    fig.update_layout(yaxis=dict(autorange="reversed", automargin=True))

    return _apply_defaults(fig, title)


# ---------------------------------------------------------------------------
# 7. Horizontal bar - single dimension comparison
# ---------------------------------------------------------------------------


def bar_dimension_comparison(
    dimension_df: pd.DataFrame,
    dimension: str,
    title: str = "",
) -> go.Figure:
    """Horizontal bar chart for a single DESMET dimension."""
    df = dimension_df[dimension_df["dimension"] == dimension].copy()
    df = df.sort_values("score", ascending=True).reset_index(drop=True)

    dim_title = dimension.replace("_", " ").title()
    colours = [get_platform_colour(pid) for pid in df["platform_id"]]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=df["platform_name"],
            x=df["score"],
            orientation="h",
            marker=dict(
                color=colours,
                line=dict(width=0),
                cornerradius=4,
            ),
            text=[f"  {v:.1f}" for v in df["score"]],
            textposition="outside",
            textfont=dict(size=13, color=_TEXT),
        )
    )
    fig.update_layout(
        xaxis=dict(range=[0, 5.5], title=dim_title),
        yaxis=dict(title="", automargin=True),
        height=max(200, len(df) * 60 + 80),
    )

    return _style_cartesian(_apply_defaults(fig, title or dim_title))
