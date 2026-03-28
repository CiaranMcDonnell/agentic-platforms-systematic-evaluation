# Retry Policy & Progress Reporter — Design Specification

**Date**: 2026-03-28
**Status**: Approved (pending implementation plan)

## Problem

All 4 platform adapters duplicate retry/validation logic and progress callback formatting that should be owned by the base class:

1. **`MAX_RETRIES = 3`** defined independently in 3 adapter files (LangGraph, CrewAI, OpenAI Agents).
2. **Retry attempt counting is inconsistent**: OpenAI Agents uses `range(MAX_RETRIES)` (3 attempts), while LangGraph and CrewAI use `range(MAX_RETRIES + 1)` (4 attempts). This is a bug.
3. **Validation calls** (`validate_workspace` + `_check_completion`) are imported and called inline by all 4 adapters with ad-hoc feedback formatting.
4. **Progress callback strings** (~40 occurrences) follow the same structure across adapters but with inconsistent formatting — different labels (`"validator"` vs `"reviewer"`), inconsistent elapsed/token inclusion, different attempt numbering.

## Approach: RetryPolicy + ProgressReporter

Two new classes that the base class creates and passes to adapters. Adapters **keep their idiomatic retry mechanisms** (graph edges, guardrails, manager orchestration) but use the shared policy for parameters and the shared reporter for formatting.

### Why not base-class retry loop

Framework-specific retry mechanisms are strengths that should be preserved:
- **LangGraph**: Retry via `route_after_reviewer` conditional edge — part of the compiled graph structure, enables checkpointing across retries.
- **OpenAI Agents**: Retry via `OutputGuardrailTripwireTriggered` exception — idiomatic SDK pattern that triggers conversation carry-forward.
- **Agent Framework**: MagenticOne's manager handles retry internally with stall detection and re-planning — bypassing it would lose orchestration intelligence.
- **CrewAI**: Plain `for` loop, but with iteration budget reallocation on retry (planner skipped, executor gets 80%).

Pulling the retry loop into the base would strip these mechanisms. Instead, the base provides the **policy** (how many retries, how to validate) and the **reporter** (how to format progress), while adapters keep their idiomatic **mechanism** (when and how to retry).

## Constraints

- Framework-specific retry mechanisms are preserved — graph edges, guardrails, manager orchestration stay in adapters.
- `_tracing.py`, `AgentTrace`, `StageResult`, `ObservationCollector` are not modified.
- `_validation.py` and `_tools._check_completion` stay as-is — `RetryPolicy` wraps them.

## Architecture

### New module: `src/desmet/adapters/_retry.py`

```
_retry.py ──imports──→ _validation.py (validate_workspace)
           ──imports──→ _tools.py (_check_completion)
           ──imports──→ _tracing.py (format_tool_detail)
           ──imports──→ _observation.py (ObservationCollector)
_base.py  ──imports──→ _retry.py (RetryPolicy, ProgressReporter)
adapters  ──receive──→ RetryPolicy, ProgressReporter via _run_agent parameters
```

### RetryPolicy

```python
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
        """Max retries + 1 initial attempt.  Fixes the 3-vs-4 inconsistency."""
        return self.max_retries + 1

    def validate(self) -> tuple[bool, str]:
        """Run workspace validation for the current stage.

        Returns ``(passed, feedback)`` where *feedback* is a human-readable
        string from ``_check_completion`` (success message when passed,
        failure hint when not).
        """
```

### ProgressReporter

```python
class ProgressReporter:
    """Standardized progress formatting for adapter execution.

    Owns elapsed time tracking, tool call counting, and token reads.
    All methods are no-ops when the callback is ``None``.
    """

    def __init__(
        self,
        callback: Callable[[str], None] | None,
        collector: ObservationCollector,
    ) -> None: ...

    def tool_call(self, name: str, args: Any) -> None:
        """Emit: '    tool 3 — read_file -> src/main.py  (12s, 1,234 tokens)'

        Increments internal tool counter.  Uses ``format_tool_detail``
        internally — adapters no longer import it.
        """

    def validation_passed(self) -> None:
        """Emit: '    validator: PASSED'"""

    def validation_failed(
        self, attempt: int, max_attempts: int, feedback: str,
    ) -> None:
        """Emit: '    validator: FAILED (attempt 2/4) — Missing artifacts...'"""

    def agent_status(self, agent: str, status: str) -> None:
        """Emit: '    [planner] done — 5 steps planned  (3s, 500 tokens)'

        Generic agent lifecycle reporting.
        """

    def heartbeat(self, step: int, label: str = "") -> None:
        """Emit: '    [executor] step 7  (15s, 2,000 tokens)'

        *label* is the agent/node name shown in brackets.
        Periodic progress during long-running execution.
        """
```

All methods read elapsed time from an internal `_t0` (set at construction) and tokens from `collector.trace`. The `tool_call` method uses `format_tool_detail` internally — adapters no longer need to import it.

## Integration with `_base.py`

### `_run_agent` signature change

```python
# Before:
@abstractmethod
async def _run_agent(self, stage_name, prompt, system_msg, tools,
                     collector: ObservationCollector, context) -> tuple[int, bool]

# After:
@abstractmethod
async def _run_agent(self, stage_name, prompt, system_msg, tools,
                     collector: ObservationCollector, context,
                     policy: RetryPolicy, progress: ProgressReporter) -> tuple[int, bool]
```

### `max_retries` as a base class attribute

```python
class ToolAgentAdapter(BasePlatformAdapter):
    TOOL_FORMAT: ToolFormat
    max_retries: int = 3  # single source of truth, overridable per adapter
```

Adapters no longer define `MAX_RETRIES` module-level constants.

### Updated `_execute_stage`

```python
async def _execute_stage(self, stage_name, prompt_fn, result_cls, context):
    trace = start_trace()
    try:
        # ... prompt/tools setup (unchanged) ...
        collector = ObservationCollector(...)

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
        warnings = collector.seal()
        # ... same as current ...
```

## Per-Adapter Migration

Framework-specific retry mechanisms are preserved. Only the policy parameters and progress formatting change.

### LangGraph (`langgraph.py`)

**Preserved**: Graph conditional edges (`route_after_reviewer`), `InMemorySaver` checkpointing, streaming with `stream_mode="updates"`, `ParentState.retry_count`.

**Changes in `_build_graph`**: Receives `policy` and `progress` via closure (same pattern as `collector`).

- `executor_wrapper`: `validate_workspace(stage, workspace)` replaced with `policy.validate()` which returns `(passed, feedback)`. Feedback emitted via `progress.validation_failed(new_retry, policy.total_attempts(), feedback)`.
- `planner_wrapper`: Ad-hoc `cb(f"    [planner] done ...")` replaced with `progress.agent_status("planner", f"done — {step_count} steps planned")`.
- `reviewer_wrapper`: Ad-hoc `cb(f"    [reviewer] done ...")` replaced with `progress.agent_status("reviewer", "done")`.
- Streaming tool calls: `format_tool_detail` import removed. Ad-hoc `cb(f"    tool ...")` replaced with `progress.tool_call(tc_name, tc_args)`.
- Heartbeats: `cb(f"    [executor] step ...")` replaced with `progress.heartbeat(llm_call_count, "executor")`.

**In `_run_agent`**: `MAX_RETRIES` references replaced with `policy.max_retries`. Inline `_check_completion` call replaced with `policy.validate()` for feedback.

**Deleted**: `MAX_RETRIES = 3`, `validate_workspace` import, `_check_completion` import, `format_tool_detail` import.

### CrewAI (`crewai.py`)

**Preserved**: Sequential crew with step/task callbacks, event bus for LLM tracking, iteration budget allocation via `_compute_iter_budget`, plan carry-forward on retry.

**Changes in `_run_agent`**: `for attempt in range(MAX_RETRIES + 1)` replaced with `for attempt in range(policy.total_attempts())`. Validation: `validate_workspace(...)` + `_check_completion(...)` replaced with `policy.validate()`. Progress: ad-hoc `cb(...)` replaced with `progress.validation_passed()` / `progress.validation_failed(attempt + 1, policy.total_attempts(), feedback)`.

**Changes in `_create_trace_callbacks`**: Receives `progress: ProgressReporter` instead of a raw callback. Tool calls: `format_tool_detail` + ad-hoc string replaced with `progress.tool_call(tool_name, tool_input)`. Heartbeats: `progress.heartbeat(counter[0], role_label)`. Task completion: `progress.agent_status(agent_name, "task complete")`.

**In `_build_crew`**: Passes `progress` to `_create_trace_callbacks` instead of `progress_callback`.

**Deleted**: `MAX_RETRIES = 3`, `validate_workspace` import, `_check_completion` import, `format_tool_detail` import.

### OpenAI Agents SDK (`openai_agents.py`)

**Preserved**: Output guardrail on reviewer (`_make_workspace_guardrail`), `OutputGuardrailTripwireTriggered` exception handling, conversation carry-forward via `result.to_input_list()`.

**Changes in `_run_agent`**: `for attempt in range(MAX_RETRIES)` replaced with `for attempt in range(policy.total_attempts())` — **fixes the 3-vs-4 attempt bug**. In the guardrail catch block: `_check_completion(...)` replaced with `policy.validate()` for the feedback string. Progress: `cb(f"    reviewer: FAILED ...")` replaced with `progress.validation_failed(attempt + 1, policy.total_attempts(), hint)`.

**The guardrail itself** still calls `validate_workspace` internally — this is intentional. The guardrail is an SDK-idiomatic trigger. `policy.validate()` in the catch block provides the feedback string for the user, not the retry decision (which is exception-driven).

**Changes in `_extract_trace`**: Receives `progress: ProgressReporter` instead of `cb`/`t0`. Tool calls: `format_tool_detail` + ad-hoc string replaced with `progress.tool_call(call.name, call.arguments)`.

**Deleted**: `MAX_RETRIES = 3`, `_check_completion` import, `format_tool_detail` import. `validate_workspace` import stays (used by guardrail factory).

### Agent Framework (`agent_framework.py`)

**Preserved**: MagenticOne orchestration with manager-driven stall detection, `MAX_STALL_COUNT` / `MAX_RESET_COUNT`, streaming events, `UsageTrackingMiddleware`.

**Changes in `_run_agent`**: Final validation: `validate_workspace(...)` + `_check_completion(...)` replaced with `policy.validate()`. Progress: ad-hoc `cb(...)` replaced with `progress.validation_passed()` / `progress.validation_failed(...)`. Tool calls: `format_tool_detail` + ad-hoc string replaced with `progress.tool_call(tc_name, tc_args)`. Manager events: `cb(f"    [manager] ...")` replaced with `progress.agent_status("manager", event_name)`. Agent completion: `cb(f"    [completed] ...")` replaced with `progress.agent_status(executor_name, "completed")`.

No retry loop added — MagenticOne handles that internally.

**Deleted**: `validate_workspace` import, `_check_completion` import, `format_tool_detail` import.

### Code deleted across all adapters

| Deleted | Files affected |
|---------|---------------|
| `MAX_RETRIES = 3` | langgraph.py, crewai.py, openai_agents.py |
| `from desmet.adapters._validation import validate_workspace` | langgraph.py, crewai.py, agent_framework.py (stays in openai_agents.py for guardrail) |
| `from desmet.adapters._tools import _check_completion` (inline) | langgraph.py, crewai.py, openai_agents.py, agent_framework.py |
| `from desmet.adapters._tracing import format_tool_detail` | langgraph.py, crewai.py, openai_agents.py, agent_framework.py |
| Ad-hoc progress f-strings | ~40 occurrences across all 4 adapters |

## Testing

### Unit tests (`test_retry_policy.py`)

- `policy.validate()` returns `(True, "VALIDATION PASSED: ...")` when workspace passes.
- `policy.validate()` returns `(False, "VALIDATION FAILED: ...")` with stage-specific hints.
- `policy.total_attempts()` returns `max_retries + 1`.
- Default `max_retries` is 3.

### Unit tests (`test_progress_reporter.py`)

- `tool_call()` emits standardized format with counter, detail, elapsed, tokens.
- `validation_passed()` emits `"    validator: PASSED"`.
- `validation_failed(2, 4, "hint")` emits `"    validator: FAILED (attempt 2/4) — hint"`.
- `agent_status("planner", "done — 5 steps")` emits `"    [planner] done — 5 steps  (Ns, N tokens)"`.
- `heartbeat(7, "executor")` emits `"    [executor] step 7  (Ns, N tokens)"`.
- All methods are no-ops when callback is `None`.
- `tool_call` increments internal counter correctly.

### Existing adapter tests

Update to pass `policy` / `progress` to `_create_trace_callbacks` and other changed signatures.
