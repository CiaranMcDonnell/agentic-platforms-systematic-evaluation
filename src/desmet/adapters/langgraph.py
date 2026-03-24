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
from desmet.llm_config import Provider
from desmet.llm_config import get_config as get_llm_config
from desmet.observability import get_langchain_callback


class LangGraphAdapter(BasePlatformAdapter):
    """
    Adapter for evaluating LangGraph.

    LangGraph is a graph-based agent orchestration framework
    built on LangChain.
    """

    TOOL_FORMAT = ToolFormat.LANGCHAIN

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._checkpointer = None
        self._llm = None

    @property
    def platform_info(self) -> PlatformInfo:
        info = load_platform_info("langgraph")
        info.version = self._get_version()
        return info

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
        from langchain.agents import create_agent
        from langchain.messages import HumanMessage

        agent = create_agent(
            self._llm,
            tools,
            system_prompt=system_msg,
            checkpointer=self._checkpointer,
        )
        execution_id = self._create_execution_id()

        messages = [HumanMessage(content=prompt)]

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

                # Token usage — always check, even on tool-call messages with empty content
                resp_meta = getattr(last_msg, "response_metadata", {})
                usage = resp_meta.get("token_usage") or resp_meta.get("usage") or {}
                if usage and isinstance(usage, dict) and usage.get("total_tokens", 0) > 0:
                    cost = usage.get("cost") or 0.0
                    record_usage(
                        trace,
                        input_tokens=usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0),
                        output_tokens=usage.get("completion_tokens", 0) or usage.get("output_tokens", 0),
                        cost_usd=float(cost),
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
            iterations, hit_limit = await self._run_agent(prompt, system_msg, tools, trace, context)
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

