"""
LangGraph Platform Adapter — StateGraph implementation.

Each DESMET SDLC stage runs an explicit StateGraph:
  START → planner_node → executor_node ⇄ tool_node → validator_node → (retry | END)
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Annotated, Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from desmet.adapters._base import ToolAgentAdapter
from desmet.adapters._tools import ToolFormat
from desmet.adapters._tracing import (
    finish_trace,
    record_message,
    record_node_event,
    record_tool_call,
    record_usage,
)
from desmet.adapters._validation import validate_workspace
from desmet.adapters.registry import load_platform_info
from desmet.harness.context import StageContext
from desmet.harness.models import PlatformInfo
from desmet.llm_config import Provider
from desmet.llm_config import get_config as get_llm_config
from desmet.observability import get_langchain_callback

MAX_RETRIES = 3


def _format_tool_detail(name: str, args: dict) -> str:
    """Format a tool call for human-readable progress logging."""
    if name in ("read_file", "write_file") and "path" in args:
        return f"{name} → {args['path']}"
    if name == "execute_shell" and "command" in args:
        cmd = args["command"]
        return f"{name} → {cmd[:60]}{'…' if len(cmd) > 60 else ''}"
    if name == "search_code" and "pattern" in args:
        return f"{name} → /{args['pattern']}/"
    if name == "list_directory":
        return f"{name} → {args.get('path', '.')}"
    if name == "deploy_remote" and "action" in args:
        return f"{name} → {args['action']}"
    return name


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    plan: str
    stage: str
    retry_count: int
    workspace: str
    validator_passed: bool


class LangGraphAdapter(ToolAgentAdapter):
    """LangGraph adapter using an explicit StateGraph per DESMET stage."""

    TOOL_FORMAT = ToolFormat.LANGCHAIN

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._llm = None
        self._model_name: str | None = None
        self._last_langsmith_run_id: str | None = None

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

    # ── Graph construction ────────────────────────────────────────────────

    def _build_graph(self, llm, tools: list):
        """Build and compile the StateGraph for a single stage run."""
        llm_with_tools = llm.bind_tools(tools)
        _llm_durations: list[float] = []

        def planner_node(state: AgentState) -> dict:
            sys = SystemMessage(
                content=(
                    f"You are a planning assistant for the '{state['stage']}' stage of a "
                    "software development lifecycle. Produce a concise numbered plan."
                )
            )
            t0 = time.monotonic()
            response = llm.invoke([sys] + state["messages"])
            _llm_durations.append((time.monotonic() - t0) * 1000)
            return {"plan": response.content, "messages": [response]}

        def executor_node(state: AgentState) -> dict:
            sys = SystemMessage(
                content=(
                    f"Stage: {state['stage']}\nPlan:\n{state['plan']}\n"
                    "Execute the next step. Use tools to write files or run commands. "
                    f"Working directory: {state['workspace']}"
                )
            )
            t0 = time.monotonic()
            response = llm_with_tools.invoke([sys] + state["messages"])
            _llm_durations.append((time.monotonic() - t0) * 1000)
            return {"messages": [response]}

        def validator_node(state: AgentState) -> dict:
            passed = validate_workspace(state["stage"], state["workspace"])
            return {
                "validator_passed": passed,
                "retry_count": state["retry_count"] + 1,
            }

        def route_after_validator(state: AgentState) -> str:
            if state["validator_passed"]:
                return END
            if state["retry_count"] >= MAX_RETRIES:
                return END
            return "executor_node"

        builder = StateGraph(AgentState)
        builder.add_node("planner_node", planner_node)
        builder.add_node("executor_node", executor_node)
        builder.add_node("tool_node", ToolNode(tools))
        builder.add_node("validator_node", validator_node)
        builder.add_edge(START, "planner_node")
        builder.add_edge("planner_node", "executor_node")
        builder.add_edge("tool_node", "executor_node")
        builder.add_conditional_edges("executor_node", self._route_executor)
        builder.add_conditional_edges("validator_node", route_after_validator)
        return builder.compile(), _llm_durations

    @staticmethod
    def _route_executor(state: AgentState) -> str:
        """Route executor output: to tool_node if tool calls pending, else validator."""
        last = state["messages"][-1] if state["messages"] else None
        if last and getattr(last, "tool_calls", None):
            return "tool_node"
        return "validator_node"

    # ── Core agent runner ─────────────────────────────────────────────────

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
        trace,
        context: StageContext,
    ) -> tuple[int, bool]:
        """Stream a compiled StateGraph for one SDLC stage."""
        self._last_langsmith_run_id = None
        graph, llm_durations = self._build_graph(self._llm, tools)

        initial_messages: list[BaseMessage] = []
        if system_msg:
            initial_messages.append(SystemMessage(content=system_msg))
        initial_messages.append(HumanMessage(content=prompt))

        record_message(trace, "user", prompt)

        run_id = uuid.uuid4()
        lf_cb = get_langchain_callback()
        config: RunnableConfig = {
            "run_id": run_id,
            "run_name": f"desmet-langgraph-{stage_name}",
        }
        if lf_cb is not None:
            config["callbacks"] = [lf_cb]

        initial_state: AgentState = {
            "messages": initial_messages,
            "plan": "",
            "stage": stage_name,
            "retry_count": 0,
            "workspace": str(context.workspace),
            "validator_passed": False,
        }

        iteration = 0
        tool_call_count = 0
        hit_limit = False
        final_state: dict[str, Any] = {}
        t0 = time.monotonic()
        cb = context.progress_callback

        async for chunk in graph.astream(initial_state, config=config, stream_mode="updates"):
            iteration += 1

            for node_name, node_update in chunk.items():
                if not node_update:
                    continue

                # Accumulate full state so finish_trace has something meaningful.
                if isinstance(node_update, dict):
                    final_state.update(node_update)

                # Emit node transitions for visibility
                if cb is not None and node_name in ("planner_node", "executor_node"):
                    elapsed = time.monotonic() - t0
                    cb(f"    [{node_name}]  ({elapsed:.0f}s)")

                messages = node_update.get("messages", []) if isinstance(node_update, dict) else []
                for msg in messages:
                    content = getattr(msg, "content", "")
                    if content:
                        record_message(
                            trace,
                            getattr(msg, "type", "assistant"),
                            str(content),
                            metadata={"node": node_name},
                        )

                    resp_meta = getattr(msg, "response_metadata", {})
                    usage = resp_meta.get("token_usage") or resp_meta.get("usage") or {}
                    if isinstance(usage, dict) and usage.get("total_tokens", 0) > 0:
                        record_usage(
                            trace,
                            input_tokens=usage.get("prompt_tokens", 0)
                            or usage.get("input_tokens", 0),
                            output_tokens=usage.get("completion_tokens", 0)
                            or usage.get("output_tokens", 0),
                            cost_usd=float(usage.get("cost") or 0.0),
                            model=self._model_name,
                        )

                    for tc in getattr(msg, "tool_calls", []):
                        tool_call_count += 1
                        tc_name = tc.get("name", "unknown")
                        tc_args = tc.get("args", {})
                        record_tool_call(trace, tc_name, tc_args, "")
                        if cb is not None:
                            elapsed = time.monotonic() - t0
                            detail = _format_tool_detail(tc_name, tc_args)
                            tokens = trace.total_tokens_input + trace.total_tokens_output
                            cb(
                                f"    tool {tool_call_count} — {detail}"
                                f"  ({elapsed:.0f}s, {tokens:,} tokens)"
                            )

                # Capture validator outcomes as named node events for per-retry visibility.
                if node_name == "validator_node" and isinstance(node_update, dict):
                    record_node_event(
                        trace,
                        "validator_node",
                        validator_passed=node_update.get("validator_passed", False),
                        retry_count=node_update.get("retry_count", 0),
                    )
                    if cb is not None:
                        passed = node_update.get("validator_passed", False)
                        retry = node_update.get("retry_count", 0)
                        if passed:
                            cb("    validator: PASSED")
                        else:
                            from desmet.adapters._tools import _check_completion

                            _, hint = _check_completion(context.workspace, stage_name)
                            cb(f"    validator: FAILED (attempt {retry}/{MAX_RETRIES}) — {hint}")

            if iteration >= context.max_iterations:
                hit_limit = True
                break

        from desmet.adapters._tracing import record_llm_duration
        for d in llm_durations:
            record_llm_duration(trace, d)
        trace.total_iterations = iteration
        finish_trace(trace, final_state=final_state)
        self._last_langsmith_run_id = str(run_id) if self._langsmith_enabled() else None
        return iteration, hit_limit

    # ── SDLC stage override (attaches LangSmith run ID) ────────────────

    async def _execute_stage(self, stage_name, prompt_fn, result_cls, context):
        result = await super()._execute_stage(stage_name, prompt_fn, result_cls, context)
        result.langsmith_run_id = self._last_langsmith_run_id
        return result

    # ── Metadata ─────────────────────────────────────────────────────────

    def get_observability_info(self) -> dict[str, Any]:
        return {
            "has_tracing": True,
            "has_step_through": True,
            "has_replay": False,
            "has_state_inspection": True,
            "has_memory_inspection": False,
            "trace_format": "LangSmith",
            "notes": "Full graph-node tracing via LangSmith (LANGCHAIN_TRACING_V2=true required)",
        }

    def get_failure_handling_info(self) -> dict[str, Any]:
        return {
            "has_checkpointing": False,
            "has_auto_recovery": True,
            "has_graceful_degradation": True,
            "supports_human_handoff": False,
            "is_idempotent": True,
            "notes": "Validator retry loop: up to 3 retries per stage before graceful exit",
        }
