"""
OpenAI Agents SDK Platform Adapter.

Uses a 3-agent handoff chain: planner (structured output) → executor → reviewer.
The reviewer carries an output guardrail that validates the workspace; on failure
the executor retries with conversation carry-forward.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from desmet.adapters._base import ToolAgentAdapter
from desmet.adapters._planning import ImplementationPlan, build_executor_instructions, parse_plan_text
from desmet.adapters._prompts import get_stage_persona, get_sub_persona
from desmet.adapters._tools import ToolFormat
from desmet.adapters._observation import ObservationCollector
from desmet.adapters._retry import ProgressReporter, RetryPolicy
from desmet.adapters._validation import validate_workspace
from desmet.adapters.registry import load_platform_info
from desmet.harness.context import StageContext
from desmet.harness.models import PlatformInfo
from desmet.llm_config import Provider
from desmet.llm_config import get_config as get_llm_config


# ── Data models ───────────────────────────────────────────────────────────────


@dataclass
class OpenAIRunContext:
    """Adapter-local context passed through RunContextWrapper."""

    stage_context: Any  # StageContext, but Any to avoid circular imports
    plan: ImplementationPlan | None = None


# ── Guardrail factory ─────────────────────────────────────────────────────────


def _make_workspace_guardrail(stage_name: str, workspace: str):
    """Create an output guardrail that validates the workspace."""
    from agents import output_guardrail
    from agents.guardrail import GuardrailFunctionOutput

    @output_guardrail
    async def workspace_guardrail(ctx, agent, output):
        passed = validate_workspace(stage_name, workspace)
        return GuardrailFunctionOutput(
            output_info={"passed": passed, "stage": stage_name},
            tripwire_triggered=not passed,
        )

    return workspace_guardrail


# ── Adapter ───────────────────────────────────────────────────────────────────


class OpenAIAgentsAdapter(ToolAgentAdapter):
    """OpenAI Agents SDK adapter using a handoff chain with structured output and guardrails."""

    TOOL_FORMAT = ToolFormat.OPENAI_AGENTS

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._model = None
        self._model_name: str | None = None

    @property
    def platform_info(self) -> PlatformInfo:
        info = load_platform_info("openai_agents_sdk")
        info.version = self._get_version()
        return info

    def _get_version(self) -> str:
        try:
            import agents
            return getattr(agents, "__version__", "unknown")
        except ImportError:
            return "not installed"

    def _get_model_name(self) -> str | None:
        return self._model_name

    async def initialize(self) -> None:
        try:
            from agents import Agent, ModelSettings, Runner
            from agents.tracing import set_trace_processors

            cfg = get_llm_config(model=self.config.get("model"))
            self._model = self._create_model(cfg)
            self._model_name = cfg.model

            # Replace the default OpenAI trace exporter with our Langfuse
            # processor.  The default BackendSpanExporter posts to
            # api.openai.com/v1/traces/ingest which rejects non-OpenAI
            # providers and unknown usage keys.
            try:
                from desmet.observability import get_openai_agents_tracing_processor
                lf_processor = get_openai_agents_tracing_processor()
                if lf_processor is not None:
                    set_trace_processors([lf_processor])
            except (ImportError, AttributeError):
                pass

            self._initialized = True
        except ImportError as e:
            raise RuntimeError(f"Failed to import OpenAI Agents SDK: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize OpenAI Agents SDK: {e}")

    @staticmethod
    def _create_model(cfg):
        """Build the model reference for Agent().

        Returns a plain string for native OpenAI, or an
        OpenAIChatCompletionsModel for other providers.
        """
        if cfg.provider == Provider.OPENAI:
            return cfg.model

        from openai import AsyncOpenAI
        from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

        client = AsyncOpenAI(
            base_url=cfg.base_url,
            api_key=cfg.api_key,
            timeout=cfg.timeout_seconds,
            max_retries=cfg.max_retries,
        )
        return OpenAIChatCompletionsModel(model=cfg.model, openai_client=client)

    async def shutdown(self) -> None:
        self._model = None
        self._initialized = False

    async def health_check(self) -> bool:
        if not self._initialized or self._model is None:
            return False
        try:
            from agents import Agent, Runner

            agent = Agent(
                name="health_check",
                instructions="Respond with 'ok'.",
                model=self._model,
            )
            result = await Runner.run(agent, input="Say 'ok'", max_turns=1)
            return len(result.final_output or "") > 0
        except Exception:
            return False

    # ── Core agent runner ─────────────────────────────────────────────────

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
        """Run a 3-agent handoff chain: planner → executor → reviewer.

        Returns (total_iterations, success) where success is True iff the
        workspace passes validation at the end of the run.
        """
        from agents import Agent, ModelSettings, Runner
        from agents.exceptions import MaxTurnsExceeded, OutputGuardrailTripwireTriggered

        planner_persona = get_sub_persona("planner")
        executor_persona = get_stage_persona(stage_name)
        reviewer_persona = get_sub_persona("reviewer")

        total_iterations = 0
        tool_call_count = 0
        validation_succeeded = False

        collector.record_message("user", prompt)

        # ── Step 1: Planner agent ────────────────────────────────────────
        # Try structured output (output_type) first — only works with
        # OpenAI models.  Fall back to free-text planning for other models.
        plan: ImplementationPlan | None = None
        try:
            planner = Agent(
                name=f"desmet_{stage_name}_planner",
                instructions=planner_persona.backstory,
                model=self._model,
                output_type=ImplementationPlan,
                model_settings=ModelSettings(temperature=context.temperature),
            )
            planner_result = await Runner.run(planner, input=prompt, max_turns=3)

            if isinstance(planner_result.final_output, ImplementationPlan):
                plan = planner_result.final_output
        except Exception:
            pass  # structured output not supported — fall back below

        if plan is None:
            # Free-text fallback: no output_type, parse steps from text
            planner = Agent(
                name=f"desmet_{stage_name}_planner",
                instructions=(
                    f"{planner_persona.backstory}\n\n"
                    "Produce a numbered implementation plan listing steps, "
                    "files to create, and files to modify."
                ),
                model=self._model,
                model_settings=ModelSettings(temperature=context.temperature),
            )
            planner_result = await Runner.run(planner, input=prompt, max_turns=3)
            text = str(planner_result.final_output or "")
            plan = parse_plan_text(text)

        iters, tool_call_count = self._extract_trace(
            collector, planner_result, progress=progress,
            tool_call_count=tool_call_count,
        )
        total_iterations += iters

        progress.agent_status("planner", f"{len(plan.steps)} steps planned")

        # ── Step 2: Build executor + reviewer agents ───────────────────────
        guardrail = _make_workspace_guardrail(stage_name, str(context.workspace))

        reviewer_agent = Agent(
            name=f"desmet_{stage_name}_reviewer",
            instructions=reviewer_persona.backstory,
            model=self._model,
            tools=tools,
            output_guardrails=[guardrail],
            model_settings=ModelSettings(temperature=context.temperature),
        )

        # Dynamic executor instructions: persona + plan + system_msg
        executor_instructions = build_executor_instructions(
            executor_persona, plan, system_msg,
        )

        executor_agent = Agent(
            name=f"desmet_{stage_name}_executor",
            instructions=executor_instructions,
            model=self._model,
            tools=tools,
            handoffs=[reviewer_agent],
            model_settings=ModelSettings(temperature=context.temperature),
        )

        # ── Step 3: Retry loop ─────────────────────────────────────────────
        # Give each attempt a generous turn budget. The planner used ~3 turns,
        # so the remaining budget is split across retry attempts.
        max_turns = max(10, (context.max_iterations - 3) // max(1, policy.max_retries))
        result = None
        last_feedback = ""

        for attempt in range(policy.total_attempts()):
            try:
                if result is None:
                    input_msg = prompt
                else:
                    # Retry with conversation carry-forward AND the actual
                    # validator feedback so the model knows what to fix.
                    input_msg = result.to_input_list() + [
                        {
                            "role": "user",
                            "content": (
                                f"Validation failed (attempt {attempt}/{policy.total_attempts()}). "
                                f"Validator feedback:\n{last_feedback or '(no feedback available)'}\n"
                                f"Address the specific issue above before stopping."
                            ),
                        }
                    ]

                tool_time_before = sum(tc.duration_ms for tc in collector.trace.tool_calls)
                run_t0 = time.monotonic()
                result = await Runner.run(executor_agent, input=input_msg, max_turns=max_turns)
                run_duration_ms = (time.monotonic() - run_t0) * 1000

                iters, tool_call_count = self._extract_trace(
                    collector, result, progress=progress,
                    tool_call_count=tool_call_count,
                )
                total_iterations += iters

                tool_time_after = sum(tc.duration_ms for tc in collector.trace.tool_calls)
                tool_time_in_run = tool_time_after - tool_time_before
                llm_time_estimate = max(0.0, run_duration_ms - tool_time_in_run)
                collector.record_llm_response(raw_usage=None, duration_ms=llm_time_estimate)

                # Reaching here means Runner.run() completed without
                # OutputGuardrailTripwireTriggered → the work passed
                # validation.  Report success even if the iteration
                # count happens to land at or above max_iterations: a
                # stage that produced the required artifacts within the
                # budget is a success, not a budget overrun.
                progress.validation_passed()
                validation_succeeded = True
                break

            except OutputGuardrailTripwireTriggered:
                total_iterations += 1
                _, last_feedback = policy.validate()
                progress.validation_failed(attempt + 1, policy.total_attempts(), last_feedback)
                if total_iterations >= context.max_iterations:
                    break
                continue

            except MaxTurnsExceeded:
                # Executor/reviewer exhausted their turn budget — treat as retry
                total_iterations += max_turns
                progress.agent_status("executor", f"max turns exceeded (attempt {attempt + 1}/{policy.total_attempts()})")
                # Pull current feedback so the next retry (if any) tells
                # the model what's still missing.
                _, last_feedback = policy.validate()
                if total_iterations >= context.max_iterations:
                    break
                continue

        collector.mark_iterations(total_iterations)

        # Final success requires the workspace to actually pass validation.
        # Falling out of the retry loop without validation_succeeded means
        # we exhausted attempts — that MUST be reported as failure.
        if validation_succeeded:
            success = True
        else:
            success, _ = policy.validate()
        return total_iterations, success

    @staticmethod
    def _extract_trace(
        collector: ObservationCollector,
        result,
        *,
        progress: ProgressReporter,
        tool_call_count: int = 0,
    ) -> tuple[int, int]:
        """Extract messages, tool calls, and usage from a RunResult.

        Returns ``(new_items_count, updated_tool_call_count)``.
        """
        from agents.items import (
            MessageOutputItem,
            ToolCallItem,
            ToolCallOutputItem,
        )

        for item in result.new_items:
            if isinstance(item, MessageOutputItem):
                text = getattr(item.raw_item.content[0], "text", "") if item.raw_item.content else ""
                collector.record_message("assistant", text)
            elif isinstance(item, ToolCallItem):
                tool_call_count += 1
                call = item.raw_item
                args = call.arguments if isinstance(call.arguments, dict) else {"raw": call.arguments}
                collector.record_tool_execution(name=call.name, args=args, result="")
                progress.tool_call(call.name, call.arguments)
            elif isinstance(item, ToolCallOutputItem):
                collector.record_message(
                    "tool", str(item.output),
                    metadata={"tool_call_id": getattr(item.raw_item, "call_id", "")},
                )

        # Token usage from raw_responses
        for resp in result.raw_responses:
            collector.record_llm_response(raw_usage=getattr(resp, "usage", None))

        # Record final output
        if result.final_output:
            collector.record_message("assistant", str(result.final_output), metadata={"event": "final_output"})

        return len(result.new_items), tool_call_count

    # Stage methods inherited from ToolAgentAdapter

    # ── Metadata ─────────────────────────────────────────────────────────

    def get_observability_info(self) -> dict[str, Any]:
        return {
            "has_tracing": True,
            "has_step_through": False,
            "has_replay": False,
            "has_state_inspection": True,
            "has_memory_inspection": False,
            "trace_format": "RunResult",
            "notes": (
                "Handoff chain: planner (structured output) → executor → reviewer. "
                "RunConfig provides workflow_name and trace_id for Langfuse."
            ),
        }

    def get_failure_handling_info(self) -> dict[str, Any]:
        return {
            "has_checkpointing": False,
            "has_auto_recovery": True,
            "has_graceful_degradation": True,
            "supports_human_handoff": False,
            "is_idempotent": True,
            "notes": (
                "Output guardrail on reviewer triggers retry via conversation carry-forward. "
                "Structured planner output prevents malformed plans."
            ),
        }
