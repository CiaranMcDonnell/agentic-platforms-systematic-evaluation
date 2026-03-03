"""
DESMET Evaluation Dashboard — Entry Point

Launch with: streamlit run src/desmet/dashboard/app.py
"""

import streamlit as st

st.set_page_config(
    page_title="DESMET Evaluation Dashboard",
    page_icon=":bar_chart:",
    layout="wide",
)


def overview_page():
    from desmet.dashboard.pages.p01_overview import render
    render()


def scoring_page():
    from desmet.dashboard.pages.p02_scoring import render
    render()


def comparison_page():
    from desmet.dashboard.pages.p03_comparison import render
    render()


def story_detail_page():
    from desmet.dashboard.pages.p04_story_detail import render
    render()


def export_page():
    from desmet.dashboard.pages.p05_export import render
    render()


pages = st.navigation([
    st.Page(overview_page, title="Overview", icon=":material/dashboard:"),
    st.Page(scoring_page, title="Scoring", icon=":material/rate_review:"),
    st.Page(comparison_page, title="Comparison", icon=":material/compare:"),
    st.Page(story_detail_page, title="Story Detail", icon=":material/article:"),
    st.Page(export_page, title="Export", icon=":material/download:"),
])

pages.run()
