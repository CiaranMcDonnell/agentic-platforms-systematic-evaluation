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
    return LangGraphAdapter(config={"model": "gpt-4.1"})


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

    def test_execute_story_still_works(self, adapter):
        assert hasattr(adapter, "execute_story")
        assert callable(adapter.execute_story)

    def test_has_tools_from_stage_context(self, adapter):
        assert hasattr(adapter, "_create_tools_from_stage_context")
        assert callable(adapter._create_tools_from_stage_context)

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

    def test_old_create_tools_preserved(self, adapter):
        """_create_tools() must still exist for backwards compat."""
        assert hasattr(adapter, "_create_tools")
        assert callable(adapter._create_tools)

    def test_generate_requirements_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.generate_requirements)

    def test_generate_code_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.generate_code)

    def test_generate_tests_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.generate_tests)

    def test_build_and_deploy_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.build_and_deploy)
