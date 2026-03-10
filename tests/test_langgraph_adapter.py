"""Tests for LangGraph adapter's new SDLC stage methods."""
import pytest
import inspect

from desmet.adapters.langgraph import LangGraphAdapter
from desmet.harness.base import (
    StageContext,
    RequirementsResult,
    CodeResult,
    TestResult,
    DeployResult,
)


@pytest.fixture
def adapter():
    return LangGraphAdapter(config={"model": "gpt-5.2-2025-12-11"})


class TestLangGraphAdapterInterface:
    def test_has_generate_requirements(self, adapter):
        assert hasattr(adapter, "generate_requirements")
        assert callable(adapter.generate_requirements)

    def test_has_generate_code(self, adapter):
        assert hasattr(adapter, "generate_code")
        assert callable(adapter.generate_code)

    def test_has_generate_tests(self, adapter):
        assert hasattr(adapter, "generate_tests")
        assert callable(adapter.generate_tests)

    def test_has_build_and_deploy(self, adapter):
        assert hasattr(adapter, "build_and_deploy")
        assert callable(adapter.build_and_deploy)

    def test_execute_story_inherited(self, adapter):
        """execute_story() is now inherited from BasePlatformAdapter."""
        assert hasattr(adapter, "execute_story")
        assert callable(adapter.execute_story)

    def test_has_run_agent(self, adapter):
        """_run_agent() is the extracted core LangGraph loop."""
        assert hasattr(adapter, "_run_agent")
        assert callable(adapter._run_agent)

    def test_generate_requirements_signature(self, adapter):
        sig = inspect.signature(adapter.generate_requirements)
        params = list(sig.parameters.keys())
        assert "context" in params

    def test_generate_code_signature(self, adapter):
        sig = inspect.signature(adapter.generate_code)
        params = list(sig.parameters.keys())
        assert "context" in params

    def test_generate_tests_signature(self, adapter):
        sig = inspect.signature(adapter.generate_tests)
        params = list(sig.parameters.keys())
        assert "context" in params

    def test_build_and_deploy_signature(self, adapter):
        sig = inspect.signature(adapter.build_and_deploy)
        params = list(sig.parameters.keys())
        assert "context" in params

    def test_generate_requirements_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.generate_requirements)

    def test_generate_code_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.generate_code)

    def test_generate_tests_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.generate_tests)

    def test_build_and_deploy_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.build_and_deploy)

    def test_run_agent_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter._run_agent)

    def test_no_legacy_create_tools(self, adapter):
        """Legacy _create_tools and _create_tools_from_stage_context are removed."""
        assert not hasattr(adapter, "_create_tools")
        assert not hasattr(adapter, "_create_tools_from_stage_context")
