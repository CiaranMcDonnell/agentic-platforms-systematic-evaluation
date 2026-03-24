# Idiomatic Adapter Redesign

**Date:** 2026-03-24
**Status:** Approved
**Scope:** `src/desmet/adapters/langgraph.py`, `crewai.py`, `openai_agents.py`, `_prompts.py`

## Problem

The current adapters share a `ToolAgentAdapter` base that provides identical prompts, tools, and validation. Each adapter's `_run_agent` runs a single agent with all tools — effectively three API wrappers around the same single-agent-with-tools loop. This suppresses the architectural differences that the evaluation is designed to measure.

The frameworks should use their native strengths so orchestration differences are visible in scoring dimensions (pipeline completeness, efficiency, orchestration, autonomy, trace quality).

## Design Principles

- **Same inputs, different orchestration.** Prompts from `_prompts.py` and tools from `_tools.py` remain shared. Each adapter decomposes them across multiple agents using its native patterns.
- **`_run_agent` contract unchanged.** Same signature, same return type `(iterations, hit_limit)`. The base class `_execute_stage` template method is untouched.
- **All tools available to all agents.** No tool restrictions — let the framework's role/goal system focus tool usage naturally. The one exception: the planner agent in each framework gets no tools (it plans from prompt content only). Tool subsets are handled inside `_run_agent`, not in `_execute_stage` — the single `create_tools` call remains, and each adapter filters internally.
- **Per-stage multi-agent, not per-pipeline.** Each `_execute_stage` call runs a self-contained multi-agent interaction. This preserves per-stage metrics collection.

## Iteration Counting

With 3 agents per stage, the iteration budget needs clear definition. An "iteration" is one LLM call (including any tool calls that result from it). The `max_iterations` from `StageContext` (default 50) is the total budget for the entire `_run_agent` call across all agents.

Budget allocation per adapter (proportional to `max_iterations`, not hardcoded):
- **LangGraph:** Planner gets 10% of budget. Executor gets 70%. Reviewer gets 20% (split across retry attempts). For default `max_iterations=50`: planner=5, executor=35, reviewer=10.
- **CrewAI:** Per-agent `max_iter` set proportionally: planner=20%, executor=60%, reviewer=20%. For default `max_iterations=50`: planner=10, executor=30, reviewer=10. The Crew-level `max_iter` is also set to `max_iterations` as a backstop.
- **OpenAI:** Planner gets `max_turns=3` (fixed, minimal). Executor+reviewer share `(max_iterations - 3) // MAX_RETRIES` turns per retry attempt.

The `iterations` return value counts total LLM calls across all agents. `hit_limit` is True if the total reaches `max_iterations`.

## Prompt Decomposition

The existing prompt builders (`build_codegen_prompt`, etc.) produce single-agent prompts that combine planning and execution instructions. With 3 agents, each adapter decomposes the prompt internally:

- **Planner agent** receives: the stage prompt as-is (it contains the task description and context needed to plan)
- **Executor agent** receives: the stage prompt + the planner's output (injected via framework-native mechanism: shared state / task context / dynamic instructions)
- **Reviewer agent** receives: a fixed review instruction from the reviewer persona backstory + access to the workspace via tools

No changes to the existing `build_*_prompt` functions are needed. The planner ignores the execution-specific instructions in the prompt (e.g. "call check_completion") because its persona focuses it on planning. The reviewer ignores the task-specific content because its persona focuses it on validation.

## Validation Strategy

Each adapter uses both the `check_completion` tool (agent-callable) and `validate_workspace()` (deterministic, programmatic), but their roles differ:

- **`check_completion` tool:** Called by the reviewer/validator agent as part of its LLM reasoning. This is what the agent "thinks" it should do — it's part of the agent's autonomous behaviour.
- **`validate_workspace()`:** Called programmatically by the adapter after the reviewer finishes, as a deterministic gate. This is the ground truth — it doesn't depend on whether the agent remembered to call the tool.

The reviewer persona backstory should NOT reference `check_completion` directly. Instead, it should say "verify that all required artefacts are present in the workspace" and let the agent discover the tool naturally. This avoids double-counting and lets the reviewer's tool usage be a genuine measure of autonomy.

## Shared Changes: `_prompts.py`

Add sub-personas for the planner and reviewer roles used by all three frameworks:

```python
_SUB_PERSONAS = {
    "planner": AgentPersona(
        role="Technical Lead",
        goal="Analyse the task and produce a structured implementation plan",
        backstory=(
            "You are a senior technical lead. You break down complex tasks "
            "into clear, actionable steps. You identify files to create or "
            "modify, dependencies between steps, and potential risks."
        ),
    ),
    "reviewer": AgentPersona(
        role="Code Reviewer",
        goal="Validate output completeness and correctness against requirements",
        backstory=(
            "You are a thorough reviewer. You verify that all required "
            "artefacts are present in the workspace, outputs are complete "
            "and correct, and the implementation matches the plan. Use the "
            "available tools to inspect the workspace and confirm completeness."
        ),
    ),
}

def get_sub_persona(name: str) -> AgentPersona:
    return _SUB_PERSONAS[name]
```

The existing stage-specific personas (Requirements Analyst, Software Developer, QA Engineer, DevOps Engineer) remain as the "executor" persona in all three frameworks.

---

## LangGraph Adapter — Subgraphs + Parallel Fan-Out

**Version:** LangGraph 1.1.2

### Architecture

Three subgraphs with private state, connected through the parent graph's shared state. Uses the Command API for routing and InMemorySaver for checkpointing.

```
Parent graph state: { plan, workspace, stage, retry_count, validator_passed }

START → planner_subgraph → executor_subgraph ⇄ tool_node → reviewer_subgraph → (retry | END)
```

### Subgraph Design

Subgraphs communicate through the parent graph's shared state. Each subgraph is invoked as a node in the parent graph — `Command(goto=...)` targets are parent graph nodes, not nodes inside other subgraphs. The parent graph edges handle inter-subgraph routing.

Each subgraph is a compiled `StateGraph` with its own state schema (private message history). The parent graph adds them as nodes:

```python
# Each subgraph is compiled from its own StateGraph
class PlannerState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

planner_builder = StateGraph(PlannerState)
planner_builder.add_node("plan", planner_node)
planner_builder.add_edge(START, "plan")
planner_builder.add_edge("plan", END)
planner_subgraph = planner_builder.compile()

# Similarly for executor_subgraph and reviewer_subgraph...

# Parent graph wires them together
parent_builder = StateGraph(ParentState)
parent_builder.add_node("planner", planner_subgraph)
parent_builder.add_node("executor", executor_subgraph)
parent_builder.add_node("reviewer", reviewer_subgraph)
parent_builder.add_edge(START, "planner")
parent_builder.add_edge("planner", "executor")
parent_builder.add_edge("executor", "reviewer")
parent_builder.add_conditional_edges("reviewer", route_after_review)  # → "executor" or END
graph = parent_builder.compile(checkpointer=InMemorySaver())
```

Communication between subgraphs happens through overlapping state keys in the parent `ParentState` (e.g. `plan`, `workspace`, `validator_passed`). Each subgraph's private `messages` list is isolated.

**Planner subgraph:**
- Private message state
- Single node: LLM call with Technical Lead persona
- Writes plan to parent state via state key mapping
- The planner's system prompt includes: "Format your plan as a numbered list. Mark independent steps with [PARALLEL] if they can be executed concurrently."

**Executor subgraph:**
- Private message state
- Reads `plan` from parent state
- Plan parsing heuristic: split plan text on numbered steps, detect `[PARALLEL]` markers. Steps marked parallel get fan-out via `Send` API. Unmarked steps run serially. If no markers found, all steps run serially (safe default).
- Each executor node: LLM with stage-specific persona (e.g. Software Developer) + all tools
- `ToolNode(tools, handle_tool_errors=True)` for self-correction on tool failures
- Routes to tool_node if `tool_calls` pending, else returns to parent graph

**Reviewer subgraph:**
- Private message state
- Single node: LLM with Code Reviewer persona + all tools
- After the reviewer LLM finishes, `validate_workspace()` is called deterministically
- Updates parent state: `validator_passed`, `retry_count`
- Parent graph's `route_after_review` edge routes to `"executor"` (retry) or `END`

### Key Changes from Current

| Aspect | Current | Proposed |
|--------|---------|----------|
| Graph structure | Flat, 4 nodes | 3 subgraphs with private state |
| Routing | External conditional edge functions | Command API (co-located routing) |
| Checkpointing | None | `InMemorySaver` at compile time |
| Parallelism | None | `Send` API fan-out for multi-file plans |
| Tool error handling | Crash on error | `ToolNode(tools, handle_tool_errors=True)` |
| Retry | State-based counter + conditional edge | Same, but inside reviewer subgraph via Command |
| Transient failure | No handling | `RetryPolicy(max_attempts=2)` on executor node |

### Parallel Execution Detail

The planner's structured plan determines whether parallelism triggers:

- **Simple stories (US001):** Plan has 1-2 steps → serial execution, no fan-out
- **Complex stories (US020):** Plan decomposes into independent file groups → `Send` API creates parallel executor branches per group → deferred node waits for all branches → fan-in aggregates results

This means the graph shape adapts per story, which is visible in the trace and directly affects efficiency scoring.

---

## CrewAI Adapter — Multi-Agent Sequential Crews

**Version:** CrewAI 1.6.1

### Architecture

2-3 specialised agents per stage in a sequential crew with `planning=True` and task context chaining.

```
Crew(process=sequential, planning=True):
  Analyst (Technical Lead) → Executor (stage persona) → Reviewer (Code Reviewer)
```

### Crew Design

**Per-stage crew (example: codegen):**

```python
Crew(
    agents=[analyst, developer, reviewer],
    tasks=[analyse_task, implement_task, review_task],
    process=Process.sequential,
    planning=True,
    planning_llm=llm,  # same model as agents, not default gpt-4o-mini
    verbose=False,
    step_callback=step_cb,
    task_callback=task_cb,
)
```

**Task definitions:**

| Task | Agent | Context | Expected Output | Guardrail |
|------|-------|---------|-----------------|-----------|
| `analyse_task` | Technical Lead | None | Numbered implementation plan | None |
| `implement_task` | Stage persona (e.g. Software Developer) | `[analyse_task]` | All required files written to disk | None |
| `review_task` | Code Reviewer | `[analyse_task, implement_task]` | Validation report | `validate_workspace` |

**Agent configuration:**

- All agents get all tools
- Per-agent `max_iter` set proportionally from `max_iterations` (20%/60%/20% — see Iteration Counting section)
- `allow_delegation=False` on all agents (avoids delegation ping-pong)
- `respect_context_window=True` (default, auto-summarises)

### Key Changes from Current

| Aspect | Current | Proposed |
|--------|---------|----------|
| Agents per stage | 1 | 3 (planner, executor, reviewer) |
| Planning | None | `planning=True` with crew-level plan |
| Task chaining | N/A (single task) | `context=[]` between tasks |
| Validation | No validation loop | `guardrail` on reviewer task |
| Expected output | Generic per-stage string | Specific per-task |
| Iteration budget | Single `max_iter` on Crew | Per-agent `max_iter` |

### Planning Mode Detail

`planning=True` triggers an AgentPlanner call before crew execution. This is distinct from the analyst agent's plan — it's a meta-plan about how the crew should coordinate:

1. AgentPlanner LLM call produces a crew execution plan
2. Plan is injected into each task's description as additional context
3. Each agent then executes with awareness of the overall crew strategy

This is unique to CrewAI and directly measurable — it adds one LLM call of overhead but potentially reduces wasted iterations by aligning all agents upfront.

---

## OpenAI Agents SDK — Handoff Chain + Guardrails + Structured Output

**Version:** openai-agents 0.8.3

### Architecture

Three-agent pipeline: planner with structured output, executor with handoff to reviewer, output guardrail for workspace validation.

All three adapters use consistent naming: **planner**, **executor**, **reviewer**.

```
Planner (output_type=ImplementationPlan) → Executor (handoffs=[reviewer]) → Reviewer (output_guardrail)
  ↑_________________________retry on guardrail trip___________________________|
```

### Agent Design

**Planner agent:**
- Persona: Technical Lead
- `output_type=ImplementationPlan` (Pydantic model — structured output)
- No handoffs (structured output terminates the agent in v0.8.3)
- No tools (planning only, based on prompt content)
- Runner returns the structured plan, adapter feeds it to executor

```python
class ImplementationPlan(BaseModel):
    steps: list[str]
    files_to_create: list[str]
    files_to_modify: list[str]
```

**Executor agent:**
- Persona: Stage-specific (e.g. Software Developer)
- `handoffs=[reviewer_agent]`
- All tools available
- Dynamic instructions via callable (injects the plan at runtime)
- When finished, calls `transfer_to_reviewer`

**Reviewer agent:**
- Persona: Code Reviewer
- All tools available (consistent with design principle)
- `output_guardrail=workspace_guardrail` — deterministic validation after the agent finishes
- No `tool_use_behavior` override — let the reviewer inspect files, run checks, and reason freely before producing output

### Guardrail Design

```python
@output_guardrail
async def workspace_guardrail(ctx, agent, output):
    passed = validate_workspace(stage_name, workspace)
    return GuardrailFunctionOutput(
        output_info={"passed": passed},
        tripwire_triggered=not passed,
    )
```

On trip: catch `OutputGuardrailTripwireTriggered`, feed conversation back to executor via `result.to_input_list()` with failure context. Max 3 retries.

### Plan Storage

The planner's `ImplementationPlan` is stored on a lightweight adapter-local context object passed as the `RunContext` type parameter. This avoids modifying the shared `StageContext` dataclass:

```python
@dataclass
class OpenAIRunContext:
    """Adapter-local context passed through RunContextWrapper."""
    stage_context: StageContext
    plan: ImplementationPlan | None = None
```

After the planner run, the adapter sets `run_ctx.plan = planner_result.final_output_as(ImplementationPlan)` before starting the executor run.

### Dynamic Instructions

The executor agent uses a callable for instructions, injecting the planner's structured output at runtime:

```python
async def executor_instructions(ctx: RunContextWrapper[OpenAIRunContext], agent: Agent) -> str:
    plan = ctx.context.plan  # ImplementationPlan set after planner run
    plan_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(plan.steps))
    files = ", ".join(plan.files_to_create + plan.files_to_modify)
    return (
        f"{persona.backstory}\n\n"
        f"## Implementation Plan\n{plan_text}\n\n"
        f"## Files: {files}\n\n"
        f"{system_msg or ''}"
    )
```

### Execution Flow

```
1. Runner.run(planner, input=stage_prompt, max_turns=3)
   → Returns ImplementationPlan (Pydantic model)
   → Adapter stores plan in a RunContext-accessible location

2. Runner.run(executor, input=stage_prompt, max_turns=(max_iterations - 3) // MAX_RETRIES)
   → Dynamic instructions inject the plan
   → Executor works using tools, then handoffs to reviewer
   → Reviewer inspects workspace, guardrail evaluates
   → If pass: RunResult returned
   → If fail: OutputGuardrailTripwireTriggered raised

3. On guardrail trip:
   result.to_input_list() + [{"role": "user", "content": "Validation failed..."}]
   → Re-run from executor (attempt 2/3)
```

### Key Changes from Current

| Aspect | Current | Proposed |
|--------|---------|----------|
| Agents | 1 | 3 (planner, executor, reviewer) |
| Planning | None | Structured output via `output_type` |
| Agent transfer | N/A | Handoff from executor → reviewer |
| Validation | External for-loop | Output guardrail (SDK-native) |
| Instructions | Static string concat | Dynamic callable |
| Tracing | Manual extraction | `RunConfig` with workflow_name, trace_id, group_id |

### Structured Output Detail

The `ImplementationPlan` Pydantic model is unique to this adapter. Neither LangGraph nor CrewAI has native structured output enforcement — their planners produce free text. This means:

- The OpenAI adapter's plan is machine-parseable (visible in trace quality scoring)
- The plan structure is consistent across runs (more reproducible)
- Invalid plans fail fast via Pydantic validation rather than downstream

---

## Scoring Impact

These changes make the following orchestration differences measurable:

| Dimension | LangGraph signal | CrewAI signal | OpenAI signal |
|-----------|-----------------|---------------|---------------|
| **Pipeline Completeness** | Checkpoint resume on failure | Crew planning aligns agents | Guardrail catches incomplete output |
| **Efficiency** | Parallel fan-out reduces wall-clock time on complex stories | Planning mode may reduce wasted iterations | Structured output prevents malformed plans |
| **Orchestration** | Graph-native routing, subgraph isolation | Role-based task chaining, per-agent iteration budgets | Handoff chain, dynamic instructions |
| **Trace Quality** | Node-level state + checkpoint history | Per-agent step callbacks + crew plan trace | Structured spans via RunConfig + guardrail events |
| **Autonomy** | Validator subgraph auto-retries via graph edges | Guardrail on reviewer task auto-retries | Output guardrail trips trigger retry |
| **Error Recovery** | `handle_tool_errors=True` + `RetryPolicy` | Per-agent `max_iter` limits + guardrail | `RunErrorHandlers` + guardrail tripwire catch |

## Token Tracking

With multiple agents per stage, all LLM calls must be accumulated into a single `AgentTrace`. The existing `record_usage()` function already accumulates (it adds to `trace.total_tokens_input` and `trace.total_tokens_output`), so the mechanism works. Per-adapter considerations:

- **LangGraph:** Parallel `Send` branches write to the same trace. Since `record_usage` is called from the streaming loop (which processes chunks sequentially even when nodes run in parallel — LangGraph's `astream` serialises output), there is no concurrency issue.
- **CrewAI:** The event bus handler is already thread-safe (uses `_llm_calls_lock`). With 3 agents, it collects calls from all agents and flushes them after `crew.kickoff()` returns. No change needed.
- **OpenAI:** Each `Runner.run()` call (planner, then executor+reviewer) produces a separate `RunResult`. Token extraction via `_extract_trace()` is called sequentially after each run. No change needed.

## Metadata Updates

Each adapter's `get_observability_info()` and `get_failure_handling_info()` should be updated to reflect the new capabilities:

- **LangGraph:** `has_checkpointing: True` (InMemorySaver), `has_state_inspection: True` (subgraph state)
- **CrewAI:** `has_auto_recovery: True` (guardrail on reviewer task retries), notes updated to describe multi-agent crew
- **OpenAI:** `has_state_inspection: True` (RunConfig trace hierarchy), notes updated to describe handoff chain + guardrails

## Files Changed

| File | Change |
|------|--------|
| `src/desmet/adapters/_prompts.py` | Add `_SUB_PERSONAS`, `get_sub_persona()` |
| `src/desmet/adapters/langgraph.py` | Rewrite: subgraphs, Command API, InMemorySaver, Send API, handle_tool_errors |
| `src/desmet/adapters/crewai.py` | Rewrite: 3-agent crew, planning=True, task context chaining, guardrail |
| `src/desmet/adapters/openai_agents.py` | Rewrite: 3-agent handoff chain, structured output, output guardrail, RunConfig, dynamic instructions |
| `src/desmet/adapters/_base.py` | No changes (ToolAgentAdapter and _execute_stage unchanged) |
| `src/desmet/adapters/_tools.py` | No changes |
| `src/desmet/adapters/_tracing.py` | No changes |
| `src/desmet/adapters/_validation.py` | No changes |

## Risks

- **CrewAI planning overhead:** `planning=True` adds an LLM call. Combined with 3 agents, token usage will increase. This is an expected trade-off — the evaluation measures efficiency, and this overhead is a real characteristic of CrewAI's orchestration.
- **LangGraph parallel complexity:** The `Send` API makes graph shape dynamic and harder to debug. Mitigated by only triggering parallelism when the planner produces `[PARALLEL]`-marked steps. Safe default: serial execution when no markers found.
- **OpenAI structured output + handoffs incompatibility:** v0.8.3 doesn't support both on the same agent. Worked around by running the planner separately and feeding output to the executor.
- **CrewAI guardrail on Task:** Must verify during implementation that `Task(guardrail=...)` is supported in v1.6.1. The `guardrail` callable signature should be `(TaskOutput) -> TaskOutput | bool | tuple[bool, str]`. **Concrete fallback if unsupported:** the reviewer task's `expected_output` includes "Call check_completion to verify all artefacts", and the adapter calls `validate_workspace()` after `crew.kickoff()` returns. If validation fails, re-run the crew with the reviewer's output + failure context appended to the executor task description. This fallback preserves the multi-agent structure while moving validation external to the crew — still more idiomatic than the current single-agent design.
- **LangGraph plan parsing:** The `[PARALLEL]` marker approach relies on the planner LLM following the instruction. If the planner doesn't produce markers, execution defaults to serial — this is safe but means parallelism may not trigger consistently. This is itself an observable orchestration characteristic: can the framework reliably get structured output from its planning step?
