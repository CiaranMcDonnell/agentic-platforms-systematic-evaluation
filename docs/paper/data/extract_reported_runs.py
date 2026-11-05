"""Pin the runs the FormaliSE paper reports and export them as the artifact.

Usage (stop the webui first — DuckDB allows one writer):
    uv run python docs/paper/data/extract_reported_runs.py

To try the export on other runs without touching the paper's outputs, pin
them on the command line and write elsewhere (``--store`` can point at a
copy of the database so the live one is never written):
    uv run python docs/paper/data/extract_reported_runs.py \
        --run glm-5.3/US-001=<run_id> --repeats 1 --out-dir <dir> [--store <db>]

Selection rule: the reported dataset is exactly the runs listed in
PINNED_RUNS, all produced by one harness version (store schema >= 7, so
stage outcomes and timeouts, workspace tests, hidden acceptance tests, the
harness-side deploy health check and the run manifest are recorded for
every execution).

Before exporting, each pinned run's 1-5 Likert scores are recomputed from
the stored rubric data so the artifact matches the current scoring code
(submit_score only writes rubric columns).  The script fails without
writing anything if a pinned run is missing, incomplete, has an unexpected
number of executions or stage rows, or has no manifest.

Outputs:
- reported-runs.json: per label, the run, its manifest and platform scores;
- results-reported.csv: one row per execution;
- results-stages.csv: one row per (execution, stage), with failure cause;
- summary.json: the per-platform x model tables (see summarise.py).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import yaml

from desmet.harness.metrics import recompute_platform_likert_from_store
from desmet.harness.store import ResultStore

sys.path.insert(0, str(Path(__file__).resolve().parent))
from summarise import STAGES, failure_cause, load, summarise  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
STORE = REPO / "results" / "desmet.duckdb"
STORIES = REPO / "data" / "stories"
DATA_DIR = Path(__file__).resolve().parent
ARTIFACT_DIR = REPO / "docs" / "paper" / "artifact"

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
# (they identify the author's machine) and are deliberately excluded;
# stages_file (the stage JSON's file name) links a row to results/stages/.
EXEC_COLS = [
    "execution_id", "run_id", "platform_id", "story_id", "repeat_index", "status",
    "execution_mode", "stages_passed", "wall_clock_seconds", "iterations", "tool_calls",
    "tokens_input", "tokens_output", "cost_usd", "human_interventions",
    "tests_run", "tests_passed", "tests_failed", "pytest_exit_code",
    "reported_tests_run", "reported_tests_passed", "reported_tests_failed",
    "criteria_results", "deploy_healthy",
    "rubric_pipeline_completeness", "rubric_tool_integration", "rubric_error_recovery",
    "rubric_trace_quality", "rubric_time_efficiency", "rubric_autonomy",
    "resource_peak_memory_bytes", "resource_avg_cpu_percent", "resource_net_tx_bytes",
    "framework_metrics",
    "score_pipeline_completeness", "score_efficiency", "score_orchestration",
    "score_autonomy", "overall_score",
]
# Prepended / appended to EXEC_COLS in the CSV.
EXEC_EXTRA_HEAD = ["label", "model"]
EXEC_EXTRA_TAIL = ["tokens_total", "llm_calls", "stages_file"]

STAGE_DB_COLS = [
    "execution_id", "stage_name", "success", "timed_out", "wall_clock_seconds",
    "iterations", "tool_calls", "tokens_input", "tokens_output", "cost_usd",
    "human_interventions",
]
# error_message is left out: it can carry paths and remote output.
STAGE_COLS = [
    "label", "model", "execution_id", "run_id", "platform_id", "story_id", "repeat_index",
    "stage_name", "success", "timed_out", "budget_exhausted", "failure_cause",
    "llm_calls", "tool_calls", "tokens_input", "tokens_output", "cost_usd",
    "wall_clock_seconds", "human_interventions",
]

MANIFEST_COLS = [
    "git_sha", "git_dirty", "provider", "deploy_mode", "execution_mode",
    "stage_timeout_seconds", "temperature", "prompts_sha256", "image_digests",
    "pricing_snapshot",
]
MANIFEST_JSON_COLS = {"image_digests", "pricing_snapshot"}


def story_budgets() -> dict[str, float]:
    budgets = {}
    for f in STORIES.rglob("*.yaml"):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        budgets[data["id"]] = float(data.get("time_budget_seconds", 600))
    return budgets


def stage_budget_flags(trace_path: str | None) -> dict[str, bool]:
    """Per-stage budget_exhausted flags from the stage JSON (not in the store)."""
    if not trace_path:
        return {}
    path = REPO / trace_path.replace("\\", "/")
    if not path.exists():
        return {}
    stages = json.loads(path.read_text(encoding="utf-8")).get("stages", {})
    return {
        name: bool((s.get("framework_metrics") or {}).get("budget_exhausted"))
        for name, s in stages.items()
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--run", action="append", default=[], metavar="LABEL=RUN_ID[:STORY,...]",
                   help="pin a run instead of PINNED_RUNS (repeatable; stories default to US-001)")
    p.add_argument("--repeats", type=int, default=REPEATS)
    p.add_argument("--store", type=Path, default=STORE)
    p.add_argument("--out-dir", type=Path,
                   help="write every output here instead of docs/paper/{data,artifact}")
    return p.parse_args(argv)


def pinned_from_args(specs: list[str]) -> dict[str, tuple[str, list[str]]]:
    pinned = {}
    for spec in specs:
        label, _, rest = spec.partition("=")
        run_id, _, stories = rest.partition(":")
        pinned[label] = (run_id, stories.split(",") if stories else ["US-001"])
    return pinned


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    pinned = pinned_from_args(args.run) if args.run else PINNED_RUNS
    if not pinned:
        print("PINNED_RUNS is empty: fill in the reported run ids first (or pass --run).")
        return 1

    if args.out_dir:
        out_json = args.out_dir / "reported-runs.json"
        out_summary = args.out_dir / "summary.json"
        out_csv = args.out_dir / "results-reported.csv"
        out_stages = args.out_dir / "results-stages.csv"
    else:
        out_json = DATA_DIR / "reported-runs.json"
        out_summary = DATA_DIR / "summary.json"
        out_csv = ARTIFACT_DIR / "results-reported.csv"
        out_stages = ARTIFACT_DIR / "results-stages.csv"

    store = ResultStore(db_path=args.store)
    con = store._conn
    failures: list[str] = []
    warnings: list[str] = []

    version = con.execute("SELECT version FROM store_meta").fetchone()[0]
    if version < 7:
        failures.append(f"store schema {version} < 7: verification or stage columns missing")

    budgets = story_budgets()
    reported: dict[str, dict] = {}
    exec_rows: list[list] = []
    stage_rows: list[list] = []

    for label, (run_id, stories) in sorted(pinned.items()):
        run = con.execute(
            f"SELECT model, started_at, finished_at, {', '.join(MANIFEST_COLS)} "
            "FROM runs WHERE run_id = ?",
            [run_id],
        ).fetchone()
        if run is None:
            failures.append(f"{label}: run {run_id} not in store")
            continue
        model, started_at, finished_at = run[:3]
        manifest = dict(zip(MANIFEST_COLS, run[3:]))
        for col in MANIFEST_JSON_COLS:
            if manifest[col]:
                manifest[col] = json.loads(manifest[col])
        if finished_at is None:
            failures.append(f"{label}: run {run_id} never finished")
        if manifest["git_sha"] is None:
            failures.append(f"{label}: run {run_id} has no manifest (pre-schema-6 run)")
        elif manifest["git_dirty"]:
            warnings.append(f"{label}: run {run_id} was started from a dirty tree at {manifest['git_sha'][:8]}")

        scores = {p: recompute_platform_likert_from_store(store, run_id, p, budgets) for p in PLATFORMS}

        # Platform-level score_* columns are written onto every execution
        # row by the recompute above (store.update_platform_scores).
        run_rows = con.execute(
            f"SELECT {', '.join(EXEC_COLS)}, trace_path FROM executions "
            "WHERE run_id = ? AND story_id IN (SELECT unnest(?)) "
            "ORDER BY story_id, platform_id, repeat_index",
            [run_id, stories],
        ).fetchall()

        expected = len(PLATFORMS) * args.repeats * len(stories)
        if len(run_rows) != expected:
            failures.append(f"{label}: expected {expected} executions, store has {len(run_rows)}")

        for r in run_rows:
            row = dict(zip(EXEC_COLS, r[:-1]))
            trace_path = r[-1]
            eid = row["execution_id"]
            if row["platform_id"] not in PLATFORMS:
                failures.append(f"{label}: unexpected platform {row['platform_id']}")
            if row["criteria_results"] is None:
                failures.append(f"{label}: {eid} has no acceptance results")

            stages = {
                s[1]: dict(zip(STAGE_DB_COLS, s))
                for s in con.execute(
                    f"SELECT {', '.join(STAGE_DB_COLS)} FROM stage_executions WHERE execution_id = ?",
                    [eid],
                ).fetchall()
            }
            if set(stages) != set(STAGES):
                failures.append(f"{label}: {eid} has stage rows {sorted(stages)}, expected {STAGES}")
            flags = stage_budget_flags(trace_path)
            if not flags:
                failures.append(f"{label}: {eid} stage JSON missing ({trace_path})")

            calls = [stages[st]["iterations"] for st in STAGES if st in stages]
            llm_calls = sum(calls) if calls and None not in calls else None
            tokens_total = (
                row["tokens_input"] + row["tokens_output"]
                if row["tokens_input"] is not None and row["tokens_output"] is not None
                else None
            )
            stages_file = Path(trace_path.replace("\\", "/")).name if trace_path else None
            exec_rows.append(
                [label, model] + [row[c] for c in EXEC_COLS] + [tokens_total, llm_calls, stages_file]
            )

            for st in STAGES:
                s = stages.get(st)
                if s is None:
                    continue
                budget = flags.get(st, False)
                stage_rows.append([
                    label, model, eid, run_id, row["platform_id"], row["story_id"], row["repeat_index"],
                    st, s["success"], s["timed_out"], budget,
                    failure_cause(s["success"], s["timed_out"], budget),
                    s["iterations"], s["tool_calls"], s["tokens_input"], s["tokens_output"],
                    s["cost_usd"], s["wall_clock_seconds"], s["human_interventions"],
                ])

        reported[label] = {
            "run_id": run_id,
            "model": model,
            "started_at": str(started_at),
            "finished_at": str(finished_at),
            "stories": stories,
            "executions": len(run_rows),
            "manifest": manifest,
            "platform_scores": scores,
        }

    store.close()

    for w in warnings:
        print("warning: " + w)
    if failures:
        print("ASSERTION FAILURES (nothing written):")
        for f in failures:
            print("  " + f)
        return 1

    for path in (out_json, out_summary, out_csv, out_stages):
        path.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(reported, indent=2, default=str) + "\n", encoding="utf-8")
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(EXEC_EXTRA_HEAD + EXEC_COLS + EXEC_EXTRA_TAIL)
        w.writerows(exec_rows)
    with out_stages.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(STAGE_COLS)
        w.writerows(stage_rows)

    # Summarise from the CSVs just written, so the paper's numbers come
    # from exactly what the artifact ships.
    summary = summarise(*load(out_csv, out_stages, out_json))
    out_summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    for path in (out_json, out_csv, out_stages, out_summary):
        print(f"wrote {path}")
    print(f"{len(exec_rows)} executions, {len(stage_rows)} stage rows")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
