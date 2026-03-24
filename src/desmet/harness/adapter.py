"""Base platform adapter abstract classes."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from .context import StageContext
from .models import PlatformInfo
from .results import (
    CodeResult,
    DeployResult,
    RequirementsResult,
    TestResult,
)


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

    # =========================================================================
    # SDLC Stage Methods (Adapter-Centric Pipeline)
    # =========================================================================

    @abstractmethod
    async def generate_requirements(
        self,
        context: StageContext,
    ) -> RequirementsResult:
        """
        Stage 2 -- Requirements Analysis.

        Analyse the user story provided in *context.story* and produce a
        structured requirements specification.
        """
        pass

    @abstractmethod
    async def generate_code(
        self,
        context: StageContext,
    ) -> CodeResult:
        """
        Stage 3 -- Code Generation.

        Using the user story and the requirements artefacts produced by
        ``generate_requirements``, implement the solution code.
        """
        pass

    @abstractmethod
    async def generate_tests(
        self,
        context: StageContext,
    ) -> TestResult:
        """
        Stage 4 -- Test Generation & Execution.

        Using the user story, requirements, and generated code, produce a
        test suite and execute it.
        """
        pass

    @abstractmethod
    async def build_and_deploy(
        self,
        context: StageContext,
    ) -> DeployResult:
        """
        Stage 5 -- Build & Deployment Verification.

        Attempt to build the generated code and verify it is deployment-ready.
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

    # Layer 2 assessment helpers — not used in Layer 3 pipeline benchmarking.
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

    # Layer 2 assessment helpers — not used in Layer 3 pipeline benchmarking.
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
        api_key: str | None = None,
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
