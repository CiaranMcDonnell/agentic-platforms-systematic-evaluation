"""
CrewAI Platform Adapter

Implements the evaluation interface for CrewAI.
"""

import os
import subprocess
from datetime import datetime
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
            self._initialized = True
        except ImportError as e:
            raise RuntimeError(f"Failed to import CrewAI: {e}")

    async def shutdown(self) -> None:
        self._crew = None
        self._initialized = False

    async def health_check(self) -> bool:
        return self._initialized

    # =========================================================================
    # SDLC Stage Methods
    # =========================================================================

    async def generate_requirements(
        self,
        context: StageContext,
    ) -> RequirementsResult:
        """
        Stage 2 -- Requirements Analysis.

        Creates a CrewAI agent and crew that analyses the user story
        and produces structured requirements, use cases, and UML diagrams.
        """
        from crewai import Agent, Crew, LLM, Process, Task

        execution_id = self._create_execution_id()
        trace = AgentTrace(start_time=datetime.now())

        try:
            model = context.model or self.config.get(
                "model", os.getenv("DEFAULT_MODEL", "gpt-4.1")
            )
            llm = LLM(
                model=model,
                temperature=context.temperature,
                api_key=os.getenv("OPENAI_API_KEY"),
            )

            tools = self._create_tools_from_stage_context(context)

            analyst = Agent(
                role="Requirements Analyst",
                goal=(
                    "Analyse the user story and produce a structured "
                    "requirements specification"
                ),
                backstory=(
                    "You are an experienced software architect and business analyst. "
                    "You always write artefacts to disk using the provided tools. "
                    "You decompose user stories into clear, actionable requirements."
                ),
                verbose=True,
                allow_delegation=False,
                llm=llm,
                tools=tools,
            )

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

            task = Task(
                description=prompt,
                expected_output=(
                    "All requirements documents and UML diagrams written to disk"
                ),
                agent=analyst,
            )

            crew = Crew(
                agents=[analyst],
                tasks=[task],
                process=Process.sequential,
                verbose=True,
            )

            result = crew.kickoff()

            trace.end_time = datetime.now()

            # Record a summary message from the crew result
            trace.messages.append(
                AgentMessage(
                    role="assistant",
                    content=str(result),
                    timestamp=datetime.now(),
                )
            )

            return RequirementsResult(
                platform_id=self.platform_info.id,
                stage_name="requirements",
                success=True,
                completed=True,
                trace=trace,
                wall_clock_seconds=trace.duration_seconds,
                iterations=1,
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

        Creates a CrewAI agent and crew that implements the solution code
        based on the user story and any prior requirements artefacts.
        """
        from crewai import Agent, Crew, LLM, Process, Task

        execution_id = self._create_execution_id()
        trace = AgentTrace(start_time=datetime.now())

        try:
            model = context.model or self.config.get(
                "model", os.getenv("DEFAULT_MODEL", "gpt-4.1")
            )
            llm = LLM(
                model=model,
                temperature=context.temperature,
                api_key=os.getenv("OPENAI_API_KEY"),
            )

            tools = self._create_tools_from_stage_context(context)

            developer = Agent(
                role="Software Developer",
                goal="Complete the assigned programming task by writing all required files",
                backstory=(
                    "You are an experienced software developer and architect. "
                    "You always write files to disk using the provided tools. "
                    "You create complete, well-structured documents and code."
                ),
                verbose=True,
                allow_delegation=False,
                llm=llm,
                tools=tools,
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

            task = Task(
                description=prompt,
                expected_output="All required files written to disk using the write_file tool",
                agent=developer,
            )

            crew = Crew(
                agents=[developer],
                tasks=[task],
                process=Process.sequential,
                verbose=True,
            )

            result = crew.kickoff()

            trace.end_time = datetime.now()

            trace.messages.append(
                AgentMessage(
                    role="assistant",
                    content=str(result),
                    timestamp=datetime.now(),
                )
            )

            return CodeResult(
                platform_id=self.platform_info.id,
                stage_name="codegen",
                success=True,
                completed=True,
                trace=trace,
                wall_clock_seconds=trace.duration_seconds,
                iterations=1,
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

        Creates a CrewAI agent and crew that writes tests for the user
        story, runs them, and reports the results.
        """
        from crewai import Agent, Crew, LLM, Process, Task

        execution_id = self._create_execution_id()
        trace = AgentTrace(start_time=datetime.now())

        try:
            model = context.model or self.config.get(
                "model", os.getenv("DEFAULT_MODEL", "gpt-4.1")
            )
            llm = LLM(
                model=model,
                temperature=context.temperature,
                api_key=os.getenv("OPENAI_API_KEY"),
            )

            tools = self._create_tools_from_stage_context(context)

            tester = Agent(
                role="QA Engineer",
                goal="Write comprehensive tests, execute them, and report results",
                backstory=(
                    "You are an experienced QA engineer and test automation specialist. "
                    "You write thorough unit and integration tests, execute them, "
                    "and report precise pass/fail counts."
                ),
                verbose=True,
                allow_delegation=False,
                llm=llm,
                tools=tools,
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

            task = Task(
                description=prompt,
                expected_output=(
                    "Test files written, test suite executed, and results reported"
                ),
                agent=tester,
            )

            crew = Crew(
                agents=[tester],
                tasks=[task],
                process=Process.sequential,
                verbose=True,
            )

            result = crew.kickoff()

            trace.end_time = datetime.now()

            trace.messages.append(
                AgentMessage(
                    role="assistant",
                    content=str(result),
                    timestamp=datetime.now(),
                )
            )

            return TestResult(
                platform_id=self.platform_info.id,
                stage_name="testing",
                success=True,
                completed=True,
                trace=trace,
                wall_clock_seconds=trace.duration_seconds,
                iterations=1,
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

        Creates a CrewAI agent and crew that builds the project, installs
        dependencies, runs tests, and verifies deployment readiness.
        """
        from crewai import Agent, Crew, LLM, Process, Task

        execution_id = self._create_execution_id()
        trace = AgentTrace(start_time=datetime.now())

        try:
            model = context.model or self.config.get(
                "model", os.getenv("DEFAULT_MODEL", "gpt-4.1")
            )
            llm = LLM(
                model=model,
                temperature=context.temperature,
                api_key=os.getenv("OPENAI_API_KEY"),
            )

            tools = self._create_tools_from_stage_context(context)

            devops = Agent(
                role="DevOps Engineer",
                goal="Build the project and verify it is deployment-ready",
                backstory=(
                    "You are an experienced DevOps engineer. "
                    "You build projects, resolve dependency issues, "
                    "and verify deployment readiness."
                ),
                verbose=True,
                allow_delegation=False,
                llm=llm,
                tools=tools,
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

            task = Task(
                description=prompt,
                expected_output=(
                    "Build completed, deployment readiness verified, "
                    "and any issues reported"
                ),
                agent=devops,
            )

            crew = Crew(
                agents=[devops],
                tasks=[task],
                process=Process.sequential,
                verbose=True,
            )

            result = crew.kickoff()

            trace.end_time = datetime.now()

            trace.messages.append(
                AgentMessage(
                    role="assistant",
                    content=str(result),
                    timestamp=datetime.now(),
                )
            )

            return DeployResult(
                platform_id=self.platform_info.id,
                stage_name="deploy",
                success=True,
                completed=True,
                trace=trace,
                wall_clock_seconds=trace.duration_seconds,
                iterations=1,
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
        Execute a user story using CrewAI.

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
        """Create CrewAI tools from a StageContext.

        Same as ``_create_tools`` but uses ``context.workspace`` instead
        of ``context.repo_path``.
        """
        from crewai.tools import BaseTool
        from pydantic import BaseModel, Field

        tools = []
        workspace = context.workspace

        if "read_file" in context.allowed_tools:

            class ReadFileInput(BaseModel):
                path: str = Field(description="Relative path to the file to read")

            class ReadFileTool(BaseTool):
                name: str = "read_file"
                description: str = "Read the contents of a file at the given relative path"
                args_schema: type[BaseModel] = ReadFileInput

                def _run(self, path: str) -> str:
                    full_path = workspace / path
                    if full_path.exists():
                        return full_path.read_text()
                    return f"File not found: {path}"

            tools.append(ReadFileTool())

        if "write_file" in context.allowed_tools:

            class WriteFileInput(BaseModel):
                path: str = Field(description="Relative path to write the file to")
                content: str = Field(description="Content to write to the file")

            class WriteFileTool(BaseTool):
                name: str = "write_file"
                description: str = "Write content to a file, creating parent directories as needed"
                args_schema: type[BaseModel] = WriteFileInput

                def _run(self, path: str, content: str) -> str:
                    full_path = workspace / path
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(content)
                    return f"Successfully wrote to {path}"

            tools.append(WriteFileTool())

        if "list_directory" in context.allowed_tools:

            class ListDirectoryInput(BaseModel):
                path: str = Field(default=".", description="Relative path to the directory to list")

            class ListDirectoryTool(BaseTool):
                name: str = "list_directory"
                description: str = "List files and directories at the given relative path"
                args_schema: type[BaseModel] = ListDirectoryInput

                def _run(self, path: str = ".") -> str:
                    full_path = workspace / path
                    if full_path.exists():
                        files = list(full_path.iterdir())
                        return "\n".join(str(f.relative_to(workspace)) for f in files)
                    return f"Directory not found: {path}"

            tools.append(ListDirectoryTool())

        if "execute_shell" in context.allowed_tools:

            class ExecuteShellInput(BaseModel):
                command: str = Field(description="Shell command to execute")

            class ExecuteShellTool(BaseTool):
                name: str = "execute_shell"
                description: str = "Execute a shell command in the project directory"
                args_schema: type[BaseModel] = ExecuteShellInput

                def _run(self, command: str) -> str:
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

            tools.append(ExecuteShellTool())

        return tools

    def _create_tools(self, context: EvaluationContext) -> list:
        """Create CrewAI tools based on allowed tools in context.

        Legacy helper retained for backwards compatibility with
        ``execute_story()`` callers that pass an ``EvaluationContext``.
        """
        from crewai.tools import BaseTool
        from pydantic import BaseModel, Field

        tools = []
        repo_path = context.repo_path

        if "read_file" in context.allowed_tools:

            class ReadFileInput(BaseModel):
                path: str = Field(description="Relative path to the file to read")

            class ReadFileTool(BaseTool):
                name: str = "read_file"
                description: str = "Read the contents of a file at the given relative path"
                args_schema: type[BaseModel] = ReadFileInput

                def _run(self, path: str) -> str:
                    full_path = repo_path / path
                    if full_path.exists():
                        return full_path.read_text()
                    return f"File not found: {path}"

            tools.append(ReadFileTool())

        if "write_file" in context.allowed_tools:

            class WriteFileInput(BaseModel):
                path: str = Field(description="Relative path to write the file to")
                content: str = Field(description="Content to write to the file")

            class WriteFileTool(BaseTool):
                name: str = "write_file"
                description: str = "Write content to a file, creating parent directories as needed"
                args_schema: type[BaseModel] = WriteFileInput

                def _run(self, path: str, content: str) -> str:
                    full_path = repo_path / path
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(content)
                    return f"Successfully wrote to {path}"

            tools.append(WriteFileTool())

        if "list_directory" in context.allowed_tools:

            class ListDirectoryInput(BaseModel):
                path: str = Field(default=".", description="Relative path to the directory to list")

            class ListDirectoryTool(BaseTool):
                name: str = "list_directory"
                description: str = "List files and directories at the given relative path"
                args_schema: type[BaseModel] = ListDirectoryInput

                def _run(self, path: str = ".") -> str:
                    full_path = repo_path / path
                    if full_path.exists():
                        files = list(full_path.iterdir())
                        return "\n".join(str(f.relative_to(repo_path)) for f in files)
                    return f"Directory not found: {path}"

            tools.append(ListDirectoryTool())

        if "execute_shell" in context.allowed_tools:

            class ExecuteShellInput(BaseModel):
                command: str = Field(description="Shell command to execute")

            class ExecuteShellTool(BaseTool):
                name: str = "execute_shell"
                description: str = "Execute a shell command in the project directory"
                args_schema: type[BaseModel] = ExecuteShellInput

                def _run(self, command: str) -> str:
                    try:
                        result = subprocess.run(
                            command,
                            shell=True,
                            cwd=repo_path,
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

            tools.append(ExecuteShellTool())

        return tools

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
