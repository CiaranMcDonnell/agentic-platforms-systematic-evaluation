"""
CrewAI Platform Adapter

Implements the evaluation interface for CrewAI.
"""

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
from desmet.harness.base import (
    AgentTrace,
    BasePlatformAdapter,
    CodeResult,
    DeployResult,
    PlatformCategory,
    PlatformInfo,
    PlatformRuntime,
    RequirementsResult,
    StageContext,
    TestResult,
)
from desmet.llm_config import get_config as get_llm_config
from desmet.observability import enable_litellm_callbacks


class CrewAIAdapter(BasePlatformAdapter):
    """
    Adapter for evaluating CrewAI.

    CrewAI is a role-based multi-agent collaboration framework.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._crew = None

    @property
    def platform_info(self) -> PlatformInfo:
        return PlatformInfo(
            name="CrewAI",
            id="crewai",
            category=PlatformCategory.MULTI_AGENT_FRAMEWORK,
            runtime=PlatformRuntime.PYTHON,
            version=self._get_version(),
            vendor="CrewAI Inc",
            description="Role-based multi-agent collaboration framework",
            documentation_url="https://docs.crewai.com/",
            repository_url="https://github.com/joaomdmoura/crewAI",
        )

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

            # Register Langfuse as a litellm callback so every LLM call
            # CrewAI makes is automatically traced.
            enable_litellm_callbacks()

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

        CrewAI uses litellm under the hood.  Litellm routes requests based on
        a ``provider/model`` prefix in the model string rather than a
        ``base_url``, so we use ``cfg.litellm_model`` which prepends the
        correct prefix (e.g. ``openrouter/minimax/minimax-m2.5``).
        """
        from crewai import LLM

        cfg = get_llm_config(
            model=context.model or self.config.get("model"),
            temperature=context.temperature,
        )
        kwargs: dict = dict(
            model=cfg.litellm_model,
            temperature=cfg.temperature,
            api_key=cfg.api_key,
        )
        return LLM(**kwargs)

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
        result = await asyncio.to_thread(crew.kickoff)
        record_message(trace, "assistant", str(result))

        # Extract token usage from the CrewOutput.  CrewAI populates
        # ``token_usage`` (a UsageMetrics object) after kickoff via litellm.
        # Field names follow the litellm / OpenAI convention.
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
            record_usage(trace, input_tokens=prompt_tokens, output_tokens=completion_tokens)

        iterations = counter[0]
        hit_limit = iterations >= context.max_iterations
        trace.total_iterations = iterations
        finish_trace(trace)
        return iterations, hit_limit

    # =========================================================================
    # SDLC Stage Methods
    # =========================================================================

    async def generate_requirements(
        self,
        context: StageContext,
    ) -> RequirementsResult:
        """Stage 2 -- Requirements Analysis."""
        trace = start_trace()
        try:
            prompt = build_requirements_prompt(context.story)
            system_msg = build_system_message(context.story)
            tools = create_tools(context.workspace, context.allowed_tools, fmt=ToolFormat.CREWAI)
            iterations, hit_limit = await self._run_agent(
                "requirements", prompt, system_msg, tools, trace, context,
            )
            return build_stage_result(
                RequirementsResult, self.platform_info.id, "requirements",
                trace, success=not hit_limit, iterations=iterations,
            )
        except Exception as e:
            finish_trace(trace, error=str(e))
            return build_stage_result(
                RequirementsResult, self.platform_info.id, "requirements",
                trace, success=False, iterations=0, error_message=str(e),
            )

    async def generate_code(
        self,
        context: StageContext,
    ) -> CodeResult:
        """Stage 3 -- Code Generation."""
        trace = start_trace()
        try:
            prior = context.get_prior_result("requirements")
            prompt = build_codegen_prompt(context.story, prior_requirements=prior)
            system_msg = build_system_message(context.story)
            tools = create_tools(context.workspace, context.allowed_tools, fmt=ToolFormat.CREWAI)
            iterations, hit_limit = await self._run_agent(
                "codegen", prompt, system_msg, tools, trace, context,
            )
            return build_stage_result(
                CodeResult, self.platform_info.id, "codegen",
                trace, success=not hit_limit, iterations=iterations,
            )
        except Exception as e:
            finish_trace(trace, error=str(e))
            return build_stage_result(
                CodeResult, self.platform_info.id, "codegen",
                trace, success=False, iterations=0, error_message=str(e),
            )

    async def generate_tests(
        self,
        context: StageContext,
    ) -> TestResult:
        """Stage 4 -- Test Generation & Execution."""
        trace = start_trace()
        try:
            prompt = build_testing_prompt(context.story)
            system_msg = build_system_message(context.story)
            tools = create_tools(context.workspace, context.allowed_tools, fmt=ToolFormat.CREWAI)
            iterations, hit_limit = await self._run_agent(
                "testing", prompt, system_msg, tools, trace, context,
            )
            return build_stage_result(
                TestResult, self.platform_info.id, "testing",
                trace, success=not hit_limit, iterations=iterations,
            )
        except Exception as e:
            finish_trace(trace, error=str(e))
            return build_stage_result(
                TestResult, self.platform_info.id, "testing",
                trace, success=False, iterations=0, error_message=str(e),
            )

    async def build_and_deploy(
        self,
        context: StageContext,
    ) -> DeployResult:
        """Stage 5 -- Build & Deployment Verification."""
        trace = start_trace()
        try:
            prompt = build_deploy_prompt(context.story)
            system_msg = build_system_message(context.story)
            tools = create_tools(context.workspace, context.allowed_tools, fmt=ToolFormat.CREWAI)
            iterations, hit_limit = await self._run_agent(
                "deploy", prompt, system_msg, tools, trace, context,
            )
            return build_stage_result(
                DeployResult, self.platform_info.id, "deploy",
                trace, success=not hit_limit, iterations=iterations,
            )
        except Exception as e:
            finish_trace(trace, error=str(e))
            return build_stage_result(
                DeployResult, self.platform_info.id, "deploy",
                trace, success=False, iterations=0, error_message=str(e),
            )

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
            content = (
                getattr(step_output, "log", "")
                or getattr(step_output, "text", "")
                or str(step_output)
            )
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
