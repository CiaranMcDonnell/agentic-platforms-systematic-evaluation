"""
Scoring Page — Manual rubric-based scoring for each platform/story pair.

Displays execution evidence, an interactive trace viewer, and a form
with sliders for each of the six DESMET scoring dimensions.
"""

from __future__ import annotations

import streamlit as st

from desmet.dashboard.data import (
    SCORING_DIMENSIONS,
    SCORING_RUBRIC,
    get_platform_ids,
    get_platform_name,
    is_story_scored,
    list_trace_files,
    load_results_raw,
    load_trace,
    save_results,
    update_story_scores,
)


def render() -> None:
    """Render the Platform Scoring page."""

    st.title("Platform Scoring")

    # ------------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------------
    data = load_results_raw()
    platform_ids = get_platform_ids(data)

    if not platform_ids:
        st.warning("No platforms found in results. Run evaluations first.")
        return

    # ------------------------------------------------------------------
    # Sidebar selectors
    # ------------------------------------------------------------------
    selected_platform = st.sidebar.selectbox(
        "Platform",
        options=platform_ids,
        format_func=get_platform_name,
    )

    # Build story list for the selected platform
    pdata = data.get("platforms", {}).get(selected_platform, {})
    story_metrics_list = pdata.get("story_metrics", [])
    story_ids = [sm.get("story_id", "unknown") for sm in story_metrics_list]

    if not story_ids:
        st.info(
            f"No stories found for **{get_platform_name(selected_platform)}**. "
            "Run evaluations first."
        )
        return

    selected_story = st.sidebar.selectbox("Story", options=story_ids)

    # ------------------------------------------------------------------
    # Find the story_metrics dict for the selected story
    # ------------------------------------------------------------------
    story_metrics: dict | None = None
    for sm in story_metrics_list:
        if sm.get("story_id") == selected_story:
            story_metrics = sm
            break

    if story_metrics is None:
        st.error(f"Story metrics not found for `{selected_story}`.")
        return

    # ------------------------------------------------------------------
    # Scored badge
    # ------------------------------------------------------------------
    if is_story_scored(story_metrics):
        st.success("This story has been scored.")
    else:
        st.info("This story has not yet been scored.")

    # ------------------------------------------------------------------
    # Execution Evidence
    # ------------------------------------------------------------------
    st.subheader("Execution Evidence")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Wall Clock", f"{story_metrics.get('wall_clock_seconds', 0):.1f}s")
    col2.metric("Iterations", story_metrics.get("iterations", 0))
    col3.metric("Tool Calls", story_metrics.get("tool_calls", 0))
    col4.metric("Success", "Yes" if story_metrics.get("success", False) else "No")

    # ------------------------------------------------------------------
    # Trace Viewer
    # ------------------------------------------------------------------
    st.subheader("Trace Viewer")

    trace_files = list_trace_files(selected_platform, selected_story)

    if trace_files:
        # Show the most recent trace file
        most_recent_trace = trace_files[-1]

        with st.expander(f"Trace: {most_recent_trace.name}", expanded=False):
            trace_data = load_trace(most_recent_trace)
            messages = trace_data.get("messages", [])

            if not messages:
                st.caption("No messages in this trace.")
            else:
                for msg in messages:
                    role = msg.get("role", "system")
                    content = msg.get("content", "")
                    timestamp = msg.get("timestamp", "")

                    # Truncate long content
                    display_content = content
                    if len(content) > 500:
                        display_content = content[:500] + "..."

                    if role == "tool":
                        st.caption(f"Tool — {timestamp}" if timestamp else "Tool")
                        st.code(display_content, language="text")
                    elif role in ("human", "ai"):
                        chat_role = "user" if role == "human" else "assistant"
                        with st.chat_message(chat_role):
                            if timestamp:
                                st.caption(timestamp)
                            st.markdown(display_content)
                    else:
                        # system or other roles
                        st.caption(f"{role} — {timestamp}" if timestamp else role)
                        st.text(display_content)
    else:
        st.caption("No trace files available for this platform/story pair.")

    # ------------------------------------------------------------------
    # Scoring Form
    # ------------------------------------------------------------------
    st.subheader("Scoring Form")

    with st.form("scoring_form"):
        scores: dict[str, int] = {}
        notes: dict[str, str] = {}

        for dim in SCORING_DIMENSIONS:
            label = dim.replace("_", " ").title()
            rubric = SCORING_RUBRIC.get(dim, {})
            help_text = " | ".join(
                f"{level}: {desc}" for level, desc in sorted(rubric.items())
            )

            st.markdown(f"**{label}**")

            # Pre-fill with existing score if already scored
            existing_score = story_metrics.get(f"{dim}_score", 0)
            existing_notes = (story_metrics.get("scoring_notes") or {}).get(dim, "")

            scores[dim] = st.slider(
                label,
                min_value=0,
                max_value=3,
                value=int(existing_score),
                help=help_text,
                key=f"slider_{dim}",
                label_visibility="collapsed",
            )

            notes[dim] = st.text_input(
                f"{label} Notes",
                value=existing_notes,
                placeholder=f"Optional notes for {label.lower()}...",
                key=f"notes_{dim}",
                label_visibility="collapsed",
            )

        submitted = st.form_submit_button("Save Scores", type="primary")

        if submitted:
            update_story_scores(
                data,
                selected_platform,
                selected_story,
                scores,
                notes,
            )
            save_results(data)
            st.success("Scores saved successfully!")
            st.rerun()
