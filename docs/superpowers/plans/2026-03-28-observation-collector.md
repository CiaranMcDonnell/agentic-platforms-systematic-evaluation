# ObservationCollector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce an `ObservationCollector` sealed accumulator so that all platform adapters record observation data through a typed, normalized interface with completeness validation.

**Architecture:** New `_observation.py` module wrapping `_tracing.py` helpers. `_base.py` creates the collector in `_execute_stage`, passes it to `_run_agent`, and seals it after. Each adapter migrates from direct `_tracing` calls to collector methods. Tasks 3–6 (adapter migrations) are independent of each other and can be parallelized.

**Tech Stack:** Python dataclasses, threading.Lock, existing `_tracing.py` helpers.

**Spec:** `docs/superpowers/specs/2026-03-28-observation-collector-design.md`

---

### Task 1: ObservationCollector — tests and implementation

**Files:**
- Create: `tests/test_observation_collector.py`
- Create: `src/desmet/adapters/_observation.py`

- [ ] **Step 1: Write the test file**

Create `tests/test_observation_collector.py` with all unit tests:

```python
"""Unit tests for ObservationCollector."""

from __future__ import annotations

import threading

import pytest

from desmet.adapters._observation import ObservationCollector, ObservationRequirements
from desmet.harness.trace import AgentTrace


# ── Completeness validation ────────────────────────────────────────────


def test_seal_all_missing_gives_five_warnings():
    trace = AgentTrace()
    collector = ObservationCollector(trace)
    warnings = collector.seal()
    assert len(warnings) == 5
    assert any("token usage" in w for w in warnings)
    assert any("tool calls" in w for w in warnings)
    assert any("LLM duration" in w for w in warnings)
    assert any("messages" in w for w in warnings)
    assert any("iterations" in w for w in warnings)


def test_seal_all_recorded_gives_no_warnings():
    trace = AgentTrace()
    collector = ObservationCollector(trace, model="test-model")
    collector.record_llm_response(
        raw_usage={"prompt_tokens": 10, "completion_tokens": 5},
        duration_ms=100.0,
    )
    collector.record_tool_execution("read_file", {"path": "x"}, "content")
    collector.record_message("user", "hello")
    collector.mark_iterations(3)
    warnings = collector.seal()
    assert warnings == []


def test_seal_relaxed_requirement_no_warning():
    trace = AgentTrace()
    reqs = ObservationRequirements(llm_duration=False)
    collector = ObservationCollector(trace, requirements=reqs, model="m")
    collector.record_llm_response(raw_usage={"prompt_tokens": 1, "completion_tokens": 1})
    collector.record_tool_execution("t", {}, "")
    collector.record_message("user", "hi")
    collector.mark_iterations(1)
    warnings = collector.seal()
    assert warnings == []


def test_seal_custom_requirement_missing():
    trace = AgentTrace()
    reqs = ObservationRequirements(
        usage=False, tool_calls=False, llm_duration=False,
        messages=False, iterations=False,
        custom={"stall_count": True},
    )
    collector = ObservationCollector(trace, requirements=reqs)
    warnings = collector.seal()
    assert len(warnings) == 1
    assert "stall_count" in warnings[0]


def test_seal_custom_requirement_recorded():
    trace = AgentTrace()
    reqs = ObservationRequirements(
        usage=False, tool_calls=False, llm_duration=False,
        messages=False, iterations=False,
        custom={"stall_count": True},
    )
    collector = ObservationCollector(trace, requirements=reqs)
    collector.record_custom("stall_count", 2)
    warnings = collector.seal()
    assert warnings == []


# ── Normalization ──────────────────────────────────────────────────────


def test_normalize_prompt_tokens_keys():
    trace = AgentTrace()
    collector = ObservationCollector(trace, model="m")
    collector.record_llm_response(
        raw_usage={"prompt_tokens": 10, "completion_tokens": 20},
    )
    assert trace.total_tokens_input == 10
    assert trace.total_tokens_output == 20
    assert collector.usage_count == 1


def test_normalize_input_tokens_keys():
    trace = AgentTrace()
    collector = ObservationCollector(trace, model="m")
    collector.record_llm_response(
        raw_usage={"input_tokens": 10, "output_tokens": 20},
    )
    assert trace.total_tokens_input == 10
    assert trace.total_tokens_output == 20
    assert collector.usage_count == 1


def test_null_usage_not_counted():
    trace = AgentTrace()
    collector = ObservationCollector(trace, model="m")
    collector.record_llm_response(raw_usage=None)
    assert collector.usage_count == 0
    assert trace.total_tokens_input == 0


def test_null_usage_with_duration_records_duration_only():
    trace = AgentTrace()
    collector = ObservationCollector(trace, model="m")
    collector.record_llm_response(raw_usage=None, duration_ms=150.0)
    assert collector.usage_count == 0
    assert trace.total_llm_duration_ms == 150.0


# ── Thread safety ──────────────────────────────────────────────────────


def test_concurrent_recording():
    trace = AgentTrace()
    collector = ObservationCollector(
        trace, model="m",
        requirements=ObservationRequirements(
            tool_calls=False, messages=False, iterations=False,
        ),
    )

    def record_batch():
        for _ in range(100):
            collector.record_llm_response(
                raw_usage={"prompt_tokens": 1, "completion_tokens": 1},
                duration_ms=1.0,
            )

    threads = [threading.Thread(target=record_batch) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert collector.usage_count == 1000
    assert trace.total_tokens_input == 1000
    assert trace.total_tokens_output == 1000


def test_record_after_seal_raises():
    trace = AgentTrace()
    collector = ObservationCollector(trace)
    collector.seal()
    with pytest.raises(RuntimeError, match="Cannot record after seal"):
        collector.record_llm_response(raw_usage={"prompt_tokens": 1, "completion_tokens": 1})
    with pytest.raises(RuntimeError, match="Cannot record after seal"):
        collector.record_tool_execution("t", {}, "")
    with pytest.raises(RuntimeError, match="Cannot record after seal"):
        collector.record_message("user", "hi")
    with pytest.raises(RuntimeError, match="Cannot record after seal"):
        collector.mark_iterations(1)
    with pytest.raises(RuntimeError, match="Cannot record after seal"):
        collector.record_custom("k", "v")


# ── Model fallback ─────────────────────────────────────────────────────


def test_constructor_model_used_by_default(mocker):
    trace = AgentTrace()
    spy = mocker.patch("desmet.adapters._observation.record_usage")
    collector = ObservationCollector(trace, model="gpt-4o")
    collector.record_llm_response(raw_usage={"prompt_tokens": 5, "completion_tokens": 5})
    spy.assert_called_once()
    assert spy.call_args.kwargs["model"] == "gpt-4o"


def test_per_call_model_overrides_constructor(mocker):
    trace = AgentTrace()
    spy = mocker.patch("desmet.adapters._observation.record_usage")
    collector = ObservationCollector(trace, model="gpt-4o")
    collector.record_llm_response(
        raw_usage={"prompt_tokens": 5, "completion_tokens": 5},
        model="claude-sonnet",
    )
    spy.assert_called_once()
    assert spy.call_args.kwargs["model"] == "claude-sonnet"


# ── seal() calls finish_trace ──────────────────────────────────────────


def test_seal_sets_end_time():
    trace = AgentTrace()
    collector = ObservationCollector(
        trace,
        requirements=ObservationRequirements(
            usage=False, tool_calls=False, llm_duration=False,
            messages=False, iterations=False,
        ),
    )
    assert trace.end_time is None
    collector.seal()
    assert trace.end_time is not None


def test_seal_idempotent_end_time():
    from datetime import datetime, timezone

    trace = AgentTrace()
    trace.end_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    collector = ObservationCollector(
        trace,
        requirements=ObservationRequirements(
            usage=False, tool_calls=False, llm_duration=False,
            messages=False, iterations=False,
        ),
    )
    collector.seal()
    assert trace.end_time == datetime(2026, 1, 1, tzinfo=timezone.utc)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_observation_collector.py -v`

Expected: `ModuleNotFoundError: No module named 'desmet.adapters._observation'`

- [ ] **Step 3: Write the implementation**

Create `src/desmet/adapters/_observation.py`:

```python
"""Observation data collection with completeness validation.

Wraps ``AgentTrace`` to provide a typed recording interface that handles
normalization internally and validates that all required observation types
were recorded before the trace is finalized.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from desmet.adapters._tracing import (
    finish_trace,
    normalize_usage,
    record_llm_duration,
    record_message as _record_message,
    record_tool_call,
    record_usage,
)
from desmet.harness.trace import AgentTrace


@dataclass
class ObservationRequirements:
    """Declares which observation types an adapter is expected to record.

    All default to ``True``.  Adapters override
    ``ToolAgentAdapter.observation_requirements()`` to relax specific ones.
    """

    usage: bool = True
    tool_calls: bool = True
    llm_duration: bool = True
    messages: bool = True
    iterations: bool = True
    custom: dict[str, bool] = field(default_factory=dict)


class ObservationCollector:
    """Thread-safe sealed accumulator for observation data.

    Wraps an ``AgentTrace``, provides typed recording methods that handle
    normalization internally, and validates completeness when sealed.
    """

    def __init__(
        self,
        trace: AgentTrace,
        *,
        model: str | None = None,
        requirements: ObservationRequirements | None = None,
    ) -> None:
        self._trace = trace
        self._model = model
        self._requirements = requirements or ObservationRequirements()
        self._lock = threading.Lock()
        self._sealed = False
        self._usage_count = 0
        self._tool_call_count = 0
        self._llm_duration_total_ms = 0.0
        self._message_count = 0
        self._iteration_count = 0
        self._custom_counts: dict[str, int] = {}

    # ── Recording methods ──────────────────────────────────────────

    def record_llm_response(
        self,
        raw_usage: Any = None,
        duration_ms: float = 0.0,
        *,
        model: str | None = None,
        cost_usd: float = 0.0,
    ) -> None:
        """Record one LLM API call — usage + duration in a single call."""
        with self._lock:
            if self._sealed:
                raise RuntimeError("Cannot record after seal()")
            resolved_model = model or self._model
            inp, out = normalize_usage(raw_usage)
            if inp or out:
                record_usage(
                    self._trace,
                    input_tokens=inp,
                    output_tokens=out,
                    cost_usd=cost_usd,
                    model=resolved_model,
                )
                self._usage_count += 1
            if duration_ms > 0:
                record_llm_duration(self._trace, duration_ms)
                self._llm_duration_total_ms += duration_ms

    def record_tool_execution(
        self,
        name: str,
        args: dict,
        result: Any,
        *,
        duration_ms: float = 0.0,
        success: bool = True,
    ) -> None:
        """Record one tool call."""
        with self._lock:
            if self._sealed:
                raise RuntimeError("Cannot record after seal()")
            record_tool_call(
                self._trace,
                name=name,
                args=args,
                result=result,
                duration_ms=duration_ms,
                success=success,
            )
            self._tool_call_count += 1

    def record_message(
        self,
        role: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a conversation message."""
        with self._lock:
            if self._sealed:
                raise RuntimeError("Cannot record after seal()")
            _record_message(self._trace, role, content, metadata=metadata)
            self._message_count += 1

    def mark_iterations(self, count: int) -> None:
        """Add *count* to the iteration counter."""
        with self._lock:
            if self._sealed:
                raise RuntimeError("Cannot record after seal()")
            self._iteration_count += count
            self._trace.total_iterations = self._iteration_count

    def record_custom(self, key: str, value: Any) -> None:
        """Record a named custom observation."""
        with self._lock:
            if self._sealed:
                raise RuntimeError("Cannot record after seal()")
            self._custom_counts[key] = self._custom_counts.get(key, 0) + 1

    # ── Lifecycle ──────────────────────────────────────────────────

    def seal(self) -> list[str]:
        """Finalize collection.  Returns list of warnings for missing data."""
        with self._lock:
            self._sealed = True

        if self._trace.end_time is None:
            finish_trace(self._trace)

        warnings: list[str] = []
        req = self._requirements

        if req.usage and self._usage_count == 0:
            warnings.append(
                "No token usage recorded (expected at least 1 LLM response)"
            )
        if req.tool_calls and self._tool_call_count == 0:
            warnings.append("No tool calls recorded")
        if req.llm_duration and self._llm_duration_total_ms == 0.0:
            warnings.append("No LLM duration recorded")
        if req.messages and self._message_count == 0:
            warnings.append("No messages recorded")
        if req.iterations and self._iteration_count == 0:
            warnings.append("No iterations recorded")

        for key, required in req.custom.items():
            if required and self._custom_counts.get(key, 0) == 0:
                warnings.append(f"No custom observation '{key}' recorded")

        return warnings

    # ── Accessors ──────────────────────────────────────────────────

    @property
    def trace(self) -> AgentTrace:
        """Direct trace access for framework-specific operations."""
        return self._trace

    @property
    def usage_count(self) -> int:
        """Number of LLM responses with non-zero usage recorded."""
        return self._usage_count

    @property
    def tool_call_count(self) -> int:
        """Number of tool executions recorded."""
        return self._tool_call_count
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_observation_collector.py -v`

Expected: All 15 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/desmet/adapters/_observation.py tests/test_observation_collector.py
git commit -m "feat: add ObservationCollector with completeness validation"
```

---

### Task 2: Integrate ObservationCollector into `_base.py`

**Files:**
- Modify: `src/desmet/adapters/_base.py`

**Depends on:** Task 1

- [ ] **Step 1: Update imports**

In `src/desmet/adapters/_base.py`, add the new import after the existing `_tracing` import block (after line 31):

```python
from desmet.adapters._observation import ObservationCollector, ObservationRequirements
```

- [ ] **Step 2: Change `_run_agent` signature**

Replace the `_run_agent` abstract method (lines 54–68) with:

```python
    @abstractmethod
    async def _run_agent(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str | None,
        tools: list,
        collector: ObservationCollector,
        context: StageContext,
    ) -> tuple[int, bool]:
        """Run the platform-specific agent for one SDLC stage.

        Records observation data via *collector*.  The caller (``_execute_stage``)
        creates the collector and seals it after this method returns.

        Returns ``(iterations, hit_limit)``.
        """
        ...
```

- [ ] **Step 3: Add `observation_requirements` and `_get_model_name` hooks**

Insert these two methods between the `_run_agent` abstract method and the `_execute_stage` method (before line 72):

```python
    def observation_requirements(self) -> ObservationRequirements:
        """Override to adjust completeness requirements per adapter."""
        return ObservationRequirements()

    def _get_model_name(self) -> str | None:
        """Override to provide the model name for usage recording."""
        return None
```

- [ ] **Step 4: Update `_execute_stage` template method**

Replace the `_execute_stage` method body (lines 72–110) with:

```python
    async def _execute_stage(
        self,
        stage_name: str,
        prompt_fn,
        result_cls: type[StageResult],
        context: StageContext,
    ) -> StageResult:
        """Shared template: build prompt → create tools → run agent → build result."""
        import logging

        trace = start_trace()
        try:
            if stage_name == "codegen":
                prior = context.get_prior_result("requirements")
                prompt = prompt_fn(context.story, prior_requirements=prior)
            else:
                prompt = prompt_fn(context.story)
            system_msg = build_system_message(context.story)
            tools = create_tools(
                context.workspace,
                context.allowed_tools,
                fmt=self.TOOL_FORMAT,
                platform_id=context.platform_id,
                story_id=context.story.id,
                stage_name=stage_name,
            )
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
                log = logging.getLogger(
                    f"desmet.adapters.{self.platform_info.id}"
                )
                for w in warnings:
                    log.warning(
                        "Observation gap [%s/%s]: %s",
                        self.platform_info.id,
                        stage_name,
                        w,
                    )
            fm = compute_framework_metrics(trace, context.max_iterations)
            return build_stage_result(
                result_cls, self.platform_info.id, stage_name,
                trace, success=not hit_limit, iterations=iterations,
                framework_metrics=fm,
            )
        except Exception as e:
            finish_trace(trace, error=str(e))
            return build_stage_result(
                result_cls, self.platform_info.id, stage_name,
                trace, success=False, iterations=0, error_message=str(e),
            )
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_observation_collector.py -v`

Expected: All tests still pass (no adapter code runs yet — only the base class changed).

- [ ] **Step 6: Commit**

```bash
git add src/desmet/adapters/_base.py
git commit -m "refactor(base): integrate ObservationCollector into _execute_stage"
```

---

### Task 3: Migrate LangGraph adapter

**Files:**
- Modify: `src/desmet/adapters/langgraph.py`

**Depends on:** Task 2

- [ ] **Step 1: Update imports**

Replace the `_tracing` import block (lines 28–35):

```python
from desmet.adapters._tracing import (
    finish_trace,
    format_tool_detail,
    record_message,
    record_node_event,
    record_tool_call,
    record_usage,
)
```

With:

```python
from desmet.adapters._observation import ObservationCollector
from desmet.adapters._tracing import (
    format_tool_detail,
    record_node_event,
)
```

- [ ] **Step 2: Add `_get_model_name` override**

Add after the `__init__` method (after line 97):

```python
    def _get_model_name(self) -> str | None:
        return self._model_name
```

- [ ] **Step 3: Change `_build_graph` signature and closure**

Replace the `_build_graph` signature and the `_extract_and_record_usage` closure (lines 256–288).

Change the signature from `trace=None` to `collector=None`:

```python
    def _build_graph(self, llm, tools: list, collector=None, progress_callback=None) -> Any:
```

Replace the `_extract_and_record_usage` closure (lines 276–288) with:

```python
        # ── Helper: extract token usage from a message ──────────────────
        def _extract_and_record_usage(msg: BaseMessage, duration_ms: float = 0.0) -> None:
            if collector is None:
                return
            resp_meta = getattr(msg, "response_metadata", {})
            raw_usage = resp_meta.get("token_usage") or resp_meta.get("usage")
            collector.record_llm_response(raw_usage=raw_usage, duration_ms=duration_ms)
```

- [ ] **Step 4: Migrate planner_wrapper**

In `planner_wrapper` (around line 291), replace the recording block. Change:

```python
            if last_msg:
                _extract_and_record_usage(last_msg)
                if trace is not None:
                    record_message(trace, "assistant", plan_text, metadata={"node": "planner"})
```

To:

```python
            if last_msg:
                planner_duration = (time.monotonic() - t0_ref[0]) * 1000
                _extract_and_record_usage(last_msg, duration_ms=planner_duration)
                if collector is not None:
                    collector.record_message("assistant", plan_text, metadata={"node": "planner"})
```

Update the progress callback token reads. Replace all occurrences of `trace.total_tokens_input + trace.total_tokens_output if trace else 0` with `collector.trace.total_tokens_input + collector.trace.total_tokens_output if collector else 0` in the planner_wrapper function.

- [ ] **Step 5: Migrate executor_wrapper**

In `executor_wrapper` (around line 336), apply these changes:

**a)** Add a timing anchor at the start of the streaming loop. Before the `async for chunk in executor_sg.astream(...)` line, add:

```python
            executor_t0 = time.monotonic()
```

**b)** Inside the streaming loop, replace `_extract_and_record_usage(msg)` calls (no duration — per-message usage only):

```python
                        _extract_and_record_usage(msg)
```

stays as-is (no duration per-message in streaming).

**c)** Replace message recording. Change:

```python
                        if content and trace is not None:
                            record_message(
                                trace,
                                getattr(msg, "type", "assistant"),
                                str(content),
                                metadata={"node": f"executor/{node_name}"},
                            )
```

To:

```python
                        if content and collector is not None:
                            collector.record_message(
                                getattr(msg, "type", "assistant"),
                                str(content),
                                metadata={"node": f"executor/{node_name}"},
                            )
```

**d)** Replace tool call recording. Change:

```python
                            if trace is not None:
                                record_tool_call(trace, tc_name, tc_args, "")
```

To:

```python
                            if collector is not None:
                                collector.record_tool_execution(tc_name, tc_args, "")
```

**e)** Replace all `trace.total_tokens_input + trace.total_tokens_output if trace else 0` with `collector.trace.total_tokens_input + collector.trace.total_tokens_output if collector else 0`.

**f)** Replace the `record_node_event` call. Change:

```python
            if trace is not None:
                record_node_event(
                    trace,
```

To:

```python
            if collector is not None:
                record_node_event(
                    collector.trace,
```

**g)** After the streaming loop ends (after the `async for` block, around line 411), add LLM duration estimation:

```python
            executor_duration = (time.monotonic() - executor_t0) * 1000
            if collector is not None:
                collector.record_llm_response(raw_usage=None, duration_ms=executor_duration)
```

- [ ] **Step 6: Migrate reviewer_wrapper**

In `reviewer_wrapper` (around line 429), apply these changes:

**a)** Add timing around the subgraph invocation. Change:

```python
            result = await reviewer_sg.ainvoke({"messages": messages})

            for msg in result.get("messages", []):
                _extract_and_record_usage(msg)
```

To:

```python
            reviewer_t0 = time.monotonic()
            result = await reviewer_sg.ainvoke({"messages": messages})
            reviewer_duration = (time.monotonic() - reviewer_t0) * 1000

            for msg in result.get("messages", []):
                _extract_and_record_usage(msg, duration_ms=0.0)
            if collector is not None:
                collector.record_llm_response(raw_usage=None, duration_ms=reviewer_duration)
```

**b)** Replace message recording. Change:

```python
            if last_msg and trace is not None:
```

To:

```python
            if last_msg and collector is not None:
```

And change `record_message(trace, ...)` to `collector.record_message(...)`.

**c)** Replace `record_node_event(trace, ...)` with `record_node_event(collector.trace, ...)`.

**d)** Update progress callback token reads as in previous steps.

- [ ] **Step 7: Migrate `_run_agent`**

Replace `_run_agent` (lines 503–575). Change the signature:

```python
    async def _run_agent(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str | None,
        tools: list,
        collector: ObservationCollector,
        context: StageContext,
    ) -> tuple[int, bool]:
```

In the body:

**a)** Change `_build_graph` call:

```python
        graph = self._build_graph(self._llm, tools, collector=collector, progress_callback=progress_cb)
```

**b)** Change `record_message(trace, "user", prompt)` to:

```python
        collector.record_message("user", prompt)
```

**c)** At the end, replace:

```python
        trace.total_iterations = final_state.get("iterations", iteration)
        finish_trace(trace, final_state=final_state)
```

With:

```python
        collector.mark_iterations(final_state.get("iterations", iteration))
        collector.trace.final_state = final_state
```

- [ ] **Step 8: Run tests**

Run: `uv run pytest tests/test_observation_collector.py tests/test_scoring_constants.py -v`

Expected: All tests PASS.

- [ ] **Step 9: Commit**

```bash
git add src/desmet/adapters/langgraph.py
git commit -m "refactor(langgraph): migrate to ObservationCollector"
```

---

### Task 4: Migrate CrewAI adapter

**Files:**
- Modify: `src/desmet/adapters/crewai.py`

**Depends on:** Task 2

- [ ] **Step 1: Update imports**

Replace the `_tracing` import block (lines 20–27):

```python
from desmet.adapters._tracing import (
    finish_trace,
    format_tool_detail,
    normalize_usage,
    record_message,
    record_tool_call,
    record_usage,
)
```

With:

```python
from desmet.adapters._observation import ObservationCollector
from desmet.adapters._tracing import (
    format_tool_detail,
    record_node_event,
)
```

- [ ] **Step 2: Simplify `__init__`**

Replace the per-LLM-call collection fields in `__init__` (lines 91–98):

```python
    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._crew = None
        # Per-LLM-call collection from CrewAI's event bus
        self._llm_calls: list[dict[str, Any]] = []
        self._llm_calls_lock = threading.Lock()
        self._collecting_llm = False
        self._last_llm_start: float = 0.0
```

With:

```python
    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._crew = None
        self._current_collector: ObservationCollector | None = None
        self._last_llm_start: float = 0.0
```

- [ ] **Step 3: Add `_get_model_name` override**

Add after `_get_version` (after line 111):

```python
    def _get_model_name(self) -> str | None:
        return None  # CrewAI creates LLM per-run; model comes from event bus
```

- [ ] **Step 4: Rewrite event bus handler**

Replace `_register_llm_event_handler` (lines 143–180) with:

```python
    def _register_llm_event_handler(self) -> None:
        """Subscribe to CrewAI's event bus for individual LLM completion events."""
        try:
            from crewai.events.event_bus import crewai_event_bus
            from crewai.events.types.llm_events import (
                LLMCallCompletedEvent,
                LLMCallStartedEvent,
            )

            @crewai_event_bus.on(LLMCallStartedEvent)
            def _on_llm_started(source, event) -> None:
                if self._current_collector is None:
                    return
                self._last_llm_start = time.monotonic()

            @crewai_event_bus.on(LLMCallCompletedEvent)
            def _on_llm_completed(source, event: LLMCallCompletedEvent) -> None:
                col = self._current_collector
                if col is None:
                    return
                duration_ms = 0.0
                if self._last_llm_start > 0:
                    duration_ms = (time.monotonic() - self._last_llm_start) * 1000
                    self._last_llm_start = 0.0
                col.record_llm_response(
                    raw_usage=getattr(event.response, "usage", None),
                    duration_ms=duration_ms,
                    model=event.model,
                )
        except ImportError:
            _log.debug("crewai.events not available — per-call tracing disabled")
```

- [ ] **Step 5: Delete `_start_llm_collection` and `_stop_llm_collection`**

Delete the methods at lines 182–193 entirely. They are no longer used.

- [ ] **Step 6: Rewrite `_create_trace_callbacks`**

Replace the `_create_trace_callbacks` method (lines 572–642). Change its first parameter from `trace: AgentTrace` to `collector: ObservationCollector`:

```python
    @staticmethod
    def _create_trace_callbacks(
        collector: ObservationCollector,
        *,
        progress_callback: Any | None = None,
        max_iterations: int = 50,
    ) -> tuple[Any, Any, list[int]]:
        """Create ``step_callback`` and ``task_callback`` closures for a Crew."""
        counter: list[int] = [0]
        tool_counter: list[int] = [0]
        t0 = time.monotonic()

        def step_callback(step_output: Any) -> None:
            counter[0] += 1

            tool_name = getattr(step_output, "tool", None)
            if tool_name:
                tool_counter[0] += 1
                tool_input = getattr(step_output, "tool_input", "")
                tool_result = getattr(step_output, "result", "")
                args = tool_input if isinstance(tool_input, dict) else {"input": str(tool_input)}
                collector.record_tool_execution(str(tool_name), args, str(tool_result))

            if progress_callback is not None:
                elapsed = time.monotonic() - t0
                tokens = collector.trace.total_tokens_input + collector.trace.total_tokens_output
                if tool_name:
                    detail = format_tool_detail(str(tool_name), tool_input)
                    progress_callback(
                        f"    tool {tool_counter[0]} — {detail}"
                        f"  ({elapsed:.0f}s, {tokens:,} tokens)"
                    )
                elif counter[0] % 5 == 0:
                    agent_role = getattr(step_output, "agent", None)
                    role_str = getattr(agent_role, "role", "") if agent_role else ""
                    role_label = f" [{role_str}]" if role_str else ""
                    progress_callback(
                        f"    step {counter[0]}/{max_iterations}{role_label} — reasoning"
                        f"  ({elapsed:.0f}s, {tokens:,} tokens)"
                    )

            content = _summarise_step(step_output)
            collector.record_message("assistant", content, metadata={"step": counter[0]})
            collector.trace.total_iterations = counter[0]

        def task_callback(task_output: Any) -> None:
            collector.record_message(
                "assistant", str(task_output),
                metadata={"event": "task_complete"},
            )
            if progress_callback is not None:
                elapsed = time.monotonic() - t0
                agent_name = getattr(task_output, "agent", "") or ""
                progress_callback(
                    f"    task complete — {agent_name}  ({elapsed:.0f}s)"
                )

        return step_callback, task_callback, counter
```

- [ ] **Step 7: Update `_build_crew` to pass collector**

In `_build_crew` (line 416), change:

```python
        step_cb, task_cb, counter = self._create_trace_callbacks(
            trace,
            progress_callback=context.progress_callback,
            max_iterations=context.max_iterations,
        )
```

To:

```python
        step_cb, task_cb, counter = self._create_trace_callbacks(
            collector,
            progress_callback=context.progress_callback,
            max_iterations=context.max_iterations,
        )
```

Also change `_build_crew`'s `trace: AgentTrace` parameter to `collector: ObservationCollector` in the signature (line 259).

- [ ] **Step 8: Rewrite `_run_agent`**

Replace `_run_agent` (lines 440–564). Key changes:

```python
    async def _run_agent(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str | None,
        tools: list,
        collector: ObservationCollector,
        context: StageContext,
    ) -> tuple[int, bool]:
        """Run a CrewAI crew with retry loop. Returns (iterations, hit_limit)."""
        import asyncio

        from desmet.adapters._tools import _check_completion

        llm = self._create_llm(context)
        cfg = get_llm_config(
            model=context.model or self.config.get("model"),
            temperature=context.temperature,
        )
        model_name = cfg.model

        collector.record_message("user", prompt)

        total_iterations = 0
        hit_limit = False
        plan_text = ""
        feedback = ""
        structured_plan: ImplementationPlan | None = None

        for attempt in range(MAX_RETRIES + 1):
            crew, counter = self._build_crew(
                stage_name, prompt, system_msg, tools, llm, context, collector,
                retry_attempt=attempt,
                prior_plan=plan_text,
                feedback=feedback,
                plan=structured_plan,
            )

            usage_before = collector.usage_count
            self._current_collector = collector
            result = await asyncio.to_thread(crew.kickoff)
            self._current_collector = None
            collector.record_message("assistant", str(result))

            # Fallback: if event bus didn't capture any LLM calls
            if collector.usage_count == usage_before:
                collector.record_llm_response(
                    raw_usage=getattr(result, "token_usage", None),
                    model=model_name,
                )

            total_iterations += counter[0]

            # ── Extract plan from first attempt ──────────────────────────
            if attempt == 0:
                tasks_output = getattr(result, "tasks_output", None)
                if tasks_output:
                    first_output = tasks_output[0]
                    pydantic_out = getattr(first_output, "pydantic", None)
                    if isinstance(pydantic_out, ImplementationPlan):
                        structured_plan = pydantic_out
                    else:
                        structured_plan = parse_plan_text(str(first_output))
                    plan_text = str(first_output)

            # ── Validate workspace ───────────────────────────────────────
            valid = validate_workspace(stage_name, str(context.workspace))
            record_node_event(
                collector.trace, "validator",
                validator_passed=valid,
                retry_count=attempt + 1,
            )

            if valid:
                if context.progress_callback is not None:
                    context.progress_callback("    validator: PASSED")
                break

            # ── Validation failed — prepare retry or exit ────────────────
            _, feedback = _check_completion(context.workspace, stage_name)

            if context.progress_callback is not None:
                context.progress_callback(
                    f"    validator: FAILED (attempt {attempt + 1}/"
                    f"{MAX_RETRIES + 1}) — {feedback}"
                )

            if total_iterations >= context.max_iterations:
                hit_limit = True
                break

        if not hit_limit:
            hit_limit = total_iterations >= context.max_iterations

        collector.mark_iterations(total_iterations)
        return total_iterations, hit_limit
```

- [ ] **Step 9: Run tests**

Run: `uv run pytest tests/test_observation_collector.py tests/test_scoring_constants.py -v`

Expected: All tests PASS.

- [ ] **Step 10: Commit**

```bash
git add src/desmet/adapters/crewai.py
git commit -m "refactor(crewai): migrate to ObservationCollector"
```

---

### Task 5: Migrate OpenAI Agents SDK adapter

**Files:**
- Modify: `src/desmet/adapters/openai_agents.py`

**Depends on:** Task 2

- [ ] **Step 1: Update imports**

Replace the `_tracing` import block (lines 18–26):

```python
from desmet.adapters._tracing import (
    finish_trace,
    format_tool_detail,
    normalize_usage,
    record_llm_duration,
    record_message,
    record_tool_call,
    record_usage,
)
```

With:

```python
from desmet.adapters._observation import ObservationCollector
from desmet.adapters._tracing import format_tool_detail
```

- [ ] **Step 2: Add `_get_model_name` override**

Add after the `__init__` method (after line 79):

```python
    def _get_model_name(self) -> str | None:
        return self._model_name
```

- [ ] **Step 3: Rewrite `_extract_trace`**

Replace `_extract_trace` (lines 328–382). Change from `@staticmethod` accepting `trace` to accepting `collector`:

```python
    @staticmethod
    def _extract_trace(
        collector: ObservationCollector,
        result,
        *,
        cb=None,
        t0: float = 0.0,
        tool_call_count: int = 0,
    ) -> tuple[int, int]:
        """Extract messages, tool calls, and usage from a RunResult.

        Returns ``(new_items_count, updated_tool_call_count)``.
        """
        from agents.items import (
            MessageOutputItem,
            ToolCallItem,
            ToolCallOutputItem,
        )

        for item in result.new_items:
            if isinstance(item, MessageOutputItem):
                text = item.raw_item.content[0].text if item.raw_item.content else ""
                collector.record_message("assistant", text)
            elif isinstance(item, ToolCallItem):
                tool_call_count += 1
                call = item.raw_item
                args = call.arguments if isinstance(call.arguments, dict) else {"raw": call.arguments}
                collector.record_tool_execution(name=call.name, args=args, result="")
                if cb is not None:
                    elapsed = time.monotonic() - t0
                    detail = format_tool_detail(call.name, call.arguments)
                    tokens = collector.trace.total_tokens_input + collector.trace.total_tokens_output
                    cb(
                        f"    tool {tool_call_count} — {detail}"
                        f"  ({elapsed:.0f}s, {tokens:,} tokens)"
                    )
            elif isinstance(item, ToolCallOutputItem):
                collector.record_message(
                    "tool", str(item.output),
                    metadata={"tool_call_id": getattr(item.raw_item, "call_id", "")},
                )

        # Token usage from raw_responses
        for resp in result.raw_responses:
            collector.record_llm_response(raw_usage=getattr(resp, "usage", None))

        # Record final output
        if result.final_output:
            collector.record_message(
                "assistant", str(result.final_output),
                metadata={"event": "final_output"},
            )

        return len(result.new_items), tool_call_count
```

- [ ] **Step 4: Rewrite `_run_agent`**

Replace `_run_agent` (lines 159–326). Key changes — the full method becomes:

```python
    async def _run_agent(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str | None,
        tools: list,
        collector: ObservationCollector,
        context: StageContext,
    ) -> tuple[int, bool]:
        """Run a 3-agent handoff chain: planner → executor → reviewer."""
        from agents import Agent, ModelSettings, Runner
        from agents.exceptions import MaxTurnsExceeded, OutputGuardrailTripwireTriggered

        planner_persona = get_sub_persona("planner")
        executor_persona = get_stage_persona(stage_name)
        reviewer_persona = get_sub_persona("reviewer")

        total_iterations = 0
        tool_call_count = 0
        hit_limit = False
        t0 = time.monotonic()
        cb = context.progress_callback

        collector.record_message("user", prompt)

        # ── Step 1: Planner agent ────────────────────────────────────────
        plan: ImplementationPlan | None = None
        try:
            planner = Agent(
                name=f"desmet_{stage_name}_planner",
                instructions=planner_persona.backstory,
                model=self._model,
                output_type=ImplementationPlan,
                model_settings=ModelSettings(temperature=context.temperature),
            )
            planner_result = await Runner.run(planner, input=prompt, max_turns=3)

            if isinstance(planner_result.final_output, ImplementationPlan):
                plan = planner_result.final_output
        except Exception:
            pass

        if plan is None:
            planner = Agent(
                name=f"desmet_{stage_name}_planner",
                instructions=(
                    f"{planner_persona.backstory}\n\n"
                    "Produce a numbered implementation plan listing steps, "
                    "files to create, and files to modify."
                ),
                model=self._model,
                model_settings=ModelSettings(temperature=context.temperature),
            )
            planner_result = await Runner.run(planner, input=prompt, max_turns=3)
            text = str(planner_result.final_output or "")
            plan = parse_plan_text(text)

        iters, tool_call_count = self._extract_trace(
            collector, planner_result, cb=cb, t0=t0,
            tool_call_count=tool_call_count,
        )
        total_iterations += iters

        if cb:
            cb(f"    planner: {len(plan.steps)} steps planned")

        # ── Step 2: Build executor + reviewer agents ───────────────────────
        guardrail = _make_workspace_guardrail(stage_name, str(context.workspace))

        reviewer_agent = Agent(
            name=f"desmet_{stage_name}_reviewer",
            instructions=reviewer_persona.backstory,
            model=self._model,
            tools=tools,
            output_guardrails=[guardrail],
            model_settings=ModelSettings(temperature=context.temperature),
        )

        executor_instructions = build_executor_instructions(
            executor_persona, plan, system_msg,
        )

        executor_agent = Agent(
            name=f"desmet_{stage_name}_executor",
            instructions=executor_instructions,
            model=self._model,
            tools=tools,
            handoffs=[reviewer_agent],
            model_settings=ModelSettings(temperature=context.temperature),
        )

        # ── Step 3: Retry loop ─────────────────────────────────────────────
        max_turns = max(10, (context.max_iterations - 3) // MAX_RETRIES)
        result = None

        for attempt in range(MAX_RETRIES):
            try:
                if result is None:
                    input_msg = prompt
                else:
                    input_msg = result.to_input_list() + [
                        {
                            "role": "user",
                            "content": f"Validation failed (attempt {attempt}/{MAX_RETRIES}). Fix issues.",
                        }
                    ]

                tool_time_before = sum(tc.duration_ms for tc in collector.trace.tool_calls)
                run_t0 = time.monotonic()
                result = await Runner.run(executor_agent, input=input_msg, max_turns=max_turns)
                run_duration_ms = (time.monotonic() - run_t0) * 1000

                iters, tool_call_count = self._extract_trace(
                    collector, result, cb=cb, t0=t0,
                    tool_call_count=tool_call_count,
                )
                total_iterations += iters

                tool_time_after = sum(tc.duration_ms for tc in collector.trace.tool_calls)
                tool_time_in_run = tool_time_after - tool_time_before
                llm_time_estimate = max(0.0, run_duration_ms - tool_time_in_run)
                collector.record_llm_response(raw_usage=None, duration_ms=llm_time_estimate)

                if total_iterations >= context.max_iterations:
                    hit_limit = True
                    break

                if cb:
                    cb("    reviewer: PASSED")
                break

            except OutputGuardrailTripwireTriggered:
                total_iterations += 1
                if cb:
                    from desmet.adapters._tools import _check_completion
                    _, hint = _check_completion(context.workspace, stage_name)
                    elapsed = time.monotonic() - t0
                    cb(f"    reviewer: FAILED (attempt {attempt + 1}/{MAX_RETRIES}) — {hint}  ({elapsed:.0f}s)")
                if total_iterations >= context.max_iterations:
                    hit_limit = True
                    break
                continue

            except MaxTurnsExceeded:
                total_iterations += max_turns
                if cb:
                    elapsed = time.monotonic() - t0
                    cb(f"    max turns exceeded (attempt {attempt + 1}/{MAX_RETRIES})  ({elapsed:.0f}s)")
                if total_iterations >= context.max_iterations:
                    hit_limit = True
                    break
                continue

        collector.mark_iterations(total_iterations)
        return total_iterations, hit_limit
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_observation_collector.py tests/test_scoring_constants.py -v`

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/desmet/adapters/openai_agents.py
git commit -m "refactor(openai-agents): migrate to ObservationCollector"
```

---

### Task 6: Migrate Agent Framework adapter

**Files:**
- Modify: `src/desmet/adapters/agent_framework.py`

**Depends on:** Task 2

- [ ] **Step 1: Update imports**

Replace the `_tracing` import block (lines 31–39):

```python
from desmet.adapters._tracing import (
    finish_trace,
    format_tool_detail,
    normalize_usage,
    record_llm_duration,
    record_message,
    record_tool_call,
    record_usage,
)
```

With:

```python
from desmet.adapters._observation import ObservationCollector
from desmet.adapters._tracing import format_tool_detail
```

- [ ] **Step 2: Rewrite `UsageTrackingMiddleware`**

Replace the class (lines 57–89) with:

```python
class UsageTrackingMiddleware:
    """ChatMiddleware that intercepts every LLM call to record token usage.

    Thread safety is provided by the ``ObservationCollector``'s internal lock.
    """

    def __init__(self, collector: ObservationCollector) -> None:
        self._collector = collector

    async def invoke(self, context: Any, next_handler: Any) -> Any:
        """Middleware handler: call next, then record usage from the response."""
        t0 = time.monotonic()
        response = await next_handler(context)
        duration_ms = (time.monotonic() - t0) * 1000
        self._collector.record_llm_response(
            raw_usage=getattr(response, "usage", None),
            duration_ms=duration_ms,
        )
        return response
```

- [ ] **Step 3: Add `_get_model_name` override**

Add after `_get_version` (after line ~121):

```python
    def _get_model_name(self) -> str | None:
        return self._model_name
```

- [ ] **Step 4: Rewrite `_run_agent`**

Replace `_run_agent` (lines 184–558). The full updated method:

```python
    async def _run_agent(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str | None,
        tools: list,
        collector: ObservationCollector,
        context: StageContext,
    ) -> tuple[int, bool]:
        """Run MagenticOne orchestration: manager + planner/executor/reviewer."""
        from agent_framework import (
            Agent,
            AgentExecutorResponse,
            AgentResponseUpdate,
            Message,
        )
        from agent_framework.orchestrations import MagenticBuilder

        planner_persona = get_sub_persona("planner")
        executor_persona = get_stage_persona(stage_name)
        reviewer_persona = get_sub_persona("reviewer")

        total_iterations = 0
        tool_call_count = 0
        hit_limit = False
        t0 = time.monotonic()
        cb = context.progress_callback

        collector.record_message("user", prompt)

        # Register usage tracking middleware on agents
        middleware = UsageTrackingMiddleware(collector)

        # -- Step 1: Planner agent (structured output) ------------------------
        plan: ImplementationPlan | None = None
        try:
            planner = Agent(
                name=f"desmet_{stage_name}_planner",
                instructions=planner_persona.backstory,
                client=self._client,
                middleware=[middleware],
            )
            planner_result = await planner.run(
                prompt,
                response_format=ImplementationPlan,
            )
            text = getattr(planner_result, "text", "") or ""
            if text:
                try:
                    plan = ImplementationPlan.model_validate_json(text)
                except Exception:
                    pass
        except Exception:
            pass

        if plan is None:
            try:
                planner = Agent(
                    name=f"desmet_{stage_name}_planner",
                    instructions=(
                        f"{planner_persona.backstory}\n\n"
                        "Produce a numbered implementation plan listing steps, "
                        "files to create, and files to modify."
                    ),
                    client=self._client,
                    middleware=[middleware],
                )
                planner_result = await planner.run(prompt)
                text = getattr(planner_result, "text", "") or ""
                plan = parse_plan_text(text)
            except Exception:
                plan = ImplementationPlan(
                    steps=["Execute the task as described"],
                    files_to_create=[],
                    files_to_modify=[],
                )

        total_iterations += 1
        plan_json = json.dumps(plan.model_dump())
        collector.record_message(
            "assistant",
            f"Plan: {plan_json}",
            metadata={"agent": "planner"},
        )
        record_generation(
            get_langfuse(),
            name="agent-planner",
            model=self._model_name,
            input=prompt[:500],
            output=plan_json[:2000],
            metadata={"steps": len(plan.steps), "stage": stage_name},
        )
        if cb:
            cb(f"    planner: {len(plan.steps)} steps planned")

        # -- Step 2: Build executor and reviewer agents -----------------------
        executor_instructions = build_executor_instructions(
            executor_persona, plan, system_msg,
        )

        executor_tools, reviewer_tools = split_tools(tools, self.TOOL_FORMAT)

        executor_agent = Agent(
            name=f"desmet_{stage_name}_executor",
            description="Implements the plan by writing files, running commands, and building the project.",
            instructions=executor_instructions,
            client=self._client,
            tools=executor_tools,
            middleware=[middleware],
        )

        reviewer_agent = Agent(
            name=f"desmet_{stage_name}_reviewer",
            description="Validates implementation completeness by inspecting the workspace.",
            instructions=(
                f"{reviewer_persona.backstory}\n\n"
                "After the executor finishes, inspect the workspace and call "
                "check_completion to verify all artifacts are present."
            ),
            client=self._client,
            tools=reviewer_tools,
            middleware=[middleware],
        )

        # -- Step 3: Build manager agent and MagenticOne workflow -------------
        manager_agent = Agent(
            name=f"desmet_{stage_name}_manager",
            description="Coordinates executor and reviewer to complete the stage.",
            instructions=(
                "You coordinate a software development team. Delegate implementation "
                "to the executor first, then have the reviewer validate. If the "
                "reviewer reports issues, send the executor back to fix them. "
                "Stop when the reviewer confirms all artifacts are present."
            ),
            client=self._client,
            middleware=[middleware],
        )

        max_rounds = max(3, context.max_iterations - 1)

        workflow = MagenticBuilder(
            participants=[executor_agent, reviewer_agent],
            manager_agent=manager_agent,
            intermediate_outputs=True,
            max_round_count=max_rounds,
            max_stall_count=MAX_STALL_COUNT,
            max_reset_count=MAX_RESET_COUNT,
        ).build()

        # -- Step 4: Stream events from the workflow --------------------------
        run_t0 = time.monotonic()

        current_message_id: str | None = None
        current_message_chunks: list[str] = []
        current_agent_id: str = ""

        def _flush_message() -> None:
            nonlocal current_message_id
            if current_message_chunks:
                full_text = "".join(current_message_chunks)
                if full_text.strip():
                    collector.record_message(
                        "assistant", full_text,
                        metadata={"agent": current_agent_id},
                    )
                current_message_chunks.clear()
                current_message_id = None

        try:
            async for event in workflow.run(prompt, stream=True):

                if event.type == "output" and isinstance(event.data, AgentResponseUpdate):
                    message_id = getattr(event.data, "message_id", None)
                    if message_id != current_message_id:
                        _flush_message()
                        current_message_id = message_id
                        current_agent_id = getattr(event, "executor_id", "") or ""
                    current_message_chunks.append(str(event.data))

                elif event.type == "magentic_orchestrator":
                    _flush_message()
                    total_iterations += 1
                    content = getattr(event.data, "content", None)
                    event_name = getattr(getattr(event.data, "event_type", None), "name", "unknown")
                    if isinstance(content, Message):
                        collector.record_message(
                            "system", content.text or "",
                            metadata={"event": f"orchestrator_{event_name}"},
                        )
                    if cb:
                        cb(f"    [manager] {event_name}")

                elif event.type == "output":
                    _flush_message()
                    total_iterations += 1
                    if isinstance(event.data, list):
                        for msg in event.data:
                            text = getattr(msg, "text", "") or ""
                            if text:
                                collector.record_message(
                                    "assistant", text,
                                    metadata={"event": "final_output"},
                                )

                elif event.type == "executor_completed":
                    _flush_message()
                    total_iterations += 1
                    executor_name = getattr(event, "executor_id", "") or ""
                    lf = get_langfuse()
                    responses = event.data if isinstance(event.data, list) else [event.data]

                    for resp in responses:
                        if not isinstance(resp, AgentExecutorResponse):
                            continue
                        agent_resp = getattr(resp, "agent_response", None)
                        if agent_resp is None:
                            continue

                        # Token usage is recorded by UsageTrackingMiddleware
                        # per-LLM-call. No duplicate recording here.

                        # Record agent completion as a Langfuse generation
                        agent_output = ""
                        agent_msgs = getattr(agent_resp, "messages", None)
                        if agent_msgs is not None:
                            if isinstance(agent_msgs, Message):
                                agent_msgs = [agent_msgs]
                            agent_output = "\n".join(
                                getattr(m, "text", "") or "" for m in agent_msgs
                            ).strip()

                        record_generation(
                            lf,
                            name=f"agent-{executor_name}",
                            model=self._model_name,
                            output=agent_output[:2000] if agent_output else None,
                            metadata={"agent": executor_name, "iteration": total_iterations},
                        )

                        # Extract tool calls from response messages
                        msgs = agent_msgs or []
                        pending_calls: dict[str, tuple[str, dict]] = {}
                        for msg in msgs:
                            for content_item in (getattr(msg, "contents", None) or []):
                                cd = content_item.to_dict() if hasattr(content_item, "to_dict") else {}
                                ctype = cd.get("type", "")

                                if ctype == "function_call":
                                    tc_name = cd.get("name", "unknown")
                                    tc_args_raw = cd.get("arguments", "{}")
                                    try:
                                        tc_args = json.loads(tc_args_raw) if isinstance(tc_args_raw, str) else tc_args_raw
                                    except (json.JSONDecodeError, TypeError):
                                        tc_args = {"raw": tc_args_raw}
                                    call_id = cd.get("call_id", "")
                                    pending_calls[call_id] = (tc_name, tc_args)

                                elif ctype == "function_result":
                                    call_id = cd.get("call_id", "")
                                    result_text = cd.get("result", "") or cd.get("output", "") or ""
                                    if not result_text:
                                        items = cd.get("items", [])
                                        if items:
                                            result_text = str(items)
                                    if isinstance(result_text, (list, dict)):
                                        result_text = json.dumps(result_text)
                                    if len(str(result_text)) > 1000:
                                        result_text = str(result_text)[:500] + "...(truncated)..." + str(result_text)[-300:]
                                    tc_name, tc_args = pending_calls.pop(call_id, ("unknown", {}))
                                    tool_call_count += 1
                                    collector.record_tool_execution(
                                        name=tc_name, args=tc_args, result=str(result_text),
                                    )
                                    if cb:
                                        elapsed = time.monotonic() - t0
                                        detail = format_tool_detail(tc_name, tc_args)
                                        tokens = collector.trace.total_tokens_input + collector.trace.total_tokens_output
                                        cb(f"    tool {tool_call_count} \u2014 {detail}  ({elapsed:.0f}s, {tokens:,} tokens)")

                        for call_id, (tc_name, tc_args) in pending_calls.items():
                            tool_call_count += 1
                            collector.record_tool_execution(
                                name=tc_name, args=tc_args, result="(no result)",
                            )
                            if cb:
                                elapsed = time.monotonic() - t0
                                detail = format_tool_detail(tc_name, tc_args)
                                tokens = collector.trace.total_tokens_input + collector.trace.total_tokens_output
                                cb(f"    tool {tool_call_count} \u2014 {detail}  ({elapsed:.0f}s, {tokens:,} tokens)")

                    if cb:
                        cb(f"    [completed] {executor_name}")

                else:
                    _log.debug(
                        "Unhandled event type=%s executor=%s data_type=%s",
                        event.type,
                        getattr(event, "executor_id", ""),
                        type(event.data).__name__,
                    )

                if total_iterations >= context.max_iterations:
                    hit_limit = True
                    break

            _flush_message()
        except Exception as e:
            _log.warning("MagenticOne orchestration error: %s", e)
            collector.trace.errors.append(str(e))

        run_duration_ms = (time.monotonic() - run_t0) * 1000

        # Estimate LLM time (total run minus tool execution time)
        tool_time = sum(tc.duration_ms for tc in collector.trace.tool_calls)
        llm_time_estimate = max(0.0, run_duration_ms - tool_time)
        collector.record_llm_response(raw_usage=None, duration_ms=llm_time_estimate)

        # -- Step 5: Final validation -----------------------------------------
        passed = validate_workspace(stage_name, str(context.workspace))
        if cb:
            if passed:
                cb("    validator: PASSED")
            else:
                from desmet.adapters._tools import _check_completion
                _, hint = _check_completion(context.workspace, stage_name)
                elapsed = time.monotonic() - t0
                cb(f"    validator: FAILED \u2014 {hint}  ({elapsed:.0f}s)")

        collector.mark_iterations(total_iterations)
        return total_iterations, hit_limit
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_observation_collector.py tests/test_scoring_constants.py -v`

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/desmet/adapters/agent_framework.py
git commit -m "refactor(agent-framework): migrate to ObservationCollector"
```

---

### Task 7: Final verification

**Files:** None (verification only)

**Depends on:** Tasks 1–6

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`

Expected: All tests PASS, no regressions.

- [ ] **Step 2: Verify no direct `normalize_usage` imports in adapters**

Run: `grep -r "from desmet.adapters._tracing import.*normalize_usage" src/desmet/adapters/ --include="*.py" | grep -v _observation.py`

Expected: No output (only `_observation.py` imports `normalize_usage`).

- [ ] **Step 3: Verify no direct `record_usage` imports in adapters**

Run: `grep -r "from desmet.adapters._tracing import.*record_usage" src/desmet/adapters/ --include="*.py" | grep -v _observation.py | grep -v _tracing.py`

Expected: No output.

- [ ] **Step 4: Verify all adapters use collector parameter**

Run: `grep -n "def _run_agent" src/desmet/adapters/*.py`

Expected: All 4 adapters + `_base.py` show `collector` in the signature, not `trace`.

- [ ] **Step 5: Verify no `finish_trace` calls in adapter `_run_agent` methods**

Run: `grep -n "finish_trace" src/desmet/adapters/langgraph.py src/desmet/adapters/crewai.py src/desmet/adapters/openai_agents.py src/desmet/adapters/agent_framework.py`

Expected: No matches (only `_base.py` and `_observation.py` call `finish_trace`).
