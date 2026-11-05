"""Aggregate the exported executions into the tables the paper reports.

Usage:
    python summarise.py RESULTS_DIR

RESULTS_DIR holds results-reported.csv, results-stages.csv and
reported-runs.json (the artifact's results/ directory).  The summary is
written to RESULTS_DIR/summary.json.  extract_reported_runs.py calls
summarise() directly and writes docs/paper/data/summary.json.  Standard library only, so the artifact can be
re-aggregated without the result store or the harness installed.

Every statistic is per (run label, platform): the median and range over
the repeats, with the per-repeat values kept so figures can plot points.
Unknown counts (a timed-out stage's LLM calls) are left out of a statistic,
never read as 0; ``n`` on each statistic says how many values it covers.

Definitions:
- A *passing* execution meets every hidden acceptance criterion.
- A stage's failure cause is ``timeout`` if the harness stopped it at the
  stage timeout, otherwise ``budget`` if it ran out of LLM calls, otherwise
  ``task`` (the stage ran to completion and failed its check).
- Prompt tokens per LLM call is tokens_input / llm_calls over the stages
  whose call count is known: how much context each call resends.
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

STAGES = ["requirements", "codegen", "testing", "deploy"]
CAUSES = ["timeout", "budget", "task"]


def _int(v: str | None) -> int | None:
    return None if v in (None, "") else int(float(v))


def _float(v: str | None) -> float | None:
    return None if v in (None, "") else float(v)


def _bool(v: str | None) -> bool | None:
    if v in (None, ""):
        return None
    return str(v).strip().lower() in ("true", "1")


def stat(values: list[float | None]) -> dict:
    """Median, range and per-repeat values; ``None`` entries are unknown."""
    known = [v for v in values if v is not None]
    out: dict = {"n": len(known), "values": values}
    if not known:
        return out | {"median": None, "min": None, "max": None}
    return out | {"median": statistics.median(known), "min": min(known), "max": max(known)}


def failure_cause(success: bool | None, timed_out: bool | None, budget: bool | None) -> str | None:
    if success:
        return None
    if timed_out:
        return "timeout"
    if budget:
        return "budget"
    return "task"


def per_call(tokens: int | None, calls: int | None) -> float | None:
    return tokens / calls if tokens is not None and calls else None


def load(exec_csv: Path, stage_csv: Path, runs_json: Path) -> tuple[list[dict], list[dict], dict]:
    with exec_csv.open(newline="", encoding="utf-8") as fh:
        execs = list(csv.DictReader(fh))
    with stage_csv.open(newline="", encoding="utf-8") as fh:
        stages = list(csv.DictReader(fh))
    runs = json.loads(runs_json.read_text(encoding="utf-8"))
    return execs, stages, runs


def summarise(execs: list[dict], stages: list[dict], runs: dict) -> dict:
    stages_by_exec: dict[str, dict[str, dict]] = defaultdict(dict)
    for s in stages:
        stages_by_exec[s["execution_id"]][s["stage_name"]] = s

    cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for e in execs:
        cells[(e["label"], e["platform_id"])].append(e)

    out_cells = []
    for (label, platform), rows in sorted(cells.items()):
        rows.sort(key=lambda r: (r["story_id"], _int(r["repeat_index"]) or 0))
        out_cells.append(_cell(label, platform, rows, stages_by_exec, runs.get(label, {})))

    return {
        "definitions": {
            "passing": "every hidden acceptance criterion met",
            "failure_cause": "timeout > budget > task, per failed stage",
            "prompt_tokens_per_call": "tokens_input / llm_calls over stages with a known call count",
            "statistics": "median and range over repeats; values lists each repeat (null = unknown)",
        },
        "cells": out_cells,
    }


def _cell(label: str, platform: str, rows: list[dict], stages_by_exec: dict, run: dict) -> dict:
    tokens, cost, wall, calls, ppc = [], [], [], [], []
    crit_met = crit_total = passing = tests_green = deploy_ok = stages_ok = 0
    criteria: dict[str, int] = Counter()
    causes: Counter = Counter()
    per_stage: dict[str, dict[str, list]] = {
        st: defaultdict(list) for st in STAGES
    }
    stage_causes: dict[str, Counter] = {st: Counter() for st in STAGES}

    for r in rows:
        tin, tout = _int(r["tokens_input"]), _int(r["tokens_output"])
        tokens.append(tin + tout if tin is not None and tout is not None else None)
        cost.append(_float(r["cost_usd"]))
        wall.append(_float(r["wall_clock_seconds"]))
        calls.append(_int(r["llm_calls"]))

        results = json.loads(r["criteria_results"]) if r["criteria_results"] else {}
        met = [k for k, v in results.items() if v is True]
        crit_met += len(met)
        crit_total += len(results)
        criteria.update({k: 0 for k in results})
        criteria.update(met)
        passing += bool(results) and len(met) == len(results)
        tests_green += (_int(r["tests_run"]) or 0) > 0 and _int(r["tests_failed"]) == 0
        deploy_ok += _bool(r["deploy_healthy"]) is True
        stages_ok += _bool(r["stages_passed"]) is True

        known_in = known_calls = 0
        for st in STAGES:
            s = stages_by_exec.get(r["execution_id"], {}).get(st)
            acc = per_stage[st]
            if s is None:
                for k in ("tokens_total", "tokens_input", "cost_usd", "wall_clock_seconds",
                          "llm_calls", "prompt_tokens_per_call"):
                    acc[k].append(None)
                continue
            sin, sout, sc = _int(s["tokens_input"]), _int(s["tokens_output"]), _int(s["llm_calls"])
            acc["tokens_total"].append(sin + sout if sin is not None and sout is not None else None)
            acc["tokens_input"].append(sin)
            acc["cost_usd"].append(_float(s["cost_usd"]))
            acc["wall_clock_seconds"].append(_float(s["wall_clock_seconds"]))
            acc["llm_calls"].append(sc)
            acc["prompt_tokens_per_call"].append(per_call(sin, sc))
            if sin is not None and sc:
                known_in += sin
                known_calls += sc
            cause = s["failure_cause"] or None
            if cause:
                causes[cause] += 1
                stage_causes[st][cause] += 1
        ppc.append(per_call(known_in, known_calls))

    n = len(rows)
    total_cost = sum(c for c in cost if c is not None)
    total_tokens = sum(t for t in tokens if t is not None)
    return {
        "label": label,
        "model": run.get("model"),
        "platform_id": platform,
        "stories": sorted({r["story_id"] for r in rows}),
        "repeats": n,
        "tokens_total": stat(tokens),
        "cost_usd": stat(cost),
        "wall_clock_seconds": stat(wall),
        "llm_calls": stat(calls),
        "prompt_tokens_per_call": stat(ppc),
        "correctness": {
            "criteria_met": crit_met,
            "criteria_total": crit_total,
            "criteria_rate": crit_met / crit_total if crit_total else None,
            "passing_executions": passing,
            "tests_green_executions": tests_green,
            "deploy_healthy_executions": deploy_ok,
            "stages_passed_executions": stages_ok,
            "executions": n,
            "per_criterion": {k: criteria[k] for k in sorted(criteria)},
        },
        "cost_efficiency": {
            "cost_per_criterion_met": total_cost / crit_met if crit_met else None,
            "cost_per_passing_execution": total_cost / passing if passing else None,
            "tokens_per_passing_execution": total_tokens / passing if passing else None,
        },
        "failures": {c: causes[c] for c in CAUSES},
        "stages": {
            st: {k: stat(v) for k, v in per_stage[st].items()}
            | {"failures": {c: stage_causes[st][c] for c in CAUSES}}
            for st in STAGES
        },
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.split("\n\n")[1])
        return 2
    results_dir = Path(argv[1])
    execs, stages, runs = load(
        results_dir / "results-reported.csv",
        results_dir / "results-stages.csv",
        results_dir / "reported-runs.json",
    )
    out = results_dir / "summary.json"
    out.write_text(json.dumps(summarise(execs, stages, runs), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(execs)} executions, {len(stages)} stage rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
