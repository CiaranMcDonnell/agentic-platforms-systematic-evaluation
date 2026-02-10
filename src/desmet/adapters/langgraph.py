"""
LangGraph Platform Adapter

Implements the evaluation interface for LangGraph.
"""

import os
from datetime import datetime
from typing import Any

from desmet.harness.base import (
    AgentMessage,
    AgentTrace,
    BasePlatformAdapter,
    EvaluationContext,
    ExecutionResult,
    PlatformCategory,
    PlatformInfo,
    PlatformRuntime,
    ToolCall,
)


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
            from langchain_openai import ChatOpenAI
            from langgraph.checkpoint.memory import MemorySaver
            from langgraph.graph import StateGraph  # noqa: F401 — needed for custom graphs in later stages

            # Initialize LLM
            model = self.config.get("model", os.getenv("DEFAULT_MODEL", "gpt-4.1"))
            self._llm = ChatOpenAI(
                model=model,
                temperature=0,
                api_key=os.getenv("OPENAI_API_KEY"),
            )

            # Initialize checkpointer for state persistence
            self._checkpointer = MemorySaver()

            self._initialized = True

        except ImportError as e:
            raise RuntimeError(f"Failed to import LangGraph: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize LangGraph: {e}")

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
            response = await self._llm.ainvoke("Say 'ok'")
            return len(response.content) > 0
        except Exception:
            return False

    async def execute_story(
        self,
        context: EvaluationContext,
    ) -> ExecutionResult:
        """
        Execute a user story using LangGraph.

        Creates a ReAct-style agent graph and executes it.
        """
        from langgraph.prebuilt import create_react_agent

        execution_id = self._create_execution_id()
        trace = AgentTrace(start_time=datetime.now())

        try:
            # Define tools based on allowed tools in context
            tools = self._create_tools(context)

            # Create the agent graph
            agent = create_react_agent(
                self._llm,
                tools,
                checkpointer=self._checkpointer,
            )

            # Prepare the input
            messages = [{"role": "user", "content": context.story_prompt}]

            if context.story_context:
                messages.insert(0, {"role": "system", "content": context.story_context})

            # Execute the agent
            config = {"configurable": {"thread_id": execution_id}}

            final_state = None
            iteration = 0

            async for event in agent.astream(
                {"messages": messages},
                config,
                stream_mode="values",
            ):
                iteration += 1
                trace.total_iterations = iteration

                # Extract messages from state
                if "messages" in event:
                    for msg in event["messages"]:
                        trace.messages.append(
                            AgentMessage(
                                role=getattr(msg, "type", "unknown"),
                                content=getattr(msg, "content", str(msg)),
                                timestamp=datetime.now(),
                            )
                        )

                        # Track tool calls
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tc in msg.tool_calls:
                                trace.tool_calls.append(
                                    ToolCall(
                                        tool_name=tc.get("name", "unknown"),
                                        arguments=tc.get("args", {}),
                                        result=None,
                                        timestamp=datetime.now(),
                                        duration_ms=0,
                                        success=True,
                                    )
                                )

                final_state = event

                # Check iteration limit
                if iteration >= context.max_iterations:
                    break

            trace.end_time = datetime.now()
            trace.final_state = final_state or {}

            # Determine success based on final state
            success = iteration < context.max_iterations

            return ExecutionResult(
                platform_id=self.platform_info.id,
                story_id=context.story_id,
                execution_id=execution_id,
                success=success,
                completed=success,
                trace=trace,
                start_time=trace.start_time,
                end_time=trace.end_time,
                wall_clock_seconds=trace.duration_seconds,
            )

        except Exception as e:
            trace.end_time = datetime.now()
            trace.errors.append(str(e))

            return ExecutionResult(
                platform_id=self.platform_info.id,
                story_id=context.story_id,
                execution_id=execution_id,
                success=False,
                completed=False,
                error_message=str(e),
                trace=trace,
                start_time=trace.start_time,
                end_time=trace.end_time,
                wall_clock_seconds=trace.duration_seconds,
            )

    def _create_tools(self, context: EvaluationContext) -> list:
        """Create LangChain tools based on allowed tools."""
        import subprocess

        from langchain_core.tools import tool

        tools = []

        if "read_file" in context.allowed_tools:

            @tool
            def read_file(path: str) -> str:
                """Read the contents of a file."""
                full_path = context.repo_path / path
                if full_path.exists():
                    return full_path.read_text()
                return f"File not found: {path}"

            tools.append(read_file)

        if "write_file" in context.allowed_tools:

            @tool
            def write_file(path: str, content: str) -> str:
                """Write content to a file."""
                full_path = context.repo_path / path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)
                return f"Successfully wrote to {path}"

            tools.append(write_file)

        if "list_directory" in context.allowed_tools:

            @tool
            def list_directory(path: str = ".") -> str:
                """List files in a directory."""
                full_path = context.repo_path / path
                if full_path.exists():
                    files = list(full_path.iterdir())
                    return "\n".join(str(f.relative_to(context.repo_path)) for f in files)
                return f"Directory not found: {path}"

            tools.append(list_directory)

        if "execute_shell" in context.allowed_tools:

            @tool
            def execute_shell(command: str) -> str:
                """Execute a shell command."""
                try:
                    result = subprocess.run(
                        command,
                        shell=True,
                        cwd=context.repo_path,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    output = result.stdout + result.stderr
                    return output if output else "(no output)"
                except subprocess.TimeoutExpired:
                    return "Command timed out"
                except Exception as e:
                    return f"Error: {e}"

            tools.append(execute_shell)

        return tools

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
