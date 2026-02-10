"""
Base Platform Adapter Interface

All agentic platforms must implement this interface to be evaluated
in the DESMET framework. This ensures fair, consistent comparison.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class PlatformCategory(Enum):
    """Categories of agentic platforms."""

    MULTI_AGENT_FRAMEWORK = "multi_agent_framework"
    AGENT_SDK_RUNTIME = "agent_sdk_runtime"
    VISUAL_WORKFLOW_PLATFORM = "visual_workflow_platform"


class PlatformRuntime(Enum):
    """Runtime environment for the platform."""

    PYTHON = "python"
    NODEJS = "nodejs"
    DOCKER = "docker"


@dataclass
class PlatformInfo:
    """Metadata about a platform."""

    name: str
    id: str
    category: PlatformCategory
    runtime: PlatformRuntime
    version: str
    vendor: str
    description: str
    documentation_url: str
    repository_url: str


@dataclass
class ToolCall:
    """Record of a tool invocation by the agent."""

    tool_name: str
    arguments: dict[str, Any]
    result: Any
    timestamp: datetime
    duration_ms: float
    success: bool
    error: Optional[str] = None


@dataclass
class AgentMessage:
    """A message in the agent conversation."""

    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: datetime
    tool_calls: list[ToolCall] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentTrace:
    """Complete trace of an agent execution."""

    messages: list[AgentMessage] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    total_iterations: int = 0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    final_state: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        """Total execution duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed."""
        return self.total_tokens_input + self.total_tokens_output


@dataclass
class EvaluationContext:
    """
    Context provided to the platform adapter for task execution.

    Contains all information needed to execute a user story.
    """

    # Story information
    story_id: str
    story_prompt: str
    story_context: str

    # Repository context
    repo_path: Path
    target_files: list[str] = field(default_factory=list)

    # Constraints
    time_budget_seconds: int = 600
    max_iterations: int = 50
    max_tool_calls: int = 100

    # Available tools
    allowed_tools: list[str] = field(
        default_factory=lambda: [
            "read_file",
            "write_file",
            "list_directory",
            "execute_shell",
            "search_code",
        ]
    )

    # Model configuration
    model: str = "gpt-4.1"
    temperature: float = 0.0

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """
    Result of executing a user story on a platform.
    """

    # Identification
    platform_id: str
    story_id: str
    execution_id: str

    # Outcome
    success: bool
    completed: bool
    error_message: Optional[str] = None

    # Artifacts
    trace: AgentTrace = field(default_factory=AgentTrace)
    output_files: list[str] = field(default_factory=list)
    git_diff: Optional[str] = None

    # Timing
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    wall_clock_seconds: float = 0.0

    # Human intervention
    interventions: list[dict[str, Any]] = field(default_factory=list)

    # Raw platform output
    raw_output: Any = None


class BasePlatformAdapter(ABC):
    """
    Abstract base class for platform adapters.

    Each agentic platform must implement this interface to participate
    in the DESMET evaluation. The adapter translates between the
    standardized evaluation harness and platform-specific APIs.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the platform adapter.

        Args:
            config: Platform-specific configuration dictionary
        """
        self.config = config or {}
        self._initialized = False

    @property
    @abstractmethod
    def platform_info(self) -> PlatformInfo:
        """Return metadata about this platform."""
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the platform.

        This may include:
        - Loading API keys
        - Initializing clients
        - Setting up agent configurations
        - Verifying connectivity
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """
        Clean up platform resources.

        Called after evaluation is complete.
        """
        pass

    @abstractmethod
    async def execute_story(
        self,
        context: EvaluationContext,
    ) -> ExecutionResult:
        """
        Execute a user story using this platform.

        This is the main evaluation method. The platform should:
        1. Parse the story prompt and context
        2. Create and configure agents as appropriate
        3. Execute the task using the platform's capabilities
        4. Capture all tool calls, messages, and artifacts
        5. Return a complete ExecutionResult

        Args:
            context: The evaluation context containing story details

        Returns:
            ExecutionResult with all execution details and artifacts
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verify the platform is operational.

        Returns:
            True if the platform is ready for evaluation
        """
        pass

    # =========================================================================
    # Optional Methods (with default implementations)
    # =========================================================================

    async def reset_state(self) -> None:
        """
        Reset any persistent state between story executions.

        Override if the platform maintains state that should be cleared.
        """
        pass

    def get_observability_info(self) -> dict[str, Any]:
        """
        Return information about the platform's observability features.

        Used for the Observability & Debugging evaluation dimension.
        """
        return {
            "has_tracing": False,
            "has_step_through": False,
            "has_replay": False,
            "has_state_inspection": False,
            "has_memory_inspection": False,
            "trace_format": None,
        }

    def get_failure_handling_info(self) -> dict[str, Any]:
        """
        Return information about the platform's failure handling.

        Used for the Failure Handling & Recovery evaluation dimension.
        """
        return {
            "has_checkpointing": False,
            "has_auto_recovery": False,
            "has_graceful_degradation": False,
            "supports_human_handoff": False,
            "is_idempotent": False,
        }

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _create_execution_id(self) -> str:
        """Generate a unique execution ID."""
        import uuid

        return f"{self.platform_info.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    async def _with_timeout(
        self,
        coro,
        timeout_seconds: int,
    ):
        """Execute a coroutine with a timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Execution exceeded {timeout_seconds}s timeout")


class VisualPlatformAdapter(BasePlatformAdapter):
    """
    Extended base class for visual/workflow platforms.

    These platforms (Flowise, LangFlow, Dify, n8n) often have
    HTTP APIs rather than Python SDKs.
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        config: dict[str, Any] | None = None,
    ):
        super().__init__(config)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = None

    @abstractmethod
    async def create_workflow(self, workflow_definition: dict) -> str:
        """
        Create a workflow/flow in the platform.

        Returns:
            Workflow ID
        """
        pass

    @abstractmethod
    async def execute_workflow(
        self,
        workflow_id: str,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute a workflow with given inputs.

        Returns:
            Workflow execution result
        """
        pass

    @abstractmethod
    async def delete_workflow(self, workflow_id: str) -> None:
        """Delete a workflow from the platform."""
        pass
