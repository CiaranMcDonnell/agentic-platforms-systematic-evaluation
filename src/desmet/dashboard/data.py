"""
Data Access Layer for the DESMET Evaluation Dashboard.

Provides ALL data access for the dashboard: reading evaluation results,
platform configuration, story definitions, and trace files. Also handles
writing scores back to the results JSON.

Works directly with JSON dicts and pandas DataFrames to avoid coupling
with the harness dataclasses.
"""

from __future__ import annotations

import functools
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from desmet.platforms_config import get_platforms_config
from desmet.harness.store import ResultStore

import pandas as pd
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

_store: ResultStore | None = None


def _get_store() -> ResultStore:
    """Lazily create a singleton ResultStore."""
    global _store
    if _store is None:
        _store = ResultStore(db_path=RESULTS_DIR / "desmet.duckdb")
    return _store


# ---------------------------------------------------------------------------
# Platform colours -- derived from config/platforms.yaml
# ---------------------------------------------------------------------------

def _build_category_colours() -> dict[str, dict[str, str]]:
    """Build ``{category: {platform_id: colour}}`` from platforms.yaml."""
    result: dict[str, dict[str, str]] = {}
    for pid, data in get_platforms_config().items():
        cat = data.get("category", "")
        colour = data.get("colour")
        if colour:
            result.setdefault(cat, {})[pid] = colour
    return result


CATEGORY_COLOURS: dict[str, dict[str, str]] = _build_category_colours()

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
# Scoring constants — imported from the canonical source in harness.story.
# ---------------------------------------------------------------------------

from desmet.harness.story import SCORING_DIMENSIONS, SCORING_RUBRIC  # noqa: E402

# ---------------------------------------------------------------------------
# Config loading (cached)
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def load_platforms_config() -> list[dict[str, str]]:
    """Load platform definitions from ``config/platforms.yaml``.

    Returns a list of dicts, each with keys: id, name, category, runtime.
    Cached because this file never changes at runtime.
    """
    with open(CONFIG_YAML, encoding="utf-8") as fh:
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


def load_results_raw(run_id: str | None = None) -> dict[str, Any]:
    """Load evaluation results for a specific run.

    When *run_id* is ``None``, loads the most recent run. Falls back to
    the legacy JSON file when the DuckDB store has no data (e.g., for
    results produced before the store was introduced).
    """
    store = _get_store()
    target_id = run_id or store.latest_run_id()

    if target_id is None:
        # No runs in DB — fall back to legacy JSON
        if not RESULTS_JSON.exists():
            return {"platforms": {}}
        with open(RESULTS_JSON, encoding="utf-8") as fh:
            return json.load(fh)

    exec_df = store.get_executions(target_id)
    if exec_df.empty:
        # Run exists but no executions — return empty
        return {"platforms": {}, "run_id": target_id}

    # Reshape into the legacy dict format expected by downstream functions
    platforms: dict[str, Any] = {}
    for pid, group in exec_df.groupby("platform_id"):
        story_metrics = []
        for _, row in group.iterrows():
            sm: dict[str, Any] = {
                "story_id": row["story_id"],
                "success": row["status"] == "completed",
                "wall_clock_seconds": row["wall_clock_seconds"],
                "iterations": int(row["iterations"] or 0),
                "tool_calls": int(row["tool_calls"] or 0),
                "tokens_input": int(row["tokens_input"] or 0),
                "tokens_output": int(row["tokens_output"] or 0),
                "api_cost_usd": row["cost_usd"],
                "pipeline_completeness_score": row["rubric_pipeline_completeness"],
                "tool_integration_score": row["rubric_tool_integration"],
                "error_recovery_score": row["rubric_error_recovery"],
                "trace_quality_score": row["rubric_trace_quality"],
                "time_efficiency_score": row["rubric_time_efficiency"],
                "autonomy_score": row["rubric_autonomy"],
                "scored": any(
                    row.get(f"rubric_{d}") not in (None, 0.0)
                    for d in ["pipeline_completeness", "tool_integration",
                              "error_recovery", "trace_quality",
                              "time_efficiency", "autonomy"]
                ),
            }
            fm_raw = row.get("framework_metrics")
            if pd.notna(fm_raw) and isinstance(fm_raw, str):
                sm["framework_metrics"] = json.loads(fm_raw)
            story_metrics.append(sm)

        platforms[str(pid)] = {
            "platform_id": str(pid),
            "platform_name": str(pid),
            "stories_total": len(group),
            "stories_completed": int((group["status"] == "completed").sum()),
            "stories_failed": int((group["status"] != "completed").sum()),
            "overall_score": float(group["overall_score"].mean()) if group["overall_score"].notna().any() else 0.0,
            "story_metrics": story_metrics,
            "dimension_scores": [],  # computed on-the-fly by dashboard
        }

    run_df = store.get_run(target_id)
    started = run_df.iloc[0]["started_at"] if len(run_df) else None

    return {
        "evaluation_date": str(started) if started else None,
        "run_id": target_id,
        "platforms": platforms,
    }


def save_results(data: dict[str, Any]) -> None:
    """Write evaluation results back.

    Delegates score updates to the store.  Also writes the legacy JSON
    file for backwards compatibility.
    """
    # Legacy file write
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
            columns=pd.Index(["platform_id", "platform_name", "story_id"])
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
            columns=pd.Index(["platform_id", "platform_name", "dimension", "score"])
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
            columns=pd.Index([
                "platform_id",
                "platform_name",
                "category",
                "stories_total",
                "stories_completed",
                "completion_rate",
                "overall_score",
            ])
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Score writing
# ---------------------------------------------------------------------------


def update_story_scores(
    data: dict[str, Any],
    platform_id: str,
    story_id: str,
    scores: Mapping[str, float],
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


def get_rubric_dim_averages(
    data: dict[str, Any],
) -> dict[str, dict[str, float | None]]:
    """Per-platform average of each 6-dimension rubric score across scored stories.

    Only scored stories (``sm["scored"] == True``) contribute to the average.
    Returns ``{platform_id: {dimension: avg_or_None}}``.
    None means the platform has no scored stories for that dimension.
    """
    result: dict[str, dict[str, float | None]] = {}
    for pid, pdata in data.get("platforms", {}).items():
        scored = [sm for sm in pdata.get("story_metrics", []) if is_story_scored(sm)]
        avgs: dict[str, float | None] = {}
        for dim in SCORING_DIMENSIONS:
            values = [
                sm[f"{dim}_score"]
                for sm in scored
                if sm.get(f"{dim}_score") is not None
            ]
            avgs[dim] = round(sum(values) / len(values), 2) if values else None
        result[pid] = avgs
    return result


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
    files = sorted(trace_dir.glob("*_stages.json"))
    if not files:
        files = sorted(trace_dir.glob("*_trace.json"))
    return files


def load_trace(trace_path: Path) -> dict[str, Any]:
    """Load a single trace file and return its contents as a dict."""
    with open(trace_path, encoding="utf-8") as fh:
        return json.load(fh)
