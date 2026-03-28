"""
LangGraph Platform Adapter — three compiled subgraphs with InMemorySaver checkpointing.

Architecture:
  ParentGraph: planner → executor → reviewer → (retry | END)
  Each stage is a compiled SubGraph with private SubgraphState.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Annotated, Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from desmet.adapters._base import ToolAgentAdapter
from desmet.adapters._planning import ImplementationPlan, build_executor_instructions, format_plan_text, parse_plan_text
from desmet.adapters._prompts import get_stage_persona, get_sub_persona
from desmet.adapters._tools import ToolFormat, split_tools
from desmet.adapters._observation import ObservationCollector
from desmet.adapters._tracing import (
    format_tool_detail,
    record_node_event,
)
from desmet.adapters._validation import validate_workspace
from desmet.adapters.registry import load_platform_info
from desmet.harness.context import StageContext
from desmet.harness.models import PlatformInfo
from desmet.llm_config import Provider
from desmet.llm_config import get_config as get_llm_config
from desmet.observability import get_langchain_callback

MAX_RETRIES = 3


# ── State schemas ──────────────────────────────────────────────────────────


class ParentState(TypedDict):
    """Shared state threaded through the parent graph."""

    prompt: str
    system_msg: str | None
    plan: str
    plan_obj: ImplementationPlan | None
    stage: str
    workspace: str
    retry_count: int
    validator_passed: bool
    iterations: int


class SubgraphState(TypedDict):
    """Private per-subgraph state with message accumulation."""

    messages: Annotated[list[BaseMessage], add_messages]


# ── Plan parser ────────────────────────────────────────────────────────────


def parse_plan(plan_text: str) -> list[dict]:
    """Split a numbered or dashed plan into step dicts.

    Each step is ``{"text": str, "parallel": bool}``.
    Delegates to shared ``parse_plan_text`` for the actual parsing.
    """
    if not plan_text or not plan_text.strip():
        return []
    plan, flags = parse_plan_text(plan_text, include_parallel=True)
    return [{"text": s, "parallel": p} for s, p in zip(plan.steps, flags)]


# ── Adapter ────────────────────────────────────────────────────────────────


class LangGraphAdapter(ToolAgentAdapter):
    """LangGraph adapter using three compiled subgraphs with InMemorySaver checkpointing."""

    TOOL_FORMAT = ToolFormat.LANGCHAIN

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._llm = None
        self._model_name: str | None = None
        self._last_langsmith_run_id: str | None = None

    def _get_model_name(self) -> str | None:
        return self._model_name

    @property
    def platform_info(self) -> PlatformInfo:
        info = load_platform_info("langgraph")
        info.version = self._get_version()
        return info

    def _get_version(self) -> str:
        try:
            import langgraph

            return getattr(langgraph, "__version__", "unknown")
        except ImportError:
            return "not installed"

    async def initialize(self) -> None:
        try:
            cfg = get_llm_config(model=self.config.get("model"))
            self._llm = self._create_chat_model(cfg)
            self._model_name = cfg.model
            self._initialized = True
        except ImportError as e:
            raise RuntimeError(f"Failed to import LangGraph: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize LangGraph: {e}")

    @staticmethod
    def _create_chat_model(cfg):
        if cfg.provider == Provider.ANTHROPIC:
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=cfg.model,
                temperature=cfg.temperature,
                api_key=cfg.api_key,
            )
        from langchain_openai import ChatOpenAI

        kwargs: dict = dict(model=cfg.model, temperature=cfg.temperature, api_key=cfg.api_key)
        if cfg.base_url:
            kwargs["base_url"] = cfg.base_url
        return ChatOpenAI(**kwargs)

    async def shutdown(self) -> None:
        self._llm = None
        self._initialized = False

    async def health_check(self) -> bool:
        if not self._initialized or self._llm is None:
            return False
        try:
            response = await self._llm.ainvoke("Say 'ok'")
            return len(response.content) > 0
        except Exception:
            return False

    # ── Subgraph builders ──────────────────────────────────────────────────

    def _build_planner_subgraph(self, llm) -> Any:
        """Single 'plan' node: Technical Lead persona produces a numbered plan.

        Tries LangChain structured output first (``with_structured_output``),
        falls back to free-text parsing when the provider does not support it.
        The structured ``ImplementationPlan`` (if obtained) is stashed in the
        response metadata so the parent wrapper can extract it.
        """
        planner_persona = get_sub_persona("planner")

        async def plan_node(state: SubgraphState) -> dict:
            from langchain_core.messages import AIMessage

            sys = SystemMessage(
                content=(
                    f"You are a {planner_persona.role}. {planner_persona.backstory}\n\n"
                    "Produce a concise numbered implementation plan. "
                    "List steps, files to create, and files to modify. "
                    "Mark independent steps that can run concurrently with [PARALLEL]."
                )
            )
            messages = [sys] + state["messages"]

            # Try structured output first
            plan: ImplementationPlan | None = None
            try:
                structured_llm = llm.with_structured_output(ImplementationPlan)
                result = await structured_llm.ainvoke(messages)
                if isinstance(result, ImplementationPlan):
                    plan = result
            except Exception:
                pass  # fall back to text parsing

            if plan is not None:
                plan_text_str, _ = format_plan_text(plan)
                all_files = plan.files_to_create + plan.files_to_modify
                if all_files:
                    plan_text_str += "\n\nFiles: " + ", ".join(all_files)
                plan_text = plan_text_str
                # Synthesize an AIMessage carrying the text + plan object
                response = AIMessage(
                    content=plan_text,
                    response_metadata={"_plan_obj": plan},
                )
                return {"messages": [response]}

            # Fallback: free-text plan
            response = await llm.ainvoke(messages)
            return {"messages": [response]}

        builder = StateGraph(SubgraphState)
        builder.add_node("plan", plan_node)
        builder.add_edge(START, "plan")
        builder.add_edge("plan", END)
        return builder.compile()

    def _build_executor_subgraph(self, llm, tools: list) -> Any:
        """executor_node ⇄ tool_node loop: executes the plan using tools."""
        llm_with_tools = llm.bind_tools(tools) if tools else llm

        async def executor_node(state: SubgraphState) -> dict:
            response = await llm_with_tools.ainvoke(state["messages"])
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

    def _build_reviewer_subgraph(self, llm, tools: list) -> Any:
        """Single 'review' node: Code Reviewer persona validates workspace."""
        reviewer_persona = get_sub_persona("reviewer")
        llm_with_tools = llm.bind_tools(tools) if tools else llm

        async def review_node(state: SubgraphState) -> dict:
            sys = SystemMessage(
                content=(
                    f"You are a {reviewer_persona.role}. {reviewer_persona.backstory}"
                )
            )
            response = await llm_with_tools.ainvoke([sys] + state["messages"])
            return {"messages": [response]}

        builder = StateGraph(SubgraphState)
        builder.add_node("review", review_node)
        builder.add_edge(START, "review")
        builder.add_edge("review", END)
        return builder.compile()

    # ── Parent graph builder ───────────────────────────────────────────────

    def _build_graph(self, llm, tools: list, collector=None, progress_callback=None) -> Any:
        """Build and compile the parent StateGraph with three subgraph nodes.

        Returns a compiled StateGraph (not a tuple).
        ``trace`` is optional; if provided, token usage is recorded during streaming.
        ``progress_callback`` is optional; if provided, subgraph wrappers emit
        per-tool-call progress during execution.
        """
        cb = progress_callback
        t0_ref: list[float] = [time.monotonic()]  # mutable ref for closures
        tool_count_ref: list[int] = [0]

        executor_tools, reviewer_tools = split_tools(tools, self.TOOL_FORMAT)

        planner_sg = self._build_planner_subgraph(llm)
        executor_sg = self._build_executor_subgraph(llm, executor_tools)
        reviewer_sg = self._build_reviewer_subgraph(llm, reviewer_tools)

        # ── Helper: extract token usage from a message ──────────────────
        def _extract_and_record_usage(msg: BaseMessage, duration_ms: float = 0.0) -> None:
            if collector is None:
                return
            resp_meta = getattr(msg, "response_metadata", {})
            raw_usage = resp_meta.get("token_usage") or resp_meta.get("usage")
            collector.record_llm_response(raw_usage=raw_usage, duration_ms=duration_ms)

        # ── Wrapper: planner ────────────────────────────────────────────
        async def planner_wrapper(state: ParentState) -> dict:
            messages: list[BaseMessage] = []
            if state.get("system_msg"):
                messages.append(SystemMessage(content=state["system_msg"]))
            messages.append(HumanMessage(content=state["prompt"]))

            if cb is not None:
                elapsed = time.monotonic() - t0_ref[0]
                cb(f"    [planner] generating plan...  ({elapsed:.0f}s)")

            result = await planner_sg.ainvoke({"messages": messages})
            last_msg = result["messages"][-1] if result["messages"] else None
            plan_text = getattr(last_msg, "content", "") if last_msg else ""

            # Extract structured plan from response metadata (if available)
            resp_meta = getattr(last_msg, "response_metadata", {}) or {}
            plan_obj: ImplementationPlan | None = resp_meta.get("_plan_obj")

            if plan_obj is None:
                # Build a fallback ImplementationPlan from text parsing
                parsed = parse_plan(plan_text)
                plan_obj = ImplementationPlan(
                    steps=[s["text"] for s in parsed] if parsed else [plan_text],
                    files_to_create=[],
                    files_to_modify=[],
                )

            if last_msg:
                planner_duration = (time.monotonic() - t0_ref[0]) * 1000
                _extract_and_record_usage(last_msg, duration_ms=planner_duration)
                if collector is not None:
                    collector.record_message("assistant", plan_text, metadata={"node": "planner"})

            if cb is not None:
                step_count = len(plan_obj.steps)
                elapsed = time.monotonic() - t0_ref[0]
                tokens = collector.trace.total_tokens_input + collector.trace.total_tokens_output if collector else 0
                cb(f"    [planner] done — {step_count} steps planned  ({elapsed:.0f}s, {tokens:,} tokens)")

            return {
                "plan": plan_text,
                "plan_obj": plan_obj,
                "iterations": state.get("iterations", 0) + 1,
            }

        # ── Wrapper: executor ───────────────────────────────────────────
        async def executor_wrapper(state: ParentState) -> dict:
            stage = state["stage"]
            plan = state.get("plan", "")
            plan_obj: ImplementationPlan | None = state.get("plan_obj")
            workspace = state.get("workspace", "")
            system_msg = state.get("system_msg")
            retry_count = state.get("retry_count", 0)

            executor_persona = get_stage_persona(stage)

            # Build enriched executor instructions matching OpenAI/AF adapters
            if plan_obj is not None:
                sys_content = build_executor_instructions(
                    executor_persona, plan_obj, system_msg,
                    stage=stage, workspace=workspace,
                )
            else:
                sys_content = (
                    f"{executor_persona.backstory}\n\n{plan}\n"
                    f"\nStage: {stage}\nWorking directory: {workspace}"
                )
            if retry_count > 0:
                sys_content += f"\n\nThis is retry attempt {retry_count}/{MAX_RETRIES}. Address any issues from the previous attempt."

            messages: list[BaseMessage] = [
                SystemMessage(content=sys_content),
                HumanMessage(content=state["prompt"]),
            ]

            # Stream the executor subgraph so we can emit per-tool progress
            llm_call_count = 0
            executor_t0 = time.monotonic()
            async for chunk in executor_sg.astream(
                {"messages": messages}, stream_mode="updates",
            ):
                for node_name, node_update in chunk.items():
                    if not node_update or not isinstance(node_update, dict):
                        continue
                    for msg in node_update.get("messages", []):
                        _extract_and_record_usage(msg)

                        # Record messages in trace
                        content = getattr(msg, "content", "")
                        if content and collector is not None:
                            collector.record_message(
                                getattr(msg, "type", "assistant"),
                                str(content),
                                metadata={"node": f"executor/{node_name}"},
                            )

                        # Count LLM calls
                        if hasattr(msg, "response_metadata") and msg.response_metadata:
                            llm_call_count += 1

                        # Record and report tool calls
                        for tc in getattr(msg, "tool_calls", []):
                            tool_count_ref[0] += 1
                            tc_name = tc.get("name", "unknown")
                            tc_args = tc.get("args", {})
                            if collector is not None:
                                collector.record_tool_execution(tc_name, tc_args, "")
                            if cb is not None:
                                elapsed = time.monotonic() - t0_ref[0]
                                detail = format_tool_detail(tc_name, tc_args)
                                tokens = collector.trace.total_tokens_input + collector.trace.total_tokens_output if collector else 0
                                cb(
                                    f"    tool {tool_count_ref[0]} — {detail}"
                                    f"  ({elapsed:.0f}s, {tokens:,} tokens)"
                                )

                    # Heartbeat for long-running executor loops
                    if cb is not None and node_name == "executor_node":
                        elapsed = time.monotonic() - t0_ref[0]
                        tokens = collector.trace.total_tokens_input + collector.trace.total_tokens_output if collector else 0
                        cb(f"    [executor] step {llm_call_count}  ({elapsed:.0f}s, {tokens:,} tokens)")

            executor_duration = (time.monotonic() - executor_t0) * 1000
            if collector is not None:
                collector.record_llm_response(raw_usage=None, duration_ms=executor_duration)

            passed = validate_workspace(stage, workspace)
            new_retry = retry_count + 1

            if collector is not None:
                record_node_event(
                    collector.trace,
                    "executor_node",
                    validator_passed=passed,
                    retry_count=new_retry,
                )

            return {
                "validator_passed": passed,
                "retry_count": new_retry,
                "iterations": state.get("iterations", 0) + max(llm_call_count, 1),
            }

        # ── Wrapper: reviewer ───────────────────────────────────────────
        async def reviewer_wrapper(state: ParentState) -> dict:
            stage = state["stage"]
            plan = state.get("plan", "")
            workspace = state.get("workspace", "")

            if cb is not None:
                elapsed = time.monotonic() - t0_ref[0]
                cb(f"    [reviewer] reviewing workspace...  ({elapsed:.0f}s)")

            messages: list[BaseMessage] = [
                HumanMessage(
                    content=(
                        f"Review the workspace for stage '{stage}'.\n"
                        f"Plan:\n{plan}\n"
                        f"Workspace: {workspace}\n"
                        "Verify all required artefacts are present and correct."
                    )
                )
            ]

            reviewer_t0 = time.monotonic()
            result = await reviewer_sg.ainvoke({"messages": messages})
            reviewer_duration = (time.monotonic() - reviewer_t0) * 1000

            for msg in result.get("messages", []):
                _extract_and_record_usage(msg, duration_ms=0.0)
            if collector is not None:
                collector.record_llm_response(raw_usage=None, duration_ms=reviewer_duration)

            last_msg = result["messages"][-1] if result.get("messages") else None
            if last_msg and collector is not None:
                content = getattr(last_msg, "content", None)
                # Content may be empty when the LLM returns tool calls only;
                # still record the message so the reviewer appears in the graph.
                text = str(content) if content else "(reviewer tool call)"
                collector.record_message("assistant", text, metadata={"node": "reviewer"})
                record_node_event(collector.trace, "reviewer", validator_passed=state.get("validator_passed", False))

            if cb is not None:
                elapsed = time.monotonic() - t0_ref[0]
                tokens = collector.trace.total_tokens_input + collector.trace.total_tokens_output if collector else 0
                cb(f"    [reviewer] done  ({elapsed:.0f}s, {tokens:,} tokens)")

            return {
                "iterations": state.get("iterations", 0) + 1,
            }

        # ── Conditional edge after reviewer ─────────────────────────────
        def route_after_reviewer(state: ParentState) -> str:
            if state.get("validator_passed"):
                return END
            if state.get("retry_count", 0) >= MAX_RETRIES:
                return END
            return "executor"

        # ── Assemble parent graph ────────────────────────────────────────
        builder = StateGraph(ParentState)
        builder.add_node("planner", planner_wrapper)
        builder.add_node("executor", executor_wrapper)
        builder.add_node("reviewer", reviewer_wrapper)

        builder.add_edge(START, "planner")
        builder.add_edge("planner", "executor")
        builder.add_edge("executor", "reviewer")
        builder.add_conditional_edges("reviewer", route_after_reviewer)

        checkpointer = InMemorySaver()
        return builder.compile(checkpointer=checkpointer)

    # ── Core agent runner ──────────────────────────────────────────────────

    @staticmethod
    def _langsmith_enabled() -> bool:
        return os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true" and bool(
            os.environ.get("LANGSMITH_API_KEY", "")
        )

    async def _run_agent(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str | None,
        tools: list,
        collector: ObservationCollector,
        context: StageContext,
    ) -> tuple[int, bool]:
        """Stream the parent StateGraph (with three subgraph nodes) for one SDLC stage."""
        self._last_langsmith_run_id = None

        # Build parent graph with collector closure for token recording
        progress_cb = getattr(context, "progress_callback", None)
        graph = self._build_graph(self._llm, tools, collector=collector, progress_callback=progress_cb)

        collector.record_message("user", prompt)

        run_id = uuid.uuid4()
        lf_cb = get_langchain_callback()
        config: RunnableConfig = {
            "run_id": run_id,
            "run_name": f"desmet-langgraph-{stage_name}",
            "configurable": {"thread_id": str(uuid.uuid4())},
        }
        if lf_cb is not None:
            config["callbacks"] = [lf_cb]

        initial_state: ParentState = {
            "prompt": prompt,
            "system_msg": system_msg,
            "plan": "",
            "plan_obj": None,
            "stage": stage_name,
            "workspace": str(context.workspace),
            "retry_count": 0,
            "validator_passed": False,
            "iterations": 0,
        }

        iteration = 0
        hit_limit = False
        final_state: dict[str, Any] = {}

        cb = progress_cb

        async for chunk in graph.astream(initial_state, config=config, stream_mode="updates"):
            iteration += 1

            for node_name, node_update in chunk.items():
                if isinstance(node_update, dict):
                    final_state.update(node_update)

                # Executor validator outcome (reported by executor_wrapper)
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

            if final_state.get("iterations", 0) >= context.max_iterations:
                hit_limit = True
                break

        collector.mark_iterations(final_state.get("iterations", iteration))
        collector.trace.final_state = final_state
        self._last_langsmith_run_id = str(run_id) if self._langsmith_enabled() else None
        return iteration, hit_limit

    # ── SDLC stage override (attaches LangSmith run ID) ───────────────────

    async def _execute_stage(self, stage_name, prompt_fn, result_cls, context):
        result = await super()._execute_stage(stage_name, prompt_fn, result_cls, context)
        result.langsmith_run_id = self._last_langsmith_run_id
        return result

    # ── Metadata ──────────────────────────────────────────────────────────

    def get_observability_info(self) -> dict[str, Any]:
        return {
            "has_tracing": True,
            "has_step_through": True,
            "has_replay": True,
            "has_state_inspection": True,
            "has_checkpointing": True,
            "has_memory_inspection": False,
            "trace_format": "LangSmith",
            "notes": (
                "Three compiled subgraphs (planner/executor/reviewer) with InMemorySaver "
                "checkpointing. Full graph-node tracing via LangSmith (LANGCHAIN_TRACING_V2=true required)."
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
                "Subgraph architecture with InMemorySaver checkpointing. "
                "Executor retry loop: up to 3 retries per stage before graceful exit."
            ),
        }
