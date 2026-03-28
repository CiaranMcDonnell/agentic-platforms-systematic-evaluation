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
import re
import threading
import time
from typing import Any

from pydantic import BaseModel

from desmet.adapters._base import ToolAgentAdapter
from desmet.adapters._prompts import get_stage_persona, get_sub_persona
from desmet.adapters._tools import ToolFormat
from desmet.adapters._tracing import (
    finish_trace,
    record_llm_duration,
    record_message,
    record_tool_call,
    record_usage,
)
from desmet.adapters._validation import validate_workspace
from desmet.adapters.registry import load_platform_info
from desmet.harness.context import StageContext
from desmet.harness.models import PlatformInfo
from desmet.harness.trace import AgentTrace
from desmet.llm_config import get_config as get_llm_config

_log = logging.getLogger(__name__)

MAX_STALL_COUNT = 3
MAX_RESET_COUNT = 2


# -- Data models -------------------------------------------------------------


class ImplementationPlan(BaseModel):
    """Structured output from the planner agent."""

    steps: list[str]
    files_to_create: list[str]
    files_to_modify: list[str]


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

        input_tokens = 0
        output_tokens = 0
        usage = getattr(response, "usage", None)
        if usage is not None:
            input_tokens = (
                getattr(usage, "prompt_tokens", 0)
                or getattr(usage, "input_tokens", 0)
                or 0
            )
            output_tokens = (
                getattr(usage, "completion_tokens", 0)
                or getattr(usage, "output_tokens", 0)
                or 0
            )

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


# -- Helper -------------------------------------------------------------------


def _format_tool_detail(name: str, raw_args: Any) -> str:
    """Format a tool call for human-readable progress logging."""
    args = raw_args if isinstance(raw_args, dict) else {}
    if not args and isinstance(raw_args, str):
        try:
            args = json.loads(raw_args)
        except (json.JSONDecodeError, TypeError):
            pass
    if name in ("read_file", "write_file") and "path" in args:
        return f"{name} \u2192 {args['path']}"
    if name == "execute_shell" and "command" in args:
        cmd = args["command"]
        ellipsis = "\u2026" if len(cmd) > 60 else ""
        return f"{name} \u2192 {cmd[:60]}{ellipsis}"
    if name == "search_code" and "pattern" in args:
        return f"{name} \u2192 /{args['pattern']}/"
    if name == "list_directory":
        return f"{name} \u2192 {args.get('path', '.')}"
    if name == "deploy_remote" and "action" in args:
        return f"{name} \u2192 {args['action']}"
    return name


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
        from agent_framework import Agent, AgentResponseUpdate, Message
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
                steps = [
                    m.group(1).strip()
                    for m in re.finditer(r"^\d+\.\s+(.*)", text, re.MULTILINE)
                ]
                plan = ImplementationPlan(
                    steps=steps or [text],
                    files_to_create=[],
                    files_to_modify=[],
                )
            except Exception:
                plan = ImplementationPlan(
                    steps=["Execute the task as described"],
                    files_to_create=[],
                    files_to_modify=[],
                )

        total_iterations += 1
        record_message(
            trace, "assistant",
            f"Plan: {json.dumps(plan.model_dump())}",
            metadata={"agent": "planner"},
        )
        if cb:
            cb(f"    planner: {len(plan.steps)} steps planned")

        # -- Step 2: Build executor and reviewer agents -----------------------
        plan_text = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(plan.steps))
        all_files = plan.files_to_create + plan.files_to_modify
        files_text = ", ".join(all_files) if all_files else "(none specified)"
        executor_instructions = (
            f"{executor_persona.backstory}\n\n"
            f"## Implementation Plan\n{plan_text}\n\n"
            f"## Files\n{files_text}\n"
        )
        if system_msg:
            executor_instructions += f"\n## Additional Context\n{system_msg}\n"

        # Separate tools: executor gets all except check_completion,
        # reviewer gets read_file, list_directory, search_code, check_completion
        executor_tools = [
            t for t in tools
            if getattr(t, "__name__", "") != "check_completion"
        ]
        reviewer_tool_names = {"read_file", "list_directory", "search_code", "check_completion"}
        reviewer_tools = [
            t for t in tools
            if getattr(t, "__name__", "") in reviewer_tool_names
        ]

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

        try:
            async for event in workflow.run(prompt, stream=True):
                total_iterations += 1

                if event.type == "output" and isinstance(event.data, AgentResponseUpdate):
                    # Streaming token from an agent
                    text = str(event.data)
                    agent_id = getattr(event, "executor_id", "") or ""
                    if text.strip():
                        record_message(
                            trace, "assistant", text,
                            metadata={"agent": agent_id},
                        )

                elif event.type == "magentic_orchestrator":
                    # Manager plan/progress event
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
                    # Final output — list[Message]
                    if isinstance(event.data, list):
                        for msg in event.data:
                            text = getattr(msg, "text", "") or ""
                            if text:
                                record_message(
                                    trace, "assistant", text,
                                    metadata={"event": "final_output"},
                                )

                # Check iteration limit
                if total_iterations >= context.max_iterations:
                    hit_limit = True
                    break
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
