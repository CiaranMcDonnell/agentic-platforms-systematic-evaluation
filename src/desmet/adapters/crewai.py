"""
CrewAI Platform Adapter

Implements the evaluation interface for CrewAI.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

from desmet.adapters._prompts import (
    STAGE_EXPECTED_OUTPUTS,
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

_log = logging.getLogger(__name__)


def _summarise_step(step_output: Any) -> str:
    """Return a readable string for a CrewAI step output.

    Prefers ``log`` / ``text`` (the LLM reasoning text).  Falls back to a
    compact summary when ``str()`` would produce a multi-kilobyte Agent/Crew
    repr that obscures the actual reasoning content.
    """
    import re

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


# ---------------------------------------------------------------------------
# HTTP interceptor for cost extraction
# ---------------------------------------------------------------------------

class _CostInterceptor:
    """Extracts ``usage.cost`` from raw HTTP responses (e.g. OpenRouter).

    Plugs into CrewAI's ``BaseInterceptor`` transport hook so we can read
    cost data from the response JSON before the provider SDK parses it.

    Falls back to a plain object (no interception) when CrewAI's hook
    infrastructure is not available.
    """

    def __init__(self) -> None:
        self.total_cost: float = 0.0
        self._cost_lock = threading.Lock()
        self._interceptor: Any = None
        self._init_interceptor()

    def _init_interceptor(self) -> None:
        """Try to create a real BaseInterceptor subclass."""
        try:
            import httpx
            from crewai.llms.hooks.base import BaseInterceptor

            outer = self

            class _Inner(BaseInterceptor[httpx.Request, httpx.Response]):
                def on_outbound(self, request: httpx.Request) -> httpx.Request:
                    return request

                def on_inbound(self, response: httpx.Response) -> httpx.Response:
                    try:
                        # Ensure body is loaded at the transport layer;
                        # .content caches after .read() so downstream
                        # consumers (OpenAI SDK) can re-read safely.
                        response.read()
                        body = json.loads(response.content)
                        cost = body.get("usage", {}).get("cost", 0)
                        if cost:
                            with outer._cost_lock:
                                outer.total_cost += float(cost)
                    except (json.JSONDecodeError, AttributeError, TypeError):
                        pass
                    return response

            self._interceptor = _Inner()
        except ImportError:
            _log.debug("crewai.llms.hooks not available — cost interception disabled")

    @property
    def interceptor(self) -> Any:
        """Return the underlying ``BaseInterceptor`` instance (or ``None``)."""
        return self._interceptor

    def reset(self) -> None:
        with self._cost_lock:
            self.total_cost = 0.0


class CrewAIAdapter(BasePlatformAdapter):
    """
    Adapter for evaluating CrewAI.

    CrewAI is a role-based multi-agent collaboration framework.
    """

    TOOL_FORMAT = ToolFormat.CREWAI

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._crew = None
        self._cost_interceptor = _CostInterceptor()

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

            self._initialized = True
        except ImportError as e:
            raise RuntimeError(f"Failed to import CrewAI: {e}")

    async def shutdown(self) -> None:
        self._crew = None
        self._initialized = False

    async def health_check(self) -> bool:
        return self._initialized

    def _create_llm(self, context: StageContext):
        """Build a CrewAI LLM from centralised config + stage context overrides.

        CrewAI v1.6+ removed litellm and routes through native provider SDKs.
        We instantiate the appropriate native provider directly (bypassing the
        ``LLM`` factory which has no OpenRouter entry) and attach our HTTP
        cost interceptor for providers that return ``usage.cost`` (OpenRouter).
        """
        cfg = get_llm_config(
            model=context.model or self.config.get("model"),
            temperature=context.temperature,
        )

        interceptor = self._cost_interceptor.interceptor

        if cfg.provider in (Provider.OPENAI, Provider.OPENROUTER):
            from crewai.llms.providers.openai.completion import OpenAICompletion
            return OpenAICompletion(
                model=cfg.model,
                temperature=cfg.temperature,
                api_key=cfg.api_key,
                base_url=cfg.base_url,
                interceptor=interceptor,
            )

        if cfg.provider == Provider.ANTHROPIC:
            from crewai.llms.providers.anthropic.completion import AnthropicCompletion
            return AnthropicCompletion(
                model=cfg.model,
                temperature=cfg.temperature,
                api_key=cfg.api_key,
                interceptor=interceptor,
            )

        if cfg.provider == Provider.GOOGLE:
            from crewai.llms.providers.gemini.completion import GeminiCompletion
            return GeminiCompletion(
                model=cfg.model,
                temperature=cfg.temperature,
                api_key=cfg.api_key,
                interceptor=interceptor,
            )

        # Fallback: treat as OpenAI-compatible with custom base_url
        from crewai.llms.providers.openai.completion import OpenAICompletion
        return OpenAICompletion(
            model=cfg.model,
            temperature=cfg.temperature,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            interceptor=interceptor,
        )

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
        """Run a CrewAI agent. Returns (iterations, hit_limit)."""
        import asyncio

        from crewai import Agent, Crew, Process, Task

        persona = get_stage_persona(stage_name)
        llm = self._create_llm(context)

        # In CrewAI the system message is injected via backstory since
        # there is no separate system-message slot.
        backstory = persona.backstory
        if system_msg:
            backstory = f"{backstory}\n\n{system_msg}"

        agent = Agent(
            role=persona.role,
            goal=persona.goal,
            backstory=backstory,
            verbose=False,
            allow_delegation=False,
            llm=llm,
            tools=tools,
        )

        task = Task(
            description=prompt,
            expected_output=STAGE_EXPECTED_OUTPUTS.get(
                stage_name, "Complete the task as described."
            ),
            agent=agent,
        )

        step_cb, task_cb, counter = self._create_trace_callbacks(trace)

        crew = Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=False,
            step_callback=step_cb,
            task_callback=task_cb,
            max_iter=context.max_iterations,
        )

        record_message(trace, "user", prompt)

        # Reset cost interceptor before kickoff so we capture only this run
        self._cost_interceptor.reset()

        result = await asyncio.to_thread(crew.kickoff)
        record_message(trace, "assistant", str(result))

        # Extract token usage from CrewOutput.  CrewAI v1.6+ populates
        # ``token_usage`` (a UsageMetrics object) natively via BaseLLM.
        # Cost comes from our HTTP interceptor reading OpenRouter responses.
        usage = getattr(result, "token_usage", None)
        if usage is not None:
            prompt_tokens = (
                getattr(usage, "prompt_tokens", 0)
                or getattr(usage, "input_tokens", 0)
                or 0
            )
            completion_tokens = (
                getattr(usage, "completion_tokens", 0)
                or getattr(usage, "output_tokens", 0)
                or 0
            )
            record_usage(
                trace,
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens,
                cost_usd=self._cost_interceptor.total_cost,
            )

        iterations = counter[0]
        hit_limit = iterations >= context.max_iterations
        trace.total_iterations = iterations
        finish_trace(trace)
        return iterations, hit_limit

    # =========================================================================
    # SDLC Stage Methods
    # =========================================================================

    async def _execute_stage(self, stage_name, prompt_fn, result_cls, context):
        """Template method for all SDLC stages."""
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
            iterations, hit_limit = await self._run_agent(stage_name, prompt, system_msg, tools, trace, context)
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

    # =========================================================================
    # Trace Callbacks
    # =========================================================================

    @staticmethod
    def _create_trace_callbacks(
        trace: AgentTrace,
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
                record_tool_call(trace, str(tool_name), args, str(tool_result))

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
        }

    def get_failure_handling_info(self) -> dict[str, Any]:
        return {
            "has_checkpointing": False,
            "has_auto_recovery": False,
            "has_graceful_degradation": False,
            "supports_human_handoff": True,
            "is_idempotent": False,
        }
