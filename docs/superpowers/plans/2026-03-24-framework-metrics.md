# Automated Framework Metrics — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 6 automated metrics (tokens_per_stage, iteration_ratio, first_action_latency_ms, redundant_tool_call_rate, tool_failure_rate, framework_overhead_ms) computed from trace data, stored per-stage and aggregated per-story, displayed in the dashboard.

**Architecture:** `compute_framework_metrics()` in `_tracing.py` computes all 6 metrics from an `AgentTrace`. Called centrally from `_execute_stage()` in `_base.py`. Per-adapter LLM timing via `record_llm_duration()`. Results flow through `StageResult.framework_metrics` → runner aggregation → `story_metrics` in JSON → dashboard API → frontend table.

**Tech Stack:** Python dataclasses, FastAPI, Svelte 5, existing trace infrastructure

**Spec:** `docs/superpowers/specs/2026-03-24-framework-metrics-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/desmet/harness/trace.py` | Modify | Add `total_llm_duration_ms` field |
| `src/desmet/harness/results.py` | Modify | Add `framework_metrics` field to `StageResult` |
| `src/desmet/harness/story.py` | Modify | Add `framework_metrics` field to `StoryResult` |
| `src/desmet/adapters/_tracing.py` | Modify | Add `compute_framework_metrics()`, `record_llm_duration()` |
| `src/desmet/adapters/_base.py` | Modify | Call `compute_framework_metrics()` in `_execute_stage()` |
| `src/desmet/adapters/langgraph.py` | Modify | Add `time.monotonic()` around LLM invoke calls |
| `src/desmet/adapters/crewai.py` | Modify | Add LLM call timing in event bus handler |
| `src/desmet/adapters/openai_agents.py` | Modify | Add LLM call timing via response timestamps |
| `src/desmet/harness/runner.py` | Modify | Aggregate framework_metrics in `_run_story()`, serialize in `_save_stage_traces()` |
| `src/desmet/harness/metrics.py` | Modify | Add `framework_metrics` to `StoryMetrics`, update `to_dict()` |
| `src/desmet/webui/api.py` | Modify | Add `GET /api/dashboard/framework-metrics` |
| `src/desmet/webui/frontend/src/lib/api.ts` | Modify | Add `fetchFrameworkMetrics()` |
| `src/desmet/webui/frontend/src/lib/pages/ResultsOverview.svelte` | Modify | Add framework metrics table |
| `src/desmet/webui/frontend/src/lib/pages/Scoring.svelte` | Modify | Show computed metrics card |
| `tests/test_framework_metrics.py` | Create | Tests for `compute_framework_metrics()` |

---

### Task 1: Add `total_llm_duration_ms` to AgentTrace and `framework_metrics` to StageResult/StoryResult

**Files:**
- Modify: `src/desmet/harness/trace.py:35-48`
- Modify: `src/desmet/harness/results.py:23-61`
- Modify: `src/desmet/harness/story.py:110-152`

- [ ] **Step 1: Add field to AgentTrace**

In `src/desmet/harness/trace.py`, add after `total_cost_usd` (line 43):

```python
    total_llm_duration_ms: float = 0.0
```

- [ ] **Step 2: Add field to StageResult**

In `src/desmet/harness/results.py`, add after `human_interventions` (line 50):

```python
    # Automated framework metrics (computed from trace data)
    framework_metrics: dict[str, float | None] = field(default_factory=dict)
```

- [ ] **Step 3: Add field to StoryResult**

In `src/desmet/harness/story.py`, add after `raw_result` (line 152):

```python
    # Aggregated framework metrics across stages
    framework_metrics: dict[str, float | None] = field(default_factory=dict)
```

- [ ] **Step 4: Verify syntax**

Run: `uv run python -c "from desmet.harness.trace import AgentTrace; from desmet.harness.results import StageResult; from desmet.harness.story import StoryResult; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/desmet/harness/trace.py src/desmet/harness/results.py src/desmet/harness/story.py
git commit -m "feat(harness): add total_llm_duration_ms and framework_metrics fields"
```

---

### Task 2: Implement `compute_framework_metrics()` and `record_llm_duration()` with tests

**Files:**
- Modify: `src/desmet/adapters/_tracing.py`
- Create: `tests/test_framework_metrics.py`

- [ ] **Step 1: Write tests**

Create `tests/test_framework_metrics.py`:

```python
"""Tests for compute_framework_metrics()."""

import json
from datetime import datetime, timedelta, timezone

from desmet.adapters._tracing import compute_framework_metrics, record_llm_duration
from desmet.harness.trace import AgentTrace, ToolCall


def _make_trace(
    *,
    tool_calls: list[ToolCall] | None = None,
    iterations: int = 10,
    tokens_in: int = 5000,
    tokens_out: int = 3000,
    duration_seconds: float = 60.0,
    llm_duration_ms: float = 0.0,
) -> AgentTrace:
    now = datetime.now(timezone.utc)
    trace = AgentTrace(
        start_time=now,
        end_time=now + timedelta(seconds=duration_seconds),
        total_iterations=iterations,
        total_tokens_input=tokens_in,
        total_tokens_output=tokens_out,
        total_llm_duration_ms=llm_duration_ms,
    )
    if tool_calls:
        trace.tool_calls = tool_calls
    return trace


def _tool(name: str, args: dict, success: bool = True, offset_s: float = 1.0) -> ToolCall:
    return ToolCall(
        tool_name=name,
        arguments=args,
        result="ok",
        timestamp=datetime.now(timezone.utc) + timedelta(seconds=offset_s),
        duration_ms=10.0,
        success=success,
    )


class TestComputeFrameworkMetrics:
    def test_basic_metrics(self):
        trace = _make_trace(
            tool_calls=[
                _tool("read_file", {"path": "a.py"}, offset_s=2.0),
                _tool("write_file", {"path": "b.py"}, offset_s=5.0),
            ],
            iterations=10,
            tokens_in=5000,
            tokens_out=3000,
            llm_duration_ms=40000.0,
            duration_seconds=60.0,
        )
        m = compute_framework_metrics(trace, max_iterations=50)
        assert m["tokens_per_stage"] == 8000
        assert m["iteration_ratio"] == 10 / 50
        assert m["first_action_latency_ms"] is not None
        assert m["first_action_latency_ms"] > 0
        assert m["redundant_tool_call_rate"] == 0.0  # no duplicates
        assert m["tool_failure_rate"] == 0.0  # no failures
        assert m["framework_overhead_ms"] == 20000.0  # 60000 - 40000

    def test_no_tool_calls(self):
        trace = _make_trace(tool_calls=[], iterations=5)
        m = compute_framework_metrics(trace, max_iterations=50)
        assert m["first_action_latency_ms"] is None
        assert m["redundant_tool_call_rate"] == 0.0
        assert m["tool_failure_rate"] == 0.0

    def test_division_by_zero_max_iterations(self):
        trace = _make_trace(iterations=5)
        m = compute_framework_metrics(trace, max_iterations=0)
        assert m["iteration_ratio"] == 0.0

    def test_redundant_calls_detected(self):
        trace = _make_trace(tool_calls=[
            _tool("read_file", {"path": "a.py"}, offset_s=1.0),
            _tool("read_file", {"path": "a.py"}, offset_s=2.0),  # duplicate
            _tool("read_file", {"path": "b.py"}, offset_s=3.0),  # different
        ])
        m = compute_framework_metrics(trace, max_iterations=50)
        # 1 duplicate out of 3 read-only calls (rounded to 4dp)
        assert m["redundant_tool_call_rate"] == round(1 / 3, 4)

    def test_write_tools_excluded_from_duplicates(self):
        trace = _make_trace(tool_calls=[
            _tool("write_file", {"path": "a.py"}, offset_s=1.0),
            _tool("write_file", {"path": "a.py"}, offset_s=2.0),
        ])
        m = compute_framework_metrics(trace, max_iterations=50)
        assert m["redundant_tool_call_rate"] == 0.0

    def test_check_completion_excluded_from_duplicates(self):
        trace = _make_trace(tool_calls=[
            _tool("check_completion", {"stage": "codegen"}, offset_s=1.0),
            _tool("check_completion", {"stage": "codegen"}, offset_s=2.0),
        ])
        m = compute_framework_metrics(trace, max_iterations=50)
        assert m["redundant_tool_call_rate"] == 0.0

    def test_tool_failure_rate(self):
        trace = _make_trace(tool_calls=[
            _tool("read_file", {"path": "a.py"}, success=True),
            _tool("read_file", {"path": "b.py"}, success=False),
            _tool("write_file", {"path": "c.py"}, success=True),
            _tool("execute_shell", {"command": "ls"}, success=False),
        ])
        m = compute_framework_metrics(trace, max_iterations=50)
        assert m["tool_failure_rate"] == 2 / 4

    def test_negative_framework_overhead_clamped(self):
        trace = _make_trace(
            llm_duration_ms=100000.0,  # more than wall clock
            duration_seconds=60.0,
        )
        m = compute_framework_metrics(trace, max_iterations=50)
        assert m["framework_overhead_ms"] == 0.0

    def test_llm_duration_none_when_zero(self):
        trace = _make_trace(llm_duration_ms=0.0, duration_seconds=60.0)
        m = compute_framework_metrics(trace, max_iterations=50)
        assert m["framework_overhead_ms"] is None


class TestRecordLlmDuration:
    def test_accumulates(self):
        trace = AgentTrace()
        record_llm_duration(trace, 100.0)
        record_llm_duration(trace, 200.0)
        assert trace.total_llm_duration_ms == 300.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_framework_metrics.py -v`
Expected: FAIL — `compute_framework_metrics` and `record_llm_duration` not defined

- [ ] **Step 3: Implement `record_llm_duration()` and `compute_framework_metrics()`**

Add to `src/desmet/adapters/_tracing.py` after the existing `record_node_event` function:

```python
def record_llm_duration(trace: AgentTrace, duration_ms: float) -> None:
    """Accumulate LLM API call wall-clock time (ms) into the trace."""
    trace.total_llm_duration_ms += duration_ms


# ── Automated framework metrics ───────────────────────────────────────

# Tools whose repeated calls indicate framework state-management issues.
_DUPLICATE_CHECK_TOOLS = frozenset({"read_file", "list_directory", "search_code"})


def compute_framework_metrics(
    trace: AgentTrace,
    max_iterations: int,
) -> dict[str, float | None]:
    """Compute automated framework metrics from a completed stage trace.

    All metrics measure framework orchestration quality, not LLM output.
    Returns a dict of metric_name → value (or None when unavailable).
    """
    import json as _json

    total_tokens = trace.total_tokens_input + trace.total_tokens_output
    tool_calls = trace.tool_calls

    # ── Tokens per stage ──────────────────────────────────────────────
    tokens_per_stage = float(total_tokens)

    # ── Iteration ratio ───────────────────────────────────────────────
    iteration_ratio = (
        trace.total_iterations / max_iterations
        if max_iterations > 0 else 0.0
    )

    # ── First-action latency ──────────────────────────────────────────
    first_action_latency_ms: float | None = None
    if tool_calls and trace.start_time is not None:
        first_tc = min(tool_calls, key=lambda tc: tc.timestamp)
        delta = (first_tc.timestamp - trace.start_time).total_seconds()
        first_action_latency_ms = max(0.0, delta * 1000.0)

    # ── Redundant tool call rate ──────────────────────────────────────
    checkable = [
        tc for tc in tool_calls
        if tc.tool_name in _DUPLICATE_CHECK_TOOLS
    ]
    if checkable:
        seen: set[str] = set()
        duplicates = 0
        for tc in checkable:
            key = tc.tool_name + "|" + _json.dumps(tc.arguments, sort_keys=True)
            if key in seen:
                duplicates += 1
            else:
                seen.add(key)
        redundant_tool_call_rate = duplicates / len(checkable)
    else:
        redundant_tool_call_rate = 0.0

    # ── Tool failure rate ─────────────────────────────────────────────
    if tool_calls:
        failed = sum(1 for tc in tool_calls if not tc.success)
        tool_failure_rate = failed / len(tool_calls)
    else:
        tool_failure_rate = 0.0

    # ── Framework overhead ────────────────────────────────────────────
    # None when LLM duration was not recorded (0.0 means "not tracked").
    if trace.total_llm_duration_ms > 0:
        wall_ms = trace.duration_seconds * 1000.0
        framework_overhead_ms: float | None = max(0.0, wall_ms - trace.total_llm_duration_ms)
    else:
        framework_overhead_ms = None

    return {
        "tokens_per_stage": tokens_per_stage,
        "iteration_ratio": round(iteration_ratio, 4),
        "first_action_latency_ms": (
            round(first_action_latency_ms, 1)
            if first_action_latency_ms is not None else None
        ),
        "redundant_tool_call_rate": round(redundant_tool_call_rate, 4),
        "tool_failure_rate": round(tool_failure_rate, 4),
        "framework_overhead_ms": (
            round(framework_overhead_ms, 1)
            if framework_overhead_ms is not None else None
        ),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_framework_metrics.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/desmet/adapters/_tracing.py tests/test_framework_metrics.py
git commit -m "feat(metrics): implement compute_framework_metrics with tests"
```

---

### Task 3: Wire `compute_framework_metrics()` into `_execute_stage()`

**Files:**
- Modify: `src/desmet/adapters/_base.py:26-30,95-101`

- [ ] **Step 1: Add import**

Add `compute_framework_metrics` to the import from `_tracing`:

```python
from desmet.adapters._tracing import (
    build_stage_result,
    compute_framework_metrics,
    finish_trace,
    start_trace,
)
```

- [ ] **Step 2: Call compute_framework_metrics in _execute_stage**

In `_execute_stage`, after the `_run_agent` call (line 95-97) and before `build_stage_result` (line 98), add:

```python
            iterations, hit_limit = await self._run_agent(
                stage_name, prompt, system_msg, tools, trace, context,
            )
            fm = compute_framework_metrics(trace, context.max_iterations)
            return build_stage_result(
                result_cls, self.platform_info.id, stage_name,
                trace, success=not hit_limit, iterations=iterations,
                framework_metrics=fm,
            )
```

- [ ] **Step 3: Verify syntax**

Run: `uv run python -c "from desmet.adapters._base import ToolAgentAdapter; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/desmet/adapters/_base.py
git commit -m "feat(adapters): wire compute_framework_metrics into _execute_stage"
```

---

### Task 4: Add LLM duration timing to LangGraph adapter

**Files:**
- Modify: `src/desmet/adapters/langgraph.py:135-158`

- [ ] **Step 1: Add import**

Add `record_llm_duration` to the existing `_tracing` import and add `time`:

```python
import time
```

(at top of file — check if `time` is already imported)

```python
from desmet.adapters._tracing import (
    build_stage_result,
    finish_trace,
    record_llm_duration,
    record_message,
    record_node_event,
    record_tool_call,
    record_usage,
    start_trace,
)
```

- [ ] **Step 2: Wrap planner_node LLM call with timing**

The `planner_node` function (around line 139) calls `llm.invoke()`. The trace is not directly accessible inside the node function, so store timing on the state and record it in the streaming loop.

Simpler approach: use a nonlocal accumulator in `_build_graph`:

In `_build_graph`, before the node definitions, add:

```python
        _llm_durations: list[float] = []
```

Wrap the `llm.invoke()` in `planner_node`:

```python
        def planner_node(state: AgentState) -> dict:
            sys = SystemMessage(content=(
                f"You are a planning assistant for the '{state['stage']}' stage of a "
                "software development lifecycle. Produce a concise numbered plan."
            ))
            t0 = time.monotonic()
            response = llm.invoke([sys] + state["messages"])
            _llm_durations.append((time.monotonic() - t0) * 1000)
            return {"plan": response.content, "messages": [response]}
```

Wrap `llm_with_tools.invoke()` in `executor_node`:

```python
        def executor_node(state: AgentState) -> dict:
            sys = SystemMessage(content=(
                f"Stage: {state['stage']}\nPlan:\n{state['plan']}\n"
                "Execute the next step. Use tools to write files or run commands. "
                f"Working directory: {state['workspace']}"
            ))
            t0 = time.monotonic()
            response = llm_with_tools.invoke([sys] + state["messages"])
            _llm_durations.append((time.monotonic() - t0) * 1000)
            return {"messages": [response]}
```

Return `_llm_durations` from `_build_graph` alongside the compiled graph. Change signature:

```python
    def _build_graph(self, llm, tools: list) -> tuple:
```

And at the end:

```python
        return builder.compile(), _llm_durations
```

- [ ] **Step 3: Update `_run_graph` to use the durations list**

In `_run_graph` (around line 202), update the graph construction call:

```python
        graph, llm_durations = self._build_graph(self._llm, tools)
```

After the `async for` streaming loop ends, before `finish_trace`, add:

```python
        for d in llm_durations:
            record_llm_duration(trace, d)
```

- [ ] **Step 4: Verify syntax**

Run: `uv run python -c "from desmet.adapters.langgraph import LangGraphAdapter; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/desmet/adapters/langgraph.py
git commit -m "feat(langgraph): add LLM call duration tracking"
```

---

### Task 5: Add LLM duration timing to CrewAI adapter

**Files:**
- Modify: `src/desmet/adapters/crewai.py:136-169`

- [ ] **Step 1: Check if LLMCallStartedEvent exists**

Run: `uv run python -c "from crewai.events.types.llm_events import LLMCallStartedEvent; print('exists')" 2>&1 || echo "not found"`

If it exists, proceed with paired start/end timing. If not, use a simpler approach: record `time.monotonic()` as `_last_llm_start` before each kickoff, then on each `LLMCallCompletedEvent`, estimate duration from the response metadata if available.

- [ ] **Step 2: Add timing to event handler**

In `_register_llm_event_handler`, the `_on_llm_completed` handler already captures per-call data. Add timing support.

If `LLMCallStartedEvent` exists:

```python
            @crewai_event_bus.on(LLMCallStartedEvent)
            def _on_llm_started(event) -> None:
                if not self._collecting_llm:
                    return
                self._last_llm_start = time.monotonic()
```

Then in `_on_llm_completed`, compute duration:

```python
                if hasattr(self, '_last_llm_start') and self._last_llm_start > 0:
                    call_data["duration_ms"] = (time.monotonic() - self._last_llm_start) * 1000
                    self._last_llm_start = 0.0
```

If `LLMCallStartedEvent` does NOT exist, skip this step — CrewAI's `framework_overhead_ms` will be `None`.

- [ ] **Step 3: Record accumulated LLM duration on trace**

In `_run_agent`, after `llm_calls = self._stop_llm_collection()` (around line 374), add:

```python
        # Record LLM call durations on trace
        from desmet.adapters._tracing import record_llm_duration
        for call in llm_calls:
            if call.get("duration_ms", 0) > 0:
                record_llm_duration(trace, call["duration_ms"])
```

- [ ] **Step 4: Add `_last_llm_start` attribute to `__init__`**

```python
        self._last_llm_start: float = 0.0
```

- [ ] **Step 5: Verify syntax**

Run: `uv run python -c "from desmet.adapters.crewai import CrewAIAdapter; print('OK')" 2>&1`
Expected: `OK` (or ImportError for crewai if not installed — that's fine)

- [ ] **Step 6: Commit**

```bash
git add src/desmet/adapters/crewai.py
git commit -m "feat(crewai): add LLM call duration tracking via event bus"
```

---

### Task 6: Add LLM duration timing to OpenAI Agents SDK adapter

**Files:**
- Modify: `src/desmet/adapters/openai_agents.py:143-218`

- [ ] **Step 1: Add timing around each Runner.run() call**

In `_run_agent`, the `Runner.run()` call is on line 198. We cannot directly measure individual LLM calls, but we can measure total time spent in `Runner.run()` minus tool execution time. The trace already has tool call durations via `record_tool_call`.

Simpler approach: measure wall-clock per `Runner.run()` call, subtract the tool execution time recorded in that iteration's trace additions.

Before the `for attempt` loop, add:

```python
        from desmet.adapters._tracing import record_llm_duration
```

Around each `Runner.run()` call:

```python
            tool_time_before = sum(tc.duration_ms for tc in trace.tool_calls)
            run_t0 = time.monotonic()
            result = await Runner.run(agent, input=input_msg, max_turns=max_turns)
            run_duration_ms = (time.monotonic() - run_t0) * 1000

            # Extract trace data from this run
            iterations, tool_call_count = self._extract_trace(
                trace, result, cb=cb, t0=t0, tool_call_count=tool_call_count,
                model=self._model_name,
            )

            tool_time_after = sum(tc.duration_ms for tc in trace.tool_calls)
            tool_time_in_run = tool_time_after - tool_time_before
            llm_time_estimate = max(0.0, run_duration_ms - tool_time_in_run)
            record_llm_duration(trace, llm_time_estimate)
```

Note: This is an approximation — it includes some framework overhead. But it's the best available without httpx hooks, and the relative comparison across platforms is still valid.

- [ ] **Step 2: Verify syntax**

Run: `uv run python -c "from desmet.adapters.openai_agents import OpenAIAgentsAdapter; print('OK')" 2>&1`
Expected: `OK` or ImportError for `agents` module (expected if not installed)

- [ ] **Step 3: Commit**

```bash
git add src/desmet/adapters/openai_agents.py
git commit -m "feat(openai-agents): add LLM call duration tracking"
```

---

### Task 7: Story-level aggregation and serialization in the runner

**Files:**
- Modify: `src/desmet/harness/runner.py:430-470,584-626`

- [ ] **Step 1: Aggregate framework_metrics in _run_story**

After the existing metrics aggregation (around line 453, after `result.human_interventions = sum(...)`), add:

```python
                # Aggregate framework metrics across stages
                all_fm = [
                    sr.framework_metrics
                    for sr in stage_results.values()
                    if sr.framework_metrics
                ]
                if all_fm:
                    agg: dict[str, float | None] = {}
                    # Averaged metrics
                    for key in ("tokens_per_stage", "iteration_ratio",
                                "redundant_tool_call_rate", "tool_failure_rate"):
                        vals = [fm[key] for fm in all_fm if fm.get(key) is not None]
                        agg[key] = sum(vals) / len(vals) if vals else None
                    # first_action_latency_ms: averaged
                    latencies = [fm["first_action_latency_ms"] for fm in all_fm
                                 if fm.get("first_action_latency_ms") is not None]
                    agg["first_action_latency_ms"] = (
                        sum(latencies) / len(latencies) if latencies else None
                    )
                    # framework_overhead_ms: summed
                    overheads = [fm["framework_overhead_ms"] for fm in all_fm
                                 if fm.get("framework_overhead_ms") is not None]
                    agg["framework_overhead_ms"] = sum(overheads) if overheads else None
                    result.framework_metrics = agg
```

- [ ] **Step 2: Serialize framework_metrics in _save_stage_traces**

In `_save_stage_traces`, after `stage_entry["langsmith_run_id"]` (around line 598), add:

```python
                if sr.framework_metrics:
                    stage_entry["framework_metrics"] = sr.framework_metrics
```

- [ ] **Step 3: Verify syntax**

Run: `uv run python -c "from desmet.harness.runner import EvaluationRunner; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/desmet/harness/runner.py
git commit -m "feat(runner): aggregate and serialize framework_metrics"
```

---

### Task 8: Add framework_metrics to StoryMetrics and EvaluationMetrics.to_dict()

**Files:**
- Modify: `src/desmet/harness/metrics.py:99-142,453-470`

- [ ] **Step 1: Add framework_metrics field to StoryMetrics**

After `autonomy_score` (line 117):

```python
    # Automated framework metrics (from StoryResult.framework_metrics)
    framework_metrics: dict[str, float | None] = field(default_factory=dict)
```

- [ ] **Step 2: Populate in from_story_result**

At the end of `from_story_result` (before `return instance`, around line 142), add:

```python
        instance.framework_metrics = getattr(result, "framework_metrics", {}) or {}
```

- [ ] **Step 3: Update to_dict() to include framework_metrics**

In `EvaluationMetrics.to_dict()`, the `story_metrics` list comprehension (lines 453-469) builds a dict per story. The current dict ends with `"trace_quality_score": m.trace_quality_score,`. Replace that trailing entry and add the missing fields:

Find:
```python
                    "trace_quality_score": m.trace_quality_score,
                }
                for m in self.story_metrics
```

Replace with:
```python
                    "trace_quality_score": m.trace_quality_score,
                    "time_efficiency_score": m.time_efficiency_score,
                    "autonomy_score": m.autonomy_score,
                    "framework_metrics": m.framework_metrics,
                }
                for m in self.story_metrics
```

This adds the two rubric scores that were already on `StoryMetrics` but missing from serialization, plus the new `framework_metrics` dict.

- [ ] **Step 4: Verify syntax**

Run: `uv run python -c "from desmet.harness.metrics import StoryMetrics, EvaluationMetrics; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/desmet/harness/metrics.py
git commit -m "feat(metrics): add framework_metrics to StoryMetrics and to_dict"
```

---

### Task 9: Backend API endpoint for framework metrics

**Files:**
- Modify: `src/desmet/webui/api.py`

- [ ] **Step 1: Add endpoint**

Add after the existing dashboard endpoints (around line 742):

```python
@app.get("/api/dashboard/framework-metrics")
async def dashboard_framework_metrics():
    """Return aggregated framework metrics per platform."""
    data = load_results_raw()
    platforms_out = []
    for pid, pdata in data.get("platforms", {}).items():
        pname = pdata.get("platform_name", pid)
        all_fm: list[dict] = []
        for sm in pdata.get("story_metrics", []):
            fm = sm.get("framework_metrics")
            if fm:
                all_fm.append(fm)
        if not all_fm:
            continue
        # Average each metric across stories
        avg_metrics: dict[str, float | None] = {}
        for key in ("tokens_per_stage", "iteration_ratio",
                     "redundant_tool_call_rate", "tool_failure_rate",
                     "first_action_latency_ms", "framework_overhead_ms"):
            vals = [fm[key] for fm in all_fm if fm.get(key) is not None]
            avg_metrics[key] = round(sum(vals) / len(vals), 2) if vals else None
        platforms_out.append({
            "platform_id": pid,
            "platform_name": pname,
            "story_count": len(all_fm),
            "metrics": avg_metrics,
        })
    return {"platforms": platforms_out}
```

- [ ] **Step 2: Verify syntax**

Run: `uv run python -c "from desmet.webui.api import app; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/api.py
git commit -m "feat(api): add GET /api/dashboard/framework-metrics endpoint"
```

---

### Task 10: Frontend — API client and ResultsOverview table

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/api.ts`
- Modify: `src/desmet/webui/frontend/src/lib/pages/ResultsOverview.svelte`

- [ ] **Step 1: Add fetchFrameworkMetrics to api.ts**

Add after the existing dashboard functions:

```ts
export interface FrameworkMetricsPlatform {
  platform_id: string;
  platform_name: string;
  story_count: number;
  metrics: Record<string, number | null>;
}

export const fetchFrameworkMetrics = () =>
  request<{ platforms: FrameworkMetricsPlatform[] }>('/api/dashboard/framework-metrics');
```

- [ ] **Step 2: Add framework metrics table to ResultsOverview.svelte**

Read the current file, then add a new section after the existing content. Import `fetchFrameworkMetrics` and the type, add a local state variable, fetch on mount, and render a comparison table.

The table should have platforms as columns and metrics as rows, with human-readable labels and appropriate formatting (percentages for rates, ms for latencies, etc.).

- [ ] **Step 3: Verify build**

Run: `cd src/desmet/webui/frontend && bun run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/api.ts src/desmet/webui/frontend/src/lib/pages/ResultsOverview.svelte
git commit -m "feat(webui): add framework metrics table to results overview"
```

---

### Task 11: Frontend — Show computed metrics on Scoring page

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/pages/Scoring.svelte`

- [ ] **Step 1: Display framework metrics card**

When `scoreData` is loaded and has `framework_metrics`, show a small read-only card with the 6 metrics. This gives the scorer context about what the framework actually did.

Read the current Scoring.svelte to find the right insertion point (above or beside the rubric sliders). Add a computed metrics card that renders when `scoreData?.framework_metrics` exists.

Note: `scoreData` comes from `fetchStoryScore(platform, story)` which reads from `story_metrics` in the results JSON. The backend already includes `framework_metrics` in the story_metrics dict (added in Task 8). The `StoryScoreData` type in `api.ts` needs a `framework_metrics` field added.

- [ ] **Step 2: Verify build**

Run: `cd src/desmet/webui/frontend && bun run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/pages/Scoring.svelte src/desmet/webui/frontend/src/lib/api.ts
git commit -m "feat(webui): show framework metrics on scoring page"
```

---

### Task 12: Run tests and verify full build

**Files:** None (verification only)

- [ ] **Step 1: Run framework metrics tests**

Run: `uv run pytest tests/test_framework_metrics.py -v`
Expected: All pass

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest --ignore=tests/test_crewai_adapter.py --ignore=tests/test_openai_agents_adapter.py -k "not test_all_registered_adapters_importable" -q`
Expected: All pass (excluding pre-existing adapter import failures)

- [ ] **Step 3: Frontend build**

Run: `cd src/desmet/webui/frontend && bun run build`
Expected: Build succeeds

- [ ] **Step 4: Commit any fixes**

If issues found, fix and commit.
