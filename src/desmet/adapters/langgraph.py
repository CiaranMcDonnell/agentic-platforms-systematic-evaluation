"""
LangGraph Platform Adapter

Implements the evaluation interface for LangGraph.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from desmet.harness.base import (
    AgentMessage,
    AgentTrace,
    BasePlatformAdapter,
    CodeResult,
    DeployResult,
    EvaluationContext,
    ExecutionResult,
    PlatformCategory,
    PlatformInfo,
    PlatformRuntime,
    RequirementsResult,
    StageContext,
    TestResult,
    ToolCall,
)
from desmet.harness.story import UserStory


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

    # =========================================================================
    # SDLC Stage Methods
    # =========================================================================

    async def generate_requirements(
        self,
        context: StageContext,
    ) -> RequirementsResult:
        """
        Stage 2 -- Requirements Analysis.

        Creates a ReAct agent that analyses the user story and produces
        structured requirements, use cases, and UML diagrams.
        """
        from langgraph.prebuilt import create_react_agent

        execution_id = self._create_execution_id()
        trace = AgentTrace(start_time=datetime.now())

        try:
            tools = self._create_tools_from_stage_context(context)

            agent = create_react_agent(
                self._llm,
                tools,
                checkpointer=self._checkpointer,
            )

            # Build requirements-specific prompt
            prompt = (
                f"Analyse the following user story and produce a structured "
                f"requirements specification.\n\n"
                f"## User Story\n"
                f"**{context.story.title}**\n"
                f"{context.story.description}\n\n"
                f"## Prompt\n{context.story.prompt}\n\n"
                f"You must:\n"
                f"1. Decompose the story into functional and non-functional requirements.\n"
                f"2. Identify domain entities, relationships and API endpoints.\n"
                f"3. Identify use cases.\n"
                f"4. Produce UML diagrams (class, sequence, use-case) in PlantUML format.\n"
                f"5. Write all artefacts as files in the workspace.\n"
            )

            messages = [{"role": "user", "content": prompt}]
            if context.story.context:
                messages.insert(0, {"role": "system", "content": context.story.context})

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

                if "messages" in event:
                    for msg in event["messages"]:
                        trace.messages.append(
                            AgentMessage(
                                role=getattr(msg, "type", "unknown"),
                                content=getattr(msg, "content", str(msg)),
                                timestamp=datetime.now(),
                            )
                        )
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

                if iteration >= context.max_iterations:
                    break

            trace.end_time = datetime.now()
            trace.final_state = final_state or {}

            success = iteration < context.max_iterations

            return RequirementsResult(
                platform_id=self.platform_info.id,
                stage_name="requirements",
                success=success,
                completed=success,
                trace=trace,
                wall_clock_seconds=trace.duration_seconds,
                iterations=iteration,
                tool_calls_count=len(trace.tool_calls),
                start_time=trace.start_time,
                end_time=trace.end_time,
            )

        except Exception as e:
            trace.end_time = datetime.now()
            trace.errors.append(str(e))

            return RequirementsResult(
                platform_id=self.platform_info.id,
                stage_name="requirements",
                success=False,
                completed=False,
                error_message=str(e),
                trace=trace,
                wall_clock_seconds=trace.duration_seconds,
                iterations=0,
                start_time=trace.start_time,
                end_time=trace.end_time,
            )

    async def generate_code(
        self,
        context: StageContext,
    ) -> CodeResult:
        """
        Stage 3 -- Code Generation.

        Creates a ReAct agent that implements the solution code based on
        the user story and any prior requirements artefacts.
        """
        from langgraph.prebuilt import create_react_agent

        execution_id = self._create_execution_id()
        trace = AgentTrace(start_time=datetime.now())

        try:
            tools = self._create_tools_from_stage_context(context)

            agent = create_react_agent(
                self._llm,
                tools,
                checkpointer=self._checkpointer,
            )

            # Build code-generation prompt from the story
            prompt = context.story.prompt

            # Append prior requirements if available
            req_result = context.get_prior_result("requirements")
            if req_result is not None:
                prompt += (
                    f"\n\n## Prior Requirements Analysis\n"
                    f"The following requirements were produced in the previous stage. "
                    f"Use them to guide your implementation.\n"
                )
                if isinstance(req_result, RequirementsResult):
                    if req_result.functional_requirements:
                        prompt += f"\nFunctional requirements: {req_result.functional_requirements}"
                    if req_result.non_functional_requirements:
                        prompt += f"\nNon-functional requirements: {req_result.non_functional_requirements}"
                    if req_result.use_cases:
                        prompt += f"\nUse cases: {req_result.use_cases}"
                    if req_result.entities:
                        prompt += f"\nEntities: {req_result.entities}"
                    if req_result.api_endpoints:
                        prompt += f"\nAPI endpoints: {req_result.api_endpoints}"

            messages = [{"role": "user", "content": prompt}]
            if context.story.context:
                messages.insert(0, {"role": "system", "content": context.story.context})

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

                if "messages" in event:
                    for msg in event["messages"]:
                        trace.messages.append(
                            AgentMessage(
                                role=getattr(msg, "type", "unknown"),
                                content=getattr(msg, "content", str(msg)),
                                timestamp=datetime.now(),
                            )
                        )
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

                if iteration >= context.max_iterations:
                    break

            trace.end_time = datetime.now()
            trace.final_state = final_state or {}

            success = iteration < context.max_iterations

            return CodeResult(
                platform_id=self.platform_info.id,
                stage_name="codegen",
                success=success,
                completed=success,
                trace=trace,
                wall_clock_seconds=trace.duration_seconds,
                iterations=iteration,
                tool_calls_count=len(trace.tool_calls),
                start_time=trace.start_time,
                end_time=trace.end_time,
            )

        except Exception as e:
            trace.end_time = datetime.now()
            trace.errors.append(str(e))

            return CodeResult(
                platform_id=self.platform_info.id,
                stage_name="codegen",
                success=False,
                completed=False,
                error_message=str(e),
                trace=trace,
                wall_clock_seconds=trace.duration_seconds,
                iterations=0,
                start_time=trace.start_time,
                end_time=trace.end_time,
            )

    async def generate_tests(
        self,
        context: StageContext,
    ) -> TestResult:
        """
        Stage 4 -- Test Generation & Execution.

        Creates a ReAct agent that writes tests for the user story,
        runs them, and reports the results.
        """
        from langgraph.prebuilt import create_react_agent

        execution_id = self._create_execution_id()
        trace = AgentTrace(start_time=datetime.now())

        try:
            tools = self._create_tools_from_stage_context(context)

            agent = create_react_agent(
                self._llm,
                tools,
                checkpointer=self._checkpointer,
            )

            prompt = (
                f"Write tests for the following user story, execute them, and "
                f"report the results.\n\n"
                f"## User Story\n"
                f"**{context.story.title}**\n"
                f"{context.story.description}\n\n"
                f"## Prompt\n{context.story.prompt}\n\n"
                f"You must:\n"
                f"1. Read the existing code in the workspace.\n"
                f"2. Write comprehensive unit and integration tests.\n"
                f"3. Run the test suite.\n"
                f"4. Report the number of tests run, passed, and failed.\n"
                f"5. If tests fail, attempt to fix the code and re-run.\n"
            )

            messages = [{"role": "user", "content": prompt}]
            if context.story.context:
                messages.insert(0, {"role": "system", "content": context.story.context})

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

                if "messages" in event:
                    for msg in event["messages"]:
                        trace.messages.append(
                            AgentMessage(
                                role=getattr(msg, "type", "unknown"),
                                content=getattr(msg, "content", str(msg)),
                                timestamp=datetime.now(),
                            )
                        )
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

                if iteration >= context.max_iterations:
                    break

            trace.end_time = datetime.now()
            trace.final_state = final_state or {}

            success = iteration < context.max_iterations

            return TestResult(
                platform_id=self.platform_info.id,
                stage_name="testing",
                success=success,
                completed=success,
                trace=trace,
                wall_clock_seconds=trace.duration_seconds,
                iterations=iteration,
                tool_calls_count=len(trace.tool_calls),
                start_time=trace.start_time,
                end_time=trace.end_time,
            )

        except Exception as e:
            trace.end_time = datetime.now()
            trace.errors.append(str(e))

            return TestResult(
                platform_id=self.platform_info.id,
                stage_name="testing",
                success=False,
                completed=False,
                error_message=str(e),
                trace=trace,
                wall_clock_seconds=trace.duration_seconds,
                iterations=0,
                start_time=trace.start_time,
                end_time=trace.end_time,
            )

    async def build_and_deploy(
        self,
        context: StageContext,
    ) -> DeployResult:
        """
        Stage 5 -- Build & Deployment Verification.

        Creates a ReAct agent that builds the project, installs
        dependencies, runs tests, and verifies deployment readiness.
        """
        from langgraph.prebuilt import create_react_agent

        execution_id = self._create_execution_id()
        trace = AgentTrace(start_time=datetime.now())

        try:
            tools = self._create_tools_from_stage_context(context)

            agent = create_react_agent(
                self._llm,
                tools,
                checkpointer=self._checkpointer,
            )

            prompt = (
                f"Build the project and verify it is deployment-ready.\n\n"
                f"## User Story\n"
                f"**{context.story.title}**\n"
                f"{context.story.description}\n\n"
                f"You must:\n"
                f"1. Install all dependencies.\n"
                f"2. Run the build step (compilation, bundling, etc.).\n"
                f"3. Run the test suite to verify the build.\n"
                f"4. Verify the build artefact starts or passes a smoke test.\n"
                f"5. Report whether the project is deployment-ready and list any "
                f"dependency or build issues encountered.\n"
            )

            messages = [{"role": "user", "content": prompt}]
            if context.story.context:
                messages.insert(0, {"role": "system", "content": context.story.context})

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

                if "messages" in event:
                    for msg in event["messages"]:
                        trace.messages.append(
                            AgentMessage(
                                role=getattr(msg, "type", "unknown"),
                                content=getattr(msg, "content", str(msg)),
                                timestamp=datetime.now(),
                            )
                        )
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

                if iteration >= context.max_iterations:
                    break

            trace.end_time = datetime.now()
            trace.final_state = final_state or {}

            success = iteration < context.max_iterations

            return DeployResult(
                platform_id=self.platform_info.id,
                stage_name="deploy",
                success=success,
                completed=success,
                trace=trace,
                wall_clock_seconds=trace.duration_seconds,
                iterations=iteration,
                tool_calls_count=len(trace.tool_calls),
                start_time=trace.start_time,
                end_time=trace.end_time,
            )

        except Exception as e:
            trace.end_time = datetime.now()
            trace.errors.append(str(e))

            return DeployResult(
                platform_id=self.platform_info.id,
                stage_name="deploy",
                success=False,
                completed=False,
                error_message=str(e),
                trace=trace,
                wall_clock_seconds=trace.duration_seconds,
                iterations=0,
                start_time=trace.start_time,
                end_time=trace.end_time,
            )

    # =========================================================================
    # Backwards-Compatible Wrapper
    # =========================================================================

    async def execute_story(
        self,
        context: EvaluationContext,
    ) -> ExecutionResult:
        """
        Execute a user story using LangGraph.

        Backwards-compatible wrapper that delegates to ``generate_code()``.
        Constructs a temporary ``UserStory`` and ``StageContext`` from the
        legacy ``EvaluationContext``, calls the new code-generation pipeline,
        then converts the ``CodeResult`` back to an ``ExecutionResult``.
        """
        # Build a temporary UserStory from the EvaluationContext fields
        story = UserStory(
            id=context.story_id,
            title=context.story_id,
            description=context.story_prompt,
            difficulty="basic",  # type: ignore[arg-type]  — legacy path, difficulty not known
            category="code_generation",
            prompt=context.story_prompt,
            context=context.story_context,
            target_files=context.target_files,
            time_budget_seconds=context.time_budget_seconds,
            max_iterations=context.max_iterations,
        )

        # Build a StageContext from the story
        stage_ctx = StageContext(
            story=story,
            workspace=context.repo_path,
            time_budget_seconds=context.time_budget_seconds,
            max_iterations=context.max_iterations,
            max_tool_calls=context.max_tool_calls,
            allowed_tools=context.allowed_tools,
            model=context.model,
            temperature=context.temperature,
        )

        # Delegate to the new generate_code method
        code_result = await self.generate_code(stage_ctx)

        # Convert CodeResult back to ExecutionResult
        return ExecutionResult(
            platform_id=code_result.platform_id,
            story_id=context.story_id,
            execution_id=self._create_execution_id(),
            success=code_result.success,
            completed=code_result.completed,
            error_message=code_result.error_message,
            trace=code_result.trace,
            output_files=code_result.output_files,
            git_diff=code_result.git_diff,
            start_time=code_result.start_time or datetime.now(),
            end_time=code_result.end_time,
            wall_clock_seconds=code_result.wall_clock_seconds,
        )

    # =========================================================================
    # Tool Helpers
    # =========================================================================

    def _create_tools_from_stage_context(self, context: StageContext) -> list:
        """Create LangChain tools from a StageContext.

        Same as ``_create_tools`` but uses ``context.workspace`` instead
        of ``context.repo_path``.
        """
        import subprocess

        from langchain_core.tools import tool

        workspace = context.workspace
        tools = []

        if "read_file" in context.allowed_tools:

            @tool
            def read_file(path: str) -> str:
                """Read the contents of a file."""
                full_path = workspace / path
                if full_path.exists():
                    return full_path.read_text()
                return f"File not found: {path}"

            tools.append(read_file)

        if "write_file" in context.allowed_tools:

            @tool
            def write_file(path: str, content: str) -> str:
                """Write content to a file."""
                full_path = workspace / path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)
                return f"Successfully wrote to {path}"

            tools.append(write_file)

        if "list_directory" in context.allowed_tools:

            @tool
            def list_directory(path: str = ".") -> str:
                """List files in a directory."""
                full_path = workspace / path
                if full_path.exists():
                    files = list(full_path.iterdir())
                    return "\n".join(str(f.relative_to(workspace)) for f in files)
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
                        cwd=workspace,
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

    def _create_tools(self, context: EvaluationContext) -> list:
        """Create LangChain tools based on allowed tools.

        Legacy helper retained for backwards compatibility with
        ``execute_story()`` callers that pass an ``EvaluationContext``.
        """
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
