"""Comparison page for the DESMET Evaluation Dashboard.

Allows the user to select two or more platforms and compare them
across DESMET dimensions, per-dimension bar charts, story-level
metrics, efficiency breakdowns, and category averages.
"""

from __future__ import annotations

import streamlit as st

from desmet.dashboard.charts import (
    bar_dimension_comparison,
    bar_efficiency_breakdown,
    bar_story_comparison,
    radar_dimensions,
)
from desmet.dashboard.data import (
    get_dimension_scores_df,
    get_platform_category,
    get_platform_ids,
    get_platform_name,
    get_story_metrics_df,
    load_results_raw,
)


def render() -> None:
    """Build the Comparison page."""
    st.title("Platform Comparison")

    # ------------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------------
    data = load_results_raw()
    all_platform_ids = get_platform_ids(data)

    if not all_platform_ids:
        st.warning("No platform results found. Run evaluations first.")
        return

    # ------------------------------------------------------------------
    # Platform multiselect
    # ------------------------------------------------------------------
    selected_ids: list[str] = st.multiselect(
        "Select platforms to compare",
        options=all_platform_ids,
        default=all_platform_ids,
        format_func=get_platform_name,
    )

    if len(selected_ids) < 2:
        st.info("Please select at least 2 platforms to compare.")
        return

    # ------------------------------------------------------------------
    # Filter DataFrames to selected platforms
    # ------------------------------------------------------------------
    dim_df = get_dimension_scores_df(data)
    story_df = get_story_metrics_df(data)

    if not dim_df.empty:
        dim_df = dim_df[dim_df["platform_id"].isin(selected_ids)].copy()
    if not story_df.empty:
        story_df = story_df[story_df["platform_id"].isin(selected_ids)].copy()

    # ------------------------------------------------------------------
    # Dimension Comparison -- Radar Chart
    # ------------------------------------------------------------------
    st.header("Dimension Comparison")

    if dim_df.empty:
        st.info("No dimension scores available yet.")
    else:
        # Build {platform_id: {dimension: score}} dict for radar chart
        dim_dict: dict[str, dict[str, float]] = {}
        for _, row in dim_df.iterrows():
            pid = row["platform_id"]
            dim_dict.setdefault(pid, {})[row["dimension"]] = row["score"]

        fig_radar = radar_dimensions(dim_dict, title="DESMET Dimension Scores")
        st.plotly_chart(
            fig_radar, width="stretch", key="comparison_radar"
        )

        # --------------------------------------------------------------
        # Per-dimension bar charts in a 3-column grid
        # --------------------------------------------------------------
        st.subheader("Per-Dimension Breakdown")

        dimensions = dim_df["dimension"].unique().tolist()
        for row_start in range(0, len(dimensions), 3):
            row_dims = dimensions[row_start : row_start + 3]
            cols = st.columns(len(row_dims))
            for col, dim_name in zip(cols, row_dims):
                with col:
                    fig_bar = bar_dimension_comparison(
                        dim_df,
                        dim_name,
                        title=dim_name.replace("_", " ").title(),
                    )
                    st.plotly_chart(
                        fig_bar,
                        width="stretch",
                        key=f"comparison_dim_{dim_name}",
                    )

    # ------------------------------------------------------------------
    # Story-Level Comparison
    # ------------------------------------------------------------------
    st.header("Story-Level Comparison")

    if story_df.empty:
        st.info("No story metrics available yet.")
    else:
        metric_options = ["wall_clock_seconds", "iterations", "tool_calls"]
        selected_metric = st.selectbox(
            "Metric to compare",
            options=metric_options,
            format_func=lambda m: m.replace("_", " ").title(),
        )

        fig_story = bar_story_comparison(
            story_df,
            selected_metric,
            title=f"{selected_metric.replace('_', ' ').title()} by Story",
        )
        st.plotly_chart(
            fig_story, width="stretch", key="comparison_story"
        )

    # ------------------------------------------------------------------
    # Efficiency Breakdown
    # ------------------------------------------------------------------
    st.header("Efficiency Breakdown")

    if story_df.empty:
        st.info("No story metrics available for efficiency analysis.")
    else:
        fig_eff = bar_efficiency_breakdown(
            story_df, title="Average Efficiency Metrics"
        )
        st.plotly_chart(
            fig_eff, width="stretch", key="comparison_efficiency"
        )

    # ------------------------------------------------------------------
    # Category Averages
    # ------------------------------------------------------------------
    st.header("Category Averages")

    if dim_df.empty:
        st.info("No dimension scores available for category analysis.")
    else:
        # Add category column and compute averages
        dim_df_cat = dim_df.copy()
        dim_df_cat["category"] = dim_df_cat["platform_id"].map(
            get_platform_category
        )

        cat_avg = (
            dim_df_cat.groupby(["category", "dimension"])["score"]
            .mean()
            .reset_index()
        )

        categories = cat_avg["category"].unique().tolist()
        cat_cols = st.columns(len(categories))

        for col, category in zip(cat_cols, categories):
            with col:
                cat_label = category.replace("_", " ").title()
                st.subheader(cat_label)

                cat_rows = cat_avg[cat_avg["category"] == category]
                for _, row in cat_rows.iterrows():
                    dim_label = row["dimension"].replace("_", " ").title()
                    st.text(f"{dim_label}: {row['score']:.2f}")
