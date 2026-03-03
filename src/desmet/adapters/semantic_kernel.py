"""
Semantic Kernel Platform Adapter

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


class SemanticKernelAdapter(BasePlatformAdapter):
    """Stub adapter for Semantic Kernel."""

    @property
    def platform_info(self) -> PlatformInfo:
        return PlatformInfo(
            name="Semantic Kernel",
            id="semantic_kernel",
            category=PlatformCategory.AGENT_SDK_RUNTIME,
            runtime=PlatformRuntime.PYTHON,
            version="stub",
            vendor="Microsoft",
            description="Lightweight SDK for integrating AI models into applications",
            documentation_url="https://learn.microsoft.com/en-us/semantic-kernel/",
            repository_url="https://github.com/microsoft/semantic-kernel",
        )

    async def initialize(self) -> None:
        raise NotImplementedError("Semantic Kernel adapter not yet implemented")

    async def shutdown(self) -> None:
        pass

    async def health_check(self) -> bool:
        return False

    async def execute_story(self, context: EvaluationContext) -> ExecutionResult:
        raise NotImplementedError("Semantic Kernel adapter not yet implemented")

    async def generate_requirements(self, context: StageContext) -> RequirementsResult:
        raise NotImplementedError("Semantic Kernel adapter not yet implemented")

    async def generate_code(self, context: StageContext) -> CodeResult:
        raise NotImplementedError("Semantic Kernel adapter not yet implemented")

    async def generate_tests(self, context: StageContext) -> TestResult:
        raise NotImplementedError("Semantic Kernel adapter not yet implemented")

    async def build_and_deploy(self, context: StageContext) -> DeployResult:
        raise NotImplementedError("Semantic Kernel adapter not yet implemented")
