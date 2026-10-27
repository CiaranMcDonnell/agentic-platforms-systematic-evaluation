"""Pin the runs the FormaliSE paper reports and export them as the artifact.

Usage (stop the webui first — DuckDB allows one writer):
    uv run python docs/paper/data/extract_reported_runs.py

Selection rule: the reported dataset is exactly the runs listed in
PINNED_RUNS, all produced by one harness version (store schema >= 5, so
stage outcomes, workspace tests, hidden acceptance tests and the
harness-side deploy health check are recorded for every execution).

Before exporting, each pinned run's 1-5 Likert scores are recomputed from
the stored rubric data so the artifact matches the current scoring code
(submit_score only writes rubric columns).  The script fails without
writing anything if a pinned run is missing, incomplete, or has an
unexpected number of executions.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import yaml

from desmet.harness.metrics import recompute_platform_likert_from_store
from desmet.harness.store import ResultStore

REPO = Path(__file__).resolve().parents[3]
STORE = REPO / "results" / "desmet.duckdb"
STORIES = REPO / "data" / "stories"
OUT_JSON = Path(__file__).with_name("reported-runs.json")
OUT_CSV = REPO / "docs" / "paper" / "artifact" / "results-reported.csv"

PLATFORMS = [
    "langgraph",
    "crewai",
    "microsoft_agent_framework",
    "openai_agents_sdk",
    "google_adk",
]
REPEATS = 3

# label -> (run_id, story ids).  Fill in after the reported runs complete.
PINNED_RUNS: dict[str, tuple[str, list[str]]] = {
    # "sonnet-5.5/US-001": ("<run_id>", ["US-001"]),
    # "gpt-5.6-terra/US-001": ("<run_id>", ["US-001"]),
    # "glm-5.3/US-001": ("<run_id>", ["US-001"]),
}

# Exported columns.  trace_path / artifact_path are local filesystem paths
# (they identify the author's machine) and are deliberately excluded.
EXEC_COLS = [
    "execution_id", "run_id", "platform_id", "story_id", "repeat_index", "status",
    "stages_passed", "wall_clock_seconds", "iterations", "tool_calls",
    "tokens_input", "tokens_output", "cost_usd", "human_interventions",
    "tests_run", "tests_passed", "tests_failed", "pytest_exit_code",
    "criteria_results", "deploy_healthy",
    "rubric_pipeline_completeness", "rubric_tool_integration", "rubric_error_recovery",
    "rubric_trace_quality", "rubric_time_efficiency", "rubric_autonomy",
    "resource_peak_memory_bytes", "framework_metrics",
    "score_pipeline_completeness", "score_efficiency", "score_orchestration",
    "score_autonomy", "overall_score",
]


def story_budgets() -> dict[str, float]:
    budgets = {}
    for f in STORIES.rglob("*.yaml"):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        budgets[data["id"]] = float(data.get("time_budget_seconds", 600))
    return budgets


def main() -> int:
    if not PINNED_RUNS:
        print("PINNED_RUNS is empty: fill in the reported run ids first.")
        return 1

    store = ResultStore(db_path=STORE)
    con = store._conn
    failures: list[str] = []

    version = con.execute("SELECT version FROM store_meta").fetchone()[0]
    if version < 5:
        failures.append(f"store schema {version} < 5: verification columns missing")

    budgets = story_budgets()
    reported: dict[str, dict] = {}
    rows: list[tuple] = []

    for label, (run_id, stories) in sorted(PINNED_RUNS.items()):
        run = con.execute(
            "SELECT run_id, model, started_at, finished_at FROM runs WHERE run_id = ?", [run_id]
        ).fetchone()
        if run is None:
            failures.append(f"{label}: run {run_id} not in store")
            continue
        if run[3] is None:
            failures.append(f"{label}: run {run_id} never finished")

        scores = {p: recompute_platform_likert_from_store(store, run_id, p, budgets) for p in PLATFORMS}

        # Platform-level score_* columns are written onto every execution
        # row by the recompute above (store.update_platform_scores).
        run_rows = con.execute(
            f"SELECT {', '.join(EXEC_COLS)} FROM executions "
            "WHERE run_id = ? AND story_id IN (SELECT unnest(?)) "
            "ORDER BY story_id, platform_id, repeat_index",
            [run_id, stories],
        ).fetchall()

        expected = len(PLATFORMS) * REPEATS * len(stories)
        if len(run_rows) != expected:
            failures.append(f"{label}: expected {expected} executions, store has {len(run_rows)}")
        for r in run_rows:
            row = dict(zip(EXEC_COLS, r))
            if row["platform_id"] not in PLATFORMS:
                failures.append(f"{label}: unexpected platform {row['platform_id']}")
            if row["criteria_results"] is None:
                failures.append(f"{label}: {row['execution_id']} has no acceptance results")
        rows.extend(run_rows)
        reported[label] = {
            "run_id": run_id,
            "model": run[1],
            "started_at": str(run[2]),
            "finished_at": str(run[3]),
            "stories": stories,
            "executions": len(run_rows),
            "platform_scores": scores,
        }

    store.close()

    if failures:
        print("ASSERTION FAILURES (nothing written):")
        for f in failures:
            print("  " + f)
        return 1

    OUT_JSON.write_text(json.dumps(reported, indent=2, default=str) + "\n")
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(EXEC_COLS)
        w.writerows(rows)
    print(f"wrote {OUT_JSON.relative_to(REPO)} and {OUT_CSV.relative_to(REPO)} ({len(rows)} executions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
