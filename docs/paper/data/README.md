# Reported runs

`extract_reported_runs.py` pins the executions the paper reports, checks
them against `results/desmet.duckdb`, and exports them. Run it with the
console stopped (DuckDB allows one writer):

```bash
uv run python docs/paper/data/extract_reported_runs.py
```

It writes nothing if any check fails. On success it writes:

| File | Contents |
|---|---|
| `reported-runs.json` (here) | Per run label: run ID, model, times, stories, the run manifest (git SHA and dirty flag, provider, deploy and execution mode, stage timeout, temperature, prompts hash, image digests, pricing snapshot) and recomputed platform scores |
| `summary.json` (here) | The paper's tables: one cell per run label × platform (see below) |
| `../artifact/results-reported.csv` | One row per execution |
| `../artifact/results-stages.csv` | One row per execution × stage |

To try it on other runs (for example a smoke run) without touching these
files, pin runs on the command line and write elsewhere. `--store` can point
at a copy of the database, so the live one is never written:

```bash
uv run python docs/paper/data/extract_reported_runs.py \
  --run glm-5.3/US-001=<run_id> --repeats 1 --store <copy.duckdb> --out-dir <dir>
```

## Selection rule

The reported dataset is exactly the runs in `PINNED_RUNS`: one per model
(and scenario), each with every platform × 3 repeats, all recorded by store
schema ≥ 7 with a run manifest. A run started from a dirty tree is reported
as a warning.

## summary.json

`summarise.py` builds it from the two CSVs and `reported-runs.json` only
(standard library, no store), so the artifact can reproduce it with
`python summarise.py results/`. Each cell holds:

- `tokens_total`, `cost_usd`, `wall_clock_seconds`, `llm_calls`,
  `prompt_tokens_per_call`: median, min and max over the repeats, plus
  each repeat's value (`null` = unknown, excluded; `n` counts known values);
- `correctness`: hidden acceptance criteria met / total, per-criterion pass
  counts (for the heatmap), and counts of passing executions (all criteria
  met), green workspace tests, healthy deploys, and all-stages-passed;
- `cost_efficiency`: cost per criterion met, and cost and tokens per
  passing execution;
- `failures`: failed stages by cause (`timeout`, then `budget` if the LLM
  call budget ran out, else `task`);
- `stages`: the same statistics per stage, with per-stage failure causes.

`prompt_tokens_per_call` is `tokens_input / llm_calls` over the stages whose
call count is known: how much history each call resends. A timed-out stage
has no call count, so it is left out of this ratio but still counts towards
tokens and cost.

## Reading the CSVs

- `status` is `completed` for every execution (the harness finished the
  run, not that every stage passed); use `stages_passed`, `criteria_results`,
  `tests_*` and `deploy_healthy`.
- `tokens_total` is `tokens_input + tokens_output`. `llm_calls` is the sum
  of per-stage calls, empty if any stage's count is unknown.
- `stages_file` names the execution's per-stage JSON (`results/stages/` in
  the artifact). Local paths are not exported.
- In `results-stages.csv`, `llm_calls` is empty for a timed-out stage;
  `error_message` is not exported (it can carry paths and remote output).
