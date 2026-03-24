# Automated Framework Metrics

**Date:** 2026-03-24
**Status:** Draft

## Problem

The current scoring system relies on manual rubric scoring (0-3) for 6 dimensions, which are then aggregated into 4 cross-cutting dimensions (1-5 Likert). These rubric scores measure subjective assessments. There are no automated, objective metrics that measure framework-specific behaviour independent of LLM quality.

## Goal

Add 6 automated metrics computed from trace data that measure framework orchestration quality. These metrics vary between frameworks given the same LLM, making them pure framework signals.

## The 6 Metrics

| Metric | Field | Formula | Unit | What it measures |
|---|---|---|---|---|
| Tokens per stage | `tokens_per_stage` | `total_tokens` (computed per-stage, averaged at story level) | float | Framework's system prompt/scaffolding verbosity |
| Iteration ratio | `iteration_ratio` | `iterations / max_iterations` | float (0-1) | Orchestration routing efficiency |
| First-action latency | `first_action_latency_ms` | `first_tool_call.timestamp - trace.start_time` | ms | Framework bootstrap + planning overhead |
| Redundant tool calls | `redundant_tool_call_rate` | `duplicate_calls / total_calls` | float (0-1) | State management quality (context loss = re-reads) |
| Tool failure rate | `tool_failure_rate` | `failed_calls / total_calls` | float (0-1) | Tool serialization/deserialization reliability |
| Framework overhead | `framework_overhead_ms` | `wall_clock_ms - sum(llm_call_durations)` | ms | Time spent in framework code vs waiting on LLM |

### Definitions and edge cases

**Tokens per stage**: Total tokens (input + output) consumed in a single stage. At the per-stage level this is simply the trace's token count. At story level, it is averaged across completed stages. Different frameworks inject different amounts of system prompt scaffolding, making this a framework signal despite being raw token count.

**Duplicate calls**: A tool call with the same `(tool_name, sorted_json(arguments))` pair as a previous call in the same stage trace. Arguments are normalised to sorted JSON strings before comparison to handle key ordering differences. Only read-only tools are checked: `read_file`, `list_directory`, `search_code`. Write tools (`write_file`, `execute_shell`) and diagnostic tools (`check_completion`) are excluded since repeating them may be intentional.

**Failed calls**: A tool call where `success == False` on the `ToolCall` record.

**Division by zero**: All rate metrics (`iteration_ratio`, `redundant_tool_call_rate`, `tool_failure_rate`) return `0.0` when the denominator is zero. `iteration_ratio` returns `0.0` if `max_iterations == 0`.

**No tool calls**: When a stage makes zero tool calls, `first_action_latency_ms` is `None` (excluded from story-level averaging), and both rate metrics return `0.0`.

**Negative framework overhead**: If LLM duration tracking is imprecise and exceeds wall clock time, `framework_overhead_ms` is clamped to `0.0`.

## Architecture

### Layer 1: Per-stage computation

New function in `src/desmet/adapters/_tracing.py`:

```python
def compute_framework_metrics(
    trace: AgentTrace,
    max_iterations: int,
) -> dict[str, float | None]:
```

Called from `_execute_stage()` in `_base.py` after `_run_agent()` returns and before `build_stage_result()`. This centralises the computation — individual adapters do not need to call it. Returns a dict with the 6 metric values. The dict is passed to `build_stage_result()` via `**extra_fields` and stored on `StageResult.framework_metrics`.

### Layer 2: LLM duration tracking

New field on `AgentTrace`:

```python
total_llm_duration_ms: float = 0.0
```

New helper in `_tracing.py`:

```python
def record_llm_duration(trace: AgentTrace, duration_ms: float) -> None:
    trace.total_llm_duration_ms += duration_ms
```

Per-adapter recording:

- **LangGraph** (`langgraph.py`): Wrap `llm.invoke()` and `llm_with_tools.invoke()` in `planner_node` and `executor_node` with `time.monotonic()`. These are the only two LLM call sites. Record the delta via `record_llm_duration()` on the trace (passed through state or closure). Cleanest and most accurate approach.

- **CrewAI** (`crewai.py`): Check if `crewai.events.types.llm_events.LLMCallStartedEvent` exists. If it does, register a start handler that records `time.monotonic()`, then compute duration as `end - start` in the existing `LLMCallCompletedEvent` handler. If `LLMCallStartedEvent` does not exist, set `total_llm_duration_ms` to `None` (unavailable) and `framework_overhead_ms` will be `None` for CrewAI runs.

- **OpenAI Agents SDK** (`openai_agents.py`): Use a custom `httpx` event hook on the `AsyncOpenAI` client to measure HTTP round-trip time for each LLM API call. Register `request`/`response` event hooks that accumulate timing. This captures actual LLM API latency without conflating tool execution time.

For all adapters, the LLM duration is a best-effort estimate. Framework overhead = wall_clock - LLM_time is still meaningful even if LLM_time is slightly imprecise, because the *relative* framework overhead across platforms is what matters for comparison. When LLM duration is unavailable (`None`), `framework_overhead_ms` is also `None`.

### Layer 3: StageResult storage

New field on `StageResult` base class:

```python
framework_metrics: dict[str, float | None] = field(default_factory=dict)
```

### Layer 4: Per-story aggregation

Aggregation happens in the runner's `_run_story()` method where `stage_results` is still available. The aggregated metrics dict is stored on `StoryResult` as a new `framework_metrics` field, which `StoryMetrics.from_story_result()` then reads.

Aggregation strategy:

- **Averaged** across stages: `tokens_per_stage`, `iteration_ratio`, `redundant_tool_call_rate`, `tool_failure_rate`, `first_action_latency_ms`
- **Summed** across stages: `framework_overhead_ms`

`None` values are excluded from averages (not treated as zero). If all stages have `None` for a metric, the story-level value is also `None`.

These are stored in `story_metrics` in the results JSON under a `framework_metrics` sub-dict.

### Layer 5: Dashboard

**Results Overview page** — new "Framework Metrics" section below existing content. A comparison table with platforms as columns and metrics as rows. Values are averaged across all story runs for each platform.

**Scoring page** — show the framework metrics as read-only computed values in a small card above or beside the manual rubric sliders. Gives the scorer context about what the framework actually did.

Both consume a new API endpoint:

```
GET /api/dashboard/framework-metrics
```

Returns `{platforms: [{platform_id, platform_name, metrics: {metric_name: avg_value}}]}`.

## Data flow

```
_execute_stage() in _base.py
  → adapter._run_agent(...)  (internally calls finish_trace)
  → compute_framework_metrics(trace, context.max_iterations)
  → build_stage_result(result_cls, ..., framework_metrics=metrics)
  → StageResult.framework_metrics = {...}

_run_story() in runner.py
  → aggregate stage framework_metrics into story-level dict
  → StoryResult.framework_metrics = aggregated dict
  → saved to evaluation_results.json

Dashboard reads results
  → GET /api/dashboard/framework-metrics
  → table/card rendering
```

## Serialization

The following serialization points need explicit updates to include `framework_metrics`:

1. **`runner.py _save_stage_traces()`** — add `stage_entry["framework_metrics"] = sr.framework_metrics` to the per-stage trace JSON.
2. **`metrics.py EvaluationMetrics.to_dict()`** — include `framework_metrics` in the story_metrics dict that is written to `evaluation_results.json`.

## Files changed

| File | Change |
|---|---|
| `src/desmet/harness/trace.py` | Add `total_llm_duration_ms` field to `AgentTrace` |
| `src/desmet/harness/results.py` | Add `framework_metrics` field to `StageResult` |
| `src/desmet/harness/story.py` | Add `framework_metrics` field to `StoryResult` |
| `src/desmet/adapters/_tracing.py` | Add `compute_framework_metrics()`, `record_llm_duration()` |
| `src/desmet/adapters/_base.py` | Call `compute_framework_metrics()` in `_execute_stage()` |
| `src/desmet/adapters/langgraph.py` | Wrap LLM invoke calls with `time.monotonic()` timing |
| `src/desmet/adapters/crewai.py` | Add LLMCallStartedEvent handler (if available) for timing |
| `src/desmet/adapters/openai_agents.py` | Add httpx event hooks for LLM call timing |
| `src/desmet/harness/runner.py` | Aggregate framework_metrics in `_run_story()`, update `_save_stage_traces()` |
| `src/desmet/harness/metrics.py` | Add framework_metrics to `StoryMetrics`, update `to_dict()` |
| `src/desmet/webui/api.py` | Add `GET /api/dashboard/framework-metrics` endpoint |
| `src/desmet/webui/frontend/src/lib/api.ts` | Add `fetchFrameworkMetrics()` |
| `src/desmet/webui/frontend/src/lib/pages/ResultsOverview.svelte` | Add framework metrics table |
| `src/desmet/webui/frontend/src/lib/pages/Scoring.svelte` | Show computed metrics card |

## What stays the same

- Manual rubric scoring (0-3) — unchanged
- 4 computed cross-cutting dimensions — unchanged
- Existing charts and dashboard — unchanged
- Trace collection — unchanged (we read existing data, just compute new metrics from it)
