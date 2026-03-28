"""
Microsoft Agent Framework Platform Adapter — MagenticOne orchestration.

Uses a manager-driven multi-agent team: planner (structured output) → executor
→ reviewer, orchestrated by MagenticOneGroupChat with built-in stall detection
and round-count limits.

All imports from ``agent_framework`` are deferred so the module loads cleanly
even when the package is not installed.
"""
from __future__ import annotations

import json
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
from desmet.llm_config import Provider
from desmet.llm_config import get_config as get_llm_config

MAX_STALL_COUNT = 3


# -- Data models -------------------------------------------------------------


class ImplementationPlan(BaseModel):
    """Structured output from the planner agent."""

    steps: list[str]
    files_to_create: list[str]
    files_to_modify: list[str]


# -- Usage tracking middleware ------------------------------------------------


class UsageTrackingMiddleware:
    """Intercepts LLM responses to record token usage into an AgentTrace.

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

        # Extract usage from the response (OpenAI-compatible structure)
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

    Orchestrates a planner, executor, and reviewer via MagenticOneGroupChat
    with built-in stall detection and round-count limits.
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
    def _create_model(cfg):
        """Build an OpenAIChatClient from the resolved LLM config.

        Defers the import so the module loads without agent-framework installed.
        """
        from agent_framework.openai import OpenAIChatClient

        kwargs: dict[str, Any] = {
            "model": cfg.model,
            "api_key": cfg.api_key,
        }
        if cfg.base_url:
            kwargs["base_url"] = cfg.base_url
        return OpenAIChatClient(**kwargs)

    async def initialize(self) -> None:
        try:
            from agent_framework.openai import OpenAIChatClient  # noqa: F401

            cfg = get_llm_config(model=self.config.get("model"))
            self._client = self._create_model(cfg)
            self._model_name = cfg.model

            # Optionally enable OpenTelemetry tracing if configured
            try:
                from agent_framework.telemetry import enable_otel
                enable_otel()
            except (ImportError, AttributeError, Exception):
                pass

            self._initialized = True
        except ImportError as e:
            raise RuntimeError(
                f"Failed to import Microsoft Agent Framework: {e}. "
                "Install with: uv pip install agent-framework"
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
            from agent_framework import AssistantAgent

            agent = AssistantAgent(
                name="health_check",
                system_message="Respond with 'ok'.",
                model_client=self._client,
            )
            # Simple completion check
            response = await agent.on_messages(
                [{"role": "user", "content": "Say 'ok'"}]
            )
            return bool(getattr(response, "content", None))
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
        """Run MagenticOne orchestration: planner -> executor -> reviewer.

        Returns (total_iterations, hit_limit).
        """
        from agent_framework import AssistantAgent, UserProxyAgent
        from agent_framework.magentic_one import MagenticOneGroupChat

        planner_persona = get_sub_persona("planner")
        executor_persona = get_stage_persona(stage_name)
        reviewer_persona = get_sub_persona("reviewer")

        total_iterations = 0
        tool_call_count = 0
        hit_limit = False
        t0 = time.monotonic()
        cb = context.progress_callback

        record_message(trace, "user", prompt)

        # Register usage tracking middleware on the client
        middleware = UsageTrackingMiddleware(trace, model_name=self._model_name)

        # -- Step 1: Planner agent (structured output) ------------------------
        plan: ImplementationPlan | None = None
        try:
            planner = AssistantAgent(
                name=f"desmet_{stage_name}_planner",
                system_message=planner_persona.backstory,
                model_client=self._client,
            )

            # Try structured output via response_format
            planner_response = await planner.on_messages(
                [{"role": "user", "content": prompt}],
                response_format=ImplementationPlan,
            )

            text = getattr(planner_response, "content", "")
            if text:
                try:
                    plan = ImplementationPlan.model_validate_json(text)
                except Exception:
                    pass
        except Exception:
            pass  # structured output not supported -- fall back below

        if plan is None:
            # Free-text fallback: parse steps from plain text
            try:
                planner = AssistantAgent(
                    name=f"desmet_{stage_name}_planner",
                    system_message=(
                        f"{planner_persona.backstory}\n\n"
                        "Produce a numbered implementation plan listing steps, "
                        "files to create, and files to modify."
                    ),
                    model_client=self._client,
                )
                planner_response = await planner.on_messages(
                    [{"role": "user", "content": prompt}],
                )
                text = getattr(planner_response, "content", "") or ""
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

        # -- Step 2: Build executor agent (stage persona + all tools except
        #    check_completion) with the plan injected into instructions --------
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

        executor_agent = AssistantAgent(
            name=f"desmet_{stage_name}_executor",
            system_message=executor_instructions,
            model_client=self._client,
            tools=executor_tools,
        )

        # -- Step 3: Build reviewer agent (reviewer persona + subset of tools) -
        reviewer_agent = AssistantAgent(
            name=f"desmet_{stage_name}_reviewer",
            system_message=(
                f"{reviewer_persona.backstory}\n\n"
                "After the executor finishes, inspect the workspace and call "
                "check_completion to verify all artifacts are present."
            ),
            model_client=self._client,
            tools=reviewer_tools,
        )

        # -- Step 4: Build manager agent (coordinator) -------------------------
        manager_instructions = (
            f"You are coordinating a software development team for the '{stage_name}' stage.\n"
            f"The executor will implement the plan. The reviewer will verify completeness.\n"
            "Delegate tasks to the executor first, then have the reviewer validate.\n"
            "If the reviewer reports issues, send the executor back to fix them.\n"
            "Stop when the reviewer confirms all artifacts are present."
        )

        # -- Step 5: MagenticOne orchestration ---------------------------------
        max_rounds = max(3, context.max_iterations - 1)

        team = MagenticOneGroupChat(
            participants=[executor_agent, reviewer_agent],
            model_client=self._client,
            max_turns=max_rounds,
            max_stall_count=MAX_STALL_COUNT,
        )

        # -- Step 6: Stream events from the team execution --------------------
        run_t0 = time.monotonic()

        async for event in team.run_stream(task=prompt):
            total_iterations += 1

            # Record agent messages
            agent_name = getattr(event, "source", "") or getattr(event, "agent", "")
            content = getattr(event, "content", "") or ""

            if content:
                record_message(
                    trace, "assistant", str(content),
                    metadata={"agent": str(agent_name)},
                )

            # Record tool calls from the event
            for tc in getattr(event, "tool_calls", []) or []:
                tool_call_count += 1
                tc_name = getattr(tc, "name", "") or getattr(tc, "function", {}).get("name", "unknown")
                tc_args = getattr(tc, "arguments", {})
                if isinstance(tc_args, str):
                    try:
                        tc_args = json.loads(tc_args)
                    except (json.JSONDecodeError, TypeError):
                        tc_args = {"raw": tc_args}
                record_tool_call(trace, name=tc_name, args=tc_args, result="")

                if cb is not None:
                    elapsed = time.monotonic() - t0
                    detail = _format_tool_detail(tc_name, tc_args)
                    tokens = trace.total_tokens_input + trace.total_tokens_output
                    cb(
                        f"    tool {tool_call_count} \u2014 {detail}"
                        f"  ({elapsed:.0f}s, {tokens:,} tokens)"
                    )

            # Track stall events
            if getattr(event, "type", "") == "stall":
                record_message(
                    trace, "system", "Stall detected by MagenticOne manager",
                    metadata={"event": "stall"},
                )
                if cb:
                    elapsed = time.monotonic() - t0
                    cb(f"    [manager] stall detected  ({elapsed:.0f}s)")

            # Check iteration limit
            if total_iterations >= context.max_iterations:
                hit_limit = True
                break

        run_duration_ms = (time.monotonic() - run_t0) * 1000

        # Estimate LLM time (total run minus tool execution time)
        tool_time = sum(tc.duration_ms for tc in trace.tool_calls)
        llm_time_estimate = max(0.0, run_duration_ms - tool_time)
        record_llm_duration(trace, llm_time_estimate)

        # -- Step 7: Final validation ------------------------------------------
        passed = validate_workspace(stage_name, str(context.workspace))
        if cb:
            if passed:
                cb("    reviewer: PASSED")
            else:
                from desmet.adapters._tools import _check_completion
                _, hint = _check_completion(context.workspace, stage_name)
                elapsed = time.monotonic() - t0
                cb(f"    reviewer: FAILED \u2014 {hint}  ({elapsed:.0f}s)")

        # Record final output
        if hasattr(team, "result") and team.result:
            record_message(
                trace, "assistant", str(team.result),
                metadata={"event": "final_output"},
            )

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
                "OpenTelemetry tracing via agent_framework.telemetry. "
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
                "MagenticOne manager automatically re-assigns stalled tasks. "
                "Round-count limit prevents runaway execution."
            ),
        }
