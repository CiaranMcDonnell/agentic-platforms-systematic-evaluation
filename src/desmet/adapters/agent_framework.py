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
import time
from typing import Any

from desmet.adapters._shared.base import ToolAgentAdapter
from desmet.adapters._shared.observation import ObservationCollector
from desmet.adapters._shared.planning import (
    ImplementationPlan,
    build_executor_instructions,
    parse_plan_text,
)
from desmet.adapters._shared.prompts import get_stage_persona, get_sub_persona
from desmet.adapters._shared.retry import ProgressReporter, RetryPolicy
from desmet.adapters._shared.tools import ToolFormat, split_tools
from desmet.adapters.registry import load_platform_info
from desmet.harness.context import StageContext
from desmet.harness.models import PlatformInfo
from desmet.harness.trace import AgentTrace
from desmet.llm_config import get_config as get_llm_config
from desmet.observability import get_langfuse, record_generation

_log = logging.getLogger(__name__)

MAX_STALL_COUNT = 3
MAX_RESET_COUNT = 2


# -- Usage tracking middleware ------------------------------------------------


class UsageTrackingMiddleware:
    """ChatMiddleware that intercepts every LLM call to record token usage.

    Thread-safe: ``ObservationCollector`` handles its own lock, so no
    additional lock is needed here.
    """

    def __init__(self, collector: ObservationCollector) -> None:
        self._collector = collector

    async def invoke(self, context: Any, next_handler: Any) -> Any:
        """Middleware handler: call next, then record usage from the response."""
        t0 = time.monotonic()
        response = await next_handler(context)
        duration_ms = (time.monotonic() - t0) * 1000

        usage = getattr(response, "usage", None)
        self._collector.record_llm_response(raw_usage=usage, duration_ms=duration_ms)

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

        OpenAIChatClient doesn't accept ``timeout`` / ``max_retries`` in
        its constructor, so we pre-build an ``AsyncOpenAI`` with those
        applied and inject it via ``async_client``.

        Defers the import so the module loads without agent-framework installed.
        """
        from agent_framework.openai import OpenAIChatClient
        from openai import AsyncOpenAI

        async_client = AsyncOpenAI(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            timeout=cfg.timeout_seconds,
            max_retries=cfg.max_retries,
        )
        return OpenAIChatClient(model_id=cfg.model, async_client=async_client)

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

    def _get_model_name(self) -> str | None:
        return self._model_name

    # -- Core agent runner ----------------------------------------------------

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
        """Run MagenticOne orchestration: manager + planner/executor/reviewer.

        Returns (total_iterations, success) where success is True iff the
        workspace passes validation at the end of the run.
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
        progress.agent_status("planner", f"{len(plan.steps)} steps planned")

        # -- Step 2: Build executor and reviewer agents -----------------------
        executor_instructions = build_executor_instructions(
            executor_persona,
            plan,
            system_msg,
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
                    collector.record_message(
                        "assistant",
                        full_text,
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
                        collector.record_message(
                            "system",
                            content.text or "",
                            metadata={"event": f"orchestrator_{event_name}"},
                        )
                    progress.agent_status("manager", event_name)

                elif event.type == "output":
                    # Final output — list[Message]; counts as an iteration
                    _flush_message()
                    total_iterations += 1
                    if isinstance(event.data, list):
                        for msg in event.data:
                            text = getattr(msg, "text", "") or ""
                            if text:
                                collector.record_message(
                                    "assistant",
                                    text,
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

                        # Token usage is recorded by UsageTrackingMiddleware per-LLM-call.
                        # No duplicate recording here.

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

                        # Extract tool calls and results from response messages.
                        # Function calls and results come as separate Content items;
                        # results reference calls by call_id.
                        msgs = agent_msgs or []
                        pending_calls: dict[str, tuple[str, dict]] = {}  # call_id -> (name, args)
                        for msg in msgs:
                            for content_item in getattr(msg, "contents", None) or []:
                                cd = (
                                    content_item.to_dict()
                                    if hasattr(content_item, "to_dict")
                                    else {}
                                )
                                ctype = cd.get("type", "")

                                if ctype == "function_call":
                                    tc_name = cd.get("name", "unknown")
                                    tc_args_raw = cd.get("arguments", "{}")
                                    try:
                                        tc_args = (
                                            json.loads(tc_args_raw)
                                            if isinstance(tc_args_raw, str)
                                            else tc_args_raw
                                        )
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
                                        result_text = (
                                            str(result_text)[:500]
                                            + "...(truncated)..."
                                            + str(result_text)[-300:]
                                        )
                                    # Match with pending call
                                    tc_name, tc_args = pending_calls.pop(call_id, ("unknown", {}))
                                    collector.record_tool_execution(
                                        tc_name, tc_args, str(result_text)
                                    )
                                    progress.tool_call(tc_name, tc_args)

                        # Record any unmatched calls (no result yet)
                        for call_id, (tc_name, tc_args) in pending_calls.items():
                            collector.record_tool_execution(tc_name, tc_args, "(no result)")
                            progress.tool_call(tc_name, tc_args)

                    progress.agent_status(executor_name, "completed")

                else:
                    # Log unhandled event types for debugging
                    _log.debug(
                        "Unhandled event type=%s executor=%s data_type=%s",
                        event.type,
                        getattr(event, "executor_id", ""),
                        type(event.data).__name__,
                    )

                # Check iteration limit — break out of streaming loop;
                # final success state is decided by policy.validate() below.
                if total_iterations >= context.max_iterations:
                    break

            # Flush any remaining chunks
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
        # Final success requires the workspace to actually pass validation.
        # Same invariant as the other adapters: artifacts present == success,
        # regardless of iteration count.
        success, feedback = policy.validate()
        if success:
            progress.validation_passed()
        else:
            progress.validation_failed(1, 1, feedback)

        collector.mark_iterations(total_iterations)
        return total_iterations, success

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
