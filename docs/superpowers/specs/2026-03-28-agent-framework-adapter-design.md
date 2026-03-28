# Microsoft Agent Framework Adapter — Design Spec

**Date:** 2026-03-28
**Status:** Approved
**Platform ID:** `microsoft_agent_framework`
**Package:** `agent-framework` (RC 1.0rc5+)

## Overview

Implement a full `ToolAgentAdapter` for Microsoft Agent Framework using the **MagenticOne orchestration pattern** — a manager agent dynamically coordinates three specialized agents (Planner, Executor, Reviewer). This is the framework's most distinctive feature and provides the richest evaluation signal for DESMET scoring.

## Architecture

### Agent Topology

Four agents orchestrated via `MagenticBuilder`:

| Agent | Persona Source | Responsibilities |
|-------|---------------|------------------|
| **Manager** | Implicit (MagenticBuilder) | Coordinates rounds, detects stalls, injects validation feedback, decides when to stop |
| **Planner** | `_prompts.planner` sub-persona | Produces a numbered implementation plan with file list and dependency order |
| **Executor** | `_prompts.{stage}` persona | Implements the plan — writes files, runs shell commands, deploys |
| **Reviewer** | `_prompts.reviewer` sub-persona | Inspects workspace via tools, calls `check_completion`, provides pass/fail feedback |

### Orchestration Flow

```
MagenticBuilder(
    manager_agent=manager,
    participants=[planner, executor, reviewer],
    max_round_count=context.max_iterations,
    max_stall_count=3,
)
```

Execution proceeds as:

1. Manager delegates planning to Planner agent
2. Planner returns structured `ImplementationPlan` (or free-text fallback)
3. Manager delegates implementation to Executor with the plan
4. Executor uses tools to write files, run commands, etc.
5. Manager delegates review to Reviewer
6. Reviewer calls `check_completion()` tool — result feeds back to manager
7. If validation fails, manager sees the feedback and re-delegates to Executor
8. If stall detected (no progress after `max_stall_count` rounds), manager resets
9. Loop continues until validation passes or `max_round_count` exhausted

### Iteration Tracking

- Each manager round increments `iterations` in the trace
- `hit_limit = True` when `max_round_count` or `max_stall_count` terminates the workflow
- Final iteration count = total rounds executed

## Token & Cost Tracking

### ChatMiddleware Approach

Register a custom `ChatMiddleware` on the chat client that intercepts every LLM call:

```python
from agent_framework import ChatMiddleware, ChatContext
import threading

class UsageTrackingMiddleware(ChatMiddleware):
    def __init__(self, trace: AgentTrace):
        self._trace = trace
        self._lock = threading.Lock()

    async def invoke(self, context: ChatContext, next):
        start = time.perf_counter()
        result = await next(context)
        duration_ms = (time.perf_counter() - start) * 1000

        # Extract UsageContent from response
        for item in result.items:
            if hasattr(item, 'input_tokens'):
                with self._lock:
                    record_usage(
                        self._trace,
                        input_tokens=item.input_tokens,
                        output_tokens=item.output_tokens,
                        cost_usd=estimate_cost(model, item.input_tokens, item.output_tokens),
                        model=context.model_id,
                    )
                    record_llm_duration(self._trace, duration_ms)
        return result
```

This gives per-call granularity (model, tokens, duration) and is thread-safe for concurrent agent execution.

## Tool Integration

### Tool Format

Add `AGENT_FRAMEWORK` to the `ToolFormat` enum in `_tools.py`.

Builder function `_build_agent_framework_tools()` wraps the shared callable tools with Agent Framework's `@tool` decorator and `Annotated` type hints:

```python
from agent_framework import tool
from typing import Annotated
from pydantic import Field

@tool
def read_file(
    path: Annotated[str, Field(description="Relative path to file")]
) -> str:
    """Read a file from the workspace."""
    return _callable_read_file(path)
```

All 7 shared tools are wrapped: `read_file`, `write_file`, `list_directory`, `execute_shell`, `search_code`, `deploy_remote`, `check_completion`.

### Tool Assignment

- **Planner**: no tools (pure reasoning)
- **Executor**: all tools except `check_completion`
- **Reviewer**: `read_file`, `list_directory`, `search_code`, `check_completion`

## Structured Output

Planner agent uses `response_format=ImplementationPlan` for deterministic plan extraction:

```python
class ImplementationPlan(BaseModel):
    steps: list[str]
    files_to_create: list[str]
    files_to_modify: list[str]
```

Fallback: if structured output fails (non-OpenAI provider), parse free-text numbered steps via regex `^\d+\.\s+(.*)`. Same pattern as the OpenAI Agents SDK adapter.

## Validation Strategy

Validation is **manager-driven** (no external retry loop):

1. Reviewer agent calls `check_completion()` tool during its turn
2. Tool returns pass/fail with specific failure reasons
3. Manager receives this as a message in the shared conversation
4. On failure: manager re-delegates to Executor with the failure context
5. On pass: manager terminates the workflow
6. Safety bounds: `max_round_count` and `max_stall_count` prevent infinite loops

After orchestration completes, `validate_workspace()` is called for the final `StageResult.success` value (consistent with all other adapters).

## Adapter Class Structure

```python
class AgentFrameworkAdapter(ToolAgentAdapter):
    TOOL_FORMAT = ToolFormat.AGENT_FRAMEWORK

    @property
    def platform_info(self) -> PlatformInfo:
        return load_platform_info("microsoft_agent_framework")

    async def initialize(self) -> None:
        # Verify agent-framework installed, API key available
        ...

    async def shutdown(self) -> None:
        # Cleanup sessions
        ...

    async def health_check(self) -> bool:
        # Quick LLM ping
        ...

    async def _run_agent(self, stage_name, prompt, system_msg, tools, trace, context):
        # 1. Create chat client with UsageTrackingMiddleware
        # 2. Create planner/executor/reviewer agents
        # 3. Build MagenticBuilder workflow
        # 4. Run workflow, stream events
        # 5. Record messages/tool calls to trace
        # 6. Return (iterations, hit_limit)
        ...

    def get_observability_info(self) -> dict:
        return {
            "has_tracing": True,
            "has_checkpointing": True,
            "has_stall_detection": True,
            "has_state_inspection": True,
            "trace_format": "opentelemetry",
        }

    def get_failure_handling_info(self) -> dict:
        return {
            "has_auto_recovery": True,
            "has_checkpointing": True,
            "recovery_mechanism": "manager-driven stall detection and re-delegation",
        }
```

## LLM Client Configuration

Create client from `context.model` and `context.temperature`, respecting `DESMET_PROVIDER`:

- **OpenAI / Azure OpenAI**: `OpenAIChatClient(model_id=...)` or `AzureOpenAIChatClient(...)`
- **Other providers** (OpenRouter, Anthropic, Google): `OpenAIChatClient` with custom `base_url` (OpenAI-compatible endpoint)

Middleware is registered on the client instance, so token tracking works regardless of provider.

## Observability Integration

- Call `configure_otel_providers()` during `initialize()` if Langfuse/Jaeger env vars are set
- Native OTel spans: `invoke_agent`, `chat`, `execute_tool` — all auto-emitted
- Compatible with existing Langfuse setup via OTLP exporter

## File Changes

| File | Change |
|------|--------|
| `src/desmet/adapters/agent_framework.py` | Replace stub with full implementation |
| `src/desmet/adapters/_tools.py` | Add `AGENT_FRAMEWORK` to `ToolFormat` enum + builder |
| `src/desmet/adapters/registry.py` | Add to `_IMPLEMENTED_PLATFORMS` frozenset |
| `tests/test_agent_framework_adapter.py` | New test file (mirrors existing adapter tests) |
| `pyproject.toml` | Add `agent-framework` dependency |

## Testing Strategy

Mirror the existing adapter test pattern (`test_crewai_adapter.py`):

1. **Unit tests**: mock the chat client, verify agent creation, tool assignment, middleware registration
2. **Tool format tests**: verify `_build_agent_framework_tools()` produces valid `@tool`-decorated callables
3. **Orchestration tests**: mock `MagenticBuilder.build().run_stream()`, verify iteration counting and trace recording
4. **Validation flow tests**: simulate manager receiving validation failure, verify re-delegation
5. **Cost tracking tests**: verify `UsageTrackingMiddleware` correctly extracts and accumulates token usage

## Dependencies

```toml
[project.optional-dependencies]
agent-framework = ["agent-framework>=1.0rc5"]
```

Add to the `all` extra as well.
