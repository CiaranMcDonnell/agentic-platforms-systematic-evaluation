"""Story Detail page for the DESMET Evaluation Dashboard.

Shows per-story performance comparison across platforms, metric charts,
and scrollable execution traces with chat-style message rendering.
"""

from __future__ import annotations

import streamlit as st

from desmet.dashboard.charts import bar_story_comparison
from desmet.dashboard.data import (
    SCORING_DIMENSIONS,
    get_platform_ids,
    get_platform_name,
    get_story_metrics_df,
    list_trace_files,
    load_results_raw,
    load_trace,
)


def _render_trace_messages(trace: dict) -> None:
    """Render trace messages inside a scrollable container.

    Message roles are mapped to Streamlit chat primitives:
    - ``human`` -> ``st.chat_message("user")``
    - ``ai`` -> ``st.chat_message("assistant")``
    - ``tool`` -> ``st.code``
    - ``system`` -> ``st.caption``

    Content is truncated to 1000 characters for readability.
    """
    messages = trace.get("messages", [])
    if not messages:
        st.info("No messages in this trace.")
        return

    with st.container(height=400):
        for msg in messages:
            role = msg.get("role", msg.get("type", "unknown"))
            content = str(msg.get("content", ""))
            if len(content) > 1000:
                content = content[:1000] + "..."

            if role == "human":
                with st.chat_message("user"):
                    st.markdown(content)
            elif role == "ai":
                with st.chat_message("assistant"):
                    st.markdown(content)
            elif role == "tool":
                st.code(content)
            elif role == "system":
                st.caption(content)
            else:
                st.text(f"[{role}] {content}")


def render() -> None:
    """Build the Story Detail page."""
    st.title("Story Detail")

    data = load_results_raw()
    platform_ids = get_platform_ids(data)

    if not platform_ids:
        st.warning("No platform results found. Run evaluations first.")
        return

    metrics_df = get_story_metrics_df(data)

    # ------------------------------------------------------------------
    # Story Selector
    # ------------------------------------------------------------------
    if metrics_df.empty or "story_id" not in metrics_df.columns:
        st.warning("No story metrics available yet.")
        return

    all_story_ids = sorted(metrics_df["story_id"].dropna().unique().tolist())
    if not all_story_ids:
        st.warning("No stories found in the metrics data.")
        return

    selected_story = st.selectbox("Select Story", all_story_ids)

    # Filter to the selected story
    story_df = metrics_df[metrics_df["story_id"] == selected_story].copy()

    if story_df.empty:
        st.info(f"No metrics recorded for story **{selected_story}**.")
        return

    # ------------------------------------------------------------------
    # Platform Performance Table
    # ------------------------------------------------------------------
    st.header("Platform Performance")

    # Build display columns: base columns + any scoring dimension columns present
    base_cols = ["platform_name", "success", "wall_clock_seconds", "iterations", "tool_calls"]
    score_cols = [
        f"{dim}_score"
        for dim in SCORING_DIMENSIONS
        if f"{dim}_score" in story_df.columns
    ]
    display_cols = [c for c in base_cols + score_cols if c in story_df.columns]

    # Rename for display
    rename_map = {
        "platform_name": "Platform",
        "success": "Success",
        "wall_clock_seconds": "Wall Clock (s)",
        "iterations": "Iterations",
        "tool_calls": "Tool Calls",
    }
    for dim in SCORING_DIMENSIONS:
        col = f"{dim}_score"
        if col in display_cols:
            rename_map[col] = dim.replace("_", " ").title()

    table_df = story_df[display_cols].rename(columns=rename_map).reset_index(drop=True)
    st.dataframe(table_df, use_container_width=True, hide_index=True)

    # ------------------------------------------------------------------
    # Metric Comparison Charts
    # ------------------------------------------------------------------
    st.header("Metric Comparison")

    left, right = st.columns(2)

    with left:
        if "wall_clock_seconds" in story_df.columns:
            fig_time = bar_story_comparison(
                story_df, "wall_clock_seconds", title="Wall Clock Time (s)"
            )
            st.plotly_chart(
                fig_time, use_container_width=True, key="story_detail_wall_clock"
            )
        else:
            st.info("No wall clock data available.")

    with right:
        if "iterations" in story_df.columns:
            fig_iter = bar_story_comparison(
                story_df, "iterations", title="Iterations"
            )
            st.plotly_chart(
                fig_iter, use_container_width=True, key="story_detail_iterations"
            )
        else:
            st.info("No iteration data available.")

    # ------------------------------------------------------------------
    # Execution Traces
    # ------------------------------------------------------------------
    st.header("Execution Traces")

    # Collect platforms that have trace files for this story
    platforms_with_traces: list[tuple[str, str, list]] = []
    for pid in platform_ids:
        pname = get_platform_name(pid)
        traces = list_trace_files(pid, selected_story)
        if traces:
            platforms_with_traces.append((pid, pname, traces))

    if not platforms_with_traces:
        st.info(
            f"No execution traces found for story **{selected_story}**. "
            "Traces are stored in `results/logs/<platform>/<story>/`."
        )
        return

    tab_labels = [pname for _, pname, _ in platforms_with_traces]
    tabs = st.tabs(tab_labels)

    for tab, (pid, pname, trace_files) in zip(tabs, platforms_with_traces):
        with tab:
            # Load the most recent trace (last file in sorted list)
            trace_path = trace_files[-1]
            trace = load_trace(trace_path)

            # Caption with execution metadata
            exec_id = trace.get("execution_id", "N/A")
            status = trace.get("status", "N/A")
            iterations = trace.get("iterations", "N/A")
            tool_calls = trace.get("tool_calls", "N/A")
            st.caption(
                f"Execution: `{exec_id}` | Status: **{status}** | "
                f"Iterations: **{iterations}** | Tool calls: **{tool_calls}**"
            )

            _render_trace_messages(trace)
