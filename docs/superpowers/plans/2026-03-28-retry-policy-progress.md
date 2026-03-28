# RetryPolicy & ProgressReporter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centralize retry parameters and progress formatting in `RetryPolicy` and `ProgressReporter` so adapters use shared policy/formatting while keeping their idiomatic retry mechanisms.

**Architecture:** New `_retry.py` module with `RetryPolicy` (wraps `validate_workspace` + `_check_completion`) and `ProgressReporter` (wraps `format_tool_detail` + callback). Base class creates both in `_execute_stage`, passes to `_run_agent`. Adapters replace ad-hoc validation/progress calls with policy/reporter methods. Tasks 3–6 (adapter migrations) are independent and can be parallelized.

**Tech Stack:** Python dataclasses, existing `_validation.py` / `_tools.py` / `_tracing.py` helpers.

**Spec:** `docs/superpowers/specs/2026-03-28-retry-policy-progress-design.md`

---

### Task 1: RetryPolicy + ProgressReporter — tests and implementation

**Files:**
- Create: `tests/test_retry_policy.py`
- Create: `tests/test_progress_reporter.py`
- Create: `src/desmet/adapters/_retry.py`

- [ ] **Step 1: Write RetryPolicy tests**

Create `tests/test_retry_policy.py`:

```python
"""Unit tests for RetryPolicy."""

from __future__ import annotations

from pathlib import Path

from desmet.adapters._retry import RetryPolicy


def test_total_attempts_default():
    policy = RetryPolicy()
    assert policy.total_attempts() == 4  # 3 retries + 1 initial


def test_total_attempts_custom():
    policy = RetryPolicy(max_retries=5)
    assert policy.total_attempts() == 6


def test_validate_passing_workspace(tmp_path):
    """A workspace with a valid requirements doc passes validation."""
    docs = tmp_path / "docs" / "design"
    docs.mkdir(parents=True)
    (docs / "requirements.md").write_text(
        "# Requirements\n\nFunctional requirements:\n- Login\n\n"
        "Non-functional requirements:\n- Performance\n\n"
        "Acceptance criteria:\n- Tests pass\n"
    )
    policy = RetryPolicy(
        max_retries=3,
        stage_name="requirements",
        workspace=tmp_path,
    )
    passed, feedback = policy.validate()
    assert passed is True
    assert "PASSED" in feedback


def test_validate_failing_workspace(tmp_path):
    """An empty workspace fails validation."""
    policy = RetryPolicy(
        max_retries=3,
        stage_name="requirements",
        workspace=tmp_path,
    )
    passed, feedback = policy.validate()
    assert passed is False
    assert "FAILED" in feedback


def test_default_max_retries():
    policy = RetryPolicy()
    assert policy.max_retries == 3
```

- [ ] **Step 2: Write ProgressReporter tests**

Create `tests/test_progress_reporter.py`:

```python
"""Unit tests for ProgressReporter."""

from __future__ import annotations

import time

from desmet.adapters._observation import ObservationCollector, ObservationRequirements
from desmet.adapters._retry import ProgressReporter
from desmet.harness.trace import AgentTrace


def _make_reporter(messages: list[str]) -> ProgressReporter:
    """Create a reporter that appends to *messages*."""
    trace = AgentTrace()
    collector = ObservationCollector(
        trace,
        requirements=ObservationRequirements(
            usage=False, tool_calls=False, llm_duration=False,
            messages=False, iterations=False,
        ),
    )
    return ProgressReporter(callback=messages.append, collector=collector)


def test_tool_call_format():
    msgs: list[str] = []
    reporter = _make_reporter(msgs)
    reporter.tool_call("read_file", {"path": "src/main.py"})
    assert len(msgs) == 1
    assert "tool 1" in msgs[0]
    assert "read_file" in msgs[0]
    assert "src/main.py" in msgs[0]


def test_tool_call_increments_counter():
    msgs: list[str] = []
    reporter = _make_reporter(msgs)
    reporter.tool_call("read_file", {"path": "a.py"})
    reporter.tool_call("write_file", {"path": "b.py", "content": "x"})
    assert "tool 1" in msgs[0]
    assert "tool 2" in msgs[1]


def test_validation_passed():
    msgs: list[str] = []
    reporter = _make_reporter(msgs)
    reporter.validation_passed()
    assert msgs == ["    validator: PASSED"]


def test_validation_failed():
    msgs: list[str] = []
    reporter = _make_reporter(msgs)
    reporter.validation_failed(2, 4, "Missing artifacts")
    assert len(msgs) == 1
    assert "validator: FAILED" in msgs[0]
    assert "(attempt 2/4)" in msgs[0]
    assert "Missing artifacts" in msgs[0]


def test_agent_status():
    msgs: list[str] = []
    reporter = _make_reporter(msgs)
    reporter.agent_status("planner", "done — 5 steps planned")
    assert len(msgs) == 1
    assert "[planner]" in msgs[0]
    assert "done — 5 steps planned" in msgs[0]


def test_heartbeat():
    msgs: list[str] = []
    reporter = _make_reporter(msgs)
    reporter.heartbeat(7, "executor")
    assert len(msgs) == 1
    assert "[executor]" in msgs[0]
    assert "step 7" in msgs[0]


def test_heartbeat_no_label():
    msgs: list[str] = []
    reporter = _make_reporter(msgs)
    reporter.heartbeat(3)
    assert len(msgs) == 1
    assert "step 3" in msgs[0]
    assert "[" not in msgs[0]  # no brackets when no label


def test_none_callback_is_noop():
    trace = AgentTrace()
    collector = ObservationCollector(
        trace,
        requirements=ObservationRequirements(
            usage=False, tool_calls=False, llm_duration=False,
            messages=False, iterations=False,
        ),
    )
    reporter = ProgressReporter(callback=None, collector=collector)
    # None of these should raise
    reporter.tool_call("read_file", {"path": "x"})
    reporter.validation_passed()
    reporter.validation_failed(1, 4, "hint")
    reporter.agent_status("planner", "done")
    reporter.heartbeat(1, "executor")


def test_elapsed_and_tokens_in_output():
    msgs: list[str] = []
    reporter = _make_reporter(msgs)
    reporter.tool_call("read_file", {"path": "x"})
    # Should contain elapsed time and token count
    assert "s," in msgs[0]  # elapsed seconds
    assert "tokens" in msgs[0]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_retry_policy.py tests/test_progress_reporter.py -v`

Expected: `ModuleNotFoundError: No module named 'desmet.adapters._retry'`

- [ ] **Step 4: Write the implementation**

Create `src/desmet/adapters/_retry.py`:

```python
"""Retry policy and progress reporting for platform adapters.

Centralizes retry parameters (``RetryPolicy``) and progress callback
formatting (``ProgressReporter``) so that adapters use shared policy
and formatting while keeping their idiomatic retry mechanisms.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from desmet.adapters._observation import ObservationCollector
from desmet.adapters._tracing import format_tool_detail


@dataclass
class RetryPolicy:
    """Single source of truth for retry parameters and validation.

    Created by the base class, passed to adapters.  Adapters call
    ``validate()`` inside their idiomatic retry mechanisms instead of
    importing ``validate_workspace`` / ``_check_completion`` directly.
    """

    max_retries: int = 3
    stage_name: str = ""
    workspace: Path = Path(".")

    def total_attempts(self) -> int:
        """Max retries + 1 initial attempt."""
        return self.max_retries + 1

    def validate(self) -> tuple[bool, str]:
        """Run workspace validation for the current stage.

        Returns ``(passed, feedback)`` where *feedback* is a human-readable
        string from ``_check_completion`` (success message when passed,
        failure hint when not).
        """
        from desmet.adapters._tools import _check_completion

        return _check_completion(self.workspace, self.stage_name)


class ProgressReporter:
    """Standardized progress formatting for adapter execution.

    Owns elapsed time tracking, tool call counting, and token reads.
    All methods are no-ops when the callback is ``None``.
    """

    def __init__(
        self,
        callback: Callable[[str], None] | None,
        collector: ObservationCollector,
    ) -> None:
        self._cb = callback
        self._collector = collector
        self._t0 = time.monotonic()
        self._tool_count = 0

    def _tokens(self) -> int:
        t = self._collector.trace
        return t.total_tokens_input + t.total_tokens_output

    def _elapsed(self) -> float:
        return time.monotonic() - self._t0

    def tool_call(self, name: str, args: Any) -> None:
        """Emit standardized tool call progress."""
        if self._cb is None:
            return
        self._tool_count += 1
        detail = format_tool_detail(name, args)
        self._cb(
            f"    tool {self._tool_count} — {detail}"
            f"  ({self._elapsed():.0f}s, {self._tokens():,} tokens)"
        )

    def validation_passed(self) -> None:
        """Emit validation success."""
        if self._cb is None:
            return
        self._cb("    validator: PASSED")

    def validation_failed(
        self, attempt: int, max_attempts: int, feedback: str,
    ) -> None:
        """Emit validation failure with attempt count and feedback."""
        if self._cb is None:
            return
        self._cb(
            f"    validator: FAILED (attempt {attempt}/{max_attempts})"
            f" — {feedback}  ({self._elapsed():.0f}s)"
        )

    def agent_status(self, agent: str, status: str) -> None:
        """Emit agent lifecycle status."""
        if self._cb is None:
            return
        self._cb(
            f"    [{agent}] {status}"
            f"  ({self._elapsed():.0f}s, {self._tokens():,} tokens)"
        )

    def heartbeat(self, step: int, label: str = "") -> None:
        """Emit periodic progress during long-running execution.

        *label* is the agent/node name shown in brackets.
        """
        if self._cb is None:
            return
        prefix = f"[{label}] " if label else ""
        self._cb(
            f"    {prefix}step {step}"
            f"  ({self._elapsed():.0f}s, {self._tokens():,} tokens)"
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_retry_policy.py tests/test_progress_reporter.py -v`

Expected: All 12 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/desmet/adapters/_retry.py tests/test_retry_policy.py tests/test_progress_reporter.py
git commit -m "feat: add RetryPolicy and ProgressReporter"
```

---

### Task 2: Integrate into `_base.py`

**Files:**
- Modify: `src/desmet/adapters/_base.py`

**Depends on:** Task 1

- [ ] **Step 1: Add imports and class attribute**

In `src/desmet/adapters/_base.py`, add after the `_observation` import (line 25):

```python
from desmet.adapters._retry import ProgressReporter, RetryPolicy
```

Add `max_retries` class attribute after `TOOL_FORMAT` (after line 51):

```python
    max_retries: int = 3
```

- [ ] **Step 2: Update `_run_agent` signature**

Replace the `_run_agent` abstract method (lines 53–70) with:

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
        policy: RetryPolicy,
        progress: ProgressReporter,
    ) -> tuple[int, bool]:
        """Run the platform-specific agent for one SDLC stage.

        Records observation data via *collector*.  Uses *policy* for retry
        parameters and validation, *progress* for standardized progress
        reporting.  The caller (``_execute_stage``) creates all three and
        seals the collector after this method returns.

        Returns ``(iterations, hit_limit)``.
        """
        ...
```

- [ ] **Step 3: Update `_execute_stage`**

In `_execute_stage` (lines 82–139), add `policy` and `progress` creation after the `collector` creation (after line 112), and pass them to `_run_agent`:

Replace lines 108–115:

```python
            collector = ObservationCollector(
                trace,
                model=self._get_model_name(),
                requirements=self.observation_requirements(),
            )
            iterations, hit_limit = await self._run_agent(
                stage_name, prompt, system_msg, tools, collector, context,
            )
```

With:

```python
            collector = ObservationCollector(
                trace,
                model=self._get_model_name(),
                requirements=self.observation_requirements(),
            )
            policy = RetryPolicy(
                max_retries=self.max_retries,
                stage_name=stage_name,
                workspace=context.workspace,
            )
            progress = ProgressReporter(
                callback=context.progress_callback,
                collector=collector,
            )
            iterations, hit_limit = await self._run_agent(
                stage_name, prompt, system_msg, tools,
                collector, context, policy, progress,
            )
```

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_retry_policy.py tests/test_progress_reporter.py tests/test_observation_collector.py -v`

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/desmet/adapters/_base.py
git commit -m "refactor(base): pass RetryPolicy and ProgressReporter to _run_agent"
```

---

### Task 3: Migrate LangGraph adapter

**Files:**
- Modify: `src/desmet/adapters/langgraph.py`

**Depends on:** Task 2

- [ ] **Step 1: Update imports**

Remove these imports (lines 28–33):

```python
from desmet.adapters._observation import ObservationCollector
from desmet.adapters._tracing import (
    format_tool_detail,
    record_node_event,
)
from desmet.adapters._validation import validate_workspace
```

Replace with:

```python
from desmet.adapters._observation import ObservationCollector
from desmet.adapters._retry import ProgressReporter, RetryPolicy
from desmet.adapters._tracing import record_node_event
```

Delete the `MAX_RETRIES = 3` constant (line 41).

- [ ] **Step 2: Update `_build_graph` signature and closures**

Change `_build_graph` signature (line 256) from:

```python
    def _build_graph(self, llm, tools: list, collector=None, progress_callback=None) -> Any:
```

To:

```python
    def _build_graph(self, llm, tools: list, collector=None, policy=None, progress=None) -> Any:
```

Remove the `cb = progress_callback` line (line 264) and `t0_ref` / `tool_count_ref` lists (lines 265–266).

In `planner_wrapper`, replace all `cb` progress calls with `progress.agent_status(...)`. Example — replace:

```python
            if cb is not None:
                elapsed = time.monotonic() - t0_ref[0]
                cb(f"    [planner] generating plan...  ({elapsed:.0f}s)")
```

With:

```python
            if progress is not None:
                progress.agent_status("planner", "generating plan...")
```

And replace the "done" callback similarly:

```python
            if progress is not None:
                progress.agent_status("planner", f"done — {step_count} steps planned")
```

In `executor_wrapper`, replace tool call progress (lines 390–397):

```python
                            if cb is not None:
                                elapsed = time.monotonic() - t0_ref[0]
                                detail = format_tool_detail(tc_name, tc_args)
                                tokens = collector.trace.total_tokens_input + collector.trace.total_tokens_output if collector else 0
                                cb(
                                    f"    tool {tool_count_ref[0]} — {detail}"
                                    f"  ({elapsed:.0f}s, {tokens:,} tokens)"
                                )
```

With:

```python
                            if progress is not None:
                                progress.tool_call(tc_name, tc_args)
```

Remove `tool_count_ref[0] += 1` (line 385) — the reporter counts internally.

Replace heartbeat (lines 399–403):

```python
                    if cb is not None and node_name == "executor_node":
                        elapsed = time.monotonic() - t0_ref[0]
                        tokens = collector.trace.total_tokens_input + collector.trace.total_tokens_output if collector else 0
                        cb(f"    [executor] step {llm_call_count}  ({elapsed:.0f}s, {tokens:,} tokens)")
```

With:

```python
                    if progress is not None and node_name == "executor_node":
                        progress.heartbeat(llm_call_count, "executor")
```

Replace validation (line 409) from `validate_workspace(stage, workspace)` to `policy.validate()`:

```python
            passed, feedback = policy.validate() if policy else (False, "")
```

In `reviewer_wrapper`, replace progress calls similarly with `progress.agent_status("reviewer", ...)`.

- [ ] **Step 3: Update `_run_agent` signature and body**

Change signature (lines 504–512) — add `policy` and `progress` parameters:

```python
    async def _run_agent(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str | None,
        tools: list,
        collector: ObservationCollector,
        context: StageContext,
        policy: RetryPolicy,
        progress: ProgressReporter,
    ) -> tuple[int, bool]:
```

Update `_build_graph` call (line 518):

```python
        graph = self._build_graph(self._llm, tools, collector=collector, policy=policy, progress=progress)
```

Replace the validation progress block in the outer streaming loop (lines 558–567):

```python
                if node_name == "executor" and isinstance(node_update, dict):
                    passed = node_update.get("validator_passed", False)
                    retry = node_update.get("retry_count", 0)
                    if cb is not None:
                        if passed:
                            cb("    validator: PASSED")
                        else:
                            from desmet.adapters._tools import _check_completion
                            _, hint = _check_completion(context.workspace, stage_name)
                            cb(f"    validator: FAILED (attempt {retry}/{MAX_RETRIES}) — {hint}")
```

With:

```python
                if node_name == "executor" and isinstance(node_update, dict):
                    passed = node_update.get("validator_passed", False)
                    retry = node_update.get("retry_count", 0)
                    if passed:
                        progress.validation_passed()
                    else:
                        _, feedback = policy.validate()
                        progress.validation_failed(retry, policy.total_attempts(), feedback)
```

Remove `cb = progress_cb` (line 548) — no longer needed.

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_observation_collector.py tests/test_retry_policy.py tests/test_progress_reporter.py tests/test_scoring_constants.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/desmet/adapters/langgraph.py
git commit -m "refactor(langgraph): use RetryPolicy and ProgressReporter"
```

---

### Task 4: Migrate CrewAI adapter

**Files:**
- Modify: `src/desmet/adapters/crewai.py`

**Depends on:** Task 2

- [ ] **Step 1: Update imports and delete constant**

Remove these imports (lines 17, 20–23):

```python
from desmet.adapters._validation import validate_workspace
from desmet.adapters._tracing import (
    format_tool_detail,
    record_node_event,
)
```

Replace with:

```python
from desmet.adapters._retry import ProgressReporter, RetryPolicy
from desmet.adapters._tracing import record_node_event
```

Delete `MAX_RETRIES = 3` (line 32).

- [ ] **Step 2: Update `_create_trace_callbacks`**

Change signature (lines 520–526) from:

```python
    @staticmethod
    def _create_trace_callbacks(
        collector: ObservationCollector,
        *,
        progress_callback: Any | None = None,
        max_iterations: int = 50,
    ) -> tuple[Any, Any, list[int]]:
```

To:

```python
    @staticmethod
    def _create_trace_callbacks(
        collector: ObservationCollector,
        progress: ProgressReporter,
    ) -> tuple[Any, Any, list[int]]:
```

In `step_callback`, replace tool call progress (lines 552–561):

```python
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
```

With:

```python
            if tool_name:
                progress.tool_call(str(tool_name), tool_input)
            elif counter[0] % 5 == 0:
                agent_role = getattr(step_output, "agent", None)
                role_str = getattr(agent_role, "role", "") if agent_role else ""
                role_label = role_str if role_str else "reasoning"
                progress.heartbeat(counter[0], role_label)
```

Remove `tool_counter` list (line 535) and `t0` (line 536) — reporter tracks both.

In `task_callback`, replace (lines 583–588):

```python
            if progress_callback is not None:
                elapsed = time.monotonic() - t0
                agent_name = getattr(task_output, "agent", "") or ""
                progress_callback(
                    f"    task complete — {agent_name}  ({elapsed:.0f}s)"
                )
```

With:

```python
            agent_name = getattr(task_output, "agent", "") or ""
            progress.agent_status(agent_name or "agent", "task complete")
```

- [ ] **Step 3: Update `_build_crew` and `_run_agent`**

In `_build_crew`, change the `_create_trace_callbacks` call (around line 393):

```python
        step_cb, task_cb, counter = self._create_trace_callbacks(
            collector,
            progress_callback=context.progress_callback,
            max_iterations=context.max_iterations,
        )
```

To:

```python
        step_cb, task_cb, counter = self._create_trace_callbacks(
            collector, progress,
        )
```

Add `progress: ProgressReporter` to `_build_crew` signature.

Update `_run_agent` signature (lines 417–425) — add `policy` and `progress`:

```python
    async def _run_agent(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str | None,
        tools: list,
        collector: ObservationCollector,
        context: StageContext,
        policy: RetryPolicy,
        progress: ProgressReporter,
    ) -> tuple[int, bool]:
```

Replace retry loop (line 446):

```python
        for attempt in range(MAX_RETRIES + 1):
```

With:

```python
        for attempt in range(policy.total_attempts()):
```

Remove the `_check_completion` import (line 429).

Replace validation block (lines 482–502):

```python
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
```

With:

```python
            valid, feedback = policy.validate()
            record_node_event(
                collector.trace, "validator",
                validator_passed=valid,
                retry_count=attempt + 1,
            )

            if valid:
                progress.validation_passed()
                break

            progress.validation_failed(
                attempt + 1, policy.total_attempts(), feedback,
            )
```

Pass `progress` to `_build_crew` call.

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_observation_collector.py tests/test_retry_policy.py tests/test_progress_reporter.py tests/test_scoring_constants.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/desmet/adapters/crewai.py
git commit -m "refactor(crewai): use RetryPolicy and ProgressReporter"
```

---

### Task 5: Migrate OpenAI Agents SDK adapter

**Files:**
- Modify: `src/desmet/adapters/openai_agents.py`

**Depends on:** Task 2

- [ ] **Step 1: Update imports and delete constant**

Remove (line 19):

```python
from desmet.adapters._tracing import format_tool_detail
```

Add:

```python
from desmet.adapters._retry import ProgressReporter, RetryPolicy
```

Delete `MAX_RETRIES = 3` (line 27).

Keep `from desmet.adapters._validation import validate_workspace` (line 20) — used by guardrail factory.

- [ ] **Step 2: Update `_extract_trace`**

Change signature (lines 322–330) — replace `cb`/`t0`/`tool_call_count` with `progress`/`tool_call_count`:

```python
    @staticmethod
    def _extract_trace(
        collector: ObservationCollector,
        result,
        *,
        progress: ProgressReporter | None = None,
        tool_call_count: int = 0,
    ) -> tuple[int, int]:
```

Replace tool call progress block (lines 349–357):

```python
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
```

With:

```python
            elif isinstance(item, ToolCallItem):
                tool_call_count += 1
                call = item.raw_item
                args = call.arguments if isinstance(call.arguments, dict) else {"raw": call.arguments}
                collector.record_tool_execution(name=call.name, args=args, result="")
                if progress is not None:
                    progress.tool_call(call.name, call.arguments)
```

- [ ] **Step 3: Update `_run_agent`**

Add `policy` and `progress` to signature (lines 154–162).

Replace `_extract_trace` calls — change `cb=cb, t0=t0` to `progress=progress`:

```python
        iters, tool_call_count = self._extract_trace(
            collector, planner_result, progress=progress,
            tool_call_count=tool_call_count,
        )
```

Replace planner progress (lines 223–224):

```python
        if cb:
            cb(f"    planner: {len(plan.steps)} steps planned")
```

With:

```python
        progress.agent_status("planner", f"{len(plan.steps)} steps planned")
```

Replace retry loop (line 255–258):

```python
        max_turns = max(10, (context.max_iterations - 3) // MAX_RETRIES)
        ...
        for attempt in range(MAX_RETRIES):
```

With:

```python
        max_turns = max(10, (context.max_iterations - 3) // policy.max_retries)
        ...
        for attempt in range(policy.total_attempts()):
```

Replace retry message (line 267):

```python
                            "content": f"Validation failed (attempt {attempt}/{MAX_RETRIES}). Fix issues.",
```

With:

```python
                            "content": f"Validation failed (attempt {attempt}/{policy.total_attempts()}). Fix issues.",
```

Replace validation passed (lines 292–294):

```python
                if cb:
                    cb("    reviewer: PASSED")
```

With:

```python
                progress.validation_passed()
```

Replace guardrail catch progress (lines 296–305):

```python
            except OutputGuardrailTripwireTriggered:
                total_iterations += 1
                if cb:
                    from desmet.adapters._tools import _check_completion
                    _, hint = _check_completion(context.workspace, stage_name)
                    elapsed = time.monotonic() - t0
                    cb(f"    reviewer: FAILED (attempt {attempt + 1}/{MAX_RETRIES}) — {hint}  ({elapsed:.0f}s)")
```

With:

```python
            except OutputGuardrailTripwireTriggered:
                total_iterations += 1
                _, feedback = policy.validate()
                progress.validation_failed(
                    attempt + 1, policy.total_attempts(), feedback,
                )
```

Replace max turns exceeded progress (lines 311–313):

```python
                if cb:
                    elapsed = time.monotonic() - t0
                    cb(f"    max turns exceeded (attempt {attempt + 1}/{MAX_RETRIES})  ({elapsed:.0f}s)")
```

With:

```python
                progress.agent_status(
                    "executor",
                    f"max turns exceeded (attempt {attempt + 1}/{policy.total_attempts()})",
                )
```

Remove `t0 = time.monotonic()` (line 177) and `cb = context.progress_callback` (line 178) — reporter owns timing.

- [ ] **Step 4: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_observation_collector.py tests/test_retry_policy.py tests/test_progress_reporter.py tests/test_scoring_constants.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/desmet/adapters/openai_agents.py
git commit -m "refactor(openai-agents): use RetryPolicy and ProgressReporter"
```

---

### Task 6: Migrate Agent Framework adapter

**Files:**
- Modify: `src/desmet/adapters/agent_framework.py`

**Depends on:** Task 2

- [ ] **Step 1: Update imports**

Remove (lines 31–32):

```python
from desmet.adapters._tracing import format_tool_detail
from desmet.adapters._validation import validate_workspace
```

Add:

```python
from desmet.adapters._retry import ProgressReporter, RetryPolicy
```

- [ ] **Step 2: Update `_run_agent` signature and progress calls**

Add `policy` and `progress` to `_run_agent` signature (lines 167–175).

Remove `t0 = time.monotonic()` and `cb = context.progress_callback` — use `progress` throughout.

Replace tool call progress in `executor_completed` handler (lines 452–458 and 462–468). Replace both identical blocks:

```python
                                    if cb:
                                        elapsed = time.monotonic() - t0
                                        detail = format_tool_detail(tc_name, tc_args)
                                        tokens = collector.trace.total_tokens_input + collector.trace.total_tokens_output
                                        cb(f"    tool {tool_call_count} — {detail}  ({elapsed:.0f}s, {tokens:,} tokens)")
```

With:

```python
                                    progress.tool_call(tc_name, tc_args)
```

Remove `tool_call_count` variable — reporter counts internally.

Replace agent completion (line 470–471):

```python
                    if cb:
                        cb(f"    [completed] {executor_name}")
```

With:

```python
                    progress.agent_status(executor_name, "completed")
```

Replace manager events (line 366):

```python
                    if cb:
                        cb(f"    [manager] {event_name}")
```

With:

```python
                    progress.agent_status("manager", event_name)
```

Replace planner progress (line 264):

```python
        if cb:
            cb(f"    planner: {len(plan.steps)} steps planned")
```

With:

```python
        progress.agent_status("planner", f"{len(plan.steps)} steps planned")
```

Replace final validation (lines 500–509):

```python
        passed = validate_workspace(stage_name, str(context.workspace))
        if cb:
            if passed:
                cb("    validator: PASSED")
            else:
                from desmet.adapters._tools import _check_completion
                _, hint = _check_completion(context.workspace, stage_name)
                elapsed = time.monotonic() - t0
                cb(f"    validator: FAILED — {hint}  ({elapsed:.0f}s)")
```

With:

```python
        passed, feedback = policy.validate()
        if passed:
            progress.validation_passed()
        else:
            progress.validation_failed(1, 1, feedback)
```

- [ ] **Step 3: Run tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_observation_collector.py tests/test_retry_policy.py tests/test_progress_reporter.py tests/test_scoring_constants.py -v`

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add src/desmet/adapters/agent_framework.py
git commit -m "refactor(agent-framework): use RetryPolicy and ProgressReporter"
```

---

### Task 7: Fix existing adapter tests

**Files:**
- Modify: `tests/test_crewai_adapter.py`
- Modify: `tests/test_agent_framework_adapter.py`

**Depends on:** Tasks 3–6

- [ ] **Step 1: Fix CrewAI adapter tests**

In `tests/test_crewai_adapter.py`:

Update `test_run_agent_signature` to expect `policy` and `progress` parameters.

Update `_create_trace_callbacks` test calls — the signature changed from `(collector, *, progress_callback=..., max_iterations=...)` to `(collector, progress)`. Create a `ProgressReporter` with a no-op callback:

```python
from desmet.adapters._retry import ProgressReporter

def _make_progress(collector):
    return ProgressReporter(callback=None, collector=collector)
```

Replace all `_create_trace_callbacks(_make_collector(trace), progress_callback=..., max_iterations=...)` calls with `_create_trace_callbacks(_make_collector(trace), _make_progress(_make_collector(trace)))`.

Note: For tests that check tool call counting, the counter is now internal to the reporter, not tracked by `tool_counter` in the callback. Update assertions accordingly — check `trace.tool_calls` length instead of counter variables.

- [ ] **Step 2: Fix Agent Framework adapter tests**

In `tests/test_agent_framework_adapter.py`:

Update `test_run_agent_signature` to expect `policy` and `progress` parameters.

- [ ] **Step 3: Run all adapter tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_crewai_adapter.py tests/test_agent_framework_adapter.py tests/test_observation_collector.py tests/test_retry_policy.py tests/test_progress_reporter.py tests/test_scoring_constants.py -v`

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_crewai_adapter.py tests/test_agent_framework_adapter.py
git commit -m "test: update adapter tests for RetryPolicy/ProgressReporter API"
```

---

### Task 8: Final verification

**Files:** None (verification only)

**Depends on:** Tasks 1–7

- [ ] **Step 1: Run full test suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -v`

Expected: No new failures beyond pre-existing ones.

- [ ] **Step 2: Verify no `MAX_RETRIES` constants in adapters**

Run: `grep -rn "^MAX_RETRIES" src/desmet/adapters/ --include="*.py"`

Expected: No output.

- [ ] **Step 3: Verify no `format_tool_detail` imports in adapters**

Run: `grep -rn "format_tool_detail" src/desmet/adapters/ --include="*.py" | grep -v _tracing.py | grep -v _retry.py`

Expected: No output.

- [ ] **Step 4: Verify no direct `validate_workspace` in 3 adapters**

Run: `grep -rn "validate_workspace" src/desmet/adapters/langgraph.py src/desmet/adapters/crewai.py src/desmet/adapters/agent_framework.py`

Expected: No output. (Only `openai_agents.py` keeps it for the guardrail factory.)

- [ ] **Step 5: Verify no `_check_completion` imports in adapters**

Run: `grep -rn "_check_completion" src/desmet/adapters/langgraph.py src/desmet/adapters/crewai.py src/desmet/adapters/openai_agents.py src/desmet/adapters/agent_framework.py`

Expected: No output.
