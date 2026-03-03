# Streamlit Evaluation Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an interactive Streamlit dashboard for scoring agentic platforms and visualising cross-platform comparisons during the DESMET evaluation.

**Architecture:** Flat multi-page Streamlit app under `src/desmet/dashboard/`. A shared `data.py` module loads/saves `results/evaluation_results.json` (the single source of truth). Reusable Plotly chart functions in `charts.py`. Static export via kaleido in `export.py`. Five pages: Overview, Scoring, Comparison, Story Detail, Export.

**Tech Stack:** Streamlit 1.30+, Plotly 5.18+, kaleido 0.2+, pandas (already a dependency)

---

## Important Context

### Existing Data Models (do not duplicate)
- `src/desmet/harness/metrics.py` — `EvaluationMetrics`, `StoryMetrics`, `DimensionScore`, `EvaluationDimension`, `SetupMetrics`, `StageMetrics`
- `src/desmet/harness/story.py` — `UserStory`, `StoryScore`, `StoryResult`, `SCORING_DIMENSIONS`, `SCORING_RUBRIC`, `DifficultyLevel`
- `src/desmet/harness/loader.py` — `load_all_stories()`, `load_story()`
- `config/platforms.yaml` — platform definitions with `id`, `name`, `category`, `runtime`

### Current JSON Format (`results/evaluation_results.json`)
```json
{
  "evaluation_date": "2026-02-10T...",
  "platforms": {
    "langgraph": {
      "platform_id": "langgraph",
      "platform_name": "LangGraph",
      "evaluation_date": "...",
      "setup_metrics": null,
      "stories_total": 4,
      "stories_completed": 4,
      "stories_failed": 0,
      "dimension_scores": [
        {"dimension": "effectiveness", "score": 2.5, "metrics": {...}},
        ...
      ],
      "overall_score": 2.5,
      "story_metrics": [
        {
          "story_id": "US-001",
          "success": true,
          "wall_clock_seconds": 4.37,
          "iterations": 8,
          "tool_calls": 15,
          "correctness_score": 0,
          "completeness_score": 0
        }
      ]
    }
  }
}
```

### Scoring Dimensions (from `story.py:241-248`)
Six dimensions scored 0-3: `correctness`, `completeness`, `code_quality`, `test_quality`, `time_efficiency`, `autonomy`

### Scoring Rubric (from `story.py:251-288`)
Each dimension has a 0-3 rubric. For example, correctness: 0="Does not compile/run", 1="Runs but wrong behavior", 2="Mostly correct, minor issues", 3="Fully correct".

### Trace File Format (`results/logs/{platform}/{story}/*_trace.json`)
```json
{
  "execution_id": "langgraph_US-001_...",
  "platform_id": "langgraph",
  "story_id": "US-001",
  "start_time": "...",
  "end_time": "...",
  "status": "completed",
  "iterations": 8,
  "tool_calls": 15,
  "messages": [
    {"role": "system"|"human"|"ai"|"tool", "content": "...", "timestamp": "..."},
    ...
  ]
}
```

### Platform Categories (from `config/platforms.yaml`)
- `multi_agent_framework`: langgraph, crewai, microsoft_autogen
- `agent_sdk_runtime`: openai_agents_sdk, google_adk, semantic_kernel
- `visual_workflow_platform`: flowise, langflow, dify, n8n

---

## Task 1: Add Dashboard Dependencies

**Files:**
- Modify: `pyproject.toml:34-73` (optional-dependencies section)

**Step 1: Add the dashboard extra to pyproject.toml**

Add after the `observability` extra (line 73):

```toml
# ── Dashboard ──
dashboard = [
    "streamlit>=1.30.0",
    "plotly>=5.18.0",
    "kaleido>=0.2.1",
]
```

**Step 2: Install the new extra**

Run: `pip install -e ".[dashboard]"`
Expected: Successfully installed streamlit, plotly, kaleido and their dependencies.

**Step 3: Verify imports work**

Run: `python -c "import streamlit; import plotly; import kaleido; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat(dashboard): add streamlit, plotly, kaleido dependencies"
```

---

## Task 2: Create Data Layer (`data.py`)

**Files:**
- Create: `src/desmet/dashboard/__init__.py`
- Create: `src/desmet/dashboard/data.py`

**Step 1: Create the package init**

```python
"""DESMET Evaluation Dashboard."""
```

**Step 2: Create `data.py` with JSON loading**

This module provides all data access for the dashboard. It reads `evaluation_results.json`, `config/platforms.yaml`, stories from `data/stories/`, and trace files. It also writes scores back to the JSON.

```python
"""
Data layer for the DESMET evaluation dashboard.

Loads evaluation results, platform config, stories, and traces.
Writes manual scores back to evaluation_results.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import yaml


def _find_repo_root() -> Path:
    """Walk up from this file to find the repo root (contains pyproject.toml)."""
    candidate = Path(__file__).resolve().parent
    while candidate != candidate.parent:
        if (candidate / "pyproject.toml").exists():
            return candidate
        candidate = candidate.parent
    raise FileNotFoundError("Cannot locate project root (pyproject.toml)")


REPO_ROOT = _find_repo_root()
RESULTS_DIR = REPO_ROOT / "results"
RESULTS_JSON = RESULTS_DIR / "evaluation_results.json"
CONFIG_YAML = REPO_ROOT / "config" / "platforms.yaml"
STORIES_DIR = REPO_ROOT / "data" / "stories"
LOGS_DIR = RESULTS_DIR / "logs"
FIGURES_DIR = REPO_ROOT / "docs" / "report" / "figures"


# -- Platform metadata -------------------------------------------------------

CATEGORY_COLOURS = {
    "multi_agent_framework": {
        "langgraph": "#1f77b4",
        "crewai": "#4a90d9",
        "microsoft_autogen": "#7eb8e4",
    },
    "agent_sdk_runtime": {
        "openai_agents_sdk": "#2ca02c",
        "google_adk": "#5cbf5c",
        "semantic_kernel": "#8dd98d",
    },
    "visual_workflow_platform": {
        "flowise": "#ff7f0e",
        "langflow": "#ffa64d",
        "dify": "#ffc98c",
        "n8n": "#ffe0b2",
    },
}


def get_platform_colour(platform_id: str) -> str:
    """Return the assigned colour for a platform."""
    for _cat, platforms in CATEGORY_COLOURS.items():
        if platform_id in platforms:
            return platforms[platform_id]
    return "#999999"


def get_platform_colours(platform_ids: list[str]) -> dict[str, str]:
    """Return a colour map for a list of platform IDs."""
    return {pid: get_platform_colour(pid) for pid in platform_ids}


# -- Config loading -----------------------------------------------------------

@st.cache_data
def load_platforms_config() -> list[dict[str, str]]:
    """Load platform definitions from config/platforms.yaml."""
    raw = yaml.safe_load(CONFIG_YAML.read_text(encoding="utf-8"))
    return raw.get("platforms", [])


def get_platform_name(platform_id: str) -> str:
    """Look up display name for a platform ID."""
    for p in load_platforms_config():
        if p["id"] == platform_id:
            return p["name"]
    return platform_id


def get_platform_category(platform_id: str) -> str:
    """Look up category for a platform ID."""
    for p in load_platforms_config():
        if p["id"] == platform_id:
            return p["category"]
    return "unknown"


# -- Results loading ----------------------------------------------------------

def load_results_raw() -> dict[str, Any]:
    """Load the raw evaluation_results.json. Not cached — always fresh."""
    if not RESULTS_JSON.exists():
        return {"evaluation_date": None, "platforms": {}}
    return json.loads(RESULTS_JSON.read_text(encoding="utf-8"))


def save_results(data: dict[str, Any]) -> None:
    """Write data back to evaluation_results.json."""
    RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_JSON.write_text(
        json.dumps(data, indent=2, default=str),
        encoding="utf-8",
    )


def get_platform_ids(data: dict[str, Any]) -> list[str]:
    """Return list of platform IDs that have results."""
    return list(data.get("platforms", {}).keys())


def get_story_metrics_df(data: dict[str, Any]) -> pd.DataFrame:
    """Flatten all story metrics across platforms into a DataFrame."""
    rows = []
    for pid, pdata in data.get("platforms", {}).items():
        for sm in pdata.get("story_metrics", []):
            row = {"platform_id": pid, "platform_name": pdata.get("platform_name", pid)}
            row.update(sm)
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def get_dimension_scores_df(data: dict[str, Any]) -> pd.DataFrame:
    """Flatten dimension scores across platforms into a DataFrame."""
    rows = []
    for pid, pdata in data.get("platforms", {}).items():
        for ds in pdata.get("dimension_scores", []):
            rows.append({
                "platform_id": pid,
                "platform_name": pdata.get("platform_name", pid),
                "dimension": ds["dimension"],
                "score": ds["score"],
            })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def get_platform_summary_df(data: dict[str, Any]) -> pd.DataFrame:
    """One row per platform with aggregate info."""
    rows = []
    for pid, pdata in data.get("platforms", {}).items():
        total = pdata.get("stories_total", 0)
        completed = pdata.get("stories_completed", 0)
        rows.append({
            "platform_id": pid,
            "platform_name": pdata.get("platform_name", pid),
            "category": get_platform_category(pid),
            "stories_total": total,
            "stories_completed": completed,
            "completion_rate": completed / total if total > 0 else 0,
            "overall_score": pdata.get("overall_score", 0),
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


# -- Score writing ------------------------------------------------------------

def update_story_scores(
    data: dict[str, Any],
    platform_id: str,
    story_id: str,
    scores: dict[str, float],
    notes: dict[str, str],
) -> dict[str, Any]:
    """Update manual scores for a specific platform/story in the results dict.

    Parameters
    ----------
    data : results dict (mutated in place and returned)
    platform_id : e.g. "langgraph"
    story_id : e.g. "US-001"
    scores : e.g. {"correctness": 2.0, "completeness": 3.0, ...}
    notes : e.g. {"correctness": "Minor issue with...", ...}
    """
    pdata = data.get("platforms", {}).get(platform_id)
    if pdata is None:
        return data

    for sm in pdata.get("story_metrics", []):
        if sm["story_id"] == story_id:
            # Write each score dimension
            for dim, score in scores.items():
                sm[f"{dim}_score"] = score
            # Write notes
            sm["scoring_notes"] = notes
            sm["scored"] = True
            break

    return data


# -- Trace loading ------------------------------------------------------------

def list_trace_files(platform_id: str, story_id: str) -> list[Path]:
    """Find trace JSON files for a platform/story combo."""
    trace_dir = LOGS_DIR / platform_id / story_id
    if not trace_dir.exists():
        return []
    return sorted(trace_dir.glob("*_trace.json"), reverse=True)


def load_trace(trace_path: Path) -> dict[str, Any]:
    """Load a single trace JSON file."""
    return json.loads(trace_path.read_text(encoding="utf-8"))


# -- Scoring progress ---------------------------------------------------------

SCORING_DIMENSIONS = [
    "correctness",
    "completeness",
    "code_quality",
    "test_quality",
    "time_efficiency",
    "autonomy",
]

SCORING_RUBRIC = {
    "correctness": {
        0: "Does not compile/run",
        1: "Runs but wrong behavior",
        2: "Mostly correct, minor issues",
        3: "Fully correct",
    },
    "completeness": {
        0: "No meaningful output",
        1: "Partial implementation",
        2: "Most requirements met",
        3: "All requirements met",
    },
    "code_quality": {
        0: "Unreadable/unmaintainable",
        1: "Poor style, no structure",
        2: "Acceptable quality",
        3: "Clean, idiomatic code",
    },
    "test_quality": {
        0: "No tests",
        1: "Tests exist but trivial",
        2: "Tests cover main paths",
        3: "Comprehensive tests",
    },
    "time_efficiency": {
        0: "Exceeded budget by 2x+",
        1: "Exceeded budget",
        2: "Met budget",
        3: "Under budget",
    },
    "autonomy": {
        0: "Required constant intervention",
        1: "Frequent intervention",
        2: "Occasional intervention",
        3: "Fully autonomous",
    },
}


def is_story_scored(story_metrics: dict[str, Any]) -> bool:
    """Check if a story has been manually scored."""
    return story_metrics.get("scored", False)


def get_scoring_progress(data: dict[str, Any]) -> dict[str, tuple[int, int]]:
    """Return {platform_id: (scored_count, total_count)}."""
    progress = {}
    for pid, pdata in data.get("platforms", {}).items():
        metrics = pdata.get("story_metrics", [])
        scored = sum(1 for m in metrics if is_story_scored(m))
        progress[pid] = (scored, len(metrics))
    return progress
```

**Step 3: Verify the module loads**

Run: `python -c "from desmet.dashboard.data import REPO_ROOT, load_results_raw; d = load_results_raw(); print(f'Loaded {len(d.get(\"platforms\", {}))} platforms')"`
Expected: `Loaded 2 platforms`

**Step 4: Commit**

```bash
git add src/desmet/dashboard/__init__.py src/desmet/dashboard/data.py
git commit -m "feat(dashboard): add data layer for loading/saving evaluation results"
```

---

## Task 3: Create Charts Module (`charts.py`)

**Files:**
- Create: `src/desmet/dashboard/charts.py`

**Step 1: Create `charts.py` with all chart builder functions**

Each function takes data (DataFrames or dicts) and returns a `plotly.graph_objects.Figure`. No Streamlit imports — pure Plotly.

```python
"""
Reusable Plotly chart builders for the DESMET dashboard.

Every function returns a plotly.graph_objects.Figure.
No Streamlit dependencies — charts are pure Plotly.
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
import pandas as pd

from .data import get_platform_colour, get_platform_name


# -- Shared layout defaults ---------------------------------------------------

_LAYOUT_DEFAULTS = dict(
    font=dict(size=12),
    plot_bgcolor="white",
    paper_bgcolor="white",
    margin=dict(l=60, r=30, t=50, b=50),
)


def _apply_defaults(fig: go.Figure, title: str = "") -> go.Figure:
    """Apply consistent styling to a figure."""
    fig.update_layout(**_LAYOUT_DEFAULTS)
    if title:
        fig.update_layout(title=dict(text=title, font=dict(size=14)))
    return fig


# -- Radar: DESMET dimensions ------------------------------------------------

def radar_dimensions(
    dimension_scores: dict[str, dict[str, float]],
    title: str = "DESMET Dimension Comparison",
) -> go.Figure:
    """Radar chart comparing platforms across DESMET dimensions.

    Parameters
    ----------
    dimension_scores : {platform_id: {dimension_name: score}}
    """
    if not dimension_scores:
        return go.Figure()

    # Collect all dimensions (union across platforms)
    all_dims: list[str] = []
    for scores in dimension_scores.values():
        for d in scores:
            if d not in all_dims:
                all_dims.append(d)

    fig = go.Figure()
    for pid, scores in dimension_scores.items():
        values = [scores.get(d, 0) for d in all_dims]
        # Close the polygon
        values.append(values[0])
        dims_closed = all_dims + [all_dims[0]]
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=[d.replace("_", " ").title() for d in dims_closed],
            name=get_platform_name(pid),
            line=dict(color=get_platform_colour(pid)),
            fill="toself",
            opacity=0.3,
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 5], tickvals=[1, 2, 3, 4, 5]),
        ),
        showlegend=True,
    )
    return _apply_defaults(fig, title)


# -- Bar: platform rankings ---------------------------------------------------

def bar_platform_rankings(
    summary_df: pd.DataFrame,
    title: str = "Platform Rankings",
) -> go.Figure:
    """Horizontal bar chart of platforms sorted by overall score.

    Expects columns: platform_id, platform_name, overall_score.
    """
    if summary_df.empty:
        return go.Figure()

    df = summary_df.sort_values("overall_score", ascending=True)
    colours = [get_platform_colour(pid) for pid in df["platform_id"]]

    fig = go.Figure(go.Bar(
        x=df["overall_score"],
        y=df["platform_name"],
        orientation="h",
        marker_color=colours,
        text=[f"{s:.1f}" for s in df["overall_score"]],
        textposition="outside",
    ))
    fig.update_xaxes(range=[0, 5.5], title_text="Overall Score (0-5)")
    fig.update_yaxes(title_text="")
    return _apply_defaults(fig, title)


# -- Bar: completion rates ----------------------------------------------------

def bar_completion_rates(
    summary_df: pd.DataFrame,
    title: str = "Story Completion Rates",
) -> go.Figure:
    """Bar chart of completion rates per platform."""
    if summary_df.empty:
        return go.Figure()

    df = summary_df.sort_values("completion_rate", ascending=True)
    colours = [get_platform_colour(pid) for pid in df["platform_id"]]

    fig = go.Figure(go.Bar(
        x=[r * 100 for r in df["completion_rate"]],
        y=df["platform_name"],
        orientation="h",
        marker_color=colours,
        text=[f"{r:.0%}" for r in df["completion_rate"]],
        textposition="outside",
    ))
    fig.update_xaxes(range=[0, 110], title_text="Completion Rate (%)")
    fig.update_yaxes(title_text="")
    return _apply_defaults(fig, title)


# -- Grouped bar: story comparison --------------------------------------------

def bar_story_comparison(
    metrics_df: pd.DataFrame,
    metric: str = "wall_clock_seconds",
    title: str = "Story Comparison",
) -> go.Figure:
    """Grouped bar chart comparing a metric across platforms per story.

    Expects columns: platform_id, platform_name, story_id, and the metric column.
    """
    if metrics_df.empty or metric not in metrics_df.columns:
        return go.Figure()

    fig = go.Figure()
    for pid in metrics_df["platform_id"].unique():
        pdf = metrics_df[metrics_df["platform_id"] == pid].sort_values("story_id")
        fig.add_trace(go.Bar(
            x=pdf["story_id"],
            y=pdf[metric],
            name=get_platform_name(pid),
            marker_color=get_platform_colour(pid),
        ))

    fig.update_layout(barmode="group")
    fig.update_xaxes(title_text="Story")
    fig.update_yaxes(title_text=metric.replace("_", " ").title())
    return _apply_defaults(fig, title)


# -- Grouped bar: efficiency breakdown ----------------------------------------

def bar_efficiency_breakdown(
    metrics_df: pd.DataFrame,
    title: str = "Efficiency Breakdown",
) -> go.Figure:
    """Three grouped bars per platform: avg time, avg iterations, avg tool calls.

    Expects columns: platform_id, platform_name, wall_clock_seconds, iterations, tool_calls.
    """
    if metrics_df.empty:
        return go.Figure()

    agg = metrics_df.groupby(["platform_id", "platform_name"]).agg(
        avg_time=("wall_clock_seconds", "mean"),
        avg_iterations=("iterations", "mean"),
        avg_tool_calls=("tool_calls", "mean"),
    ).reset_index().sort_values("platform_name")

    fig = go.Figure()
    for metric_col, label in [
        ("avg_time", "Avg Time (s)"),
        ("avg_iterations", "Avg Iterations"),
        ("avg_tool_calls", "Avg Tool Calls"),
    ]:
        fig.add_trace(go.Bar(
            x=agg["platform_name"],
            y=agg[metric_col],
            name=label,
        ))

    fig.update_layout(barmode="group")
    fig.update_xaxes(title_text="Platform")
    fig.update_yaxes(title_text="Value")
    return _apply_defaults(fig, title)


# -- Heatmap: acceptance criteria matrix --------------------------------------

def heatmap_criteria(
    criteria_data: dict[str, dict[str, bool | None]],
    title: str = "Acceptance Criteria Pass/Fail",
) -> go.Figure:
    """Heatmap with platforms as columns and criteria as rows.

    Parameters
    ----------
    criteria_data : {platform_id: {criterion_id: True/False/None}}
    """
    if not criteria_data:
        return go.Figure()

    platforms = list(criteria_data.keys())
    all_criteria: list[str] = []
    for crit_map in criteria_data.values():
        for c in crit_map:
            if c not in all_criteria:
                all_criteria.append(c)

    z = []
    text = []
    for crit in all_criteria:
        row = []
        text_row = []
        for pid in platforms:
            val = criteria_data[pid].get(crit)
            if val is True:
                row.append(1)
                text_row.append("Pass")
            elif val is False:
                row.append(0)
                text_row.append("Fail")
            else:
                row.append(0.5)
                text_row.append("N/A")
        z.append(row)
        text.append(text_row)

    fig = go.Figure(go.Heatmap(
        z=z,
        x=[get_platform_name(p) for p in platforms],
        y=all_criteria,
        text=text,
        texttemplate="%{text}",
        colorscale=[[0, "#ef5350"], [0.5, "#bdbdbd"], [1, "#66bb6a"]],
        showscale=False,
    ))
    fig.update_yaxes(autorange="reversed")
    return _apply_defaults(fig, title)


# -- Dimension bar: per-dimension across platforms ----------------------------

def bar_dimension_comparison(
    dimension_df: pd.DataFrame,
    dimension: str,
    title: str = "",
) -> go.Figure:
    """Bar chart for a single dimension across platforms.

    Expects columns: platform_id, platform_name, dimension, score.
    """
    if dimension_df.empty:
        return go.Figure()

    df = dimension_df[dimension_df["dimension"] == dimension].sort_values("score", ascending=True)
    if df.empty:
        return go.Figure()

    colours = [get_platform_colour(pid) for pid in df["platform_id"]]
    if not title:
        title = f"{dimension.replace('_', ' ').title()} Scores"

    fig = go.Figure(go.Bar(
        x=df["score"],
        y=df["platform_name"],
        orientation="h",
        marker_color=colours,
        text=[f"{s:.1f}" for s in df["score"]],
        textposition="outside",
    ))
    fig.update_xaxes(range=[0, 5.5], title_text="Score (0-5)")
    fig.update_yaxes(title_text="")
    return _apply_defaults(fig, title)
```

**Step 2: Quick smoke test**

Run: `python -c "from desmet.dashboard.charts import radar_dimensions; fig = radar_dimensions({'langgraph': {'effectiveness': 2.5, 'efficiency': 5.0}}); print(type(fig))"`
Expected: `<class 'plotly.graph_objs._figure.Figure'>`

**Step 3: Commit**

```bash
git add src/desmet/dashboard/charts.py
git commit -m "feat(dashboard): add Plotly chart builder functions"
```

---

## Task 4: Create Export Module (`export.py`)

**Files:**
- Create: `src/desmet/dashboard/export.py`

**Step 1: Create `export.py`**

```python
"""
Chart export helpers for the DESMET dashboard.

Exports Plotly figures as PNG or SVG for the Typst report.
Requires the kaleido package.
"""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go

from .data import FIGURES_DIR


# A4 widths at 300 DPI
PRESETS = {
    "full_width": {"width": 1890, "height": 1181},   # ~160mm at 300 DPI
    "half_width": {"width": 886, "height": 591},      # ~75mm at 300 DPI
    "default": {"width": 800, "height": 500},
}


def export_figure(
    fig: go.Figure,
    name: str,
    fmt: str = "svg",
    preset: str = "default",
    width: int | None = None,
    height: int | None = None,
    output_dir: Path | None = None,
) -> Path:
    """Export a Plotly figure to disk.

    Parameters
    ----------
    fig : The Plotly figure to export.
    name : Filename stem (e.g. "radar_all_platforms").
    fmt : "png" or "svg".
    preset : Size preset: "full_width", "half_width", or "default".
    width, height : Override preset dimensions (pixels).
    output_dir : Where to save. Defaults to docs/report/figures/.

    Returns
    -------
    Path to the saved file.
    """
    out = output_dir or FIGURES_DIR
    out.mkdir(parents=True, exist_ok=True)

    dims = PRESETS.get(preset, PRESETS["default"])
    w = width or dims["width"]
    h = height or dims["height"]

    path = out / f"{name}.{fmt}"
    fig.write_image(
        str(path),
        format=fmt,
        width=w,
        height=h,
        scale=2 if fmt == "png" else 1,
    )
    return path
```

**Step 2: Verify export works**

Run: `python -c "from desmet.dashboard.charts import bar_platform_rankings; from desmet.dashboard.export import export_figure; import pandas as pd; df = pd.DataFrame([{'platform_id': 'langgraph', 'platform_name': 'LangGraph', 'overall_score': 2.5}]); fig = bar_platform_rankings(df); p = export_figure(fig, 'test_export', 'png'); print(f'Saved to {p}'); p.unlink()"`
Expected: `Saved to .../docs/report/figures/test_export.png`

**Step 3: Commit**

```bash
git add src/desmet/dashboard/export.py
git commit -m "feat(dashboard): add chart export helpers with size presets"
```

---

## Task 5: Create App Entry Point (`app.py`)

**Files:**
- Create: `src/desmet/dashboard/app.py`

**Step 1: Create `app.py`**

```python
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
```

**Step 2: Create the pages directory**

Create: `src/desmet/dashboard/pages/__init__.py` (empty file)

**Step 3: Commit**

```bash
git add src/desmet/dashboard/app.py src/desmet/dashboard/pages/__init__.py
git commit -m "feat(dashboard): add app entry point with 5-page navigation"
```

---

## Task 6: Create Overview Page

**Files:**
- Create: `src/desmet/dashboard/pages/p01_overview.py`

**Step 1: Create the overview page**

```python
"""
Page 01: Overview

Platform ranking table, completion rates, and DESMET radar chart.
"""

from __future__ import annotations

import streamlit as st

from desmet.dashboard.data import (
    get_dimension_scores_df,
    get_platform_summary_df,
    get_scoring_progress,
    load_results_raw,
)
from desmet.dashboard.charts import (
    bar_completion_rates,
    bar_platform_rankings,
    radar_dimensions,
)


def render():
    st.title("DESMET Evaluation Overview")

    # Reload button
    if st.button("Reload data"):
        st.cache_data.clear()

    data = load_results_raw()
    if not data.get("platforms"):
        st.warning("No evaluation results found. Run an evaluation first.")
        return

    summary_df = get_platform_summary_df(data)
    dim_df = get_dimension_scores_df(data)

    # -- Scoring progress -----------------------------------------------------
    st.subheader("Scoring Progress")
    progress = get_scoring_progress(data)
    cols = st.columns(len(progress))
    for col, (pid, (scored, total)) in zip(cols, progress.items()):
        with col:
            pct = scored / total if total > 0 else 0
            st.metric(
                label=summary_df[summary_df["platform_id"] == pid]["platform_name"].iloc[0],
                value=f"{scored}/{total} stories",
            )
            st.progress(pct)

    # -- Rankings table -------------------------------------------------------
    st.subheader("Platform Rankings")
    display_df = summary_df[["platform_name", "category", "overall_score", "completion_rate"]].copy()
    display_df["completion_rate"] = display_df["completion_rate"].apply(lambda x: f"{x:.0%}")
    display_df["overall_score"] = display_df["overall_score"].apply(lambda x: f"{x:.1f}/5")
    display_df = display_df.sort_values("overall_score", ascending=False)
    display_df.columns = ["Platform", "Category", "Score", "Completion"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # -- Charts ---------------------------------------------------------------
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Overall Rankings")
        fig = bar_platform_rankings(summary_df)
        st.plotly_chart(fig, use_container_width=True, key="overview_rankings")

    with col2:
        st.subheader("Completion Rates")
        fig = bar_completion_rates(summary_df)
        st.plotly_chart(fig, use_container_width=True, key="overview_completion")

    # -- Radar chart ----------------------------------------------------------
    if not dim_df.empty:
        st.subheader("DESMET Dimensions")
        # Build {platform_id: {dimension: score}} dict
        dim_dict: dict[str, dict[str, float]] = {}
        for _, row in dim_df.iterrows():
            dim_dict.setdefault(row["platform_id"], {})[row["dimension"]] = row["score"]
        fig = radar_dimensions(dim_dict)
        st.plotly_chart(fig, use_container_width=True, key="overview_radar")
```

**Step 2: Verify the page renders**

Run: `streamlit run src/desmet/dashboard/app.py` (manual check — opens browser, Overview page loads with data)

**Step 3: Commit**

```bash
git add src/desmet/dashboard/pages/p01_overview.py
git commit -m "feat(dashboard): add overview page with rankings and radar chart"
```

---

## Task 7: Create Scoring Page

**Files:**
- Create: `src/desmet/dashboard/pages/p02_scoring.py`

**Step 1: Create the scoring page**

```python
"""
Page 02: Scoring

Manual rubric-based scoring for each platform/story combination.
Displays execution evidence and writes scores back to results JSON.
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


def render():
    st.title("Platform Scoring")

    data = load_results_raw()
    if not data.get("platforms"):
        st.warning("No evaluation results found.")
        return

    platform_ids = get_platform_ids(data)

    # -- Sidebar selectors ----------------------------------------------------
    with st.sidebar:
        st.header("Select Target")
        selected_platform = st.selectbox(
            "Platform",
            platform_ids,
            format_func=get_platform_name,
        )

        pdata = data["platforms"][selected_platform]
        story_ids = [m["story_id"] for m in pdata.get("story_metrics", [])]
        selected_story = st.selectbox("Story", story_ids)

    # Find the story metrics entry
    story_metrics = None
    for m in pdata.get("story_metrics", []):
        if m["story_id"] == selected_story:
            story_metrics = m
            break

    if story_metrics is None:
        st.error(f"No metrics found for {selected_platform}/{selected_story}")
        return

    scored = is_story_scored(story_metrics)
    if scored:
        st.success("This story has been scored.")
    else:
        st.info("This story has not been scored yet.")

    # -- Execution evidence ---------------------------------------------------
    st.subheader("Execution Evidence")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Wall Clock", f"{story_metrics.get('wall_clock_seconds', 0):.1f}s")
    col2.metric("Iterations", story_metrics.get("iterations", 0))
    col3.metric("Tool Calls", story_metrics.get("tool_calls", 0))
    col4.metric("Success", "Yes" if story_metrics.get("success") else "No")

    # -- Trace viewer ---------------------------------------------------------
    trace_files = list_trace_files(selected_platform, selected_story)
    if trace_files:
        with st.expander("Execution Trace", expanded=False):
            trace_path = trace_files[0]  # Most recent
            trace = load_trace(trace_path)
            messages = trace.get("messages", [])

            for msg in messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                if not content:
                    continue
                if role == "human":
                    st.chat_message("user").write(content[:500])
                elif role == "ai":
                    st.chat_message("assistant").write(content[:500])
                elif role == "tool":
                    with st.chat_message("assistant"):
                        st.code(content[:500], language="text")

    # -- Scoring form ---------------------------------------------------------
    st.subheader("Score Rubric")
    st.caption("Rate each dimension from 0 to 3. Hover over rubric descriptions for guidance.")

    with st.form(key="scoring_form"):
        scores: dict[str, float] = {}
        notes: dict[str, str] = {}

        for dim in SCORING_DIMENSIONS:
            rubric = SCORING_RUBRIC[dim]
            current_score = story_metrics.get(f"{dim}_score", 0.0)

            st.markdown(f"**{dim.replace('_', ' ').title()}**")

            # Show rubric as help text
            rubric_text = " | ".join(f"{k}: {v}" for k, v in rubric.items())
            scores[dim] = float(st.slider(
                f"{dim} score",
                min_value=0,
                max_value=3,
                value=int(current_score),
                help=rubric_text,
                key=f"score_{dim}",
                label_visibility="collapsed",
            ))

            notes[dim] = st.text_input(
                f"{dim} notes",
                value=story_metrics.get("scoring_notes", {}).get(dim, ""),
                key=f"notes_{dim}",
                label_visibility="collapsed",
                placeholder=f"Notes for {dim.replace('_', ' ')}...",
            )

        submitted = st.form_submit_button("Save Scores", type="primary")
        if submitted:
            data = update_story_scores(data, selected_platform, selected_story, scores, notes)
            save_results(data)
            st.success(f"Scores saved for {get_platform_name(selected_platform)} / {selected_story}")
            st.rerun()
```

**Step 2: Manual verification**

Run: `streamlit run src/desmet/dashboard/app.py` — navigate to Scoring page, select LangGraph / US-001, verify evidence metrics display, set some scores, submit, verify JSON updated.

**Step 3: Commit**

```bash
git add src/desmet/dashboard/pages/p02_scoring.py
git commit -m "feat(dashboard): add scoring page with rubric forms and trace viewer"
```

---

## Task 8: Create Comparison Page

**Files:**
- Create: `src/desmet/dashboard/pages/p03_comparison.py`

**Step 1: Create the comparison page**

```python
"""
Page 03: Comparison

Cross-platform comparison with side-by-side charts.
"""

from __future__ import annotations

import streamlit as st

from desmet.dashboard.data import (
    get_dimension_scores_df,
    get_platform_ids,
    get_platform_name,
    get_platform_category,
    get_story_metrics_df,
    load_results_raw,
)
from desmet.dashboard.charts import (
    bar_dimension_comparison,
    bar_efficiency_breakdown,
    bar_story_comparison,
    radar_dimensions,
)


def render():
    st.title("Platform Comparison")

    data = load_results_raw()
    if not data.get("platforms"):
        st.warning("No evaluation results found.")
        return

    platform_ids = get_platform_ids(data)

    # -- Platform selector ----------------------------------------------------
    selected = st.multiselect(
        "Select platforms to compare",
        platform_ids,
        default=platform_ids,
        format_func=get_platform_name,
    )

    if len(selected) < 2:
        st.info("Select at least 2 platforms to compare.")
        return

    metrics_df = get_story_metrics_df(data)
    metrics_df = metrics_df[metrics_df["platform_id"].isin(selected)]

    dim_df = get_dimension_scores_df(data)
    dim_df = dim_df[dim_df["platform_id"].isin(selected)]

    # -- Radar chart ----------------------------------------------------------
    st.subheader("Dimension Comparison")
    if not dim_df.empty:
        dim_dict: dict[str, dict[str, float]] = {}
        for _, row in dim_df.iterrows():
            dim_dict.setdefault(row["platform_id"], {})[row["dimension"]] = row["score"]
        fig = radar_dimensions(dim_dict, title="DESMET Dimensions — Selected Platforms")
        st.plotly_chart(fig, use_container_width=True, key="comparison_radar")

    # -- Per-dimension bars ---------------------------------------------------
    if not dim_df.empty:
        dimensions = dim_df["dimension"].unique().tolist()
        cols = st.columns(min(3, len(dimensions)))
        for i, dim in enumerate(dimensions):
            with cols[i % len(cols)]:
                fig = bar_dimension_comparison(dim_df, dim)
                st.plotly_chart(fig, use_container_width=True, key=f"comp_dim_{dim}")

    # -- Story-level comparison -----------------------------------------------
    st.subheader("Story-Level Comparison")
    if not metrics_df.empty:
        metric = st.selectbox(
            "Metric",
            ["wall_clock_seconds", "iterations", "tool_calls"],
            format_func=lambda x: x.replace("_", " ").title(),
        )
        fig = bar_story_comparison(metrics_df, metric=metric, title=f"{metric.replace('_', ' ').title()} by Story")
        st.plotly_chart(fig, use_container_width=True, key="comp_story")

    # -- Efficiency breakdown -------------------------------------------------
    st.subheader("Efficiency Breakdown")
    if not metrics_df.empty:
        fig = bar_efficiency_breakdown(metrics_df)
        st.plotly_chart(fig, use_container_width=True, key="comp_efficiency")

    # -- Category averages ----------------------------------------------------
    st.subheader("Category Averages")
    if not dim_df.empty:
        dim_df_cat = dim_df.copy()
        dim_df_cat["category"] = dim_df_cat["platform_id"].apply(get_platform_category)
        cat_avg = dim_df_cat.groupby(["category", "dimension"])["score"].mean().reset_index()

        categories = cat_avg["category"].unique().tolist()
        cols = st.columns(len(categories))
        for col, cat in zip(cols, categories):
            with col:
                st.markdown(f"**{cat.replace('_', ' ').title()}**")
                cat_data = cat_avg[cat_avg["category"] == cat]
                for _, row in cat_data.iterrows():
                    st.text(f"  {row['dimension']:20s} {row['score']:.1f}/5")
```

**Step 2: Manual verification**

Run: `streamlit run src/desmet/dashboard/app.py` — navigate to Comparison, select both platforms, verify all charts render.

**Step 3: Commit**

```bash
git add src/desmet/dashboard/pages/p03_comparison.py
git commit -m "feat(dashboard): add comparison page with dimension and story charts"
```

---

## Task 9: Create Story Detail Page

**Files:**
- Create: `src/desmet/dashboard/pages/p04_story_detail.py`

**Step 1: Create the story detail page**

```python
"""
Page 04: Story Detail

Per-story drill-down showing how all platforms performed on a single story.
Includes criteria matrix, trace viewer, and generated code.
"""

from __future__ import annotations

import streamlit as st

from desmet.dashboard.data import (
    SCORING_DIMENSIONS,
    get_platform_ids,
    get_platform_name,
    get_story_metrics_df,
    list_trace_files,
    load_results_raw,
    load_trace,
)
from desmet.dashboard.charts import bar_story_comparison


def render():
    st.title("Story Detail")

    data = load_results_raw()
    if not data.get("platforms"):
        st.warning("No evaluation results found.")
        return

    # Collect all story IDs across platforms
    all_stories: list[str] = []
    for pdata in data["platforms"].values():
        for m in pdata.get("story_metrics", []):
            if m["story_id"] not in all_stories:
                all_stories.append(m["story_id"])
    all_stories.sort()

    selected_story = st.selectbox("Select Story", all_stories)

    metrics_df = get_story_metrics_df(data)
    story_df = metrics_df[metrics_df["story_id"] == selected_story]

    if story_df.empty:
        st.info("No data for this story.")
        return

    # -- Summary table --------------------------------------------------------
    st.subheader("Platform Performance")

    display_cols = ["platform_name", "success", "wall_clock_seconds", "iterations", "tool_calls"]
    # Add scoring columns if they exist
    for dim in SCORING_DIMENSIONS:
        col = f"{dim}_score"
        if col in story_df.columns:
            display_cols.append(col)

    display_df = story_df[display_cols].copy()
    display_df.columns = [c.replace("_", " ").title() for c in display_cols]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # -- Comparison charts ----------------------------------------------------
    st.subheader("Metric Comparison")
    col1, col2 = st.columns(2)
    with col1:
        fig = bar_story_comparison(
            story_df, metric="wall_clock_seconds",
            title=f"{selected_story} — Wall Clock Time",
        )
        st.plotly_chart(fig, use_container_width=True, key="detail_time")
    with col2:
        fig = bar_story_comparison(
            story_df, metric="iterations",
            title=f"{selected_story} — Iterations",
        )
        st.plotly_chart(fig, use_container_width=True, key="detail_iterations")

    # -- Per-platform trace viewer --------------------------------------------
    st.subheader("Execution Traces")
    platform_ids = get_platform_ids(data)

    tabs = st.tabs([get_platform_name(pid) for pid in platform_ids])
    for tab, pid in zip(tabs, platform_ids):
        with tab:
            trace_files = list_trace_files(pid, selected_story)
            if not trace_files:
                st.caption("No trace available.")
                continue

            trace = load_trace(trace_files[0])
            messages = trace.get("messages", [])

            st.caption(
                f"Execution: {trace.get('execution_id', 'N/A')} | "
                f"Status: {trace.get('status', 'N/A')} | "
                f"Iterations: {trace.get('iterations', 0)} | "
                f"Tool calls: {trace.get('tool_calls', 0)}"
            )

            # Show messages in a scrollable container
            with st.container(height=400):
                for msg in messages:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    if not content:
                        continue
                    if role == "human":
                        st.chat_message("user").write(content[:1000])
                    elif role == "ai":
                        st.chat_message("assistant").write(content[:1000])
                    elif role == "tool":
                        with st.chat_message("assistant"):
                            st.code(content[:1000], language="text")
                    elif role == "system":
                        st.caption(f"System: {content[:200]}")
```

**Step 2: Manual verification**

Run: `streamlit run src/desmet/dashboard/app.py` — navigate to Story Detail, select US-001, verify table and traces render for both platforms.

**Step 3: Commit**

```bash
git add src/desmet/dashboard/pages/p04_story_detail.py
git commit -m "feat(dashboard): add story detail page with traces and comparison"
```

---

## Task 10: Create Export Page

**Files:**
- Create: `src/desmet/dashboard/pages/p05_export.py`

**Step 1: Create the export page**

```python
"""
Page 05: Export

Batch export charts as PNG/SVG for the Typst report.
"""

from __future__ import annotations

import streamlit as st

from desmet.dashboard.data import (
    FIGURES_DIR,
    get_dimension_scores_df,
    get_platform_summary_df,
    get_story_metrics_df,
    load_results_raw,
)
from desmet.dashboard.charts import (
    bar_completion_rates,
    bar_efficiency_breakdown,
    bar_platform_rankings,
    bar_story_comparison,
    radar_dimensions,
)
from desmet.dashboard.export import PRESETS, export_figure


# Chart registry: (key, label, builder function)
def _build_chart_registry(data):
    """Build list of available charts from current data."""
    summary_df = get_platform_summary_df(data)
    metrics_df = get_story_metrics_df(data)
    dim_df = get_dimension_scores_df(data)

    charts = []

    if not summary_df.empty:
        charts.append(("rankings", "Platform Rankings", bar_platform_rankings(summary_df)))
        charts.append(("completion", "Completion Rates", bar_completion_rates(summary_df)))

    if not dim_df.empty:
        dim_dict: dict[str, dict[str, float]] = {}
        for _, row in dim_df.iterrows():
            dim_dict.setdefault(row["platform_id"], {})[row["dimension"]] = row["score"]
        charts.append(("radar", "DESMET Radar", radar_dimensions(dim_dict)))

    if not metrics_df.empty:
        for metric in ["wall_clock_seconds", "iterations", "tool_calls"]:
            label = metric.replace("_", " ").title()
            charts.append((
                f"story_{metric}",
                f"Story Comparison — {label}",
                bar_story_comparison(metrics_df, metric=metric, title=f"Story Comparison — {label}"),
            ))
        charts.append(("efficiency", "Efficiency Breakdown", bar_efficiency_breakdown(metrics_df)))

    return charts


def render():
    st.title("Export Charts")
    st.caption(f"Export destination: `{FIGURES_DIR}`")

    data = load_results_raw()
    if not data.get("platforms"):
        st.warning("No evaluation results found.")
        return

    charts = _build_chart_registry(data)

    if not charts:
        st.info("No charts available to export.")
        return

    # -- Settings -------------------------------------------------------------
    col1, col2 = st.columns(2)
    with col1:
        fmt = st.radio("Format", ["svg", "png"], horizontal=True)
    with col2:
        preset = st.selectbox("Size Preset", list(PRESETS.keys()), index=0)

    # -- Chart selection ------------------------------------------------------
    st.subheader("Available Charts")

    selected_keys: list[str] = []
    for key, label, fig in charts:
        col_check, col_preview = st.columns([1, 5])
        with col_check:
            if st.checkbox(label, key=f"export_{key}"):
                selected_keys.append(key)
        with col_preview:
            st.plotly_chart(fig, use_container_width=True, key=f"preview_{key}")

    # -- Export button --------------------------------------------------------
    if selected_keys:
        if st.button(f"Export {len(selected_keys)} chart(s)", type="primary"):
            exported = []
            for key, label, fig in charts:
                if key in selected_keys:
                    path = export_figure(fig, key, fmt=fmt, preset=preset)
                    exported.append(str(path))

            st.success(f"Exported {len(exported)} charts to `{FIGURES_DIR}`")
            for p in exported:
                st.code(p, language="text")
    else:
        st.info("Select charts to export.")
```

**Step 2: Manual verification**

Run: `streamlit run src/desmet/dashboard/app.py` — navigate to Export, select a chart, export as SVG, verify file appears in `docs/report/figures/`.

**Step 3: Commit**

```bash
git add src/desmet/dashboard/pages/p05_export.py
git commit -m "feat(dashboard): add export page with batch chart export"
```

---

## Task 11: Add Dashboard CLI Command

**Files:**
- Modify: `src/desmet/cli.py:46-49` (add dashboard command)

**Step 1: Add a `dashboard` command to the CLI**

Add after the existing commands (after `list_stories`):

```python
@app.command()
def dashboard():
    """Launch the Streamlit evaluation dashboard."""
    import subprocess
    import sys
    from desmet.dashboard.data import REPO_ROOT

    app_path = REPO_ROOT / "src" / "desmet" / "dashboard" / "app.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)], check=True)
```

**Step 2: Verify**

Run: `desmet-eval dashboard`
Expected: Streamlit server starts and opens browser.

**Step 3: Commit**

```bash
git add src/desmet/cli.py
git commit -m "feat(cli): add 'dashboard' command to launch Streamlit app"
```

---

## Task 12: Final Integration Test

**Step 1: Launch the dashboard end-to-end**

Run: `streamlit run src/desmet/dashboard/app.py`

Verify each page:
1. **Overview**: Rankings table, radar chart, completion bars, scoring progress (all showing 0/4 scored)
2. **Scoring**: Select LangGraph/US-001, view evidence metrics, view trace, submit scores (e.g. correctness=2, completeness=2), verify "scored" badge appears
3. **Comparison**: Select both platforms, verify radar, dimension bars, story comparison, efficiency breakdown
4. **Story Detail**: Select US-001, verify both platforms appear in table and trace tabs
5. **Export**: Select radar chart, export as SVG, verify file in `docs/report/figures/`

**Step 2: Verify JSON was updated**

Run: `python -c "import json; d = json.load(open('results/evaluation_results.json')); m = d['platforms']['langgraph']['story_metrics'][1]; print(m.get('scored'), m.get('correctness_score'))"`
Expected: `True 2.0` (or whatever scores you entered)

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat(dashboard): complete Streamlit evaluation dashboard

Five-page dashboard for scoring agentic platforms and visualising
cross-platform comparisons. Includes rubric-based scoring, DESMET
radar charts, efficiency breakdowns, trace viewer, and publication-
ready chart export for the Typst report."
```
