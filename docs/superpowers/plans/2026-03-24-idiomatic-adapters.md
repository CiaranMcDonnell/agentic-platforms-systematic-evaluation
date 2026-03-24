# Idiomatic Adapter Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the LangGraph, CrewAI, and OpenAI Agents SDK adapters to use each framework's native multi-agent orchestration patterns, making architectural differences visible in evaluation scoring.

**Architecture:** Each adapter keeps the same `_run_agent` contract but internally decomposes work across 3 agents (planner, executor, reviewer) using framework-native mechanisms: LangGraph subgraphs + Send API, CrewAI sequential crews with planning mode, OpenAI handoffs + structured output + guardrails. Shared prompts, tools, and validation are unchanged.

**Tech Stack:** LangGraph 1.1.2, CrewAI 1.6.1, openai-agents 0.8.3, Python 3.12, uv, pytest

**Spec:** `docs/superpowers/specs/2026-03-24-idiomatic-adapters-design.md`

---

### Task 1: Add Sub-Personas to `_prompts.py`

**Files:**
- Modify: `src/desmet/adapters/_prompts.py:97-147`
- Test: `tests/test_adapter_prompts.py`

- [ ] **Step 1: Write failing tests for sub-personas**

Add to `tests/test_adapter_prompts.py`:

```python
from desmet.adapters._prompts import get_sub_persona


class TestGetSubPersona:
    """get_sub_persona returns correct AgentPersona for planner and reviewer."""

    def test_planner_persona(self):
        persona = get_sub_persona("planner")
        assert isinstance(persona, AgentPersona)
        assert persona.role == "Technical Lead"
        assert "plan" in persona.goal.lower()

    def test_reviewer_persona(self):
        persona = get_sub_persona("reviewer")
        assert isinstance(persona, AgentPersona)
        assert persona.role == "Code Reviewer"
        assert "validate" in persona.goal.lower()

    def test_reviewer_backstory_does_not_mention_check_completion(self):
        persona = get_sub_persona("reviewer")
        assert "check_completion" not in persona.backstory

    def test_unknown_sub_persona_raises_key_error(self):
        with pytest.raises(KeyError):
            get_sub_persona("nonexistent")

    def test_sub_persona_is_frozen(self):
        persona = get_sub_persona("planner")
        with pytest.raises(AttributeError):
            persona.role = "Hacker"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_adapter_prompts.py::TestGetSubPersona -v`
Expected: FAIL with `ImportError` (get_sub_persona doesn't exist yet)

- [ ] **Step 3: Implement sub-personas**

In `src/desmet/adapters/_prompts.py`, after the `_STAGE_PERSONAS` dict (after line 137), add:

```python
_SUB_PERSONAS: dict[str, AgentPersona] = {
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
    """Return the :class:`AgentPersona` for sub-persona *name*.

    Valid names: ``planner``, ``reviewer``.
    Raises :exc:`KeyError` if *name* is not recognised.
    """
    return _SUB_PERSONAS[name]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_adapter_prompts.py -v`
Expected: All tests PASS (both existing and new)

- [ ] **Step 5: Commit**

```bash
git add src/desmet/adapters/_prompts.py tests/test_adapter_prompts.py
git commit -m "feat(prompts): add planner and reviewer sub-personas"
```

---

### Task 2: Rewrite LangGraph Adapter — Subgraph Architecture

**Files:**
- Rewrite: `src/desmet/adapters/langgraph.py`
- Test: `tests/test_langgraph_adapter.py` (new)

This is the largest adapter rewrite. The current flat graph (planner_node → executor_node ⇄ tool_node → validator_node) becomes three compiled subgraphs with private state, connected by a parent graph with checkpointing.

**New imports needed** at the top of `langgraph.py`:
```python
from langgraph.checkpoint.memory import InMemorySaver
from desmet.adapters._prompts import get_sub_persona
```

- [ ] **Step 1: Write failing tests for the new graph structure**

Create `tests/test_langgraph_adapter.py`:

```python
"""Tests for the LangGraph idiomatic adapter (subgraph architecture)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestLangGraphAdapterStructure:
    """Verify the adapter exposes the correct structure and metadata."""

    def test_imports(self):
        from desmet.adapters.langgraph import LangGraphAdapter
        adapter = LangGraphAdapter()
        assert adapter.TOOL_FORMAT is not None

    def test_observability_reports_checkpointing(self):
        from desmet.adapters.langgraph import LangGraphAdapter
        adapter = LangGraphAdapter()
        info = adapter.get_observability_info()
        assert info["has_checkpointing"] is True
        assert info["has_state_inspection"] is True

    def test_failure_handling_reports_auto_recovery(self):
        from desmet.adapters.langgraph import LangGraphAdapter
        adapter = LangGraphAdapter()
        info = adapter.get_failure_handling_info()
        assert info["has_auto_recovery"] is True


class TestBuildGraph:
    """Verify graph construction produces the expected node structure."""

    def test_graph_has_three_subgraph_nodes(self):
        from desmet.adapters.langgraph import LangGraphAdapter
        adapter = LangGraphAdapter()
        mock_llm = MagicMock()
        # bind_tools must return another mock that is callable
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        adapter._llm = mock_llm
        adapter._model_name = "test-model"
        graph = adapter._build_graph(mock_llm, [])
        node_names = set(graph.nodes.keys())
        assert "planner" in node_names
        assert "executor" in node_names
        assert "reviewer" in node_names


class TestPlanParsing:
    """Verify the plan parsing heuristic for parallel detection."""

    def test_serial_plan_returns_no_parallel_groups(self):
        from desmet.adapters.langgraph import parse_plan
        steps = parse_plan("1. Create models\n2. Create views\n3. Create templates")
        assert all(not s.get("parallel") for s in steps)

    def test_parallel_markers_detected(self):
        from desmet.adapters.langgraph import parse_plan
        plan = "1. [PARALLEL] Create models.py\n2. [PARALLEL] Create views.py\n3. Run tests"
        steps = parse_plan(plan)
        assert steps[0]["parallel"] is True
        assert steps[1]["parallel"] is True
        assert steps[2]["parallel"] is False

    def test_empty_plan_returns_empty_list(self):
        from desmet.adapters.langgraph import parse_plan
        assert parse_plan("") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_langgraph_adapter.py -v`
Expected: FAIL (new structure doesn't exist yet)

- [ ] **Step 3: Implement plan parsing helper**

At the top of `src/desmet/adapters/langgraph.py` (after imports), add the plan parser. This is a pure function, easy to test in isolation:

```python
import re

def parse_plan(plan_text: str) -> list[dict]:
    """Parse a numbered plan into steps, detecting [PARALLEL] markers.

    Returns a list of dicts: [{"text": str, "parallel": bool}, ...]
    """
    if not plan_text.strip():
        return []
    steps = []
    for line in plan_text.strip().split("\n"):
        line = line.strip()
        # Match numbered steps: "1. ...", "1) ...", "- ..."
        m = re.match(r"^(?:\d+[.)]\s*|-\s*)(.*)", line)
        if not m:
            continue
        text = m.group(1).strip()
        parallel = "[PARALLEL]" in text
        text = text.replace("[PARALLEL]", "").strip()
        steps.append({"text": text, "parallel": parallel})
    return steps
```

- [ ] **Step 4: Run plan parsing tests to verify they pass**

Run: `uv run pytest tests/test_langgraph_adapter.py::TestPlanParsing -v`
Expected: PASS

- [ ] **Step 5: Implement the subgraph state schemas**

In `src/desmet/adapters/langgraph.py`, replace the existing `AgentState` with the new schemas:

```python
class ParentState(TypedDict):
    """Shared state across all subgraphs."""
    prompt: str  # stage prompt, passed to planner and executor
    system_msg: str  # system message from story context
    plan: str
    stage: str
    workspace: str
    retry_count: int
    validator_passed: bool
    iterations: int  # accumulated LLM call count for budget tracking


class SubgraphState(TypedDict):
    """Private state for planner, executor, and reviewer subgraphs."""
    messages: Annotated[list[BaseMessage], add_messages]
```

- [ ] **Step 6: Implement the planner subgraph builder**

```python
def _build_planner_subgraph(self, llm) -> CompiledGraph:
    """Build and compile the planner subgraph."""
    from desmet.adapters._prompts import get_sub_persona

    planner_persona = get_sub_persona("planner")

    def plan_node(state: SubgraphState) -> dict:
        sys = SystemMessage(content=(
            f"{planner_persona.backstory}\n\n"
            "Format your plan as a numbered list. Mark independent steps "
            "with [PARALLEL] if they can be executed concurrently."
        ))
        response = llm.invoke([sys] + state["messages"])
        return {"messages": [response]}

    builder = StateGraph(SubgraphState)
    builder.add_node("plan", plan_node)
    builder.add_edge(START, "plan")
    builder.add_edge("plan", END)
    return builder.compile()
```

- [ ] **Step 7: Implement the executor subgraph builder**

```python
def _build_executor_subgraph(self, llm, tools: list) -> CompiledGraph:
    """Build and compile the executor subgraph with tool loop."""
    llm_with_tools = llm.bind_tools(tools)

    def executor_node(state: SubgraphState) -> dict:
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    def route_executor(state: SubgraphState) -> str:
        last = state["messages"][-1] if state["messages"] else None
        if last and getattr(last, "tool_calls", None):
            return "tool_node"
        return END

    builder = StateGraph(SubgraphState)
    builder.add_node("executor_node", executor_node)
    builder.add_node("tool_node", ToolNode(tools, handle_tool_errors=True))
    builder.add_edge(START, "executor_node")
    builder.add_conditional_edges("executor_node", route_executor)
    builder.add_edge("tool_node", "executor_node")
    return builder.compile()
```

- [ ] **Step 8: Implement the reviewer subgraph builder**

```python
def _build_reviewer_subgraph(self, llm, tools: list) -> CompiledGraph:
    """Build and compile the reviewer subgraph."""
    from desmet.adapters._prompts import get_sub_persona

    reviewer_persona = get_sub_persona("reviewer")
    llm_with_tools = llm.bind_tools(tools)

    def review_node(state: SubgraphState) -> dict:
        sys = SystemMessage(content=reviewer_persona.backstory)
        response = llm_with_tools.invoke([sys] + state["messages"])
        return {"messages": [response]}

    builder = StateGraph(SubgraphState)
    builder.add_node("review", review_node)
    builder.add_edge(START, "review")
    builder.add_edge("review", END)
    return builder.compile()
```

- [ ] **Step 9: Implement the parent graph builder**

Replace the existing `_build_graph` method:

```python
def _build_graph(self, llm, tools: list):
    """Build and compile the parent graph with subgraphs."""
    from desmet.adapters._prompts import get_stage_persona
    from langgraph.checkpoint.memory import InMemorySaver

    planner_sub = self._build_planner_subgraph(llm)
    executor_sub = self._build_executor_subgraph(llm, tools)
    reviewer_sub = self._build_reviewer_subgraph(llm, tools)

    def planner_wrapper(state: ParentState) -> dict:
        """Invoke planner subgraph, extract plan from response."""
        result = planner_sub.invoke({
            "messages": [HumanMessage(content=state["prompt"])],
        })
        plan_text = result["messages"][-1].content if result["messages"] else ""
        return {"plan": plan_text, "iterations": state.get("iterations", 0) + 1}

    def executor_wrapper(state: ParentState) -> dict:
        """Invoke executor subgraph with plan context."""
        persona = get_stage_persona(state["stage"])
        sys_content = (
            f"{persona.backstory}\n\n"
            f"## Plan\n{state['plan']}\n\n"
            f"Working directory: {state['workspace']}"
        )
        result = executor_sub.invoke({
            "messages": [
                SystemMessage(content=sys_content),
                HumanMessage(content=state["prompt"]),
            ],
        })
        new_iters = len([m for m in result["messages"]
                         if hasattr(m, "response_metadata")])
        return {"iterations": state.get("iterations", 0) + max(new_iters, 1)}

    def reviewer_wrapper(state: ParentState) -> dict:
        """Invoke reviewer subgraph, then validate deterministically."""
        result = reviewer_sub.invoke({
            "messages": [HumanMessage(content=(
                f"Review the workspace at {state['workspace']} for stage "
                f"'{state['stage']}'. Verify all required artefacts are present."
            ))],
        })
        passed = validate_workspace(state["stage"], state["workspace"])
        return {
            "validator_passed": passed,
            "retry_count": state["retry_count"] + 1,
            "iterations": state.get("iterations", 0) + 1,
        }

    def route_after_review(state: ParentState) -> str:
        if state["validator_passed"]:
            return END
        if state["retry_count"] >= MAX_RETRIES:
            return END
        return "executor"

    builder = StateGraph(ParentState)
    builder.add_node("planner", planner_wrapper)
    builder.add_node("executor", executor_wrapper)
    builder.add_node("reviewer", reviewer_wrapper)
    builder.add_edge(START, "planner")
    builder.add_edge("planner", "executor")
    builder.add_edge("executor", "reviewer")
    builder.add_conditional_edges("reviewer", route_after_review)
    return builder.compile(checkpointer=InMemorySaver())
```

- [ ] **Step 10: Rewrite `_run_agent` to use the new graph**

Replace the existing `_run_agent` method entirely:

```python
async def _run_agent(
    self,
    stage_name: str,
    prompt: str,
    system_msg: str | None,
    tools: list,
    trace,
    context: StageContext,
) -> tuple[int, bool]:
    """Stream a compiled parent graph with planner/executor/reviewer subgraphs."""
    self._last_langsmith_run_id = None
    graph = self._build_graph(self._llm, tools)

    run_id = uuid.uuid4()
    thread_id = str(uuid.uuid4())
    lf_cb = get_langchain_callback()
    config: RunnableConfig = {
        "run_id": run_id,
        "run_name": f"desmet-langgraph-{stage_name}",
        "configurable": {"thread_id": thread_id},
    }
    if lf_cb is not None:
        config["callbacks"] = [lf_cb]

    initial_state: ParentState = {
        "prompt": prompt,
        "system_msg": system_msg or "",
        "plan": "",
        "stage": stage_name,
        "workspace": str(context.workspace),
        "retry_count": 0,
        "validator_passed": False,
        "iterations": 0,
    }

    record_message(trace, "user", prompt)

    iteration = 0
    tool_call_count = 0
    hit_limit = False
    final_state: dict[str, Any] = {}
    t0 = time.monotonic()
    cb = context.progress_callback

    async for chunk in graph.astream(initial_state, config=config, stream_mode="updates"):
        for node_name, node_update in chunk.items():
            if not node_update or not isinstance(node_update, dict):
                continue

            final_state.update(node_update)

            # Progress callbacks per node
            if cb and node_name in ("planner", "executor", "reviewer"):
                elapsed = time.monotonic() - t0
                cb(f"    [{node_name}]  ({elapsed:.0f}s)")

            # Extract iteration count from state
            iteration = final_state.get("iterations", iteration)

            # Record messages from subgraph results if present
            # (subgraph wrappers don't propagate messages to parent,
            #  but we record node transitions for trace visibility)
            record_node_event(trace, node_name, **{
                k: v for k, v in node_update.items()
                if k in ("plan", "validator_passed", "retry_count")
            })

            # Validator outcome logging
            if node_name == "reviewer":
                passed = node_update.get("validator_passed", False)
                retry = node_update.get("retry_count", 0)
                if cb:
                    if passed:
                        cb("    reviewer: PASSED")
                    else:
                        from desmet.adapters._tools import _check_completion
                        _, hint = _check_completion(context.workspace, stage_name)
                        cb(f"    reviewer: FAILED (attempt {retry}/{MAX_RETRIES}) — {hint}")

        if iteration >= context.max_iterations:
            hit_limit = True
            break

    trace.total_iterations = iteration
    finish_trace(trace, final_state=final_state)
    self._last_langsmith_run_id = str(run_id) if self._langsmith_enabled() else None
    return iteration, hit_limit
```

Note: Token tracking happens inside the subgraph wrapper functions. Each wrapper should call `record_usage(trace, ...)` after invoking its subgraph, extracting usage from the response metadata of the last message in the subgraph result. Update the wrapper functions from Step 9 to include:

```python
# Inside planner_wrapper, after getting result:
last_msg = result["messages"][-1] if result["messages"] else None
if last_msg:
    resp_meta = getattr(last_msg, "response_metadata", {})
    usage = resp_meta.get("token_usage") or resp_meta.get("usage") or {}
    if isinstance(usage, dict) and usage.get("total_tokens", 0) > 0:
        record_usage(
            trace,
            input_tokens=usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0) or usage.get("output_tokens", 0),
            model=self._model_name,
        )
```

Apply the same pattern to `executor_wrapper` (iterating all messages with `response_metadata`) and `reviewer_wrapper`.

Also preserve the existing `_execute_stage` override for LangSmith run ID attachment:

```python
async def _execute_stage(self, stage_name, prompt_fn, result_cls, context):
    result = await super()._execute_stage(stage_name, prompt_fn, result_cls, context)
    result.langsmith_run_id = self._last_langsmith_run_id
    return result
```

- [ ] **Step 11: Update metadata methods**

```python
def get_observability_info(self) -> dict[str, Any]:
    return {
        "has_tracing": True,
        "has_step_through": True,
        "has_replay": True,
        "has_state_inspection": True,
        "has_memory_inspection": False,
        "trace_format": "LangSmith",
        "notes": (
            "Subgraph architecture: planner/executor/reviewer with private state. "
            "InMemorySaver checkpointing enables replay and state inspection."
        ),
    }

def get_failure_handling_info(self) -> dict[str, Any]:
    return {
        "has_checkpointing": True,
        "has_auto_recovery": True,
        "has_graceful_degradation": True,
        "supports_human_handoff": False,
        "is_idempotent": True,
        "notes": (
            "Reviewer subgraph validates then routes retry via parent graph. "
            "ToolNode handle_tool_errors=True enables LLM self-correction."
        ),
    }
```

- [ ] **Step 12: Run all tests**

Run: `uv run pytest tests/test_langgraph_adapter.py -v`
Expected: All PASS

- [ ] **Step 13: Commit**

```bash
git add src/desmet/adapters/langgraph.py tests/test_langgraph_adapter.py
git commit -m "feat(langgraph): rewrite adapter with subgraphs, checkpointing, and plan parsing"
```

---

### Task 3: Rewrite CrewAI Adapter — Multi-Agent Sequential Crew

**Files:**
- Rewrite: `src/desmet/adapters/crewai.py`
- Test: `tests/test_crewai_adapter.py` (new)

The current single-agent crew becomes a 3-agent sequential crew with `planning=True` and task context chaining.

**New imports needed** at the top of `crewai.py`:
```python
from desmet.adapters._prompts import get_sub_persona
from desmet.adapters._validation import validate_workspace
```
(Add `get_sub_persona` to the existing `from desmet.adapters._prompts import ...` line.)

- [ ] **Step 1: Write failing tests for the new crew structure**

Create `tests/test_crewai_adapter.py`:

```python
"""Tests for the CrewAI idiomatic adapter (multi-agent crew)."""
from __future__ import annotations

from unittest.mock import MagicMock


class TestCrewAIAdapterStructure:
    """Verify the adapter exposes the correct structure and metadata."""

    def test_imports(self):
        from desmet.adapters.crewai import CrewAIAdapter
        adapter = CrewAIAdapter()
        assert adapter.TOOL_FORMAT is not None

    def test_observability_reports_auto_recovery(self):
        from desmet.adapters.crewai import CrewAIAdapter
        adapter = CrewAIAdapter()
        info = adapter.get_failure_handling_info()
        assert info["has_auto_recovery"] is True

    def test_observability_notes_mention_multi_agent(self):
        from desmet.adapters.crewai import CrewAIAdapter
        adapter = CrewAIAdapter()
        info = adapter.get_observability_info()
        assert "multi-agent" in info.get("notes", "").lower() or "crew" in info.get("notes", "").lower()


class TestIterationBudget:
    """Verify iteration budget allocation is proportional."""

    def test_budget_allocation_default_50(self):
        from desmet.adapters.crewai import _compute_iter_budget
        planner, executor, reviewer = _compute_iter_budget(50)
        assert planner == 10
        assert executor == 30
        assert reviewer == 10

    def test_budget_allocation_custom_30(self):
        from desmet.adapters.crewai import _compute_iter_budget
        planner, executor, reviewer = _compute_iter_budget(30)
        assert planner + executor + reviewer <= 30
        assert executor > planner
        assert executor > reviewer

    def test_budget_allocation_minimum(self):
        from desmet.adapters.crewai import _compute_iter_budget
        planner, executor, reviewer = _compute_iter_budget(10)
        assert planner >= 1
        assert executor >= 1
        assert reviewer >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_crewai_adapter.py -v`
Expected: FAIL

- [ ] **Step 3: Implement the iteration budget helper**

At the top of `src/desmet/adapters/crewai.py` (after imports), add:

```python
def _compute_iter_budget(max_iterations: int) -> tuple[int, int, int]:
    """Compute per-agent max_iter from total budget (20%/60%/20%).

    Returns (planner, executor, reviewer).
    """
    planner = max(1, int(max_iterations * 0.2))
    reviewer = max(1, int(max_iterations * 0.2))
    executor = max(1, max_iterations - planner - reviewer)
    return planner, executor, reviewer
```

- [ ] **Step 4: Run budget tests to verify they pass**

Run: `uv run pytest tests/test_crewai_adapter.py::TestIterationBudget -v`
Expected: PASS

- [ ] **Step 5: Rewrite `_run_agent` with 3-agent crew**

Replace the existing `_run_agent` method. Key changes:

```python
async def _run_agent(
    self,
    stage_name: str,
    prompt: str,
    system_msg: str | None,
    tools: list,
    trace: AgentTrace,
    context: StageContext,
) -> tuple[int, bool]:
    """Run a 3-agent CrewAI crew. Returns (iterations, hit_limit)."""
    import asyncio
    from crewai import Agent, Crew, Process, Task

    planner_persona = get_sub_persona("planner")
    executor_persona = get_stage_persona(stage_name)
    reviewer_persona = get_sub_persona("reviewer")

    llm = self._create_llm(context)
    cfg = get_llm_config(
        model=context.model or self.config.get("model"),
        temperature=context.temperature,
    )
    model_name = cfg.model

    planner_budget, executor_budget, reviewer_budget = _compute_iter_budget(
        context.max_iterations
    )

    # --- Agents ---
    planner_agent = Agent(
        role=planner_persona.role,
        goal=planner_persona.goal,
        backstory=planner_persona.backstory + (f"\n\n{system_msg}" if system_msg else ""),
        verbose=False,
        allow_delegation=False,
        llm=llm,
        tools=tools,
        max_iter=planner_budget,
    )

    executor_agent = Agent(
        role=executor_persona.role,
        goal=executor_persona.goal,
        backstory=executor_persona.backstory + (f"\n\n{system_msg}" if system_msg else ""),
        verbose=False,
        allow_delegation=False,
        llm=llm,
        tools=tools,
        max_iter=executor_budget,
    )

    reviewer_agent = Agent(
        role=reviewer_persona.role,
        goal=reviewer_persona.goal,
        backstory=reviewer_persona.backstory,
        verbose=False,
        allow_delegation=False,
        llm=llm,
        tools=tools,
        max_iter=reviewer_budget,
    )

    # --- Tasks ---
    analyse_task = Task(
        description=(
            f"Analyse the following task and produce a numbered implementation plan.\n\n"
            f"{prompt}"
        ),
        expected_output="A numbered implementation plan with files to create/modify",
        agent=planner_agent,
    )

    implement_task = Task(
        description=prompt,
        expected_output=STAGE_EXPECTED_OUTPUTS.get(
            stage_name, "Complete the task as described."
        ),
        agent=executor_agent,
        context=[analyse_task],
    )

    review_task = Task(
        description=(
            f"Review the implementation in the workspace for the '{stage_name}' stage. "
            f"Verify all required artefacts are present and correct."
        ),
        expected_output="Validation report confirming all artefacts are present and correct",
        agent=reviewer_agent,
        context=[analyse_task, implement_task],
    )

    # --- Crew ---
    step_cb, task_cb, counter = self._create_trace_callbacks(
        trace, progress_callback=context.progress_callback,
        max_iterations=context.max_iterations,
    )

    crew = Crew(
        agents=[planner_agent, executor_agent, reviewer_agent],
        tasks=[analyse_task, implement_task, review_task],
        process=Process.sequential,
        planning=True,
        planning_llm=llm,
        verbose=False,
        step_callback=step_cb,
        task_callback=task_cb,
        max_iter=context.max_iterations,
    )

    record_message(trace, "user", prompt)
    self._start_llm_collection()

    result = await asyncio.to_thread(crew.kickoff)
    record_message(trace, "assistant", str(result))

    # --- Post-run: token tracking ---
    # The event bus handler collects LLM calls from ALL agents in the crew.
    # This code is identical to the current adapter — it works without changes
    # because the event bus is agent-agnostic.
    llm_calls = self._stop_llm_collection()

    if llm_calls:
        for call in llm_calls:
            record_usage(
                trace,
                input_tokens=call.get("input_tokens", 0),
                output_tokens=call.get("output_tokens", 0),
                model=call.get("model") or model_name,
            )
        from desmet.observability import get_langfuse
        lf = get_langfuse()
        if lf is not None:
            for i, call in enumerate(llm_calls):
                with lf.start_as_current_observation(
                    name=f"llm-{call.get('call_type', 'call')}-{i + 1}",
                    as_type="generation",
                    model=call.get("model"),
                    usage_details={
                        "input": call.get("input_tokens", 0),
                        "output": call.get("output_tokens", 0),
                    },
                    metadata={"agent_role": call.get("agent_role")},
                ):
                    pass
    else:
        usage = getattr(result, "token_usage", None)
        if usage is not None:
            record_usage(
                trace,
                input_tokens=getattr(usage, "prompt_tokens", 0) or getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "completion_tokens", 0) or getattr(usage, "output_tokens", 0) or 0,
                model=model_name,
            )

    # --- Post-run: deterministic validation ---
    passed = validate_workspace(stage_name, str(context.workspace))
    if not passed and context.progress_callback:
        from desmet.adapters._tools import _check_completion
        _, hint = _check_completion(context.workspace, stage_name)
        context.progress_callback(f"    validator: FAILED — {hint}")

    iterations = counter[0]
    hit_limit = iterations >= context.max_iterations
    trace.total_iterations = iterations
    finish_trace(trace)
    return iterations, hit_limit
```

Note: keep the existing `_create_llm`, `_register_llm_event_handler`, `_start_llm_collection`, `_stop_llm_collection`, `_create_trace_callbacks` methods unchanged. They work with the multi-agent crew without modification (the event bus collects from all agents, callbacks fire for all steps).

- [ ] **Step 6: Verify CrewAI `Task(guardrail=...)` support**

Before implementing the guardrail, check if the parameter exists:

Run: `uv run python -c "from crewai import Task; import inspect; print('guardrail' in inspect.signature(Task).parameters)"`

If `True`: add `guardrail=lambda output: validate_workspace(stage_name, str(context.workspace))` to `review_task`.
If `False`: skip — the external `validate_workspace()` call after `crew.kickoff()` serves as the fallback (already implemented in step 5).

- [ ] **Step 7: Update metadata methods**

```python
def get_observability_info(self) -> dict[str, Any]:
    return {
        "has_tracing": True,
        "has_step_through": False,
        "has_replay": False,
        "has_state_inspection": True,
        "has_memory_inspection": True,
        "trace_format": "Custom logs",
        "notes": (
            "Multi-agent sequential crew (planner/executor/reviewer) with "
            "planning=True. Per-agent step callbacks + event bus for LLM call tracing."
        ),
    }

def get_failure_handling_info(self) -> dict[str, Any]:
    return {
        "has_checkpointing": False,
        "has_auto_recovery": True,
        "has_graceful_degradation": True,
        "supports_human_handoff": True,
        "is_idempotent": False,
        "notes": (
            "Post-crew validate_workspace() gate. Per-agent max_iter limits. "
            "Crew planning mode aligns agents before execution."
        ),
    }
```

- [ ] **Step 8: Run all tests**

Run: `uv run pytest tests/test_crewai_adapter.py -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add src/desmet/adapters/crewai.py tests/test_crewai_adapter.py
git commit -m "feat(crewai): rewrite adapter with 3-agent crew and planning mode"
```

---

### Task 4: Rewrite OpenAI Agents SDK Adapter — Handoffs + Guardrails

**Files:**
- Rewrite: `src/desmet/adapters/openai_agents.py`
- Test: `tests/test_openai_agents_adapter.py` (new)

The current single-agent `Runner.run()` with external retry becomes a 3-agent handoff chain with structured output and output guardrails.

**New imports needed** at the top of `openai_agents.py`:
```python
from dataclasses import dataclass
from pydantic import BaseModel
from agents import RunConfig, output_guardrail
from agents.guardrail import GuardrailFunctionOutput
from agents.exceptions import OutputGuardrailTripwireTriggered
from desmet.adapters._prompts import get_sub_persona
```
(Add `get_sub_persona` to the existing `from desmet.adapters._prompts import ...` line. Add the new `agents` imports alongside existing ones.)

- [ ] **Step 1: Write failing tests for the new structure**

Create `tests/test_openai_agents_adapter.py`:

```python
"""Tests for the OpenAI Agents SDK idiomatic adapter (handoff chain)."""
from __future__ import annotations

from pydantic import BaseModel


class TestImplementationPlan:
    """Verify the ImplementationPlan model."""

    def test_creates_valid_plan(self):
        from desmet.adapters.openai_agents import ImplementationPlan
        plan = ImplementationPlan(
            steps=["Create models", "Create views"],
            files_to_create=["models.py", "views.py"],
            files_to_modify=[],
        )
        assert len(plan.steps) == 2
        assert plan.files_to_create == ["models.py", "views.py"]
        assert plan.files_to_modify == []

    def test_plan_requires_steps(self):
        from desmet.adapters.openai_agents import ImplementationPlan
        import pytest
        with pytest.raises(Exception):
            ImplementationPlan(files_to_create=[], files_to_modify=[])


class TestOpenAIRunContext:
    """Verify the adapter-local run context."""

    def test_creates_with_none_plan(self):
        from desmet.adapters.openai_agents import OpenAIRunContext
        ctx = OpenAIRunContext(stage_context=None, plan=None)
        assert ctx.plan is None

    def test_plan_can_be_set(self):
        from desmet.adapters.openai_agents import OpenAIRunContext, ImplementationPlan
        ctx = OpenAIRunContext(stage_context=None, plan=None)
        ctx.plan = ImplementationPlan(
            steps=["step 1"], files_to_create=[], files_to_modify=[]
        )
        assert ctx.plan is not None
        assert len(ctx.plan.steps) == 1


class TestOpenAIAdapterStructure:
    """Verify the adapter exposes the correct metadata."""

    def test_imports(self):
        from desmet.adapters.openai_agents import OpenAIAgentsAdapter
        adapter = OpenAIAgentsAdapter()
        assert adapter.TOOL_FORMAT is not None

    def test_observability_reports_state_inspection(self):
        from desmet.adapters.openai_agents import OpenAIAgentsAdapter
        adapter = OpenAIAgentsAdapter()
        info = adapter.get_observability_info()
        assert info["has_tracing"] is True

    def test_failure_handling_mentions_guardrail(self):
        from desmet.adapters.openai_agents import OpenAIAgentsAdapter
        adapter = OpenAIAgentsAdapter()
        info = adapter.get_failure_handling_info()
        assert "guardrail" in info.get("notes", "").lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_openai_agents_adapter.py -v`
Expected: FAIL

- [ ] **Step 3: Implement ImplementationPlan and OpenAIRunContext**

At the top of `src/desmet/adapters/openai_agents.py` (after imports), add:

```python
from dataclasses import dataclass
from pydantic import BaseModel


class ImplementationPlan(BaseModel):
    """Structured output from the planner agent."""
    steps: list[str]
    files_to_create: list[str]
    files_to_modify: list[str]


@dataclass
class OpenAIRunContext:
    """Adapter-local context passed through RunContextWrapper."""
    stage_context: StageContext | None
    plan: ImplementationPlan | None = None
```

- [ ] **Step 4: Run model tests to verify they pass**

Run: `uv run pytest tests/test_openai_agents_adapter.py::TestImplementationPlan tests/test_openai_agents_adapter.py::TestOpenAIRunContext -v`
Expected: PASS

- [ ] **Step 5: Implement the output guardrail**

```python
from agents import output_guardrail
from agents.guardrail import GuardrailFunctionOutput


def _make_workspace_guardrail(stage_name: str, workspace: str):
    """Create an output guardrail that validates the workspace."""

    @output_guardrail
    async def workspace_guardrail(ctx, agent, output):
        passed = validate_workspace(stage_name, workspace)
        return GuardrailFunctionOutput(
            output_info={"passed": passed, "stage": stage_name},
            tripwire_triggered=not passed,
        )

    return workspace_guardrail
```

- [ ] **Step 6: Rewrite `_run_agent` with handoff chain**

Replace the existing `_run_agent`. The flow is:
1. Run planner agent with `output_type=ImplementationPlan`, `max_turns=3`
2. Store plan in `OpenAIRunContext`
3. Create executor agent with `handoffs=[reviewer_agent]` and dynamic instructions
4. Create reviewer agent with `output_guardrails=[workspace_guardrail]`
5. Run executor (which will handoff to reviewer)
6. On `OutputGuardrailTripwireTriggered`: retry with conversation carry-forward

```python
async def _run_agent(
    self,
    stage_name: str,
    prompt: str,
    system_msg: str | None,
    tools: list,
    trace: AgentTrace,
    context: StageContext,
) -> tuple[int, bool]:
    from agents import Agent, Runner, ModelSettings
    from agents.exceptions import OutputGuardrailTripwireTriggered

    planner_persona = get_sub_persona("planner")
    executor_persona = get_stage_persona(stage_name)
    reviewer_persona = get_sub_persona("reviewer")

    run_ctx = OpenAIRunContext(stage_context=context)
    total_iterations = 0
    tool_call_count = 0
    t0 = time.monotonic()
    cb = context.progress_callback

    record_message(trace, "user", prompt)

    # --- Step 1: Planner ---
    planner = Agent(
        name=f"desmet-{stage_name}-planner",
        instructions=planner_persona.backstory + (f"\n\n{system_msg}" if system_msg else ""),
        model=self._model,
        output_type=ImplementationPlan,
        model_settings=ModelSettings(temperature=context.temperature),
    )

    from agents import RunConfig
    run_config = RunConfig(
        workflow_name=f"desmet-{stage_name}",
        trace_id=f"desmet-{stage_name}-{id(context)}",
    )

    planner_result = await Runner.run(planner, input=prompt, max_turns=3, run_config=run_config)
    planner_iters, tool_call_count = self._extract_trace(
        trace, planner_result, cb=cb, t0=t0,
        tool_call_count=tool_call_count, model=self._model_name,
    )
    total_iterations += planner_iters

    # Extract structured plan
    if isinstance(planner_result.final_output, ImplementationPlan):
        run_ctx.plan = planner_result.final_output
    else:
        # Fallback: parse as text
        run_ctx.plan = ImplementationPlan(
            steps=[str(planner_result.final_output)],
            files_to_create=[], files_to_modify=[],
        )

    if cb:
        cb(f"    planner: {len(run_ctx.plan.steps)} steps planned")

    # --- Step 2: Executor + Reviewer via handoff ---
    guardrail = _make_workspace_guardrail(stage_name, str(context.workspace))

    reviewer_agent = Agent(
        name=f"desmet-{stage_name}-reviewer",
        instructions=reviewer_persona.backstory,
        model=self._model,
        tools=tools,
        output_guardrails=[guardrail],
        model_settings=ModelSettings(temperature=context.temperature),
    )

    # Dynamic instructions callable — injects the plan at runtime,
    # so instructions update correctly on retry
    def make_executor_instructions(persona_backstory, sys_msg, run_context):
        async def executor_instructions(ctx, agent):
            plan = run_context.plan
            if plan:
                plan_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(plan.steps))
                files = ", ".join(plan.files_to_create + plan.files_to_modify)
                plan_section = f"## Implementation Plan\n{plan_text}\n\n## Files: {files}\n\n"
            else:
                plan_section = ""
            return f"{persona_backstory}\n\n{plan_section}{sys_msg or ''}"
        return executor_instructions

    executor_agent = Agent(
        name=f"desmet-{stage_name}-executor",
        instructions=make_executor_instructions(
            executor_persona.backstory, system_msg, run_ctx,
        ),
        model=self._model,
        tools=tools,
        handoffs=[reviewer_agent],
        model_settings=ModelSettings(temperature=context.temperature),
    )

    max_turns = (context.max_iterations - 3) // MAX_RETRIES
    hit_limit = False
    result = None

    for attempt in range(MAX_RETRIES):
        try:
            if result is None:
                input_msg = prompt
            else:
                if cb:
                    from desmet.adapters._tools import _check_completion
                    _, hint = _check_completion(context.workspace, stage_name)
                    elapsed = time.monotonic() - t0
                    cb(f"    reviewer: FAILED (attempt {attempt}/{MAX_RETRIES}) — {hint}  ({elapsed:.0f}s)")
                input_msg = result.to_input_list() + [{
                    "role": "user",
                    "content": f"Validation failed (attempt {attempt}/{MAX_RETRIES}). Fix issues.",
                }]

            result = await Runner.run(executor_agent, input=input_msg, max_turns=max_turns, run_config=run_config)

            iters, tool_call_count = self._extract_trace(
                trace, result, cb=cb, t0=t0,
                tool_call_count=tool_call_count, model=self._model_name,
            )
            total_iterations += iters

            if total_iterations >= context.max_iterations:
                hit_limit = True
                break

            # If we got here without guardrail tripping, validation passed
            if cb:
                cb("    reviewer: PASSED")
            break

        except OutputGuardrailTripwireTriggered:
            # Guardrail tripped — retry
            total_iterations += 1  # count the failed reviewer turn
            if total_iterations >= context.max_iterations:
                hit_limit = True
                break
            continue

    trace.total_iterations = total_iterations
    finish_trace(trace)
    return total_iterations, hit_limit
```

- [ ] **Step 7: Update metadata methods**

```python
def get_observability_info(self) -> dict[str, Any]:
    return {
        "has_tracing": True,
        "has_step_through": False,
        "has_replay": False,
        "has_state_inspection": True,
        "has_memory_inspection": False,
        "trace_format": "RunResult",
        "notes": (
            "Handoff chain: planner (structured output) → executor → reviewer. "
            "RunConfig provides workflow_name and trace_id for Langfuse."
        ),
    }

def get_failure_handling_info(self) -> dict[str, Any]:
    return {
        "has_checkpointing": False,
        "has_auto_recovery": True,
        "has_graceful_degradation": True,
        "supports_human_handoff": False,
        "is_idempotent": True,
        "notes": (
            "Output guardrail on reviewer triggers retry via conversation carry-forward. "
            "Structured planner output prevents malformed plans."
        ),
    }
```

- [ ] **Step 8: Run all tests**

Run: `uv run pytest tests/test_openai_agents_adapter.py -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add src/desmet/adapters/openai_agents.py tests/test_openai_agents_adapter.py
git commit -m "feat(openai): rewrite adapter with handoff chain, structured output, and guardrails"
```

---

### Task 5: Integration Smoke Test

**Files:**
- Test: `tests/test_adapter_interface.py` (existing — verify no regressions)
- Test: `tests/test_adapter_prompts.py` (existing — verify no regressions)

- [ ] **Step 1: Run the full existing test suite**

Run: `uv run pytest tests/ -v --tb=short`
Expected: All existing tests PASS. No regressions from the adapter rewrites.

- [ ] **Step 2: Verify all three adapters can be imported and instantiated**

Run:
```bash
uv run python -c "
from desmet.adapters.langgraph import LangGraphAdapter
from desmet.adapters.crewai import CrewAIAdapter
from desmet.adapters.openai_agents import OpenAIAgentsAdapter
print('LangGraph:', LangGraphAdapter().TOOL_FORMAT)
print('CrewAI:', CrewAIAdapter().TOOL_FORMAT)
print('OpenAI:', OpenAIAgentsAdapter().TOOL_FORMAT)
print('All adapters instantiate OK')
"
```
Expected: All three print their TOOL_FORMAT without errors.

- [ ] **Step 3: Verify adapter registry still works**

Run:
```bash
uv run python -c "
from desmet.adapters.registry import load_platform_info
for pid in ['langgraph', 'crewai', 'openai_agents_sdk']:
    info = load_platform_info(pid)
    print(f'{pid}: {info.name} ({info.category})')
"
```
Expected: All three platforms load successfully.

- [ ] **Step 4: Commit if any test fixes were needed**

```bash
git add -u
git commit -m "fix: resolve integration issues from adapter rewrites"
```

---

### Task 6: Update Existing Tests for New Imports

**Files:**
- Modify: `tests/test_adapter_prompts.py` (add import for `get_sub_persona`)

- [ ] **Step 1: Verify `get_sub_persona` is exported in test imports**

The tests from Task 1 should already be passing. Verify the import works alongside existing imports:

Run: `uv run pytest tests/test_adapter_prompts.py -v`
Expected: All PASS

- [ ] **Step 2: Final commit if needed**

Only commit if there were changes needed. Otherwise skip.
