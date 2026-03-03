"""Overview page for the DESMET Evaluation Dashboard.

Shows scoring progress, platform rankings, completion rates, and a
DESMET dimensions radar chart.
"""

from __future__ import annotations

import streamlit as st

from desmet.dashboard.charts import (
    bar_completion_rates,
    bar_platform_rankings,
    radar_dimensions,
)
from desmet.dashboard.data import (
    get_dimension_scores_df,
    get_platform_ids,
    get_platform_name,
    get_platform_summary_df,
    get_scoring_progress,
    load_results_raw,
)


def render() -> None:
    """Build the Overview page."""
    st.title("DESMET Evaluation Overview")

    # Reload button -- clears all cached data so the dashboard refreshes.
    if st.button("Reload data"):
        st.cache_data.clear()

    # Load raw results (intentionally uncached -- always fresh).
    data = load_results_raw()
    platform_ids = get_platform_ids(data)

    if not platform_ids:
        st.warning("No platform results found. Run evaluations first.")
        return

    # ------------------------------------------------------------------
    # Scoring Progress
    # ------------------------------------------------------------------
    st.header("Scoring Progress")

    progress = get_scoring_progress(data)
    cols = st.columns(min(len(platform_ids), 4))
    for idx, pid in enumerate(platform_ids):
        scored, total = progress.get(pid, (0, 0))
        with cols[idx % len(cols)]:
            st.metric(
                label=get_platform_name(pid),
                value=f"{scored}/{total}",
            )
            st.progress(scored / total if total > 0 else 0.0)

    # ------------------------------------------------------------------
    # Rankings Table
    # ------------------------------------------------------------------
    st.header("Rankings")

    summary_df = get_platform_summary_df(data)

    table_df = (
        summary_df.sort_values("overall_score", ascending=False)
        .reset_index(drop=True)
        .assign(
            Score=lambda df: df["overall_score"].map(lambda v: f"{v:.1f}/5"),
            Completion=lambda df: df["completion_rate"].map(
                lambda v: f"{v * 100:.0f}%"
            ),
        )
        .rename(
            columns={
                "platform_name": "Platform",
                "category": "Category",
            }
        )[["Platform", "Category", "Score", "Completion"]]
    )

    st.dataframe(table_df, width="stretch", hide_index=True)

    # ------------------------------------------------------------------
    # Charts: Rankings & Completion side-by-side
    # ------------------------------------------------------------------
    left, right = st.columns(2)

    with left:
        fig_rankings = bar_platform_rankings(summary_df, title="Platform Rankings")
        st.plotly_chart(fig_rankings, width="stretch", key="overview_rankings")

    with right:
        fig_completion = bar_completion_rates(
            summary_df, title="Story Completion Rates"
        )
        st.plotly_chart(
            fig_completion, width="stretch", key="overview_completion"
        )

    # ------------------------------------------------------------------
    # DESMET Dimensions Radar
    # ------------------------------------------------------------------
    st.header("DESMET Dimensions")

    dim_df = get_dimension_scores_df(data)

    if dim_df.empty:
        st.info("No dimension scores available yet.")
    else:
        dim_dict: dict[str, dict[str, float]] = {}
        for _, row in dim_df.iterrows():
            pid = row["platform_id"]
            dim_dict.setdefault(pid, {})[row["dimension"]] = row["score"]

        fig_radar = radar_dimensions(dim_dict, title="DESMET Dimension Scores")
        st.plotly_chart(fig_radar, width="stretch", key="overview_radar")
