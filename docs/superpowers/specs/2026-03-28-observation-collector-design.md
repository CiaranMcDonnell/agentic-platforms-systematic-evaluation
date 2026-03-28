# Observation Collector — Design Specification

**Date**: 2026-03-28
**Status**: Approved (pending implementation plan)

## Problem

Each of the 4 platform adapters (LangGraph, CrewAI, OpenAI Agents SDK, Agent Framework) extracts token usage, tool calls, and LLM timing from its framework's SDK responses using ad-hoc inline code — different event handlers, middleware, response iterators, and callback shapes that all ultimately call the same `record_usage()` / `record_tool_call()` / `record_llm_duration()` helpers in `_tracing.py`.

**Consequences**:

- LangGraph never records LLM duration (`framework_overhead_ms` is always `None`).
- LangGraph manually extracts `prompt_tokens`/`input_tokens` instead of using `normalize_usage()`.
- No structural guarantee that an adapter records all required observation types — omissions are silent.
- A new adapter author (e.g., Google ADK) has no clear contract telling them what to record.
- `normalize_usage` is called directly by 3 of 4 adapters — they know about key-name variance.

## Approach: ObservationCollector (sealed accumulator)

A new `ObservationCollector` class wraps `AgentTrace` and provides typed recording methods. The collector handles normalization internally, tracks what has been recorded, and validates completeness when sealed. Framework-specific delivery mechanisms (streaming, event bus, middleware, post-hoc iteration) are preserved — only the recording interface changes.

### Why not other approaches

**Protocol with extraction methods**: The delivery mechanisms are so different across SDKs (streaming vs event bus vs post-hoc iteration) that extraction method parameter types would all be `Any`, making the Protocol nearly meaningless. The Protocol methods would still need different call sites per adapter.

**Normalized event pipeline (producer-consumer)**: Over-engineered. Adds async queue machinery, consumer tasks, and cross-thread/async-boundary complexity for CrewAI's `asyncio.to_thread`. Solves a problem we don't have yet.

## Constraints

- `AgentTrace`, `StageResult`, and the recording helpers in `_tracing.py` are not modified.
- Framework-specific idiomatic patterns (LangGraph streaming, CrewAI event bus, OpenAI RunResult iteration, Agent Framework middleware) are preserved — the abstraction wraps them, not replaces them.
- Existing tests are unaffected.

## Architecture

### New module: `src/desmet/adapters/_observation.py`

Sits alongside `_tracing.py`, imports from it. No new cross-package imports.

```
_observation.py ──imports──→ _tracing.py (record_usage, normalize_usage, etc.)
_base.py ──imports──→ _observation.py (ObservationCollector, ObservationRequirements)
langgraph.py ─────→ _observation.py (receives collector in _run_agent)
crewai.py ────────→ _observation.py
openai_agents.py ──→ _observation.py
agent_framework.py → _observation.py
```

### ObservationRequirements

```python
@dataclass
class ObservationRequirements:
    """Declares which observation types an adapter is expected to record.

    All default to True. Adapters override observation_requirements()
    to relax specific ones (explicit, auditable decision).
    """
    usage: bool = True
    tool_calls: bool = True
    llm_duration: bool = True
    messages: bool = True
    iterations: bool = True
    custom: dict[str, bool] = field(default_factory=dict)
```

### ObservationCollector

```python
class ObservationCollector:
    """Thread-safe sealed accumulator for observation data.

    Wraps an AgentTrace, provides typed recording methods that handle
    normalization internally, and validates completeness when sealed.
    """

    def __init__(
        self,
        trace: AgentTrace,
        *,
        model: str | None = None,
        requirements: ObservationRequirements | None = None,
    ) -> None: ...

    # ── Recording methods ──────────────────────────────────────────

    def record_llm_response(
        self,
        raw_usage: Any = None,
        duration_ms: float = 0.0,
        *,
        model: str | None = None,
        cost_usd: float = 0.0,
    ) -> None:
        """Record one LLM API call — usage + duration in a single call.

        Calls normalize_usage() internally, then record_usage() and
        record_llm_duration(). Adapters never import normalize_usage.

        If normalize_usage returns (0, 0), _usage_count is not
        incremented (zero-value not counted toward completeness).
        """

    def record_tool_execution(
        self,
        name: str,
        args: dict,
        result: Any,
        *,
        duration_ms: float = 0.0,
        success: bool = True,
    ) -> None:
        """Record one tool call. Delegates to record_tool_call()."""

    def record_message(
        self,
        role: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a conversation message. Delegates to _tracing.record_message()."""

    def mark_iterations(self, count: int) -> None:
        """Add to the iteration counter. Sets trace.total_iterations."""

    def record_custom(self, key: str, value: Any) -> None:
        """Record a named custom observation.

        Tracked for completeness if key appears in requirements.custom.
        """

    # ── Lifecycle ──────────────────────────────────────────────────

    def seal(self) -> list[str]:
        """Finalize collection. Returns list of warnings for missing data.

        Checks each requirement flag against its counter. Does NOT raise —
        returns warnings so the caller decides severity. Also calls
        finish_trace() if not already finalized.
        """

    # ── Accessors ──────────────────────────────────────────────────

    @property
    def trace(self) -> AgentTrace:
        """Direct trace access for framework-specific operations
        (e.g., record_node_event). Auditable via grep for '.trace'.
        """

    @property
    def usage_count(self) -> int:
        """Number of LLM responses with non-zero usage recorded."""

    @property
    def tool_call_count(self) -> int:
        """Number of tool executions recorded."""
```

### Thread safety

A single `threading.Lock` protects all counter mutations and trace writes. Each recording method acquires the lock, calls the underlying `_tracing.py` helper, increments its counter, and releases. No I/O under the lock.

The `_sealed` flag prevents recording after `seal()` — catches bugs where an event handler fires late (e.g., a CrewAI event bus callback firing after `_run_agent` returns). Raises `RuntimeError`.

This replaces per-adapter locking: `UsageTrackingMiddleware._lock` (Agent Framework) and `_llm_calls_lock` (CrewAI).

## Integration with `_base.py`

### Signature change

```python
# Before:
@abstractmethod
async def _run_agent(self, stage_name, prompt, system_msg, tools,
                     trace: AgentTrace, context) -> tuple[int, bool]

# After:
@abstractmethod
async def _run_agent(self, stage_name, prompt, system_msg, tools,
                     collector: ObservationCollector, context) -> tuple[int, bool]
```

### New overridable hook

```python
def observation_requirements(self) -> ObservationRequirements:
    """Override to adjust completeness requirements per adapter.

    Default requires all five. An adapter can relax specific ones.
    """
    return ObservationRequirements()
```

### Updated `_execute_stage`

```python
async def _execute_stage(self, stage_name, prompt_fn, result_cls, context):
    trace = start_trace()
    try:
        # ... prompt/tools setup (unchanged) ...

        collector = ObservationCollector(
            trace,
            model=self._get_model_name(),
            requirements=self.observation_requirements(),
        )

        iterations, hit_limit = await self._run_agent(
            stage_name, prompt, system_msg, tools, collector, context,
        )

        warnings = collector.seal()
        if warnings:
            import logging
            log = logging.getLogger(f"desmet.adapters.{self.platform_info.id}")
            for w in warnings:
                log.warning("Observation gap [%s/%s]: %s",
                           self.platform_info.id, stage_name, w)

        fm = compute_framework_metrics(trace, context.max_iterations)
        return build_stage_result(...)
    except Exception as e:
        finish_trace(trace, error=str(e))
        return build_stage_result(...)
```

### `_get_model_name` hook

```python
def _get_model_name(self) -> str | None:
    """Override to provide the model name for usage recording.

    Returns None by default. Adapters that store the model name
    (all 4 current ones do via self._model_name) override this.
    """
    return None
```

## Per-Adapter Migration

Framework-specific delivery mechanisms stay intact. Only recording calls change.

### LangGraph (`langgraph.py`)

**`_build_graph` receives `collector` instead of `trace`.**

Token usage extraction simplifies:

```python
# Before: manual prompt_tokens/input_tokens fallback chain
def _extract_and_record_usage(msg):
    resp_meta = getattr(msg, "response_metadata", {})
    usage = resp_meta.get("token_usage") or resp_meta.get("usage") or {}
    if isinstance(usage, dict) and usage.get("total_tokens", 0) > 0:
        record_usage(trace,
            input_tokens=usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0) or usage.get("output_tokens", 0),
            cost_usd=float(usage.get("cost") or 0.0),
            model=model_name)

# After: collector handles normalization
def _extract_and_record_usage(msg):
    resp_meta = getattr(msg, "response_metadata", {})
    raw_usage = resp_meta.get("token_usage") or resp_meta.get("usage")
    collector.record_llm_response(raw_usage=raw_usage)
```

**LLM duration now recorded** (biggest fix): Capture `time.monotonic()` before/after LLM node processing in the streaming loop, pass `duration_ms` to `record_llm_response`.

Tool calls: `record_tool_call(trace, ...)` → `collector.record_tool_execution(...)`.
Messages: `record_message(trace, ...)` → `collector.record_message(...)`.
Node events: `record_node_event(trace, ...)` → `record_node_event(collector.trace, ...)` (escape hatch).

### CrewAI (`crewai.py`)

**Event bus handler calls collector directly** instead of storing in `_llm_calls` list.

The event handler is registered once in `initialize()`, but the collector is created per-stage in `_execute_stage()`. To bridge this, CrewAI stores the current collector as `self._current_collector` (set at `_run_agent` start, cleared after). The handler checks `self._current_collector is not None` instead of `self._collecting_llm`:

```python
# In _run_agent:
self._current_collector = collector
# ... crew.kickoff() ...
self._current_collector = None

# Event handler (registered once in initialize):
@crewai_event_bus.on(LLMCallCompletedEvent)
def _on_llm_completed(source, event):
    col = self._current_collector
    if col is None:
        return
    duration_ms = (time.monotonic() - self._last_llm_start) * 1000
    col.record_llm_response(
        raw_usage=getattr(event.response, "usage", None),
        duration_ms=duration_ms,
        model=event.model,
    )
```

**Deleted**: `_llm_calls` list, `_llm_calls_lock`, `_collecting_llm` flag, bulk-recording loop after `crew.kickoff()`.

Fallback (no event bus calls): `if collector.usage_count == 0: collector.record_llm_response(raw_usage=getattr(result, "token_usage", None))`.

Step callback: `record_tool_call(trace, ...)` → `collector.record_tool_execution(...)`.
Messages: `record_message(trace, ...)` → `collector.record_message(...)`.

### OpenAI Agents SDK (`openai_agents.py`)

**`_extract_trace` accepts `collector` instead of `trace`:**

```python
# Before:
for resp in result.raw_responses:
    usage = getattr(resp, "usage", None)
    if usage:
        in_tok, out_tok = normalize_usage(usage)
        record_usage(trace, input_tokens=in_tok, output_tokens=out_tok, model=model)

# After:
for resp in result.raw_responses:
    collector.record_llm_response(raw_usage=getattr(resp, "usage", None))
```

LLM duration estimation (wall clock minus tool time) stays:
```python
collector.record_llm_response(raw_usage=None, duration_ms=llm_time_estimate)
```

Tool calls and messages: `record_tool_call(trace, ...)` → `collector.record_tool_execution(...)`, etc.

### Agent Framework (`agent_framework.py`)

**`UsageTrackingMiddleware` receives collector instead of trace:**

```python
class UsageTrackingMiddleware:
    def __init__(self, collector: ObservationCollector):
        self._collector = collector

    async def invoke(self, context, next_handler):
        t0 = time.monotonic()
        response = await next_handler(context)
        duration_ms = (time.monotonic() - t0) * 1000
        self._collector.record_llm_response(
            raw_usage=getattr(response, "usage", None),
            duration_ms=duration_ms,
        )
        return response
```

**Deleted**: middleware's own `_lock` (collector is thread-safe), direct `normalize_usage` / `record_usage` / `record_llm_duration` imports.

The `executor_completed` event handler's three-source usage fallback (`usage_details` → `raw_representation.usage` → content items) simplifies — each source calls `collector.record_llm_response(raw_usage=...)`. Zero-value results don't increment `_usage_count`.

Tool calls from `function_call`/`function_result` content items: `record_tool_call(trace, ...)` → `collector.record_tool_execution(...)`.

### Code deleted across all adapters

| Adapter         | Deleted                                                         |
|-----------------|-----------------------------------------------------------------|
| LangGraph       | Manual `prompt_tokens`/`input_tokens` extraction chain          |
| CrewAI          | `_llm_calls` list, `_llm_calls_lock`, bulk-recording loop, direct `normalize_usage` import |
| OpenAI Agents   | Direct `normalize_usage` import                                 |
| Agent Framework | Middleware `_lock`, direct `normalize_usage`/`record_usage`/`record_llm_duration` imports |

## New Adapter Contract

When implementing a new adapter (e.g., Google ADK):

```python
class GoogleADKAdapter(ToolAgentAdapter):
    TOOL_FORMAT = ToolFormat.CALLABLE

    async def _run_agent(self, stage_name, prompt, system_msg, tools,
                         collector: ObservationCollector, context) -> tuple[int, bool]:
        # collector.record_llm_response(...)   ← IDE autocomplete
        # collector.record_tool_execution(...)
        # collector.record_message(...)
        # collector.mark_iterations(...)
        ...
```

If the adapter does nothing with the collector, `seal()` produces:

```
WARNING desmet.adapters.google_adk: Observation gap [google_adk/requirements]:
  No token usage recorded (expected at least 1 LLM response)
WARNING desmet.adapters.google_adk: Observation gap [google_adk/requirements]:
  No LLM duration recorded
WARNING desmet.adapters.google_adk: Observation gap [google_adk/requirements]:
  No messages recorded
WARNING desmet.adapters.google_adk: Observation gap [google_adk/requirements]:
  No iterations recorded
```

To relax a requirement:

```python
def observation_requirements(self) -> ObservationRequirements:
    return ObservationRequirements(llm_duration=False)
```

## Extensibility

Adding a new observation type (e.g., `agent_handoffs`):

1. Add `record_handoff(from_agent, to_agent, reason)` method to `ObservationCollector`.
2. Add `handoffs: bool = False` to `ObservationRequirements` (default `False` — existing adapters unaffected).
3. Adapters that track handoffs set `handoffs=True` in their requirements and call `record_handoff()`.

No changes to `_tracing.py`, `AgentTrace`, or existing adapters required.

## Testing

### Unit tests (`test_observation_collector.py`)

**Completeness validation**:
- Default requirements, seal without recording → 5 warnings.
- Record all five types, seal → 0 warnings.
- Relax one requirement, omit it, seal → 0 warnings.
- Custom requirement present, recorded → 0 warnings; omitted → 1 warning.

**Normalization**:
- `raw_usage={"prompt_tokens": 10, "completion_tokens": 20}` → trace tokens correct.
- `raw_usage={"input_tokens": 10, "output_tokens": 20}` → same result.
- `raw_usage=None` → `_usage_count` stays 0.
- `raw_usage=None, duration_ms=150.0` → duration recorded, usage not counted.

**Thread safety**:
- 10 threads × 100 calls → `_usage_count == 1000`, no data races.
- Recording after `seal()` → `RuntimeError`.

**Model fallback**:
- Constructor model used when per-call model omitted.
- Per-call model overrides constructor model.

### Integration tests (`test_adapter_observation.py`)

For each adapter, mock the LLM with canned responses and verify:
- `collector.seal()` returns no warnings.
- Token counts are non-zero.
- At least one tool call recorded.
- At least one message recorded.
- `trace.total_iterations > 0`.

### Existing tests

Unchanged — `_tracing.py` and core models are not modified.
