# Reported runs

`extract_reported_runs.py` pins the executions the paper reports and asserts
the paper's token totals against `results/desmet.duckdb`. Run it with
`uv run --with duckdb python docs/paper/data/extract_reported_runs.py`; it
writes `reported-runs.json` here and `docs/paper/artifact/results-reported.csv`.

## Selection rule

For each platform, the reported run is its complete end-to-end US-001
execution; runs cancelled part-way during adapter development are excluded.

| Pass | Run ID | Model | Platforms |
|---|---|---|---|
| Baseline | `0273188d…` (23 Apr 2026) | `gpt-4.1-mini` | OpenAI Agents SDK, LangGraph, CrewAI, Microsoft Agent Framework |
| Baseline | `51ea5ac9…` (21 Apr 2026) | `gpt-4.1-mini` | Google ADK |
| Cross-model | `2b6c4730…` (20 Apr 2026) | `anthropic/claude-sonnet-4.6` | all five |

Full IDs are in `reported-runs.json`.

## Reading the export

- `status` is `completed` for every execution in the store (it records that
  the harness finished the run, not that every stage passed). Stage outcome
  is carried by `score_pipeline_completeness` (3.0 = all stages passed on
  the 1–5 scale's input; 1.0 = at least one stage failed) and by the
  per-stage JSON file named in `trace_path`.
- `tokens_total` is `tokens_input + tokens_output`.
- `framework_metrics` is a JSON object with `tokens_per_stage`,
  `iteration_ratio`, `redundant_tool_call_rate`, `tool_failure_rate`,
  `first_action_latency_ms`, `framework_overhead_ms`.
- The Sonnet rows for Google ADK and Microsoft Agent Framework are included
  for completeness; the paper does not report their token totals because
  provider-level failures truncated the comparable work (see §6.2).
