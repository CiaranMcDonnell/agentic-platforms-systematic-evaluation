"""
CrewAI Platform Adapter

Implements the evaluation interface for CrewAI.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from desmet.adapters._base import ToolAgentAdapter
from desmet.adapters._planning import ImplementationPlan, format_plan_text, parse_plan_text
from desmet.adapters._prompts import STAGE_EXPECTED_OUTPUTS, get_stage_persona, get_sub_persona
from desmet.adapters._tools import ToolFormat, split_tools
from desmet.adapters._observation import ObservationCollector
from desmet.adapters._retry import ProgressReporter, RetryPolicy
from desmet.adapters._tracing import record_node_event
from desmet.adapters.registry import load_platform_info
from desmet.harness.context import StageContext
from desmet.harness.models import PlatformInfo
from desmet.llm_config import Provider
from desmet.llm_config import get_config as get_llm_config

_log = logging.getLogger(__name__)


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
        # Bridges the event bus handler (registered once) to the per-stage collector
        self._current_collector: ObservationCollector | None = None
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

    def _get_model_name(self) -> str | None:
        # CrewAI creates the LLM per-run; model name is not known at init time
        return None

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
            from crewai.events.types.llm_events import LLMCallCompletedEvent, LLMCallStartedEvent

            @crewai_event_bus.on(LLMCallStartedEvent)
            def _on_llm_started(source, event) -> None:
                if self._current_collector is None:
                    return
                self._last_llm_start = time.monotonic()

            @crewai_event_bus.on(LLMCallCompletedEvent)
            def _on_llm_completed(source, event: LLMCallCompletedEvent) -> None:
                col = self._current_collector
                if col is None:
                    return
                resp = event.response
                raw_usage = getattr(resp, "usage", None)
                duration_ms = 0.0
                if self._last_llm_start > 0:
                    duration_ms = (time.monotonic() - self._last_llm_start) * 1000
                    self._last_llm_start = 0.0
                col.record_llm_response(
                    raw_usage=raw_usage,
                    duration_ms=duration_ms,
                    model=event.model,
                )
        except ImportError:
            _log.debug("crewai.events not available — per-call tracing disabled")

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
        collector: ObservationCollector,
        progress: ProgressReporter,
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
        executor_tools, reviewer_tools = split_tools(tools, self.TOOL_FORMAT)

        # ── Enriched executor context from structured plan ───────────────
        if plan is not None:
            plan_text_fmt, files_text = format_plan_text(plan)
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
                f"{retry_attempt}).\n"
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
            collector,
            progress,
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
        collector: ObservationCollector,
        context: StageContext,
        policy: RetryPolicy,
        progress: ProgressReporter,
    ) -> tuple[int, bool]:
        """Run a CrewAI crew with retry loop. Returns (iterations, hit_limit)."""
        import asyncio

        llm = self._create_llm(context)
        cfg = get_llm_config(
            model=context.model or self.config.get("model"),
            temperature=context.temperature,
        )
        model_name = cfg.model

        collector.record_message("user", prompt)

        total_iterations = 0
        hit_limit = False
        plan_text = ""
        feedback = ""
        structured_plan: ImplementationPlan | None = None

        for attempt in range(policy.total_attempts()):
            crew, counter = self._build_crew(
                stage_name, prompt, system_msg, tools, llm, context, collector,
                progress,
                retry_attempt=attempt,
                prior_plan=plan_text,
                feedback=feedback,
                plan=structured_plan,
            )

            usage_before = collector.usage_count
            self._current_collector = collector
            result = await asyncio.to_thread(crew.kickoff)
            self._current_collector = None
            collector.record_message("assistant", str(result))

            # ── Fallback: use result.token_usage if event bus recorded nothing ─
            if collector.usage_count == usage_before:
                usage = getattr(result, "token_usage", None)
                if usage is not None:
                    collector.record_llm_response(raw_usage=usage, model=model_name)

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
                        structured_plan = parse_plan_text(str(first_output))
                    plan_text = str(first_output)

            # ── Validate workspace ───────────────────────────────────────
            passed, feedback = policy.validate()
            record_node_event(
                collector.trace, "validator",
                validator_passed=passed,
                retry_count=attempt + 1,
            )

            if passed:
                progress.validation_passed()
                break

            # ── Validation failed — prepare retry or exit ────────────────
            progress.validation_failed(attempt + 1, policy.total_attempts(), feedback)

            if total_iterations >= context.max_iterations:
                hit_limit = True
                break

        if not hit_limit:
            hit_limit = total_iterations >= context.max_iterations

        collector.mark_iterations(total_iterations)
        return total_iterations, hit_limit

    # Stage methods inherited from ToolAgentAdapter

    # =========================================================================
    # Trace Callbacks
    # =========================================================================

    @staticmethod
    def _create_trace_callbacks(
        collector: ObservationCollector,
        progress: ProgressReporter,
    ) -> tuple[Any, Any, list[int]]:
        """Create ``step_callback`` and ``task_callback`` closures for a Crew.

        Returns a 3-tuple of ``(step_callback, task_callback, step_counter)``
        where *step_counter* is a single-element list whose ``[0]`` value is
        incremented on every agent step so the caller can read the true
        iteration count after ``crew.kickoff()`` returns.
        """
        counter: list[int] = [0]

        def step_callback(step_output: Any) -> None:
            """Called after every agent reasoning step."""
            counter[0] += 1

            # CrewAI step outputs vary by type.  Inspect common attributes
            # to extract tool-call information when present.
            tool_name = getattr(step_output, "tool", None)
            if tool_name:
                tool_input = getattr(step_output, "tool_input", "")
                tool_result = getattr(step_output, "result", "")
                args = tool_input if isinstance(tool_input, dict) else {"input": str(tool_input)}
                collector.record_tool_execution(str(tool_name), args, str(tool_result))
                progress.tool_call(str(tool_name), tool_input)
            elif counter[0] % 5 == 0:
                agent_role = getattr(step_output, "agent", None)
                role_str = getattr(agent_role, "role", "") if agent_role else ""
                progress.heartbeat(counter[0], role_str)

            # Always record the step as a message so the full reasoning
            # chain is visible in the trace.
            content = _summarise_step(step_output)
            collector.record_message("assistant", content, metadata={"step": counter[0]})
            collector.trace.total_iterations = counter[0]

        def task_callback(task_output: Any) -> None:
            """Called when a CrewAI Task completes."""
            collector.record_message(
                "assistant", str(task_output),
                metadata={"event": "task_complete"},
            )
            agent_name = getattr(task_output, "agent", "") or ""
            progress.agent_status(agent_name or "agent", "task complete")

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
