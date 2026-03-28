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

from desmet.adapters._base import ToolAgentAdapter
from desmet.adapters._observation import ObservationCollector
from desmet.adapters._planning import (
    ImplementationPlan,
    build_executor_instructions,
    format_plan_text,
    parse_plan_text,
)
from desmet.adapters._prompts import get_stage_persona, get_sub_persona
from desmet.adapters._retry import ProgressReporter, RetryPolicy
from desmet.adapters._tools import ToolFormat, split_tools
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
        self._model_id: str | None = None
        self._model_name: str | None = None

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

    def _resolve_model_id(self, cfg) -> str:
        """Build the model string for ADK agents.

        Gemini models pass through directly. Non-Gemini models use LiteLLM
        format (``provider/model``) which requires ``google-adk[extensions]``.
        """
        if cfg.provider == Provider.GOOGLE:
            return cfg.model
        prefix_map = {
            Provider.OPENAI: "openai",
            Provider.OPENROUTER: "openrouter",
            Provider.ANTHROPIC: "anthropic",
        }
        prefix = prefix_map.get(cfg.provider, "openai")
        return f"{prefix}/{cfg.model}"

    async def initialize(self) -> None:
        try:
            from google.adk.agents import Agent  # noqa: F401
            from google.adk.agents import SequentialAgent, LoopAgent  # noqa: F401
            from google.adk.runners import Runner  # noqa: F401

            cfg = get_llm_config(model=self.config.get("model"))
            self._model_id = self._resolve_model_id(cfg)
            self._model_name = cfg.model
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
                app_name="desmet_health", user_id="health",
            )
            async for event in runner.run_async(
                user_id="health",
                session_id=session.id,
                new_message=types.Content(
                    role="user", parts=[types.Part(text="Say 'ok'")],
                ),
            ):
                if event.is_final_response() and event.content:
                    return True
            return False
        except Exception:
            return False

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

        Returns (total_iterations, hit_limit).
        """
        # Placeholder — will be implemented in Task 6
        return 0, False

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
