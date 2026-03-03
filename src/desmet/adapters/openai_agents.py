"""
OpenAI Agents SDK Platform Adapter

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


class OpenAIAgentsAdapter(BasePlatformAdapter):
    """Stub adapter for OpenAI Agents SDK."""

    @property
    def platform_info(self) -> PlatformInfo:
        return PlatformInfo(
            name="OpenAI Agents SDK",
            id="openai_agents_sdk",
            category=PlatformCategory.AGENT_SDK_RUNTIME,
            runtime=PlatformRuntime.PYTHON,
            version="stub",
            vendor="OpenAI",
            description="Official OpenAI SDK for building agentic applications",
            documentation_url="https://platform.openai.com/docs/agents",
            repository_url="https://github.com/openai/openai-agents-python",
        )

    async def initialize(self) -> None:
        raise NotImplementedError("OpenAI Agents SDK adapter not yet implemented")

    async def shutdown(self) -> None:
        pass

    async def health_check(self) -> bool:
        return False

    async def execute_story(self, context: EvaluationContext) -> ExecutionResult:
        raise NotImplementedError("OpenAI Agents SDK adapter not yet implemented")

    async def generate_requirements(self, context: StageContext) -> RequirementsResult:
        raise NotImplementedError("OpenAI Agents SDK adapter not yet implemented")

    async def generate_code(self, context: StageContext) -> CodeResult:
        raise NotImplementedError("OpenAI Agents SDK adapter not yet implemented")

    async def generate_tests(self, context: StageContext) -> TestResult:
        raise NotImplementedError("OpenAI Agents SDK adapter not yet implemented")

    async def build_and_deploy(self, context: StageContext) -> DeployResult:
        raise NotImplementedError("OpenAI Agents SDK adapter not yet implemented")
