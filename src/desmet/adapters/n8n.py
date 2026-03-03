"""
n8n Platform Adapter

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


class N8nAdapter(VisualPlatformAdapter):
    """Stub adapter for n8n."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(
            base_url=config.get("base_url", "http://localhost:5678") if config else "http://localhost:5678",
            api_key=config.get("api_key") if config else None,
            config=config,
        )

    @property
    def platform_info(self) -> PlatformInfo:
        return PlatformInfo(
            name="n8n",
            id="n8n",
            category=PlatformCategory.VISUAL_WORKFLOW_PLATFORM,
            runtime=PlatformRuntime.NODEJS,
            version="stub",
            vendor="n8n GmbH",
            description="Workflow automation platform with AI agent capabilities",
            documentation_url="https://docs.n8n.io/",
            repository_url="https://github.com/n8n-io/n8n",
        )

    async def initialize(self) -> None:
        raise NotImplementedError("n8n adapter not yet implemented")

    async def shutdown(self) -> None:
        pass

    async def health_check(self) -> bool:
        return False

    async def create_workflow(self, workflow_definition: dict) -> str:
        raise NotImplementedError("n8n adapter not yet implemented")

    async def execute_workflow(self, workflow_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("n8n adapter not yet implemented")

    async def delete_workflow(self, workflow_id: str) -> None:
        raise NotImplementedError("n8n adapter not yet implemented")

    async def execute_story(self, context: EvaluationContext) -> ExecutionResult:
        raise NotImplementedError("n8n adapter not yet implemented")

    async def generate_requirements(self, context: StageContext) -> RequirementsResult:
        raise NotImplementedError("n8n adapter not yet implemented")

    async def generate_code(self, context: StageContext) -> CodeResult:
        raise NotImplementedError("n8n adapter not yet implemented")

    async def generate_tests(self, context: StageContext) -> TestResult:
        raise NotImplementedError("n8n adapter not yet implemented")

    async def build_and_deploy(self, context: StageContext) -> DeployResult:
        raise NotImplementedError("n8n adapter not yet implemented")
