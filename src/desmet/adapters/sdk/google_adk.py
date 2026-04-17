"""
Google ADK Platform Adapter — SequentialAgent + LoopAgent orchestration.

Architecture:
  SequentialAgent: planner → LoopAgent[executor ⇄ reviewer] → validation
  Planner uses structured output (output_schema=ImplementationPlan).
  LoopAgent provides native retry via exit_loop tool.
  Callbacks capture per-call token/tool usage for ObservationCollector.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from desmet.adapters._shared.base import ToolAgentAdapter
from desmet.adapters._shared.observation import ObservationCollector
from desmet.adapters._shared.planning import (
    ImplementationPlan,
    build_executor_instructions,
    format_plan_text,
    parse_plan_text,
)
from desmet.adapters._shared.prompts import get_stage_persona, get_sub_persona
from desmet.adapters._shared.retry import ProgressReporter, RetryPolicy
from desmet.adapters._shared.tools import ToolFormat, split_tools
from desmet.adapters.registry import load_platform_info
from desmet.harness.context import StageContext
from desmet.harness.models import PlatformInfo
from desmet.llm_config import Provider
from desmet.llm_config import get_config as get_llm_config

_log = logging.getLogger(__name__)


class GoogleADKAdapter(ToolAgentAdapter):
    """Google ADK adapter using SequentialAgent + LoopAgent orchestration."""

    TOOL_FORMAT = ToolFormat.CALLABLE

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        # str for native Gemini, LiteLlm wrapper for everything else.
        self._model_id: Any = None
        self._model_name: str | None = None
        self._timeout_seconds: float = 120.0

    @property
    def platform_info(self) -> PlatformInfo:
        info = load_platform_info("google_adk")
        info.version = self._get_version()
        return info

    def _get_version(self) -> str:
        try:
            import google.adk

            return getattr(google.adk, "__version__", "unknown")
        except ImportError:
            return "not installed"

    def _get_model_name(self) -> str | None:
        return self._model_name

    def _resolve_model_id(self, cfg) -> Any:
        """Build the model value for ADK agents.

        Gemini models pass through as bare strings (ADK has native
        support).  Everything else is wrapped in ``LiteLlm`` — ADK only
        routes non-Gemini through LiteLLM when the ``BaseLlm`` instance
        is provided explicitly; a bare ``provider/model`` string isn't
        recognised.  Requires ``google-adk[extensions]``.
        """
        if cfg.provider == Provider.GOOGLE:
            return cfg.model
        from google.adk.models.lite_llm import LiteLlm

        prefix_map = {
            Provider.OPENAI: "openai",
            Provider.OPENROUTER: "openrouter",
            Provider.ANTHROPIC: "anthropic",
        }
        prefix = prefix_map.get(cfg.provider, "openai")
        return LiteLlm(model=f"{prefix}/{cfg.model}")

    async def initialize(self) -> None:
        try:
            from google.adk.agents import (  # noqa: F401
                Agent,  # noqa: F401
                LoopAgent,
                SequentialAgent,
            )
            from google.adk.runners import Runner  # noqa: F401

            cfg = get_llm_config(model=self.config.get("model"))
            self._model_id = self._resolve_model_id(cfg)
            self._model_name = cfg.model
            self._timeout_seconds = cfg.timeout_seconds
            self._initialized = True
        except ImportError as e:
            raise RuntimeError(
                f"Failed to import Google ADK: {e}. "
                'Install with: uv pip install "google-adk[extensions]"'
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Google ADK: {e}")

    async def shutdown(self) -> None:
        self._model_id = None
        self._model_name = None
        self._initialized = False

    async def health_check(self) -> bool:
        if not self._initialized or self._model_id is None:
            return False
        try:
            from google.adk.agents import Agent
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService
            from google.genai import types

            agent = Agent(
                name="health_check",
                model=self._model_id,
                instruction="Respond with 'ok'.",
            )
            runner = Runner(
                app_name="desmet_health",
                agent=agent,
                session_service=InMemorySessionService(),
            )
            session = await runner.session_service.create_session(
                app_name="desmet_health",
                user_id="health",
            )
            async for event in runner.run_async(
                user_id="health",
                session_id=session.id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part(text="Say 'ok'")],
                ),
            ):
                if event.is_final_response() and event.content:
                    return True
            return False
        except Exception:
            return False

    async def _run_planner(
        self,
        stage_name: str,
        prompt: str,
        collector: ObservationCollector,
        progress: ProgressReporter,
        temperature: float = 0.0,
    ) -> ImplementationPlan:
        """Run planner agent with structured output, falling back to text parsing.

        Returns an ImplementationPlan. Records planner messages and usage
        via the collector.
        """
        from google.adk.agents import Agent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        planner_persona = get_sub_persona("planner")

        # Try structured output first.
        # The planner runs in its own Runner/Session because output_schema
        # disables tool use in ADK — so it cannot share a SequentialAgent
        # with tool-using agents.  The plan is extracted from session state
        # and injected into the executor via build_executor_instructions().
        plan: ImplementationPlan | None = None
        try:
            planner = Agent(
                name=f"desmet_{stage_name}_planner",
                model=self._model_id,
                instruction=planner_persona.backstory,
                output_schema=ImplementationPlan,
                output_key="plan",  # ADK stores validated output in session.state["plan"]
                # ADK rejects output_schema alongside agent transfers — set
                # these explicitly to silence ADK's auto-correct warning.
                disallow_transfer_to_parent=True,
                disallow_transfer_to_peers=True,
                generate_content_config=types.GenerateContentConfig(
                    temperature=temperature,
                ),
            )
            session_svc = InMemorySessionService()
            runner = Runner(
                app_name="desmet_planner",
                agent=planner,
                session_service=session_svc,
            )
            session = await session_svc.create_session(
                app_name="desmet_planner",
                user_id="eval",
            )

            t0 = time.monotonic()
            async for event in runner.run_async(
                user_id="eval",
                session_id=session.id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part(text=prompt)],
                ),
            ):
                if event.content and event.content.parts:
                    text = "".join(
                        p.text for p in event.content.parts if hasattr(p, "text") and p.text
                    )
                    if text:
                        collector.record_message(
                            "assistant",
                            text,
                            metadata={"agent": "planner"},
                        )
                # Extract usage from event
                usage = getattr(event, "usage_metadata", None)
                if usage:
                    collector.record_llm_response(raw_usage=usage)

            duration_ms = (time.monotonic() - t0) * 1000
            collector.record_llm_response(raw_usage=None, duration_ms=duration_ms)

            # Extract plan from session state
            plan_data = session.state.get("plan")
            if isinstance(plan_data, ImplementationPlan):
                plan = plan_data
            elif isinstance(plan_data, dict):
                plan = ImplementationPlan.model_validate(plan_data)
            elif isinstance(plan_data, str):
                try:
                    plan = ImplementationPlan.model_validate_json(plan_data)
                except Exception:
                    plan = parse_plan_text(plan_data)
        except Exception as e:
            _log.debug("Structured planner failed: %s — falling back to text", e)

        # Fallback: free-text planning
        if plan is None:
            try:
                planner = Agent(
                    name=f"desmet_{stage_name}_planner_fallback",
                    model=self._model_id,
                    instruction=(
                        f"{planner_persona.backstory}\n\n"
                        "Produce a numbered implementation plan listing steps, "
                        "files to create, and files to modify."
                    ),
                    generate_content_config=types.GenerateContentConfig(
                        temperature=temperature,
                    ),
                )
                session_svc = InMemorySessionService()
                runner = Runner(
                    app_name="desmet_planner_fallback",
                    agent=planner,
                    session_service=session_svc,
                )
                session = await session_svc.create_session(
                    app_name="desmet_planner_fallback",
                    user_id="eval",
                )

                plan_text = ""
                t0 = time.monotonic()
                async for event in runner.run_async(
                    user_id="eval",
                    session_id=session.id,
                    new_message=types.Content(
                        role="user",
                        parts=[types.Part(text=prompt)],
                    ),
                ):
                    if event.content and event.content.parts:
                        text = "".join(
                            p.text for p in event.content.parts if hasattr(p, "text") and p.text
                        )
                        if text:
                            plan_text += text
                            collector.record_message(
                                "assistant",
                                text,
                                metadata={"agent": "planner"},
                            )

                duration_ms = (time.monotonic() - t0) * 1000
                collector.record_llm_response(raw_usage=None, duration_ms=duration_ms)
                plan = parse_plan_text(plan_text)
            except Exception:
                plan = ImplementationPlan(
                    steps=["Execute the task as described"],
                    files_to_create=[],
                    files_to_modify=[],
                )

        progress.agent_status("planner", f"{len(plan.steps)} steps planned")
        return plan

    # ── Core agent runner ─────────────────────────────────────────────

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
        """Run SequentialAgent pipeline: planner → LoopAgent[executor, reviewer].

        Returns (total_iterations, success) where success is True iff the
        workspace passes validation at the end of the run.
        """
        from google.adk.agents import Agent, LoopAgent, RunConfig, SequentialAgent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.adk.tools import exit_loop
        from google.genai import types

        total_iterations = 0

        collector.record_message("user", prompt)

        # ── Step 1: Planner ──────────────────────────────────────────────
        plan = await self._run_planner(
            stage_name,
            prompt,
            collector,
            progress,
            temperature=context.temperature,
        )
        total_iterations += 1

        # ── Step 2: Build executor and reviewer agents ───────────────────
        executor_persona = get_stage_persona(stage_name)
        reviewer_persona = get_sub_persona("reviewer")

        executor_instructions = build_executor_instructions(
            executor_persona,
            plan,
            system_msg,
        )

        executor_tools, reviewer_tools = split_tools(tools, self.TOOL_FORMAT)

        # ADK HttpOptions.timeout is in milliseconds.  Convert from the
        # seconds-based LLMConfig so a hung Gemini call surfaces as a
        # transport error instead of waiting forever.
        gen_config = types.GenerateContentConfig(
            temperature=context.temperature,
            http_options=types.HttpOptions(
                timeout=int(self._timeout_seconds * 1000),
            ),
        )

        # Callback closures for observation tracking.  ADK invokes these
        # with keyword-only arguments whose names are part of the contract
        # — renaming them (e.g. llm_response → response) raises a
        # "unexpected keyword argument" TypeError at runtime.
        def _after_model_callback(*, callback_context, llm_response):
            """Record token usage from every LLM call."""
            usage = getattr(llm_response, "usage_metadata", None)
            if usage:
                collector.record_llm_response(raw_usage=usage)
            return None

        def _after_tool_callback(*, tool, args, tool_context, tool_response):
            """Record tool execution for observation."""
            tool_name = getattr(tool, "name", "") or getattr(tool, "__name__", "unknown")
            collector.record_tool_execution(
                tool_name, args, str(tool_response) if tool_response else ""
            )
            progress.tool_call(tool_name, args)
            return None

        executor_agent = Agent(
            name=f"desmet_{stage_name}_executor",
            model=self._model_id,
            instruction=executor_instructions,
            tools=executor_tools,
            generate_content_config=gen_config,
            after_model_callback=_after_model_callback,
            after_tool_callback=_after_tool_callback,
        )

        reviewer_agent = Agent(
            name=f"desmet_{stage_name}_reviewer",
            model=self._model_id,
            instruction=(
                f"{reviewer_persona.backstory}\n\n"
                "After the executor finishes, inspect the workspace using "
                "the available tools and call check_completion to verify "
                "all artifacts are present.\n"
                "If check_completion reports VALIDATION PASSED, call exit_loop "
                "to signal completion.\n"
                "If validation fails, describe what is missing so the executor "
                "can fix it on the next iteration."
            ),
            # exit_loop sets tool_context.actions.escalate = True, which
            # tells LoopAgent to stop iterating — the ADK-native way to
            # signal "validation passed, no more executor→reviewer cycles."
            tools=reviewer_tools + [exit_loop],
            generate_content_config=gen_config,
            after_model_callback=_after_model_callback,
            after_tool_callback=_after_tool_callback,
        )

        # ── Step 3: Build LoopAgent + SequentialAgent ────────────────────
        # Budget: planner consumed 1 iteration in its own Runner above.
        # Remaining budget goes to the executor⇄reviewer loop.
        loop_budget = max(3, context.max_iterations - 1)

        execute_loop = LoopAgent(
            name=f"desmet_{stage_name}_loop",
            max_iterations=loop_budget,
            sub_agents=[executor_agent, reviewer_agent],
        )

        pipeline = SequentialAgent(
            name=f"desmet_{stage_name}_pipeline",
            sub_agents=[execute_loop],
        )

        # ── Step 4: Stream events ────────────────────────────────────────
        session_svc = InMemorySessionService()
        runner = Runner(
            app_name=f"desmet_{stage_name}",
            agent=pipeline,
            session_service=session_svc,
        )
        session = await session_svc.create_session(
            app_name=f"desmet_{stage_name}",
            user_id="eval",
        )

        # Hard ceiling on total LLM calls — RunConfig is ADK's built-in
        # iteration budget, independent of LoopAgent.max_iterations.
        run_config = RunConfig(max_llm_calls=context.max_iterations)

        run_t0 = time.monotonic()
        try:
            async for event in runner.run_async(
                user_id="eval",
                session_id=session.id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part(text=prompt)],
                ),
                run_config=run_config,
            ):
                author = getattr(event, "author", "") or ""

                # Record text content (skip final response — recorded separately)
                is_final = event.is_final_response()
                if not is_final and event.content and event.content.parts:
                    text = "".join(
                        p.text for p in event.content.parts if hasattr(p, "text") and p.text
                    )
                    if text:
                        collector.record_message(
                            "assistant",
                            text,
                            metadata={"agent": author},
                        )

                # Count agent turns (not user messages)
                if author and author != "user":
                    total_iterations += 1

                # Record final response once
                if is_final:
                    collector.record_message(
                        "assistant",
                        "".join(
                            p.text
                            for p in (event.content.parts if event.content else [])
                            if hasattr(p, "text") and p.text
                        )
                        or "(final)",
                        metadata={"event": "final_output"},
                    )

                # Check iteration limit — break out of the streaming loop;
                # final success state is decided by policy.validate() below.
                if total_iterations >= context.max_iterations:
                    break

        except Exception as e:
            _log.warning("ADK pipeline error: %s", e)
            collector.trace.errors.append(str(e))

        run_duration_ms = (time.monotonic() - run_t0) * 1000

        # Estimate LLM time (total minus tool time)
        tool_time = sum(tc.duration_ms for tc in collector.trace.tool_calls)
        llm_time_estimate = max(0.0, run_duration_ms - tool_time)
        collector.record_llm_response(raw_usage=None, duration_ms=llm_time_estimate)

        # ── Step 5: Final validation ─────────────────────────────────────
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

    # ── Metadata ──────────────────────────────────────────────────────

    def get_observability_info(self) -> dict[str, Any]:
        return {
            "has_tracing": True,
            "has_step_through": False,
            "has_replay": True,
            "has_state_inspection": True,
            "has_memory_inspection": False,
            "trace_format": "Event stream",
            "notes": (
                "SequentialAgent pipeline: planner (structured output) → "
                "LoopAgent[executor ⇄ reviewer]. Event-driven streaming "
                "with after_model_callback for per-call token tracking. "
                "Session state carries plan between agents."
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
                "LoopAgent retry with exit_loop tool for native retry. "
                "RunConfig.max_llm_calls as iteration ceiling. "
                "Session state persists across loop iterations."
            ),
        }
