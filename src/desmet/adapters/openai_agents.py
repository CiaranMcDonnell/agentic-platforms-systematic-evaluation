"""
OpenAI Agents SDK Platform Adapter.

Uses the Agents SDK's Runner.run() with a validation/retry loop per SDLC stage.
"""
from __future__ import annotations

from typing import Any

from agents import Agent, ModelSettings, Runner
from agents.items import (
    MessageOutputItem,
    ToolCallItem,
    ToolCallOutputItem,
)
from openai import AsyncOpenAI

from desmet.adapters._prompts import (
    build_codegen_prompt,
    build_deploy_prompt,
    build_requirements_prompt,
    build_system_message,
    build_testing_prompt,
    get_stage_persona,
)
from desmet.adapters._tools import ToolFormat, create_tools
from desmet.adapters._tracing import (
    build_stage_result,
    finish_trace,
    record_message,
    record_tool_call,
    record_usage,
    start_trace,
)
from desmet.adapters._validation import validate_workspace
from desmet.adapters.registry import load_platform_info
from desmet.harness.adapter import BasePlatformAdapter
from desmet.harness.context import StageContext
from desmet.harness.models import PlatformInfo
from desmet.harness.results import (
    CodeResult,
    DeployResult,
    RequirementsResult,
    TestResult,
)
from desmet.harness.trace import AgentTrace
from desmet.llm_config import Provider
from desmet.llm_config import get_config as get_llm_config

MAX_RETRIES = 3


class OpenAIAgentsAdapter(BasePlatformAdapter):
    """OpenAI Agents SDK adapter using Runner.run() with a retry/validation loop."""

    TOOL_FORMAT = ToolFormat.OPENAI_AGENTS

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._model = None

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

    async def initialize(self) -> None:
        try:
            cfg = get_llm_config(model=self.config.get("model"))
            self._model = self._create_model(cfg)
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

        from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

        client = AsyncOpenAI(base_url=cfg.base_url, api_key=cfg.api_key)
        return OpenAIChatCompletionsModel(model=cfg.model, openai_client=client)

    async def shutdown(self) -> None:
        self._model = None
        self._initialized = False

    async def health_check(self) -> bool:
        if not self._initialized or self._model is None:
            return False
        try:
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
        trace: AgentTrace,
        context: StageContext,
    ) -> tuple[int, bool]:
        """Run an OpenAI Agent with retry/validation loop.

        Returns (total_iterations, hit_limit).
        """
        persona = get_stage_persona(stage_name)
        instructions = persona.backstory
        if system_msg:
            instructions = f"{instructions}\n\n{system_msg}"

        agent = Agent(
            name=f"desmet-{stage_name}",
            instructions=instructions,
            model=self._model,
            tools=tools,
            model_settings=ModelSettings(temperature=context.temperature),
        )

        max_turns = context.max_iterations // MAX_RETRIES
        total_iterations = 0
        hit_limit = False
        result = None

        record_message(trace, "user", prompt)

        for attempt in range(MAX_RETRIES):
            if result is None:
                input_msg = prompt
            else:
                input_msg = result.to_input_list() + [
                    {
                        "role": "user",
                        "content": (
                            f"Validation failed (attempt {attempt}/{MAX_RETRIES}). "
                            f"Review the workspace and fix issues."
                        ),
                    }
                ]

            result = await Runner.run(agent, input=input_msg, max_turns=max_turns)

            # Extract trace data from this run
            iterations = self._extract_trace(trace, result)
            total_iterations += iterations

            if total_iterations >= context.max_iterations:
                hit_limit = True
                break

            if validate_workspace(stage_name, str(context.workspace)):
                break

        trace.total_iterations = total_iterations
        finish_trace(trace)
        return total_iterations, hit_limit

    @staticmethod
    def _extract_trace(trace: AgentTrace, result) -> int:
        """Extract messages, tool calls, and usage from a RunResult.

        Returns the number of new_items processed (used as iteration count).
        """
        # Messages and tool calls from new_items
        for item in result.new_items:
            if isinstance(item, MessageOutputItem):
                text = item.raw_item.content[0].text if item.raw_item.content else ""
                record_message(trace, "assistant", text)
            elif isinstance(item, ToolCallItem):
                call = item.raw_item
                record_tool_call(
                    trace,
                    name=call.name,
                    args=call.arguments if isinstance(call.arguments, dict) else {"raw": call.arguments},
                    result="",
                )
            elif isinstance(item, ToolCallOutputItem):
                record_message(
                    trace, "tool", str(item.output),
                    metadata={"tool_call_id": getattr(item.raw_item, "call_id", "")},
                )

        # Token usage from raw_responses
        for resp in result.raw_responses:
            usage = getattr(resp, "usage", None)
            if usage:
                record_usage(
                    trace,
                    input_tokens=getattr(usage, "input_tokens", 0) or getattr(usage, "prompt_tokens", 0) or 0,
                    output_tokens=getattr(usage, "output_tokens", 0) or getattr(usage, "completion_tokens", 0) or 0,
                )

        # Record final output
        if result.final_output:
            record_message(trace, "assistant", result.final_output, metadata={"event": "final_output"})

        return len(result.new_items)

    # ── SDLC stage methods ────────────────────────────────────────────────

    async def _execute_stage(self, stage_name, prompt_fn, result_cls, context):
        trace = start_trace()
        try:
            if stage_name == "codegen":
                prior = context.get_prior_result("requirements")
                prompt = prompt_fn(context.story, prior_requirements=prior)
            else:
                prompt = prompt_fn(context.story)
            system_msg = build_system_message(context.story)
            tools = create_tools(
                context.workspace, context.allowed_tools, fmt=self.TOOL_FORMAT,
                platform_id=context.platform_id, story_id=context.story.id,
            )
            iterations, hit_limit = await self._run_agent(
                stage_name, prompt, system_msg, tools, trace, context,
            )
            return build_stage_result(
                result_cls, self.platform_info.id, stage_name,
                trace, success=not hit_limit, iterations=iterations,
            )
        except Exception as e:
            finish_trace(trace, error=str(e))
            return build_stage_result(
                result_cls, self.platform_info.id, stage_name,
                trace, success=False, iterations=0, error_message=str(e),
            )

    async def generate_requirements(self, context: StageContext) -> RequirementsResult:
        return await self._execute_stage("requirements", build_requirements_prompt, RequirementsResult, context)

    async def generate_code(self, context: StageContext) -> CodeResult:
        return await self._execute_stage("codegen", build_codegen_prompt, CodeResult, context)

    async def generate_tests(self, context: StageContext) -> TestResult:
        return await self._execute_stage("testing", build_testing_prompt, TestResult, context)

    async def build_and_deploy(self, context: StageContext) -> DeployResult:
        return await self._execute_stage("deploy", build_deploy_prompt, DeployResult, context)

    # ── Metadata ─────────────────────────────────────────────────────────

    def get_observability_info(self) -> dict[str, Any]:
        return {
            "has_tracing": True,
            "has_step_through": False,
            "has_replay": False,
            "has_state_inspection": False,
            "has_memory_inspection": False,
            "trace_format": "RunResult",
            "notes": "Token usage from RunResult.raw_responses; message/tool trace from new_items",
        }

    def get_failure_handling_info(self) -> dict[str, Any]:
        return {
            "has_checkpointing": False,
            "has_auto_recovery": True,
            "has_graceful_degradation": True,
            "supports_human_handoff": False,
            "is_idempotent": True,
            "notes": "Retry/validation loop: up to 3 attempts per stage with conversation carry-forward",
        }
