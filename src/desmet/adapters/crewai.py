"""
CrewAI Platform Adapter

Implements the evaluation interface for CrewAI.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any

from pydantic import BaseModel

from desmet.adapters._base import ToolAgentAdapter
from desmet.adapters._prompts import STAGE_EXPECTED_OUTPUTS, get_stage_persona, get_sub_persona
from desmet.adapters._validation import validate_workspace
from desmet.adapters._tools import ToolFormat
from desmet.adapters._tracing import (
    finish_trace,
    record_message,
    record_tool_call,
    record_usage,
)
from desmet.adapters.registry import load_platform_info
from desmet.harness.context import StageContext
from desmet.harness.models import PlatformInfo
from desmet.harness.trace import AgentTrace
from desmet.llm_config import Provider
from desmet.llm_config import get_config as get_llm_config

_log = logging.getLogger(__name__)

MAX_RETRIES = 3


class ImplementationPlan(BaseModel):
    """Structured output for the planner agent (parity with OpenAI/AF adapters)."""
    steps: list[str]
    files_to_create: list[str]
    files_to_modify: list[str]


def _compute_iter_budget(max_iterations: int, *, retry: bool = False) -> tuple[int, int, int]:
    """Compute per-agent max_iter from total budget.

    First attempt: 20%/60%/20% (planner/executor/reviewer).
    Retry: 0%/80%/20% (no planner, more executor budget).

    Returns (planner, executor, reviewer).
    """
    if retry:
        reviewer = max(1, int(max_iterations * 0.2))
        executor = max(1, max_iterations - reviewer)
        return 0, executor, reviewer
    planner = max(1, int(max_iterations * 0.2))
    reviewer = max(1, int(max_iterations * 0.2))
    executor = max(1, max_iterations - planner - reviewer)
    return planner, executor, reviewer


def _format_crewai_tool_detail(name: str, tool_input: Any) -> str:
    """Format a CrewAI tool call for human-readable progress logging."""
    args = tool_input if isinstance(tool_input, dict) else {}
    # CrewAI sometimes passes tool_input as a JSON string
    if not args and isinstance(tool_input, str):
        try:
            import json
            args = json.loads(tool_input)
        except (json.JSONDecodeError, TypeError):
            pass
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


def _summarise_step(step_output: Any) -> str:
    """Return a readable string for a CrewAI step output.

    Prefers ``log`` / ``text`` (the LLM reasoning text).  Falls back to a
    compact summary when ``str()`` would produce a multi-kilobyte Agent/Crew
    repr that obscures the actual reasoning content.
    """
    content = getattr(step_output, "log", "") or getattr(step_output, "text", "")
    if content:
        return content

    raw = str(step_output)
    # Detect verbose CrewAI object reprs (Agent, Task, Crew contain these fields).
    if len(raw) > 300 and ("role=" in raw or "backstory=" in raw):
        role_m = re.search(r"role=['\"]([^'\"]{1,80})", raw)
        goal_m = re.search(r"goal=['\"]([^'\"]{1,120})", raw)
        role = role_m.group(1) if role_m else "?"
        goal = (goal_m.group(1)[:100] + "…") if goal_m and len(goal_m.group(1)) > 100 else (goal_m.group(1) if goal_m else "")
        return f"[Agent: {role}] {goal}".strip()

    return raw


class CrewAIAdapter(ToolAgentAdapter):
    """
    Adapter for evaluating CrewAI.

    CrewAI is a role-based multi-agent collaboration framework.
    """

    TOOL_FORMAT = ToolFormat.CREWAI

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._crew = None
        # Per-LLM-call collection from CrewAI's event bus
        self._llm_calls: list[dict[str, Any]] = []
        self._llm_calls_lock = threading.Lock()
        self._collecting_llm = False
        self._last_llm_start: float = 0.0

    @property
    def platform_info(self) -> PlatformInfo:
        info = load_platform_info("crewai")
        info.version = self._get_version()
        return info

    def _get_version(self) -> str:
        try:
            import crewai
            return getattr(crewai, "__version__", "unknown")
        except ImportError:
            return "not installed"

    async def initialize(self) -> None:
        """Initialize CrewAI components."""
        try:
            from crewai import Agent, Crew, Process, Task  # noqa: F401 — verify core components

            # OTEL instrumentation for CrewAI orchestration layer
            # (crew → task → agent → tool spans in Langfuse)
            try:
                from openinference.instrumentation.crewai import CrewAIInstrumentor
                CrewAIInstrumentor().instrument(skip_dep_check=True)
            except ImportError:
                pass  # optional — tracing degrades gracefully

            # Per-LLM-call tracing via CrewAI's native event bus.
            # The handler fires for every chat completion inside the ReAct
            # loop, giving us per-call token counts and Langfuse generations.
            self._register_llm_event_handler()

            self._initialized = True
        except ImportError as e:
            raise RuntimeError(f"Failed to import CrewAI: {e}")

    async def shutdown(self) -> None:
        self._crew = None
        self._initialized = False

    async def health_check(self) -> bool:
        return self._initialized

    # ── Per-LLM-call event collection ─────────────────────────────────────

    def _register_llm_event_handler(self) -> None:
        """Subscribe to CrewAI's event bus for individual LLM completion events."""
        try:
            from crewai.events.event_bus import crewai_event_bus
            from crewai.events.types.llm_events import LLMCallCompletedEvent

            from crewai.events.types.llm_events import LLMCallStartedEvent

            @crewai_event_bus.on(LLMCallStartedEvent)
            def _on_llm_started(source, event) -> None:
                if not self._collecting_llm:
                    return
                self._last_llm_start = time.monotonic()

            @crewai_event_bus.on(LLMCallCompletedEvent)
            def _on_llm_completed(source, event: LLMCallCompletedEvent) -> None:
                if not self._collecting_llm:
                    return
                call_data: dict[str, Any] = {
                    "model": event.model,
                    "call_type": event.call_type.value if event.call_type else "unknown",
                    "agent_role": getattr(event, "agent_role", None),
                    "input_tokens": 0,
                    "output_tokens": 0,
                }
                resp = event.response
                usage = getattr(resp, "usage", None)
                if usage is not None:
                    call_data["input_tokens"] = (
                        getattr(usage, "prompt_tokens", 0)
                        or getattr(usage, "input_tokens", 0)
                        or 0
                    )
                    call_data["output_tokens"] = (
                        getattr(usage, "completion_tokens", 0)
                        or getattr(usage, "output_tokens", 0)
                        or 0
                    )
                if self._last_llm_start > 0:
                    call_data["duration_ms"] = (time.monotonic() - self._last_llm_start) * 1000
                    self._last_llm_start = 0.0
                with self._llm_calls_lock:
                    self._llm_calls.append(call_data)
        except ImportError:
            _log.debug("crewai.events not available — per-call tracing disabled")

    def _start_llm_collection(self) -> None:
        with self._llm_calls_lock:
            self._llm_calls.clear()
            self._collecting_llm = True

    def _stop_llm_collection(self) -> list[dict[str, Any]]:
        self._collecting_llm = False
        with self._llm_calls_lock:
            calls = list(self._llm_calls)
            self._llm_calls.clear()
        return calls

    def _create_llm(self, context: StageContext):
        """Build a CrewAI LLM from centralised config + stage context overrides.

        CrewAI v1.6+ removed litellm and routes through native provider SDKs.
        We instantiate the appropriate native provider directly (bypassing the
        ``LLM`` factory which has no OpenRouter entry).  Cost estimation is
        handled by ``record_usage()`` via the ``cost_calculator`` module.
        """
        cfg = get_llm_config(
            model=context.model or self.config.get("model"),
            temperature=context.temperature,
        )

        if cfg.provider in (Provider.OPENAI, Provider.OPENROUTER):
            from crewai.llms.providers.openai.completion import OpenAICompletion
            return OpenAICompletion(
                model=cfg.model,
                temperature=cfg.temperature,
                api_key=cfg.api_key,
                base_url=cfg.base_url,
            )

        if cfg.provider == Provider.ANTHROPIC:
            from crewai.llms.providers.anthropic.completion import AnthropicCompletion
            return AnthropicCompletion(
                model=cfg.model,
                temperature=cfg.temperature,
                api_key=cfg.api_key,
            )

        if cfg.provider == Provider.GOOGLE:
            from crewai.llms.providers.gemini.completion import GeminiCompletion
            return GeminiCompletion(
                model=cfg.model,
                temperature=cfg.temperature,
                api_key=cfg.api_key,
            )

        # Fallback: treat as OpenAI-compatible with custom base_url
        from crewai.llms.providers.openai.completion import OpenAICompletion
        return OpenAICompletion(
            model=cfg.model,
            temperature=cfg.temperature,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
        )

    # =========================================================================
    # Crew Builder
    # =========================================================================

    def _build_crew(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str | None,
        tools: list,
        llm: Any,
        context: StageContext,
        trace: AgentTrace,
        *,
        retry_attempt: int = 0,
        prior_plan: str = "",
        feedback: str = "",
        plan: ImplementationPlan | None = None,
    ) -> tuple[Any, list[int]]:
        """Build a CrewAI crew for one execution attempt.

        First attempt (``retry_attempt == 0``): 3-agent crew (planner +
        executor + reviewer) with context chaining.

        Retry (``retry_attempt > 0``): 2-agent crew (executor + reviewer)
        with the prior plan and validation feedback injected.

        Returns ``(crew, step_counter)`` where *step_counter* is a
        single-element list whose ``[0]`` value tracks iterations.
        """
        from crewai import Agent, Crew, Process, Task

        is_retry = retry_attempt > 0
        planner_budget, executor_budget, reviewer_budget = _compute_iter_budget(
            context.max_iterations, retry=is_retry,
        )
        # Distribute time budget proportionally (same ratio as iterations)
        total_budget = planner_budget + executor_budget + reviewer_budget
        time_budget = context.time_budget_seconds or 0

        def _make_backstory(persona_backstory: str) -> str:
            if system_msg:
                return f"{persona_backstory}\n\n{system_msg}"
            return persona_backstory

        # ── Asymmetric tool distribution ─────────────────────────────────
        executor_tools = [t for t in tools if t.name != "check_completion"]
        reviewer_tool_names = {"read_file", "list_directory", "search_code", "check_completion"}
        reviewer_tools = [t for t in tools if t.name in reviewer_tool_names]

        # ── Enriched executor context from structured plan ───────────────
        if plan is not None:
            plan_text_fmt = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(plan.steps))
            all_files = plan.files_to_create + plan.files_to_modify
            files_text = ", ".join(all_files) if all_files else "(none specified)"
            executor_context = (
                f"\n\n## Implementation Plan\n{plan_text_fmt}\n\n"
                f"## Files\n{files_text}\n"
            )
        else:
            executor_context = ""

        # ── Executor — stage-specific persona ────────────────────────────
        executor_persona = get_stage_persona(stage_name)
        executor_time = int(time_budget * executor_budget / total_budget) if time_budget else None
        executor_backstory = _make_backstory(executor_persona.backstory) + executor_context
        executor_agent = Agent(
            role=executor_persona.role,
            goal=executor_persona.goal,
            backstory=executor_backstory,
            verbose=False,
            allow_delegation=False,
            llm=llm,
            tools=executor_tools,
            max_iter=executor_budget,
            max_execution_time=executor_time,
        )

        # ── Reviewer — Code Reviewer ─────────────────────────────────────
        reviewer_persona = get_sub_persona("reviewer")
        reviewer_time = int(time_budget * reviewer_budget / total_budget) if time_budget else None
        reviewer_agent = Agent(
            role=reviewer_persona.role,
            goal=reviewer_persona.goal,
            backstory=_make_backstory(reviewer_persona.backstory),
            verbose=False,
            allow_delegation=False,
            llm=llm,
            tools=reviewer_tools,
            max_iter=reviewer_budget,
            max_execution_time=reviewer_time,
        )

        agents: list = []
        tasks: list = []

        if not is_retry:
            # ── Planner — Technical Lead ─────────────────────────────────
            planner_persona = get_sub_persona("planner")
            planner_time = int(time_budget * planner_budget / total_budget) if time_budget else None
            planner_agent = Agent(
                role=planner_persona.role,
                goal=planner_persona.goal,
                backstory=_make_backstory(planner_persona.backstory),
                verbose=False,
                allow_delegation=False,
                llm=llm,
                tools=tools,
                max_iter=planner_budget,
                max_execution_time=planner_time,
            )
            analyse_task = Task(
                description=(
                    f"Analyse the following task and produce a numbered "
                    f"implementation plan identifying all files to create "
                    f"or modify.\n\n{prompt}"
                ),
                expected_output=(
                    "A numbered implementation plan with files to create/modify"
                ),
                agent=planner_agent,
                output_pydantic=ImplementationPlan,
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
                    "Review the implementation against the plan. Verify all "
                    "required artefacts are present in the workspace and "
                    "outputs are complete and correct."
                ),
                expected_output=(
                    "Validation report confirming all artefacts are present "
                    "and correct"
                ),
                agent=reviewer_agent,
                context=[analyse_task, implement_task],
            )
            agents = [planner_agent, executor_agent, reviewer_agent]
            tasks = [analyse_task, implement_task, review_task]
        else:
            # ── Retry: executor + reviewer only, plan carried forward ────
            retry_description = (
                f"Previous attempt failed validation (attempt "
                f"{retry_attempt}/{MAX_RETRIES}).\n"
                f"{feedback}\n\n"
                f"## Plan from previous attempt\n{prior_plan}\n\n"
                f"## Original task\n{prompt}\n\n"
                f"Fix the issues and complete the task."
            )
            implement_task = Task(
                description=retry_description,
                expected_output=STAGE_EXPECTED_OUTPUTS.get(
                    stage_name, "Complete the task as described."
                ),
                agent=executor_agent,
            )
            review_task = Task(
                description=(
                    "Review the implementation against the plan. Verify all "
                    "required artefacts are present in the workspace and "
                    "outputs are complete and correct."
                ),
                expected_output=(
                    "Validation report confirming all artefacts are present "
                    "and correct"
                ),
                agent=reviewer_agent,
                context=[implement_task],
            )
            agents = [executor_agent, reviewer_agent]
            tasks = [implement_task, review_task]

        step_cb, task_cb, counter = self._create_trace_callbacks(
            trace,
            progress_callback=context.progress_callback,
            max_iterations=context.max_iterations,
        )

        # planning=True disabled: redundant with our planner agent and
        # defaults to gpt-4o-mini which would introduce a second model.
        # Note: max_iter and max_execution_time are per-Agent fields in
        # crewai >=1.7; the per-agent max_iter is already set above.
        crew = Crew(
            agents=agents,
            tasks=tasks,
            process=Process.sequential,
            verbose=False,
            step_callback=step_cb,
            task_callback=task_cb,
        )
        return crew, counter

    # =========================================================================
    # Core Agent Runner
    # =========================================================================

    async def _run_agent(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str | None,
        tools: list,
        trace: AgentTrace,
        context: StageContext,
    ) -> tuple[int, bool]:
        """Run a CrewAI crew with retry loop. Returns (iterations, hit_limit)."""
        import asyncio

        from desmet.adapters._tools import _check_completion
        from desmet.adapters._tracing import record_llm_duration, record_node_event

        llm = self._create_llm(context)
        cfg = get_llm_config(
            model=context.model or self.config.get("model"),
            temperature=context.temperature,
        )
        model_name = cfg.model

        record_message(trace, "user", prompt)

        total_iterations = 0
        hit_limit = False
        plan_text = ""
        feedback = ""
        structured_plan: ImplementationPlan | None = None

        for attempt in range(MAX_RETRIES + 1):
            crew, counter = self._build_crew(
                stage_name, prompt, system_msg, tools, llm, context, trace,
                retry_attempt=attempt,
                prior_plan=plan_text,
                feedback=feedback,
                plan=structured_plan,
            )

            self._start_llm_collection()
            result = await asyncio.to_thread(crew.kickoff)
            record_message(trace, "assistant", str(result))
            llm_calls = self._stop_llm_collection()

            # ── Record LLM call durations and token usage ────────────────
            for call in llm_calls:
                if call.get("duration_ms", 0) > 0:
                    record_llm_duration(trace, call["duration_ms"])

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
                        input_tokens=(
                            getattr(usage, "prompt_tokens", 0)
                            or getattr(usage, "input_tokens", 0) or 0
                        ),
                        output_tokens=(
                            getattr(usage, "completion_tokens", 0)
                            or getattr(usage, "output_tokens", 0) or 0
                        ),
                        model=model_name,
                    )

            total_iterations += counter[0]

            # ── Extract plan from first attempt ──────────────────────────
            if attempt == 0:
                tasks_output = getattr(result, "tasks_output", None)
                if tasks_output:
                    first_output = tasks_output[0]
                    # Try pydantic output first (structured output from CrewAI)
                    pydantic_out = getattr(first_output, "pydantic", None)
                    if isinstance(pydantic_out, ImplementationPlan):
                        structured_plan = pydantic_out
                    else:
                        # Parse from text as fallback
                        raw_plan = str(first_output)
                        steps = [
                            m.group(1).strip()
                            for m in re.finditer(r"^\d+\.\s+(.*)", raw_plan, re.MULTILINE)
                        ]
                        structured_plan = ImplementationPlan(
                            steps=steps or [raw_plan],
                            files_to_create=[],
                            files_to_modify=[],
                        )
                    plan_text = str(first_output)

            # ── Validate workspace ───────────────────────────────────────
            valid = validate_workspace(stage_name, str(context.workspace))
            record_node_event(
                trace, "validator",
                validator_passed=valid,
                retry_count=attempt + 1,
            )

            if valid:
                if context.progress_callback is not None:
                    context.progress_callback("    validator: PASSED")
                break

            # ── Validation failed — prepare retry or exit ────────────────
            _, feedback = _check_completion(context.workspace, stage_name)

            if context.progress_callback is not None:
                context.progress_callback(
                    f"    validator: FAILED (attempt {attempt + 1}/"
                    f"{MAX_RETRIES + 1}) — {feedback}"
                )

            if total_iterations >= context.max_iterations:
                hit_limit = True
                break

        if not hit_limit:
            hit_limit = total_iterations >= context.max_iterations

        trace.total_iterations = total_iterations
        finish_trace(trace)
        return total_iterations, hit_limit

    # Stage methods inherited from ToolAgentAdapter

    # =========================================================================
    # Trace Callbacks
    # =========================================================================

    @staticmethod
    def _create_trace_callbacks(
        trace: AgentTrace,
        *,
        progress_callback: Any | None = None,
        max_iterations: int = 50,
    ) -> tuple[Any, Any, list[int]]:
        """Create ``step_callback`` and ``task_callback`` closures for a Crew.

        Returns a 3-tuple of ``(step_callback, task_callback, step_counter)``
        where *step_counter* is a single-element list whose ``[0]`` value is
        incremented on every agent step so the caller can read the true
        iteration count after ``crew.kickoff()`` returns.
        """
        counter: list[int] = [0]
        tool_counter: list[int] = [0]
        t0 = time.monotonic()

        def step_callback(step_output: Any) -> None:
            """Called after every agent reasoning step."""
            counter[0] += 1

            # CrewAI step outputs vary by type.  Inspect common attributes
            # to extract tool-call information when present.
            tool_name = getattr(step_output, "tool", None)
            if tool_name:
                tool_counter[0] += 1
                tool_input = getattr(step_output, "tool_input", "")
                tool_result = getattr(step_output, "result", "")
                args = tool_input if isinstance(tool_input, dict) else {"input": str(tool_input)}
                record_tool_call(trace, str(tool_name), args, str(tool_result))

            # Emit progress for tool calls and periodic heartbeats
            if progress_callback is not None:
                elapsed = time.monotonic() - t0
                tokens = trace.total_tokens_input + trace.total_tokens_output
                if tool_name:
                    detail = _format_crewai_tool_detail(str(tool_name), tool_input)
                    progress_callback(
                        f"    tool {tool_counter[0]} — {detail}"
                        f"  ({elapsed:.0f}s, {tokens:,} tokens)"
                    )
                elif counter[0] % 5 == 0:
                    agent_role = getattr(step_output, "agent", None)
                    role_str = getattr(agent_role, "role", "") if agent_role else ""
                    role_label = f" [{role_str}]" if role_str else ""
                    progress_callback(
                        f"    step {counter[0]}/{max_iterations}{role_label} — reasoning"
                        f"  ({elapsed:.0f}s, {tokens:,} tokens)"
                    )

            # Always record the step as a message so the full reasoning
            # chain is visible in the trace.
            content = _summarise_step(step_output)
            record_message(trace, "assistant", content, metadata={"step": counter[0]})
            trace.total_iterations = counter[0]

        def task_callback(task_output: Any) -> None:
            """Called when a CrewAI Task completes."""
            record_message(
                trace, "assistant", str(task_output),
                metadata={"event": "task_complete"},
            )
            if progress_callback is not None:
                elapsed = time.monotonic() - t0
                agent_name = getattr(task_output, "agent", "") or ""
                progress_callback(
                    f"    task complete — {agent_name}  ({elapsed:.0f}s)"
                )

        return step_callback, task_callback, counter

    # =========================================================================
    # Metadata & Lifecycle
    # =========================================================================

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
                "up to 3 retries. Per-agent step callbacks + event bus for "
                "LLM call tracing. Native function calling via provider SDKs."
            ),
        }

    def get_failure_handling_info(self) -> dict[str, Any]:
        return {
            "has_checkpointing": False,
            "has_auto_recovery": True,
            "has_graceful_degradation": True,
            "supports_human_handoff": True,
            "is_idempotent": True,
            "notes": (
                "Post-crew validate_workspace() with up to 3 retries. Plan "
                "carried forward on retry (executor + reviewer only, no "
                "re-planning). Per-agent max_iter limits."
            ),
        }
