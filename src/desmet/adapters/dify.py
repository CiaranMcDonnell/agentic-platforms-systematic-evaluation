"""
Dify Platform Adapter

Stub implementation — not yet functional.
"""
from typing import Any

from desmet.harness.base import (
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
    VisualPlatformAdapter,
)


class DifyAdapter(VisualPlatformAdapter):
    """Stub adapter for Dify."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(
            base_url=config.get("base_url", "http://localhost:3000") if config else "http://localhost:3000",
            api_key=config.get("api_key") if config else None,
            config=config,
        )

    @property
    def platform_info(self) -> PlatformInfo:
        return PlatformInfo(
            name="Dify",
            id="dify",
            category=PlatformCategory.VISUAL_WORKFLOW_PLATFORM,
            runtime=PlatformRuntime.DOCKER,
            version="stub",
            vendor="Dify.AI",
            description="Open-source LLM app development platform with visual workflow builder",
            documentation_url="https://docs.dify.ai/",
            repository_url="https://github.com/langgenius/dify",
        )

    async def initialize(self) -> None:
        raise NotImplementedError("Dify adapter not yet implemented")

    async def shutdown(self) -> None:
        pass

    async def health_check(self) -> bool:
        return False

    async def create_workflow(self, workflow_definition: dict) -> str:
        raise NotImplementedError("Dify adapter not yet implemented")

    async def execute_workflow(self, workflow_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Dify adapter not yet implemented")

    async def delete_workflow(self, workflow_id: str) -> None:
        raise NotImplementedError("Dify adapter not yet implemented")

    async def execute_story(self, context: EvaluationContext) -> ExecutionResult:
        raise NotImplementedError("Dify adapter not yet implemented")

    async def generate_requirements(self, context: StageContext) -> RequirementsResult:
        raise NotImplementedError("Dify adapter not yet implemented")

    async def generate_code(self, context: StageContext) -> CodeResult:
        raise NotImplementedError("Dify adapter not yet implemented")

    async def generate_tests(self, context: StageContext) -> TestResult:
        raise NotImplementedError("Dify adapter not yet implemented")

    async def build_and_deploy(self, context: StageContext) -> DeployResult:
        raise NotImplementedError("Dify adapter not yet implemented")
