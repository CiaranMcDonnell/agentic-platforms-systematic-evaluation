# Google ADK Adapter Design

## Overview

Implement the Google ADK (Agent Development Kit) platform adapter, replacing the current stub. The adapter follows the same `ToolAgentAdapter` base class pattern as the 4 existing adapters (LangGraph, CrewAI, OpenAI Agents SDK, Agent Framework) while leveraging ADK's distinctive orchestration primitives.

## ADK Strengths Leveraged

1. **SequentialAgent + LoopAgent** — first-class multi-agent orchestration, no hand-rolled graphs or manual retry loops
2. **Event-driven streaming** — `runner.run_async()` yields typed `Event` objects for observation
3. **Session state** — `InMemorySessionService` with `output_key` for inter-agent data flow (planner → executor)
4. **Callback system** — `after_model_callback` and `after_tool_callback` for token/tool tracking
5. **`RunConfig.max_llm_calls`** — built-in iteration budget mapping to DESMET's `max_iterations`
6. **Plain functions as tools** — ADK auto-wraps via `FunctionTool`, so `ToolFormat.CALLABLE` works directly
7. **Structured output** — `output_schema=ImplementationPlan` on planner agent

## Architecture

### Class Structure

```python
class GoogleADKAdapter(ToolAgentAdapter):
    TOOL_FORMAT = ToolFormat.CALLABLE

    async def _run_agent(self, stage_name, prompt, system_msg, tools,
                         collector, context, policy, progress) -> tuple[int, bool]
```

Extends `ToolAgentAdapter`. The 4 SDLC stage methods (`generate_requirements`, `generate_code`, `generate_tests`, `build_and_deploy`) are inherited from `_execute_stage()`.

### Agent Pipeline (per stage)

```
SequentialAgent("desmet_{stage}_pipeline")
  |-- LlmAgent("planner")        # output_schema=ImplementationPlan, output_key="plan"
  |-- LoopAgent("execute_loop", max_iterations=retry_budget)
  |     |-- LlmAgent("executor") # tools=executor_tools, reads state["plan"]
  |     +-- LlmAgent("reviewer") # tools=reviewer_tools + exit_loop
  +-- (post-loop validation via policy.validate())
```

**Planner**: Structured output via `output_schema=ImplementationPlan`. No tools (ADK constraint: output_schema disables tools). Stores result in `session.state["plan"]` via `output_key`. Fallback: if structured output fails, re-run without `output_schema` and parse via `parse_plan_text()`.

**Executor**: Instructions built via `build_executor_instructions(persona, plan, system_msg)`. Gets `executor_tools` (all except `check_completion`) via `split_tools()`. Reads plan from session state.

**Reviewer**: Gets `reviewer_tools` (read_file, list_directory, search_code, check_completion) via `split_tools()`, plus ADK's built-in `exit_loop` tool. Calls `check_completion`, then `exit_loop` if validation passes.

**LoopAgent**: `max_iterations` = `max(3, context.max_iterations - 3)`. Native retry — executor→reviewer cycles until `exit_loop` or iteration limit.

### Tool Format

`ToolFormat.CALLABLE` — no new enum value needed. ADK auto-wraps plain Python functions with docstrings and type hints into `FunctionTool` instances. The existing `_build_callable_tools()` output works directly.

### Tool Distribution

Same asymmetric split as all other adapters via `split_tools()`:
- **Executor**: all tools except `check_completion`
- **Reviewer**: `read_file`, `list_directory`, `search_code`, `check_completion` + `exit_loop`

## Observation & Token Tracking

### Callbacks (per-LLM-call granularity)

`after_model_callback` on executor and reviewer agents:
- Extracts `response.usage_metadata` (input/output token counts)
- Calls `collector.record_llm_response(raw_usage=usage, duration_ms=...)`

`after_tool_callback` on executor and reviewer agents:
- Calls `collector.record_tool_execution(name, args, result)`
- Calls `progress.tool_call(name, args)`

### Event Stream Processing

`runner.run_async()` yields `Event` objects:
- `event.get_function_calls()` — tool call events
- `event.get_function_responses()` — tool result events
- `event.content` with text parts — `collector.record_message()`
- `event.is_final_response()` — final output recording
- `event.author` — attribute messages to planner/executor/reviewer

### Iteration Counting

- Count agent-authored events from the stream
- `RunConfig(max_llm_calls=context.max_iterations)` as hard ceiling
- `collector.mark_iterations(total)` after streaming completes

## Model Configuration

Uses `get_llm_config()` like all other adapters.

**Gemini (native)**: Pass model string directly (`"gemini-2.5-flash"`). Temperature via `GenerateContentConfig`.

**Non-Gemini (LiteLLM)**: Requires `google-adk[extensions]`. Model formatted as `"openai/gpt-5.4-2026-03-05"` or `"anthropic/claude-sonnet-4-20250514"`. API keys from existing env vars.

```python
def _create_model(self, cfg: LLMConfig) -> str:
    if cfg.provider == Provider.GOOGLE:
        return cfg.model
    prefix = {"openai": "openai", "openrouter": "openrouter", "anthropic": "anthropic"}
    return f"{prefix[cfg.provider.value]}/{cfg.model}"
```

## Validation & Retry

**Primary**: `LoopAgent` handles executor→reviewer retry natively. Reviewer calls `check_completion` → `exit_loop` on pass. Loop exhaustion on fail.

**Post-loop**: `policy.validate()` for final confirmation. Reports via `progress.validation_passed()` / `progress.validation_failed()`.

**Iteration budget**: Planner ~3 calls. Remaining budget → LoopAgent. `RunConfig.max_llm_calls` as safety ceiling.

**Hit limit**: `total_iterations >= context.max_iterations` or `RunConfig` terminates early.

## Registry Integration

- Add `"google_adk"` to `_IMPLEMENTED_PLATFORMS` in `registry.py`
- `ADAPTER_REGISTRY` entry already exists
- `platforms.yaml` entry already defined

## Metadata

```python
def get_observability_info(self):
    return {
        "has_tracing": True,
        "has_step_through": False,
        "has_replay": True,            # Session rewind
        "has_state_inspection": True,   # Session state per agent
        "has_memory_inspection": False,
        "trace_format": "Event stream",
    }

def get_failure_handling_info(self):
    return {
        "has_checkpointing": True,          # Session state across loop iterations
        "has_auto_recovery": True,          # LoopAgent retry
        "has_graceful_degradation": True,   # max_llm_calls ceiling
        "supports_human_handoff": False,
        "is_idempotent": True,
    }
```

## Dependencies

`google-adk[extensions]` added to project optional deps (for LiteLLM non-Gemini support).

## Files Changed

- `src/desmet/adapters/google_adk.py` — full adapter implementation (replaces stub)
- `src/desmet/adapters/registry.py` — add to `_IMPLEMENTED_PLATFORMS`
- `pyproject.toml` — add `google-adk[extensions]` to optional deps
