"""Pin the runs the FormaliSE paper reports and assert its numbers against the store.

Usage: uv run --with duckdb python docs/paper/data/extract_reported_runs.py

Selection rule (author, 2026-10-27): for each platform, the reported run is its
complete end-to-end US-001 execution; runs cancelled part-way during adapter
development are excluded. Baseline (gpt-4.1-mini) rows come from run 0273188d
except Google ADK, which comes from 51ea5ac9. The Sonnet cross-model pass is
whichever Sonnet run carries the token totals the thesis reports.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[3]
STORE = REPO / "results" / "desmet.duckdb"
OUT_JSON = Path(__file__).with_name("reported-runs.json")
OUT_CSV = REPO / "docs" / "paper" / "artifact" / "results-reported.csv"

BASELINE_PREFIXES = {"0273188d": ["openai_agents_sdk", "langgraph", "crewai", "microsoft_agent_framework"], "51ea5ac9": ["google_adk"]}
EXPECTED_BASELINE = {
    "openai_agents_sdk": 100_383,
    "langgraph": 190_309,
    "crewai": 103_776,
    "microsoft_agent_framework": 239_801,
    "google_adk": 56_764,
}
EXPECTED_SONNET = {"langgraph": 209_130, "openai_agents_sdk": 111_442, "crewai": 538_715}

EXEC_COLS = (
    "execution_id, run_id, platform_id, story_id, status, wall_clock_seconds, iterations, tool_calls, "
    "tokens_input, tokens_output, tokens_input + tokens_output AS tokens_total, cost_usd, human_interventions, "
    "score_pipeline_completeness, score_efficiency, score_orchestration, score_autonomy, overall_score, "
    "rubric_pipeline_completeness, rubric_tool_integration, rubric_error_recovery, rubric_trace_quality, "
    "rubric_time_efficiency, rubric_autonomy, resource_peak_memory_bytes, framework_metrics, trace_path"
)


def main() -> int:
    con = duckdb.connect(str(STORE), read_only=True)
    runs = con.execute("SELECT run_id, started_at, model FROM runs ORDER BY started_at").fetchall()
    by_prefix = {r[0][:8]: r for r in runs}

    reported: dict[str, dict] = {"baseline": {}, "sonnet": {}}
    rows: list[tuple] = []
    failures: list[str] = []

    # Baseline rows.
    for prefix, platforms in BASELINE_PREFIXES.items():
        run_id, started, model = by_prefix[prefix]
        for platform in platforms:
            row = con.execute(
                f"SELECT {EXEC_COLS} FROM executions WHERE run_id = ? AND platform_id = ? AND story_id LIKE 'US%001%'",
                [run_id, platform],
            ).fetchone()
            if row is None:
                failures.append(f"baseline {platform}: no execution in run {prefix}")
                continue
            tokens = row[10]
            if tokens != EXPECTED_BASELINE[platform]:
                failures.append(f"baseline {platform}: expected {EXPECTED_BASELINE[platform]:,} tokens, store has {tokens:,}")
            rows.append(row)
            reported["baseline"][platform] = {"run_id": run_id, "model": model, "started_at": str(started), "tokens": tokens}

    # Sonnet pass: find, per platform, the Sonnet execution whose total matches the thesis.
    sonnet = con.execute(
        f"SELECT {EXEC_COLS} FROM executions e JOIN runs r USING (run_id) "
        "WHERE lower(r.model) LIKE '%sonnet%' AND e.story_id LIKE 'US%001%' ORDER BY r.started_at"
    ).fetchall()
    sonnet_run_ids: set[str] = set()
    for platform, expected in EXPECTED_SONNET.items():
        match = [r for r in sonnet if r[2] == platform and r[10] == expected]
        if not match:
            seen = sorted({(r[1][:8], r[10]) for r in sonnet if r[2] == platform})
            failures.append(f"sonnet {platform}: expected {expected:,} tokens; Sonnet rows seen {seen}")
            continue
        rows.append(match[0])
        sonnet_run_ids.add(match[0][1])
        reported["sonnet"][platform] = {"run_id": match[0][1], "tokens": expected}
    # Carry the other platforms from the same Sonnet run(s) so the artifact holds the whole pass.
    for r in sonnet:
        if r[1] in sonnet_run_ids and r not in rows:
            rows.append(r)
            reported["sonnet"].setdefault(r[2], {"run_id": r[1], "tokens": r[10]})

    header = [c.strip().split(" AS ")[-1] for c in EXEC_COLS.split(",")]
    print(f"{'run':8} {'platform':16} {'status':10} {'tokens':>9} {'cost':>7} {'wall':>7}")
    for r in rows:
        print(f"{r[1][:8]:8} {r[2]:16} {r[4]:10} {r[10]:>9,} {r[11]:>7.3f} {r[5] / 60:>6.1f}m")

    if failures:
        print("\nASSERTION FAILURES:")
        for f in failures:
            print("  " + f)
        return 1

    OUT_JSON.write_text(json.dumps(reported, indent=2) + "\n")
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    print(f"\nwrote {OUT_JSON.relative_to(REPO)} and {OUT_CSV.relative_to(REPO)} ({len(rows)} executions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
