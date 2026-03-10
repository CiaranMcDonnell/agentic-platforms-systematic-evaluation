"""
LangGraph Platform Adapter

Implements the evaluation interface for LangGraph.
"""

from typing import Any

from desmet.adapters._prompts import (
    build_codegen_prompt,
    build_deploy_prompt,
    build_requirements_prompt,
    build_system_message,
    build_testing_prompt,
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
from desmet.llm_config import Provider
from desmet.llm_config import get_config as get_llm_config
from desmet.observability import get_langchain_callback


class LangGraphAdapter(BasePlatformAdapter):
    """
    Adapter for evaluating LangGraph.

    LangGraph is a graph-based agent orchestration framework
    built on LangChain.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._checkpointer = None
        self._llm = None
        self._graph = None

    @property
    def platform_info(self) -> PlatformInfo:
        return PlatformInfo(
            name="LangGraph",
            id="langgraph",
            category=PlatformCategory.MULTI_AGENT_FRAMEWORK,
            runtime=PlatformRuntime.PYTHON,
            version=self._get_version(),
            vendor="LangChain Inc",
            description="Graph-based agent orchestration built on LangChain",
            documentation_url="https://langchain-ai.github.io/langgraph/",
            repository_url="https://github.com/langchain-ai/langgraph",
        )

    def _get_version(self) -> str:
        try:
            import langgraph

            return getattr(langgraph, "__version__", "unknown")
        except ImportError:
            return "not installed"

    async def initialize(self) -> None:
        """Initialize LangGraph components."""
        try:
            from langgraph.checkpoint.memory import MemorySaver
            from langgraph.graph import (
                StateGraph,  # noqa: F401 — needed for custom graphs in later stages
            )

            cfg = get_llm_config(model=self.config.get("model"))
            self._llm = self._create_chat_model(cfg)

            # Initialize checkpointer for state persistence
            self._checkpointer = MemorySaver()

            self._initialized = True

        except ImportError as e:
            raise RuntimeError(f"Failed to import LangGraph: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize LangGraph: {e}")

    @staticmethod
    def _create_chat_model(cfg):
        """Instantiate the appropriate LangChain chat model for the provider."""
        if cfg.provider == Provider.ANTHROPIC:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=cfg.model,
                temperature=cfg.temperature,
                api_key=cfg.api_key,
            )
        # OpenAI-compatible providers (OpenAI, OpenRouter, Azure, etc.)
        from langchain_openai import ChatOpenAI
        kwargs: dict = dict(
            model=cfg.model,
            temperature=cfg.temperature,
            api_key=cfg.api_key,
        )
        if cfg.base_url:
            kwargs["base_url"] = cfg.base_url
        return ChatOpenAI(**kwargs)

    async def shutdown(self) -> None:
        """Clean up LangGraph resources."""
        self._checkpointer = None
        self._llm = None
        self._graph = None
        self._initialized = False

    async def health_check(self) -> bool:
        """Verify LangGraph is operational."""
        if not self._initialized:
            return False

        try:
            # Simple test to verify LLM connectivity
            if self._llm is None:
                return False
            response = await self._llm.ainvoke("Say 'ok'")
            return len(response.content) > 0
        except Exception:
            return False

    # =========================================================================
    # Core Agent Runner
    # =========================================================================

    async def _run_agent(
        self,
        prompt: str,
        system_msg: str | None,
        tools: list,
        trace,
        context: StageContext,
    ) -> tuple[int, bool]:
        """Run a LangGraph ReAct agent. Returns (iterations, hit_limit)."""
        from langchain_core.messages import HumanMessage, SystemMessage
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(self._llm, tools, checkpointer=self._checkpointer)
        execution_id = self._create_execution_id()

        messages = []
        if system_msg:
            messages.append(SystemMessage(content=system_msg))
        messages.append(HumanMessage(content=prompt))

        record_message(trace, "user", prompt)

        config: dict[str, Any] = {"configurable": {"thread_id": execution_id}}
        lf_cb = get_langchain_callback()
        if lf_cb is not None:
            config["callbacks"] = [lf_cb]

        final_state = None
        iteration = 0
        hit_limit = False

        async for event in agent.astream(
            {"messages": messages}, config=config, stream_mode="values",
        ):
            iteration += 1
            final_state = event

            if "messages" in event and event["messages"]:
                # stream_mode="values" yields FULL accumulated message list each time,
                # so only process the last (newest) message to avoid duplicates.
                last_msg = event["messages"][-1]
                content = getattr(last_msg, "content", "")
                role = getattr(last_msg, "type", "assistant")
                if content:
                    record_message(trace, role, str(content))
                # Token usage (handles both Anthropic and OpenAI key formats)
                usage = getattr(last_msg, "response_metadata", {}).get("usage", {})
                if usage:
                    record_usage(
                        trace,
                        input_tokens=usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0) or usage.get("completion_tokens", 0),
                    )
                # Record tool calls
                tool_calls = getattr(last_msg, "tool_calls", [])
                for tc in tool_calls:
                    record_tool_call(trace, tc.get("name", "unknown"), tc.get("args", {}), "")

            if iteration >= context.max_iterations:
                hit_limit = True
                break

        trace.total_iterations = iteration
        finish_trace(trace, final_state=final_state)
        return iteration, hit_limit

    # =========================================================================
    # SDLC Stage Methods
    # =========================================================================

    async def generate_requirements(self, context: StageContext) -> RequirementsResult:
        """Stage 2 -- Requirements Analysis."""
        trace = start_trace()
        try:
            prompt = build_requirements_prompt(context.story)
            system_msg = build_system_message(context.story)
            tools = create_tools(context.workspace, context.allowed_tools, fmt=ToolFormat.LANGCHAIN)
            iterations, hit_limit = await self._run_agent(prompt, system_msg, tools, trace, context)
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

    async def generate_code(self, context: StageContext) -> CodeResult:
        """Stage 3 -- Code Generation."""
        trace = start_trace()
        try:
            prior = context.get_prior_result("requirements")
            prompt = build_codegen_prompt(context.story, prior_requirements=prior)
            system_msg = build_system_message(context.story)
            tools = create_tools(context.workspace, context.allowed_tools, fmt=ToolFormat.LANGCHAIN)
            iterations, hit_limit = await self._run_agent(prompt, system_msg, tools, trace, context)
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

    async def generate_tests(self, context: StageContext) -> TestResult:
        """Stage 4 -- Test Generation & Execution."""
        trace = start_trace()
        try:
            prompt = build_testing_prompt(context.story)
            system_msg = build_system_message(context.story)
            tools = create_tools(context.workspace, context.allowed_tools, fmt=ToolFormat.LANGCHAIN)
            iterations, hit_limit = await self._run_agent(prompt, system_msg, tools, trace, context)
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

    async def build_and_deploy(self, context: StageContext) -> DeployResult:
        """Stage 5 -- Build & Deployment Verification."""
        trace = start_trace()
        try:
            prompt = build_deploy_prompt(context.story)
            system_msg = build_system_message(context.story)
            tools = create_tools(context.workspace, context.allowed_tools, fmt=ToolFormat.LANGCHAIN)
            iterations, hit_limit = await self._run_agent(prompt, system_msg, tools, trace, context)
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
    # Metadata & Lifecycle
    # =========================================================================

    def get_observability_info(self) -> dict[str, Any]:
        """LangGraph observability features."""
        return {
            "has_tracing": True,
            "has_step_through": True,  # Via checkpointer
            "has_replay": True,  # Via checkpointer
            "has_state_inspection": True,
            "has_memory_inspection": True,
            "trace_format": "LangSmith",
            "notes": "Full observability via LangSmith integration",
        }

    def get_failure_handling_info(self) -> dict[str, Any]:
        """LangGraph failure handling features."""
        return {
            "has_checkpointing": True,
            "has_auto_recovery": False,
            "has_graceful_degradation": True,
            "supports_human_handoff": True,  # Via interrupt_before/after
            "is_idempotent": True,  # With checkpointer
            "notes": "Supports human-in-the-loop via interrupt nodes",
        }

    async def reset_state(self) -> None:
        """Reset LangGraph state between runs."""
        if self._checkpointer:
            # MemorySaver doesn't persist, so nothing to clear
            pass
