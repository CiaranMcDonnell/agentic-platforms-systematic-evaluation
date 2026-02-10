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
    EvaluationContext,
    ExecutionResult,
    PlatformCategory,
    PlatformInfo,
    PlatformRuntime,
    ToolCall,
)


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

    async def execute_story(
        self,
        context: EvaluationContext,
    ) -> ExecutionResult:
        """Execute a user story using CrewAI."""
        from crewai import Agent, Task, Crew, Process, LLM

        execution_id = self._create_execution_id()
        trace = AgentTrace(start_time=datetime.now())

        try:
            # Configure LLM
            model = self.config.get("model", os.getenv("DEFAULT_MODEL", "gpt-4.1"))
            llm = LLM(
                model=model,
                temperature=0,
                api_key=os.getenv("OPENAI_API_KEY"),
            )

            # Create tools
            tools = self._create_tools(context)

            # Create a developer agent with tools
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

            # Create the task
            task = Task(
                description=context.story_prompt,
                expected_output="All required files written to disk using the write_file tool",
                agent=developer,
            )

            # Create and run the crew
            crew = Crew(
                agents=[developer],
                tasks=[task],
                process=Process.sequential,
                verbose=True,
            )

            result = crew.kickoff()

            trace.end_time = datetime.now()

            return ExecutionResult(
                platform_id=self.platform_info.id,
                story_id=context.story_id,
                execution_id=execution_id,
                success=True,
                completed=True,
                trace=trace,
                raw_output=str(result),
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
        """Create CrewAI tools based on allowed tools in context."""
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
