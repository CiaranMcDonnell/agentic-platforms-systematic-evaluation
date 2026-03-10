"""Test that BasePlatformAdapter provides a default execute_story()."""
import asyncio

from desmet.harness.base import (
    BasePlatformAdapter,
    CodeResult,
    EvaluationContext,
    ExecutionResult,
    PlatformCategory,
    PlatformInfo,
    PlatformRuntime,
    StageContext,
)


class ConcreteAdapter(BasePlatformAdapter):
    """Minimal concrete adapter for testing."""

    @property
    def platform_info(self):
        return PlatformInfo(
            name="Test",
            id="test",
            category=PlatformCategory.AGENT_SDK_RUNTIME,
            runtime=PlatformRuntime.PYTHON,
            version="0.1",
            vendor="test",
            description="test",
            documentation_url="",
            repository_url="",
        )

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    async def generate_requirements(self, context):
        raise NotImplementedError

    async def generate_code(self, context):
        return CodeResult(
            platform_id="test",
            stage_name="codegen",
            success=True,
            completed=True,
            output_files=["main.py"],
        )

    async def generate_tests(self, context):
        raise NotImplementedError

    async def build_and_deploy(self, context):
        raise NotImplementedError

    async def health_check(self):
        return True


class TestExecuteStoryDefault:
    def test_delegates_to_generate_code(self, tmp_path):
        adapter = ConcreteAdapter()
        ctx = EvaluationContext(
            story_id="US-001",
            story_prompt="Build a thing",
            story_context="",
            repo_path=tmp_path,
        )
        result = asyncio.run(adapter.execute_story(ctx))
        assert isinstance(result, ExecutionResult)
        assert result.success is True
        assert result.platform_id == "test"
        assert result.story_id == "US-001"
        assert "main.py" in result.output_files
