"""
OpenAI Agents SDK Platform Adapter.

Uses the Agents SDK's Runner.run() with a validation/retry loop per SDLC stage.
"""
from __future__ import annotations

import json
import time
from typing import Any

from agents import Agent, ModelSettings, Runner
from agents.items import (
    MessageOutputItem,
    ToolCallItem,
    ToolCallOutputItem,
)
from openai import AsyncOpenAI

from agents.tracing import set_trace_processors

from desmet.adapters._base import ToolAgentAdapter
from desmet.adapters._prompts import get_stage_persona
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
from desmet.observability import get_openai_agents_tracing_processor

MAX_RETRIES = 3


def _format_tool_detail(name: str, raw_args: Any) -> str:
    """Format an OpenAI Agents tool call for human-readable progress logging."""
    args = raw_args if isinstance(raw_args, dict) else {}
    if not args and isinstance(raw_args, str):
        try:
            args = json.loads(raw_args)
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


class OpenAIAgentsAdapter(ToolAgentAdapter):
    """OpenAI Agents SDK adapter using Runner.run() with a retry/validation loop."""

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

    async def initialize(self) -> None:
        try:
            cfg = get_llm_config(model=self.config.get("model"))
            self._model = self._create_model(cfg)
            self._model_name = cfg.model

            # Replace the default OpenAI trace exporter with our Langfuse
            # processor.  The default BackendSpanExporter posts to
            # api.openai.com/v1/traces/ingest which rejects non-OpenAI
            # providers and unknown usage keys.
            lf_processor = get_openai_agents_tracing_processor()
            if lf_processor is not None:
                set_trace_processors([lf_processor])

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
        tool_call_count = 0
        hit_limit = False
        result = None
        t0 = time.monotonic()
        cb = context.progress_callback

        record_message(trace, "user", prompt)

        for attempt in range(MAX_RETRIES):
            if result is None:
                input_msg = prompt
            else:
                if cb is not None:
                    from desmet.adapters._tools import _check_completion
                    _, hint = _check_completion(context.workspace, stage_name)
                    elapsed = time.monotonic() - t0
                    cb(f"    validator: FAILED (attempt {attempt}/{MAX_RETRIES}) — {hint}  ({elapsed:.0f}s)")
                input_msg = result.to_input_list() + [
                    {
                        "role": "user",
                        "content": (
                            f"Validation failed (attempt {attempt}/{MAX_RETRIES}). "
                            f"Review the workspace and fix issues."
                        ),
                    }
                ]

            tool_time_before = sum(tc.duration_ms for tc in trace.tool_calls)
            run_t0 = time.monotonic()
            result = await Runner.run(agent, input=input_msg, max_turns=max_turns)
            run_duration_ms = (time.monotonic() - run_t0) * 1000

            # Extract trace data from this run
            iterations, tool_call_count = self._extract_trace(
                trace, result, cb=cb, t0=t0, tool_call_count=tool_call_count,
                model=self._model_name,
            )
            total_iterations += iterations

            tool_time_after = sum(tc.duration_ms for tc in trace.tool_calls)
            tool_time_in_run = tool_time_after - tool_time_before
            llm_time_estimate = max(0.0, run_duration_ms - tool_time_in_run)
            record_llm_duration(trace, llm_time_estimate)

            if total_iterations >= context.max_iterations:
                hit_limit = True
                break

            if validate_workspace(stage_name, str(context.workspace)):
                if cb is not None:
                    cb("    validator: PASSED")
                break

        trace.total_iterations = total_iterations
        finish_trace(trace)
        return total_iterations, hit_limit

    @staticmethod
    def _extract_trace(
        trace: AgentTrace,
        result,
        *,
        cb=None,
        t0: float = 0.0,
        tool_call_count: int = 0,
        model: str | None = None,
    ) -> tuple[int, int]:
        """Extract messages, tool calls, and usage from a RunResult.

        Returns ``(new_items_count, updated_tool_call_count)``.
        """
        for item in result.new_items:
            if isinstance(item, MessageOutputItem):
                text = item.raw_item.content[0].text if item.raw_item.content else ""
                record_message(trace, "assistant", text)
            elif isinstance(item, ToolCallItem):
                tool_call_count += 1
                call = item.raw_item
                args = call.arguments if isinstance(call.arguments, dict) else {"raw": call.arguments}
                record_tool_call(trace, name=call.name, args=args, result="")
                if cb is not None:
                    elapsed = time.monotonic() - t0
                    detail = _format_tool_detail(call.name, call.arguments)
                    tokens = trace.total_tokens_input + trace.total_tokens_output
                    cb(
                        f"    tool {tool_call_count} — {detail}"
                        f"  ({elapsed:.0f}s, {tokens:,} tokens)"
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
                    model=model,
                )

        # Record final output
        if result.final_output:
            record_message(trace, "assistant", result.final_output, metadata={"event": "final_output"})

        return len(result.new_items), tool_call_count

    # Stage methods inherited from ToolAgentAdapter

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
