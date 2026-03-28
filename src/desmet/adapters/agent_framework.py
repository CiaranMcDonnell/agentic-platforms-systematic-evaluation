"""
Microsoft Agent Framework Platform Adapter — MagenticOne orchestration.

Uses a manager-driven multi-agent team: planner (structured output) → executor
→ reviewer, orchestrated by MagenticBuilder with built-in stall detection
and round-count limits.

All imports from ``agent_framework`` are deferred so the module loads cleanly
even when the package is not installed.

Requires::

    uv pip install -e ".[agent-framework]"
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from desmet.adapters._base import ToolAgentAdapter
from desmet.adapters._planning import (
    ImplementationPlan,
    build_executor_instructions,
    parse_plan_text,
)
from desmet.adapters._prompts import get_stage_persona, get_sub_persona
from desmet.adapters._tools import ToolFormat, split_tools
from desmet.adapters._tracing import (
    finish_trace,
    format_tool_detail,
    normalize_usage,
    record_llm_duration,
    record_message,
    record_tool_call,
    record_usage,
)
from desmet.adapters._validation import validate_workspace
from desmet.adapters.registry import load_platform_info
from desmet.observability import get_langfuse, record_generation
from desmet.harness.context import StageContext
from desmet.harness.models import PlatformInfo
from desmet.harness.trace import AgentTrace
from desmet.llm_config import get_config as get_llm_config

_log = logging.getLogger(__name__)

MAX_STALL_COUNT = 3
MAX_RESET_COUNT = 2


# -- Usage tracking middleware ------------------------------------------------


class UsageTrackingMiddleware:
    """ChatMiddleware that intercepts every LLM call to record token usage.

    Thread-safe: multiple agents in a MagenticOne team may invoke the
    model concurrently, so all trace mutations go through ``_lock``.
    """

    def __init__(self, trace: AgentTrace, model_name: str | None = None) -> None:
        self._trace = trace
        self._model_name = model_name
        self._lock = threading.Lock()

    async def invoke(self, context: Any, next_handler: Any) -> Any:
        """Middleware handler: call next, then record usage from the response."""
        t0 = time.monotonic()
        response = await next_handler(context)
        duration_ms = (time.monotonic() - t0) * 1000

        usage = getattr(response, "usage", None)
        input_tokens, output_tokens = normalize_usage(usage)

        with self._lock:
            if input_tokens or output_tokens:
                record_usage(
                    self._trace,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model=self._model_name,
                )
            record_llm_duration(self._trace, duration_ms)

        return response


# -- Adapter ------------------------------------------------------------------


class AgentFrameworkAdapter(ToolAgentAdapter):
    """Microsoft Agent Framework adapter using MagenticOne orchestration.

    Orchestrates a planner, executor, and reviewer via ``MagenticBuilder``
    with built-in stall detection, automatic re-planning, and round-count
    limits.
    """

    TOOL_FORMAT = ToolFormat.AGENT_FRAMEWORK

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._client = None
        self._model_name: str | None = None

    @property
    def platform_info(self) -> PlatformInfo:
        info = load_platform_info("microsoft_agent_framework")
        info.version = self._get_version()
        return info

    def _get_version(self) -> str:
        try:
            import agent_framework
            return getattr(agent_framework, "__version__", "unknown")
        except ImportError:
            return "not installed"

    @staticmethod
    def _create_client(cfg):
        """Build an OpenAIChatClient from the resolved LLM config.

        Defers the import so the module loads without agent-framework installed.
        """
        from agent_framework.openai import OpenAIChatClient

        kwargs: dict[str, Any] = {"model_id": cfg.model}
        if cfg.api_key:
            kwargs["api_key"] = cfg.api_key
        if cfg.base_url:
            kwargs["base_url"] = cfg.base_url
        return OpenAIChatClient(**kwargs)

    async def initialize(self) -> None:
        try:
            from agent_framework import Agent  # noqa: F401
            from agent_framework.orchestrations import MagenticBuilder  # noqa: F401

            cfg = get_llm_config(model=self.config.get("model"))
            self._client = self._create_client(cfg)
            self._model_name = cfg.model

            # Optionally enable OpenTelemetry tracing if configured
            try:
                from agent_framework.observability import configure_otel_providers
                configure_otel_providers()
            except (ImportError, AttributeError, Exception):
                pass

            self._initialized = True
        except ImportError as e:
            raise RuntimeError(
                f"Failed to import Microsoft Agent Framework: {e}. "
                'Install with: uv pip install -e ".[agent-framework]"'
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Agent Framework: {e}")

    async def shutdown(self) -> None:
        self._client = None
        self._initialized = False

    async def health_check(self) -> bool:
        if not self._initialized or self._client is None:
            return False
        try:
            from agent_framework import Agent

            agent = Agent(
                name="health_check",
                instructions="Respond with 'ok'.",
                client=self._client,
            )
            result = await agent.run("Say 'ok'")
            return bool(getattr(result, "text", None))
        except Exception:
            return False

    # -- Core agent runner ----------------------------------------------------

    async def _run_agent(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str | None,
        tools: list,
        trace: AgentTrace,
        context: StageContext,
    ) -> tuple[int, bool]:
        """Run MagenticOne orchestration: manager + planner/executor/reviewer.

        Returns (total_iterations, hit_limit).
        """
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

        record_message(trace, "user", prompt)

        # Register usage tracking middleware on agents
        middleware = UsageTrackingMiddleware(trace, model_name=self._model_name)

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
            pass  # structured output not supported — fall back below

        if plan is None:
            # Free-text fallback: parse steps from plain text
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
        record_message(
            trace, "assistant",
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

        # Aggregate streaming token chunks into full messages per agent turn
        current_message_id: str | None = None
        current_message_chunks: list[str] = []
        current_agent_id: str = ""

        def _flush_message() -> None:
            """Flush accumulated token chunks into a single trace message."""
            nonlocal current_message_id
            if current_message_chunks:
                full_text = "".join(current_message_chunks)
                if full_text.strip():
                    record_message(
                        trace, "assistant", full_text,
                        metadata={"agent": current_agent_id},
                    )
                current_message_chunks.clear()
                current_message_id = None

        try:
            async for event in workflow.run(prompt, stream=True):

                if event.type == "output" and isinstance(event.data, AgentResponseUpdate):
                    # Streaming token chunk — aggregate, don't count as iteration
                    message_id = getattr(event.data, "message_id", None)
                    if message_id != current_message_id:
                        # New message from agent — flush previous
                        _flush_message()
                        current_message_id = message_id
                        current_agent_id = getattr(event, "executor_id", "") or ""
                    current_message_chunks.append(str(event.data))

                elif event.type == "magentic_orchestrator":
                    # Manager plan/progress event — counts as an iteration
                    _flush_message()
                    total_iterations += 1
                    content = getattr(event.data, "content", None)
                    event_name = getattr(getattr(event.data, "event_type", None), "name", "unknown")
                    if isinstance(content, Message):
                        record_message(
                            trace, "system", content.text or "",
                            metadata={"event": f"orchestrator_{event_name}"},
                        )
                    if cb:
                        cb(f"    [manager] {event_name}")

                elif event.type == "output":
                    # Final output — list[Message]; counts as an iteration
                    _flush_message()
                    total_iterations += 1
                    if isinstance(event.data, list):
                        for msg in event.data:
                            text = getattr(msg, "text", "") or ""
                            if text:
                                record_message(
                                    trace, "assistant", text,
                                    metadata={"event": "final_output"},
                                )

                elif event.type == "executor_completed":
                    # Agent finished — extract tool calls and token usage
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

                        # Extract token usage — try multiple sources
                        in_tok = 0
                        out_tok = 0

                        # Source 1: AgentResponse.usage_details
                        # Keys vary by provider: input_token_count (Gemini/OpenRouter),
                        # input_tokens (OpenAI), prompt_tokens (legacy)
                        usage = getattr(agent_resp, "usage_details", None)
                        in_tok, out_tok = normalize_usage(usage)

                        # Source 2: raw_representation
                        if not (in_tok or out_tok):
                            raw = getattr(agent_resp, "raw_representation", None)
                            raw_usage = getattr(raw, "usage", None)
                            in_tok, out_tok = normalize_usage(raw_usage)

                        # Source 3: usage Content items in messages
                        if not (in_tok or out_tok):
                            for msg in (agent_msgs or []):
                                for ci in (getattr(msg, "contents", None) or []):
                                    cd = ci.to_dict() if hasattr(ci, "to_dict") else {}
                                    if cd.get("type") == "usage":
                                        ud = cd.get("usage_details", {})
                                        if isinstance(ud, dict):
                                            in_tok += ud.get("input_tokens", 0) or 0
                                            out_tok += ud.get("output_tokens", 0) or 0

                        if in_tok or out_tok:
                            record_usage(trace, input_tokens=in_tok, output_tokens=out_tok, model=self._model_name)

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
                            usage={"input_tokens": in_tok, "output_tokens": out_tok} if (in_tok or out_tok) else None,
                            metadata={"agent": executor_name, "iteration": total_iterations},
                        )

                        # Extract tool calls and results from response messages.
                        # Function calls and results come as separate Content items;
                        # results reference calls by call_id.
                        msgs = agent_msgs or []
                        pending_calls: dict[str, tuple[str, dict]] = {}  # call_id -> (name, args)
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
                                    # Result may be in 'result', 'output', or 'items'
                                    result_text = cd.get("result", "") or cd.get("output", "") or ""
                                    if not result_text:
                                        items = cd.get("items", [])
                                        if items:
                                            result_text = str(items)
                                    if isinstance(result_text, (list, dict)):
                                        result_text = json.dumps(result_text)
                                    # Truncate large results for trace storage
                                    if len(str(result_text)) > 1000:
                                        result_text = str(result_text)[:500] + "...(truncated)..." + str(result_text)[-300:]
                                    # Match with pending call
                                    tc_name, tc_args = pending_calls.pop(call_id, ("unknown", {}))
                                    tool_call_count += 1
                                    record_tool_call(trace, name=tc_name, args=tc_args, result=str(result_text))
                                    if cb:
                                        elapsed = time.monotonic() - t0
                                        detail = format_tool_detail(tc_name, tc_args)
                                        tokens = trace.total_tokens_input + trace.total_tokens_output
                                        cb(f"    tool {tool_call_count} \u2014 {detail}  ({elapsed:.0f}s, {tokens:,} tokens)")

                        # Record any unmatched calls (no result yet)
                        for call_id, (tc_name, tc_args) in pending_calls.items():
                            tool_call_count += 1
                            record_tool_call(trace, name=tc_name, args=tc_args, result="(no result)")
                            if cb:
                                elapsed = time.monotonic() - t0
                                detail = format_tool_detail(tc_name, tc_args)
                                tokens = trace.total_tokens_input + trace.total_tokens_output
                                cb(f"    tool {tool_call_count} \u2014 {detail}  ({elapsed:.0f}s, {tokens:,} tokens)")

                    if cb:
                        cb(f"    [completed] {executor_name}")

                else:
                    # Log unhandled event types for debugging
                    _log.debug(
                        "Unhandled event type=%s executor=%s data_type=%s",
                        event.type,
                        getattr(event, "executor_id", ""),
                        type(event.data).__name__,
                    )

                # Check iteration limit
                if total_iterations >= context.max_iterations:
                    hit_limit = True
                    break

            # Flush any remaining chunks
            _flush_message()
        except Exception as e:
            _log.warning("MagenticOne orchestration error: %s", e)
            trace.errors.append(str(e))

        run_duration_ms = (time.monotonic() - run_t0) * 1000

        # Estimate LLM time (total run minus tool execution time)
        tool_time = sum(tc.duration_ms for tc in trace.tool_calls)
        llm_time_estimate = max(0.0, run_duration_ms - tool_time)
        record_llm_duration(trace, llm_time_estimate)

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

        trace.total_iterations = total_iterations
        finish_trace(trace)
        return total_iterations, hit_limit

    # -- Metadata -------------------------------------------------------------

    def get_observability_info(self) -> dict[str, Any]:
        return {
            "has_tracing": True,
            "has_step_through": False,
            "has_replay": False,
            "has_state_inspection": True,
            "has_memory_inspection": False,
            "has_stall_detection": True,
            "has_checkpointing": True,
            "trace_format": "opentelemetry",
            "notes": (
                "MagenticOne orchestration with manager-driven stall detection. "
                "OpenTelemetry tracing via agent_framework.observability. "
                "Planner (structured output) -> executor -> reviewer team."
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
                "Manager-driven stall detection with max_stall_count=3. "
                "MagenticOne manager automatically re-plans on stalls. "
                "Round-count limit prevents runaway execution."
            ),
        }
