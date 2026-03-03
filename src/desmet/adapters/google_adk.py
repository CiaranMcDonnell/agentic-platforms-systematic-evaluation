"""
Google ADK Platform Adapter

Stub implementation — not yet functional.
"""
from typing import Any

from desmet.harness.base import (
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
)


class GoogleADKAdapter(BasePlatformAdapter):
    """Stub adapter for Google ADK."""

    @property
    def platform_info(self) -> PlatformInfo:
        return PlatformInfo(
            name="Google ADK",
            id="google_adk",
            category=PlatformCategory.AGENT_SDK_RUNTIME,
            runtime=PlatformRuntime.PYTHON,
            version="stub",
            vendor="Google",
            description="Google Agent Development Kit for building AI agents",
            documentation_url="https://google.github.io/adk-docs/",
            repository_url="https://github.com/google/adk-python",
        )

    async def initialize(self) -> None:
        raise NotImplementedError("Google ADK adapter not yet implemented")

    async def shutdown(self) -> None:
        pass

    async def health_check(self) -> bool:
        return False

    async def execute_story(self, context: EvaluationContext) -> ExecutionResult:
        raise NotImplementedError("Google ADK adapter not yet implemented")

    async def generate_requirements(self, context: StageContext) -> RequirementsResult:
        raise NotImplementedError("Google ADK adapter not yet implemented")

    async def generate_code(self, context: StageContext) -> CodeResult:
        raise NotImplementedError("Google ADK adapter not yet implemented")

    async def generate_tests(self, context: StageContext) -> TestResult:
        raise NotImplementedError("Google ADK adapter not yet implemented")

    async def build_and_deploy(self, context: StageContext) -> DeployResult:
        raise NotImplementedError("Google ADK adapter not yet implemented")
