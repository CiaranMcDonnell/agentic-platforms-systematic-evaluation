# desmet — evaluation harness artifact (anonymised)

This artifact accompanies the FormaliSE 2027 submission *A Reproducible
Harness for Framework-Centric Evaluation of Agentic Platforms on Software
Engineering Pipelines*. It contains the harness source, platform
configuration, scenario definitions, prompt templates, Gherkin acceptance
criteria, and the executions the paper reports.

## Layout

| Path | Contents |
|---|---|
| `src/desmet/` | Harness package: `harness/` (runner, adapter ABC, metrics, trace, result store), `adapters/` (one subpackage per platform category; `_shared/` holds the stage template and tracing), `stages/`, `webui/` (management console), `cli.py` |
| `config/platforms.yaml` | Platform registry and per-difficulty budget defaults |
| `data/stories/` | Scenario YAML (US-001 is the reported scenario) |
| `data/prompts/`, `data/gherkin/` | Prompt templates and acceptance criteria per scenario |
| `results/results-reported.csv` | The reported executions exported from the result store, one row per execution |
| `results/results-stages.csv` | One row per execution × stage: tokens, cost, time, LLM calls, outcome and failure cause |
| `results/reported-runs.json` | The reported runs and each run's manifest (git SHA, prompts hash, image digests, pricing snapshot) |
| `results/summary.json`, `results/summarise.py` | The paper's per-platform × model tables, and the standard-library script that rebuilds them from the two CSVs |
| `results/stages/*.json` | Per-stage results for each reported execution |
| `pyproject.toml`, `uv.lock` | Dependency pins (the versions in the paper's Table III) |

## Reported executions

The reported runs (one per model, five platforms × three repeats each) are
listed with their manifests in `results/reported-runs.json`.

In the CSVs, `status` is `completed` for every row (it records that the
harness finished the run). Correctness is carried by `criteria_results`
(hidden acceptance criteria), `tests_*` (the workspace test suite run by
the harness), `deploy_healthy` (the harness's own health check) and
`stages_passed`. `framework_metrics` is a JSON object holding
`tokens_per_stage`, `iteration_ratio`, `redundant_tool_call_rate`,
`tool_failure_rate`, `first_action_latency_ms`, `framework_overhead_ms`,
`llm_calls` and `budget_exhausted_stages`. Rebuild the summary with
`python results/summarise.py results/`.

## Re-running US-001 on one platform

Requirements: Python 3.11+, [`uv`](https://docs.astral.sh/uv/), Docker (for
the Langfuse tracing service), an OpenAI API key, and — for Stage 4 — an SSH
deploy target (see `config/platforms.yaml` and the `DEPLOY_*` environment
variables in `src/desmet/llm_config.py` and `src/desmet/harness/runner.py`).

```bash
uv sync --extra langgraph            # or: crewai, openai-agents, agent-framework, google-adk
export OPENAI_API_KEY=...
export DESMET_MODEL=gpt-4.1-mini DESMET_TEMPERATURE=0
uv run desmet                        # starts Langfuse and the management console on :8042
```

In the console, open *New Run*, select the platform, the US-001 scenario,
all four stages, and the model, then *Start Benchmark Run*. Results are
written to `results/desmet.duckdb` and `results/logs/`; the *Scoring* page
presents the rubric form beside the Langfuse trace, and *Comparison* renders
the cross-platform view. `uv run desmet export-typst` emits the result
tables.

## Reading the CSVs

```python
import pandas as pd, json
df = pd.read_csv("results/results-reported.csv")
df["rtc"] = df["framework_metrics"].map(lambda s: json.loads(s)["redundant_tool_call_rate"])
print(df.groupby(["model", "platform_id"])[["tokens_total", "cost_usd"]].median())
stages = pd.read_csv("results/results-stages.csv")
print(stages.pivot_table(index=["model", "platform_id"], columns="stage_name", values="cost_usd", aggfunc="median"))
```
