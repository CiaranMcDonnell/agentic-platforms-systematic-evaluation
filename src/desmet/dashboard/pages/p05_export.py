"""Export page for the DESMET Evaluation Dashboard.

Allows batch export of dashboard charts as SVG or PNG files for
inclusion in the Typst report.
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
import streamlit as st

from desmet.dashboard.charts import (
    bar_completion_rates,
    bar_efficiency_breakdown,
    bar_platform_rankings,
    bar_story_comparison,
    radar_dimensions,
)
from desmet.dashboard.data import (
    FIGURES_DIR,
    get_dimension_scores_df,
    get_platform_summary_df,
    get_story_metrics_df,
    load_results_raw,
)
from desmet.dashboard.export import PRESETS, export_figure

# Human-readable labels for story-level metrics.
_METRIC_LABELS: dict[str, str] = {
    "wall_clock_seconds": "Wall Clock (s)",
    "iterations": "Iterations",
    "tool_calls": "Tool Calls",
}


def _build_chart_registry(
    data: dict[str, Any],
) -> list[tuple[str, str, go.Figure]]:
    """Build the list of exportable charts.

    Returns a list of ``(key, label, figure)`` tuples where *key* is used as
    the filename stem, *label* is the human-readable chart title, and *figure*
    is the Plotly figure object.
    """
    summary_df = get_platform_summary_df(data)
    metrics_df = get_story_metrics_df(data)
    dim_df = get_dimension_scores_df(data)

    registry: list[tuple[str, str, go.Figure]] = []

    # Platform rankings
    registry.append((
        "rankings",
        "Platform Rankings",
        bar_platform_rankings(summary_df),
    ))

    # Completion rates
    registry.append((
        "completion",
        "Completion Rates",
        bar_completion_rates(summary_df),
    ))

    # DESMET radar
    dim_dict: dict[str, dict[str, float]] = {}
    for _, row in dim_df.iterrows():
        pid = row["platform_id"]
        dim_dict.setdefault(pid, {})[row["dimension"]] = row["score"]
    registry.append((
        "radar",
        "DESMET Radar",
        radar_dimensions(dim_dict),
    ))

    # Story-level metric comparisons
    for metric, label in _METRIC_LABELS.items():
        registry.append((
            f"story_{metric}",
            f"Story Comparison \u2014 {label}",
            bar_story_comparison(metrics_df, metric),
        ))

    # Efficiency breakdown
    registry.append((
        "efficiency",
        "Efficiency Breakdown",
        bar_efficiency_breakdown(metrics_df),
    ))

    return registry


def render() -> None:
    """Build the Export Charts page."""
    st.title("Export Charts")
    st.caption(f"Figures will be saved to `{FIGURES_DIR}`")

    data = load_results_raw()
    registry = _build_chart_registry(data)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    col_fmt, col_preset = st.columns(2)

    with col_fmt:
        fmt = st.radio(
            "Format",
            options=["svg", "png"],
            horizontal=True,
        )

    with col_preset:
        preset = st.selectbox(
            "Size preset",
            options=list(PRESETS.keys()),
            format_func=lambda k: f"{k}  ({PRESETS[k]['width']}x{PRESETS[k]['height']})",
        )

    # ------------------------------------------------------------------
    # Chart selection with previews
    # ------------------------------------------------------------------
    selected: list[tuple[str, str, go.Figure]] = []

    for key, label, fig in registry:
        col_check, col_preview = st.columns([1, 5])

        with col_check:
            checked = st.checkbox(label, value=True, key=f"chk_{key}")

        with col_preview:
            st.plotly_chart(fig, width="stretch", key=f"preview_{key}")

        if checked:
            selected.append((key, label, fig))

    # ------------------------------------------------------------------
    # Export button
    # ------------------------------------------------------------------
    if st.button("Export selected charts", type="primary"):
        if not selected:
            st.warning("No charts selected.")
            return

        for key, label, fig in selected:
            path = export_figure(fig, name=key, fmt=fmt, preset=preset)
            st.success(f"Exported **{label}** \u2192 `{path}`")
