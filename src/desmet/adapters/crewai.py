"""
CrewAI Platform Adapter

Implements the evaluation interface for CrewAI.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from desmet.adapters._shared.base import ToolAgentAdapter
from desmet.adapters._shared.observation import ObservationCollector
from desmet.adapters._shared.planning import ImplementationPlan, format_plan_text, parse_plan_text
from desmet.adapters._shared.prompts import STAGE_EXPECTED_OUTPUTS, get_stage_persona, get_sub_persona
from desmet.adapters._shared.retry import ProgressReporter, RetryPolicy
from desmet.adapters._shared.tools import ToolFormat, split_tools
from desmet.adapters._shared.tracing import record_node_event
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


class CrewAIAdapter(ToolAgentAdapter):
    """
    Adapter for evaluating CrewAI.

    CrewAI is a role-based multi-agent collaboration framework.
    """

    TOOL_FORMAT = ToolFormat.CREWAI

    _event_handlers_registered: bool = False

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._crew = None
        # Bridges the event bus handlers (registered once) to the per-stage
        # collector and progress reporter.  Set before kickoff, cleared after.
        self._current_collector: ObservationCollector | None = None
        self._current_progress: ProgressReporter | None = None
        self._last_llm_start: float = 0.0
        self._last_usage_snapshot: dict[str, int] = {}
        self._llm_call_count: int = 0

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

            # All tracing (LLM calls, tool usage, task completion, iteration
            # counting) via CrewAI's native event bus — fires on every
            # execution path including native function calling.
            self._register_event_handlers()

            self._initialized = True
        except ImportError as e:
            raise RuntimeError(f"Failed to import CrewAI: {e}")

    async def shutdown(self) -> None:
        self._crew = None
        self._initialized = False

    async def health_check(self) -> bool:
        return self._initialized

    # ── Event bus tracing ────────────────────────────────────────────────

    def _register_event_handlers(self) -> None:
        """Subscribe to CrewAI's event bus for all tracing.

        Replaces the legacy ``step_callback`` / ``task_callback`` closures
        that were passed to ``Crew()``.  The event bus fires for every
        execution path (ReAct text parsing *and* native function calling),
        giving complete coverage.
        """
        if CrewAIAdapter._event_handlers_registered:
            return
        try:
            from crewai.events.event_bus import crewai_event_bus
            from crewai.events.types.llm_events import LLMCallCompletedEvent, LLMCallStartedEvent
            from crewai.events.types.task_events import TaskCompletedEvent
            from crewai.events.types.tool_usage_events import ToolUsageFinishedEvent

            # ── LLM calls ───────────────────────────────────────────────

            @crewai_event_bus.on(LLMCallStartedEvent)
            def _on_llm_started(source, event) -> None:
                if self._current_collector is None:
                    return
                self._last_llm_start = time.monotonic()
                # Snapshot cumulative token counts so we can compute per-call delta
                usage = getattr(source, "_token_usage", None)
                self._last_usage_snapshot = dict(usage) if usage else {}

            @crewai_event_bus.on(LLMCallCompletedEvent)
            def _on_llm_completed(source, event: LLMCallCompletedEvent) -> None:
                col = self._current_collector
                if col is None:
                    return

                # Duration
                duration_ms = 0.0
                if self._last_llm_start > 0:
                    duration_ms = (time.monotonic() - self._last_llm_start) * 1000
                    self._last_llm_start = 0.0

                # Per-call token delta from LLM's cumulative counters
                raw_usage = None
                usage = getattr(source, "_token_usage", None)
                if usage:
                    prev = self._last_usage_snapshot
                    raw_usage = {
                        "prompt_tokens": usage.get("prompt_tokens", 0)
                        - prev.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0)
                        - prev.get("completion_tokens", 0),
                    }
                col.record_llm_response(
                    raw_usage=raw_usage,
                    duration_ms=duration_ms,
                    model=event.model,
                )

                # Iteration counting — each LLM call is one reasoning step
                self._llm_call_count += 1
                col.trace.total_iterations = self._llm_call_count

                # Record LLM response text as a message in the trace
                resp_text = str(event.response) if event.response else ""
                if resp_text:
                    col.record_message(
                        "assistant",
                        resp_text[:2000],
                        metadata={"step": self._llm_call_count},
                    )

                # Heartbeat every 5 iterations
                progress = self._current_progress
                if progress and self._llm_call_count % 5 == 0:
                    progress.heartbeat(self._llm_call_count, "")

            # ── Tool calls ──────────────────────────────────────────────

            @crewai_event_bus.on(ToolUsageFinishedEvent)
            def _on_tool_finished(source, event: ToolUsageFinishedEvent) -> None:
                col = self._current_collector
                if col is None:
                    return
                args = (
                    event.tool_args
                    if isinstance(event.tool_args, dict)
                    else {"input": str(event.tool_args)}
                )
                col.record_tool_execution(
                    event.tool_name,
                    args,
                    str(event.output or ""),
                )
                progress = self._current_progress
                if progress:
                    progress.tool_call(event.tool_name, event.tool_args)

            # ── Task completion ──────────────────────────────────────────

            @crewai_event_bus.on(TaskCompletedEvent)
            def _on_task_completed(source, event: TaskCompletedEvent) -> None:
                col = self._current_collector
                if col is None:
                    return
                output_str = str(event.output) if event.output else ""
                col.record_message(
                    "assistant",
                    output_str,
                    metadata={"event": "task_complete"},
                )
                progress = self._current_progress
                if progress:
                    agent_name = ""
                    if event.task:
                        agent = getattr(event.task, "agent", None)
                        if agent:
                            agent_name = getattr(agent, "role", "") or ""
                    progress.agent_status(agent_name or "agent", "task complete")

            CrewAIAdapter._event_handlers_registered = True
        except ImportError:
            _log.debug("crewai.events not available — event bus tracing disabled")

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
                timeout=cfg.timeout_seconds,
                max_retries=cfg.max_retries,
            )

        if cfg.provider == Provider.ANTHROPIC:
            from crewai.llms.providers.anthropic.completion import AnthropicCompletion

            return AnthropicCompletion(
                model=cfg.model,
                temperature=cfg.temperature,
                api_key=cfg.api_key,
                timeout=cfg.timeout_seconds,
                max_retries=cfg.max_retries,
            )

        if cfg.provider == Provider.GOOGLE:
            from crewai.llms.providers.gemini.completion import GeminiCompletion

            # NOTE: GeminiCompletion does not expose timeout/max_retries —
            # the native google-genai SDK doesn't surface them through
            # CrewAI's completion wrapper.  Hung calls on this path will
            # only be bounded by the stage iteration budget.
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
            timeout=cfg.timeout_seconds,
            max_retries=cfg.max_retries,
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
        *,
        retry_attempt: int = 0,
        prior_plan: str = "",
        feedback: str = "",
        plan: ImplementationPlan | None = None,
    ) -> Any:
        """Build a CrewAI crew for one execution attempt.

        First attempt (``retry_attempt == 0``): 3-agent crew (planner +
        executor + reviewer) with context chaining.

        Retry (``retry_attempt > 0``): 2-agent crew (executor + reviewer)
        with the prior plan and validation feedback injected.
        """
        from crewai import Agent, Crew, Process, Task

        is_retry = retry_attempt > 0
        planner_budget, executor_budget, reviewer_budget = _compute_iter_budget(
            context.max_iterations,
            retry=is_retry,
        )
        time_budget = context.time_budget_seconds or 0

        # Time split — executor gets the bulk of the budget (80%) because
        # it does the real work.  Planner and reviewer cap at 10% each.
        # This avoids a previous bug where the iteration ratio (60% for
        # the executor) starved CrewAI of time vs other frameworks that
        # give the main agent the full budget.
        def _time_share(fraction: float) -> int | None:
            return int(time_budget * fraction) if time_budget else None

        planner_time = _time_share(0.10)
        executor_time = _time_share(0.80)
        reviewer_time = _time_share(0.10)

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
                f"\n\n## Implementation Plan\n{plan_text_fmt}\n\n## Files\n{files_text}\n"
            )
        else:
            executor_context = ""

        # ── Executor — stage-specific persona ────────────────────────────
        executor_persona = get_stage_persona(stage_name)
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
                expected_output=("A numbered implementation plan with files to create/modify"),
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
                    "Validation report confirming all artefacts are present and correct"
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
                    "Validation report confirming all artefacts are present and correct"
                ),
                agent=reviewer_agent,
                context=[implement_task],
            )
            agents = [executor_agent, reviewer_agent]
            tasks = [implement_task, review_task]

        # planning=True disabled: redundant with our planner agent and
        # defaults to gpt-4o-mini which would introduce a second model.
        # Note: max_iter and max_execution_time are per-Agent fields in
        # crewai >=1.7; the per-agent max_iter is already set above.
        # Tracing is handled entirely via the event bus (no step/task callbacks).
        crew = Crew(
            agents=agents,
            tasks=tasks,
            process=Process.sequential,
            verbose=False,
        )
        return crew

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
        """Run a CrewAI crew with retry loop. Returns (iterations, success).

        success is True iff the workspace passes validation at the end of
        the run — exhausting the retry budget without a passing validator
        returns success=False.
        """
        import asyncio

        llm = self._create_llm(context)
        cfg = get_llm_config(
            model=context.model or self.config.get("model"),
            temperature=context.temperature,
        )
        model_name = cfg.model

        collector.record_message("user", prompt)

        total_iterations = 0
        # Tracks whether ANY attempt produced a workspace that passes
        # validation.  Once True, exhausting the iteration budget on a
        # later attempt must NOT flip success to failure: a stage that
        # produced the required artifacts before running out of budget
        # is a success.
        validation_succeeded = False
        plan_text = ""
        feedback = ""
        structured_plan: ImplementationPlan | None = None

        for attempt in range(policy.total_attempts()):
            crew = self._build_crew(
                stage_name,
                prompt,
                system_msg,
                tools,
                llm,
                context,
                retry_attempt=attempt,
                prior_plan=plan_text,
                feedback=feedback,
                plan=structured_plan,
            )

            usage_before = collector.usage_count
            llm_calls_before = self._llm_call_count
            self._current_collector = collector
            self._current_progress = progress
            result = await asyncio.to_thread(crew.kickoff)
            self._current_collector = None
            self._current_progress = None
            collector.record_message("assistant", str(result))

            # ── Fallback: use result.token_usage if event bus recorded nothing ─
            if collector.usage_count == usage_before:
                usage = getattr(result, "token_usage", None)
                if usage is not None:
                    collector.record_llm_response(raw_usage=usage, model=model_name)

            total_iterations += self._llm_call_count - llm_calls_before

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
                collector.trace,
                "validator",
                validator_passed=passed,
                retry_count=attempt + 1,
            )

            if passed:
                validation_succeeded = True
                progress.validation_passed()
                break

            # ── Validation failed — prepare retry or exit ────────────────
            progress.validation_failed(attempt + 1, policy.total_attempts(), feedback)

            if total_iterations >= context.max_iterations:
                break

        collector.mark_iterations(total_iterations)

        # Final success requires the workspace to actually pass validation
        # at the END of the run.  validation_succeeded covers mid-run
        # passes; the post-loop policy.validate() catches the case where
        # a late attempt produced the artifacts on the way out.
        if validation_succeeded:
            success = True
        else:
            success, _ = policy.validate()
        return total_iterations, success

    # Stage methods inherited from ToolAgentAdapter

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
                "up to 3 retries. Event bus for LLM, tool, and task tracing. "
                "Native function calling via provider SDKs."
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
