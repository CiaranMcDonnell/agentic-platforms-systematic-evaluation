"""
OpenAI Agents SDK Platform Adapter.

Uses a 3-agent handoff chain: planner (structured output) → executor → reviewer.
The reviewer carries an output guardrail that validates the workspace; on failure
the executor retries with conversation carry-forward.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from desmet.adapters._shared.budget import mark_budget_exhausted, remaining_llm_calls
from desmet.adapters._shared.base import ToolAgentAdapter
from desmet.adapters._shared.planning import ImplementationPlan, build_executor_instructions, parse_plan_text
from desmet.adapters._shared.prompts import get_stage_persona, get_sub_persona
from desmet.adapters._shared.tools import ToolFormat, split_tools
from desmet.adapters._shared.observation import ObservationCollector
from desmet.adapters._shared.retry import ProgressReporter, RetryPolicy
from desmet.adapters._shared.validation import validate_workspace
from desmet.adapters.registry import load_platform_info
from desmet.harness.context import StageContext
from desmet.harness.models import PlatformInfo
from desmet.llm_config import Provider
from desmet.llm_config import get_config as get_llm_config


_log = logging.getLogger(__name__)


def _item_metadata(item: Any) -> dict[str, Any]:
    """Trace metadata naming the agent that produced a ``RunItem``.

    Every Agents SDK run item carries the ``Agent`` that emitted it, which is
    the only place the handoff chain (planner → executor → reviewer) is
    visible in the local trace.
    """
    agent = getattr(item, "agent", None)
    name = getattr(agent, "name", None) if agent is not None else None
    return {"agent": str(name)} if name else {}


def _conversation(run) -> list:
    """Input items for continuing *run* (a RunResult or RunErrorDetails).

    Mirrors ``RunResultBase.to_input_list``, which RunErrorDetails lacks.
    """
    from agents import ItemHelpers

    return ItemHelpers.input_to_new_input_list(run.input) + [
        item.to_input_item() for item in run.new_items
    ]


# ── Data models ───────────────────────────────────────────────────────────────



def _build_run_hooks(collector: ObservationCollector, progress: ProgressReporter) -> Any:
    """RunHooks that record each LLM call's usage and duration as it ends
    and emit tool progress as each tool starts (so timeout lower bounds and
    the live log see OpenAI runs like the streaming adapters)."""
    from agents import RunHooks

    class _UsageHooks(RunHooks):
        def __init__(self) -> None:
            self._t0: float | None = None

        async def on_llm_start(self, context, agent, system_prompt, input_items) -> None:
            self._t0 = time.monotonic()

        async def on_llm_end(self, context, agent, response) -> None:
            duration_ms = 0.0
            if self._t0 is not None:
                duration_ms = (time.monotonic() - self._t0) * 1000
                self._t0 = None
            collector.record_llm_response(
                raw_usage=getattr(response, "usage", None), duration_ms=duration_ms,
            )

        async def on_tool_start(self, context, agent, tool) -> None:
            progress.tool_call(getattr(tool, "name", "tool"), {})

    return _UsageHooks()

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
        from agents.exceptions import (
            AgentsException,
            MaxTurnsExceeded,
            OutputGuardrailTripwireTriggered,
        )

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
        plan_source = "structured"
        # The structured attempt's run (or the run_data of the exception it
        # raised, e.g. MaxTurnsExceeded): its calls count either way.
        planner_result = None
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
        except (NotImplementedError, TypeError, ValueError) as exc:
            # Known provider/model incompatibilities with structured output.
            _log.warning("Structured planner unavailable; falling back to free-text: %s", exc)
            plan_source = "freetext"
            planner_result = getattr(exc, "run_data", None)
        except Exception as exc:  # noqa: BLE001 — we want to record, not suppress
            # Unexpected failure — record to trace.errors so the run is auditable.
            _log.warning("Structured planner failed unexpectedly: %s", exc)
            collector.trace.errors.append(
                f"planner_structured_failed: {type(exc).__name__}: {exc}"
            )
            plan_source = "fallback_error"
            planner_result = getattr(exc, "run_data", None)

        if plan is None:
            # The failed structured attempt still made (and paid for) its
            # LLM calls: record them before the free-text run replaces it.
            if planner_result is not None:
                iters, tool_call_count = self._extract_trace(
                    collector, planner_result, progress=progress,
                    tool_call_count=tool_call_count,
                )
                total_iterations += iters
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
            if plan_source == "structured":
                plan_source = "freetext"

        collector.trace.metadata["plan_source"] = plan_source

        iters, tool_call_count = self._extract_trace(
            collector, planner_result, progress=progress,
            tool_call_count=tool_call_count,
        )
        total_iterations += iters

        progress.agent_status("planner", f"{len(plan.steps)} steps planned")

        # ── Step 2: Build executor + reviewer agents ───────────────────────
        # Asymmetric tool distribution (parity invariant): the reviewer
        # gets inspection tools only (read_file, list_directory,
        # search_code, check_completion).  Giving the reviewer write or
        # execute tools would let it "fix" the workspace itself, which
        # defeats the point of having a separate reviewer.
        executor_tools, reviewer_tools = split_tools(tools, ToolFormat.OPENAI_AGENTS)

        guardrail = _make_workspace_guardrail(stage_name, str(context.workspace))

        reviewer_agent = Agent(
            name=f"desmet_{stage_name}_reviewer",
            instructions=reviewer_persona.backstory,
            model=self._model,
            tools=reviewer_tools,
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
            tools=executor_tools,
            handoffs=[reviewer_agent],
            model_settings=ModelSettings(temperature=context.temperature),
        )

        # Executor/reviewer runs record usage, durations and tool progress
        # per call as they happen, so a run that dies mid-way (API error,
        # ModelBehaviorError) keeps the tokens it spent, as the streaming
        # adapters do. _extract_trace then skips usage for these runs.
        run_hooks = _build_run_hooks(collector, progress)

        # ── Step 3: Retry loop ─────────────────────────────────────────────
        # Shared per-stage LLM-call budget (budget.py).  One turn is one LLM
        # call, so each attempt's max_turns is whatever the planner and
        # earlier attempts left; running out ends the stage.
        result = None
        # The latest run's data, successful (RunResult) or not (the
        # RunErrorDetails on a guardrail/max-turns exception), so a retry
        # carries the conversation forward either way.
        last_run = None
        last_feedback = ""

        for attempt in range(policy.total_attempts()):
            max_turns = remaining_llm_calls(collector.trace, context.max_iterations)
            if max_turns <= 0:
                mark_budget_exhausted(collector.trace)
                break
            try:
                if last_run is None:
                    input_msg = prompt
                else:
                    # Retry with conversation carry-forward AND the actual
                    # validator feedback so the model knows what to fix.
                    input_msg = _conversation(last_run) + [
                        {
                            "role": "user",
                            "content": (
                                f"Validation failed (attempt {attempt}/{policy.total_attempts()}). "
                                f"Validator feedback:\n{last_feedback or '(no feedback available)'}\n"
                                f"Address the specific issue above before stopping."
                            ),
                        }
                    ]

                result = await Runner.run(
                    executor_agent, input=input_msg, max_turns=max_turns, hooks=run_hooks,
                )
                last_run = result

                iters, tool_call_count = self._extract_trace(
                    collector, result, progress=progress,
                    tool_call_count=tool_call_count, live_hooks=True,
                )
                total_iterations += iters

                # Reaching here means Runner.run() completed without
                # OutputGuardrailTripwireTriggered.  The guardrail only
                # fires when the executor hands off to the reviewer; if
                # the executor returns a final output directly, the
                # workspace was never validated.  Validate unconditionally
                # here so executor-final-output runs cannot report
                # success without the artifacts actually being present.
                success, feedback = policy.validate()
                if success:
                    progress.validation_passed()
                    validation_succeeded = True
                    break
                else:
                    last_feedback = feedback
                    total_iterations += 1
                    progress.validation_failed(
                        attempt + 1, policy.total_attempts(), last_feedback,
                    )
                    continue

            except OutputGuardrailTripwireTriggered as exc:
                # The aborted run's model calls still cost tokens; record
                # them instead of dropping them.
                if exc.run_data is not None:
                    last_run = exc.run_data
                    iters, tool_call_count = self._extract_trace(
                        collector, exc.run_data, progress=progress,
                        tool_call_count=tool_call_count, live_hooks=True,
                    )
                    total_iterations += iters
                total_iterations += 1
                _, last_feedback = policy.validate()
                progress.validation_failed(attempt + 1, policy.total_attempts(), last_feedback)
                continue

            except MaxTurnsExceeded as exc:
                # max_turns is the remaining LLM-call budget, so hitting it
                # means the stage's budget is spent: no further attempts.
                if exc.run_data is not None:
                    last_run = exc.run_data
                    iters, tool_call_count = self._extract_trace(
                        collector, exc.run_data, progress=progress,
                        tool_call_count=tool_call_count, live_hooks=True,
                    )
                    total_iterations += iters
                else:
                    total_iterations += max_turns
                progress.agent_status(
                    "executor", f"LLM-call budget exhausted (attempt {attempt + 1}/{policy.total_attempts()})"
                )
                mark_budget_exhausted(collector.trace)
                break

            except AgentsException as exc:
                # Any other SDK error (e.g. ModelBehaviorError on a
                # hallucinated tool name) ends this attempt, not the stage:
                # keep its items, record the error, and retry with the
                # validator's feedback like a failed validation.
                collector.trace.errors.append(f"{type(exc).__name__}: {exc}")
                if exc.run_data is not None:
                    last_run = exc.run_data
                    iters, tool_call_count = self._extract_trace(
                        collector, exc.run_data, progress=progress,
                        tool_call_count=tool_call_count, live_hooks=True,
                    )
                    total_iterations += iters
                total_iterations += 1
                _, last_feedback = policy.validate()
                progress.validation_failed(attempt + 1, policy.total_attempts(), last_feedback)
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
        live_hooks: bool = False,
    ) -> tuple[int, int]:
        """Extract messages, tool calls, and usage from a RunResult.

        With *live_hooks* the run was made with ``_build_run_hooks``, which
        already recorded usage and emitted tool progress per call; only
        messages and tool-call records are taken from the result then.

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
                collector.record_message("assistant", text, metadata=_item_metadata(item))
            elif isinstance(item, ToolCallItem):
                tool_call_count += 1
                call = item.raw_item
                args = call.arguments if isinstance(call.arguments, dict) else {"raw": call.arguments}
                collector.record_tool_execution(name=call.name, args=args, result="")
                if not live_hooks:
                    progress.tool_call(call.name, call.arguments)
            elif isinstance(item, ToolCallOutputItem):
                collector.record_message(
                    "tool", str(item.output),
                    metadata={
                        "tool_call_id": getattr(item.raw_item, "call_id", ""),
                        **_item_metadata(item),
                    },
                )

        # Token usage from raw_responses
        if not live_hooks:
            for resp in result.raw_responses:
                collector.record_llm_response(raw_usage=getattr(resp, "usage", None))

        # Record final output
        if getattr(result, "final_output", None):
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
