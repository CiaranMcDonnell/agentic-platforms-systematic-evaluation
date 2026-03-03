"""
Data Access Layer for the DESMET Evaluation Dashboard.

Provides ALL data access for the dashboard: reading evaluation results,
platform configuration, story definitions, and trace files. Also handles
writing scores back to the results JSON.

Works directly with JSON dicts and pandas DataFrames to avoid coupling
with the harness dataclasses.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import yaml

# ---------------------------------------------------------------------------
# Repository root discovery
# ---------------------------------------------------------------------------


def _find_repo_root() -> Path:
    """Walk up from this file's directory to find the repository root.

    The root is identified by the presence of ``pyproject.toml``.
    """
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    # Fallback: assume four levels up from this file
    return Path(__file__).resolve().parent.parent.parent.parent


# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

REPO_ROOT = _find_repo_root()
RESULTS_DIR = REPO_ROOT / "results"
RESULTS_JSON = RESULTS_DIR / "evaluation_results.json"
CONFIG_YAML = REPO_ROOT / "config" / "platforms.yaml"
STORIES_DIR = REPO_ROOT / "data" / "stories"
LOGS_DIR = RESULTS_DIR / "logs"
FIGURES_DIR = RESULTS_DIR / "figures"

# ---------------------------------------------------------------------------
# Platform colours -- fixed per category for consistent visual identity
# ---------------------------------------------------------------------------

CATEGORY_COLOURS: dict[str, dict[str, str]] = {
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

# Build a flat lookup: platform_id -> colour
_PLATFORM_COLOUR_MAP: dict[str, str] = {
    pid: colour
    for cat_colours in CATEGORY_COLOURS.values()
    for pid, colour in cat_colours.items()
}


def get_platform_colour(platform_id: str) -> str:
    """Return the fixed hex colour for a platform, or a grey fallback."""
    return _PLATFORM_COLOUR_MAP.get(platform_id, "#999999")


def get_platform_colours(platform_ids: list[str]) -> dict[str, str]:
    """Return a mapping of platform_id -> hex colour for the given IDs."""
    return {pid: get_platform_colour(pid) for pid in platform_ids}


# ---------------------------------------------------------------------------
# Scoring constants (duplicated from story.py to avoid import coupling)
# ---------------------------------------------------------------------------

SCORING_DIMENSIONS: list[str] = [
    "correctness",
    "completeness",
    "code_quality",
    "test_quality",
    "time_efficiency",
    "autonomy",
]

SCORING_RUBRIC: dict[str, dict[int, str]] = {
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

# ---------------------------------------------------------------------------
# Config loading (cached)
# ---------------------------------------------------------------------------


@st.cache_data
def load_platforms_config() -> list[dict[str, str]]:
    """Load platform definitions from ``config/platforms.yaml``.

    Returns a list of dicts, each with keys: id, name, category, runtime.
    Cached via ``@st.cache_data`` because this file never changes at runtime.
    """
    with open(CONFIG_YAML, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return cfg.get("platforms", [])


def get_platform_name(platform_id: str) -> str:
    """Return the human-readable name for a platform, or the id as fallback."""
    for p in load_platforms_config():
        if p["id"] == platform_id:
            return p["name"]
    return platform_id


def get_platform_category(platform_id: str) -> str:
    """Return the category slug for a platform, or 'unknown'."""
    for p in load_platforms_config():
        if p["id"] == platform_id:
            return p["category"]
    return "unknown"


# ---------------------------------------------------------------------------
# Results loading (NOT cached -- always fresh for scoring updates)
# ---------------------------------------------------------------------------


def load_results_raw() -> dict[str, Any]:
    """Load the evaluation results JSON as a plain dict.

    Intentionally **not** cached so that the dashboard always reflects
    the latest state after scoring updates.
    """
    if not RESULTS_JSON.exists():
        return {"platforms": {}}
    with open(RESULTS_JSON, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_results(data: dict[str, Any]) -> None:
    """Write evaluation results back to the JSON file.

    Uses ``default=str`` so datetime objects serialise cleanly.
    """
    RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_JSON, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)


def get_platform_ids(data: dict[str, Any]) -> list[str]:
    """Return the sorted list of platform IDs present in the results."""
    return sorted(data.get("platforms", {}).keys())


def get_story_metrics_df(data: dict[str, Any]) -> pd.DataFrame:
    """Flatten all story_metrics across platforms into a single DataFrame.

    Adds ``platform_id`` and ``platform_name`` columns to each row.
    Returns an empty DataFrame (with expected columns) when there is no data.
    """
    rows: list[dict[str, Any]] = []
    for pid, pdata in data.get("platforms", {}).items():
        pname = pdata.get("platform_name", pid)
        for sm in pdata.get("story_metrics", []):
            row = dict(sm)  # shallow copy of the metric dict
            row["platform_id"] = pid
            row["platform_name"] = pname
            rows.append(row)
    if not rows:
        return pd.DataFrame(
            columns=["platform_id", "platform_name", "story_id"]
        )
    return pd.DataFrame(rows)


def get_dimension_scores_df(data: dict[str, Any]) -> pd.DataFrame:
    """Flatten dimension_scores across platforms into a single DataFrame.

    Each row has: platform_id, platform_name, dimension, score, plus any
    nested metrics expanded as individual columns.
    """
    rows: list[dict[str, Any]] = []
    for pid, pdata in data.get("platforms", {}).items():
        pname = pdata.get("platform_name", pid)
        for ds in pdata.get("dimension_scores", []):
            row: dict[str, Any] = {
                "platform_id": pid,
                "platform_name": pname,
                "dimension": ds.get("dimension", ""),
                "score": ds.get("score", 0.0),
            }
            # Expand nested metrics dict into top-level columns
            for mk, mv in ds.get("metrics", {}).items():
                row[mk] = mv
            rows.append(row)
    if not rows:
        return pd.DataFrame(
            columns=["platform_id", "platform_name", "dimension", "score"]
        )
    return pd.DataFrame(rows)


def get_platform_summary_df(data: dict[str, Any]) -> pd.DataFrame:
    """One-row-per-platform summary DataFrame.

    Columns: platform_id, platform_name, category, stories_total,
    stories_completed, completion_rate, overall_score.
    """
    rows: list[dict[str, Any]] = []
    for pid, pdata in data.get("platforms", {}).items():
        total = pdata.get("stories_total", 0)
        completed = pdata.get("stories_completed", 0)
        rows.append(
            {
                "platform_id": pid,
                "platform_name": pdata.get("platform_name", pid),
                "category": get_platform_category(pid),
                "stories_total": total,
                "stories_completed": completed,
                "completion_rate": (
                    completed / total if total > 0 else 0.0
                ),
                "overall_score": pdata.get("overall_score", 0.0),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "platform_id",
                "platform_name",
                "category",
                "stories_total",
                "stories_completed",
                "completion_rate",
                "overall_score",
            ]
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Score writing
# ---------------------------------------------------------------------------


def update_story_scores(
    data: dict[str, Any],
    platform_id: str,
    story_id: str,
    scores: dict[str, float],
    notes: dict[str, str],
) -> dict[str, Any]:
    """Mutate *data* in-place: write dimension scores for a story.

    For each key in *scores* (e.g. ``"correctness"``), sets
    ``sm["correctness_score"] = value``.  Also stores *notes* under
    ``sm["scoring_notes"]`` and marks ``sm["scored"] = True``.

    Returns the (mutated) *data* dict for convenience.
    """
    platforms = data.get("platforms", {})
    pdata = platforms.get(platform_id, {})
    for sm in pdata.get("story_metrics", []):
        if sm.get("story_id") == story_id:
            for dim, value in scores.items():
                sm[f"{dim}_score"] = value
            sm["scoring_notes"] = dict(notes)
            sm["scored"] = True
            break
    return data


def is_story_scored(story_metrics: dict[str, Any]) -> bool:
    """Return True if a story_metrics dict has been manually scored."""
    return bool(story_metrics.get("scored", False))


def get_scoring_progress(
    data: dict[str, Any],
) -> dict[str, tuple[int, int]]:
    """Return per-platform scoring progress.

    Returns ``{platform_id: (scored_count, total_count)}``.
    """
    progress: dict[str, tuple[int, int]] = {}
    for pid, pdata in data.get("platforms", {}).items():
        metrics = pdata.get("story_metrics", [])
        scored = sum(1 for sm in metrics if is_story_scored(sm))
        progress[pid] = (scored, len(metrics))
    return progress


# ---------------------------------------------------------------------------
# Trace loading
# ---------------------------------------------------------------------------


def list_trace_files(platform_id: str, story_id: str) -> list[Path]:
    """List all trace JSON files for a given platform/story pair.

    Looks in ``results/logs/{platform_id}/{story_id}/`` for files matching
    ``*_trace.json``.  Returns an empty list if the directory does not exist.
    """
    trace_dir = LOGS_DIR / platform_id / story_id
    if not trace_dir.is_dir():
        return []
    return sorted(trace_dir.glob("*_trace.json"))


def load_trace(trace_path: Path) -> dict[str, Any]:
    """Load a single trace file and return its contents as a dict."""
    with open(trace_path, "r", encoding="utf-8") as fh:
        return json.load(fh)
