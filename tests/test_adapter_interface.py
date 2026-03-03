"""Tests for the adapter interface contract."""
import pytest
import inspect

from desmet.harness.base import (
    BasePlatformAdapter,
    StageContext,
    RequirementsResult,
    CodeResult,
    TestResult,
    DeployResult,
)


class TestAdapterInterface:
    def test_has_generate_requirements_method(self):
        assert hasattr(BasePlatformAdapter, "generate_requirements")
        sig = inspect.signature(BasePlatformAdapter.generate_requirements)
        params = list(sig.parameters.keys())
        assert "context" in params

    def test_has_generate_code_method(self):
        assert hasattr(BasePlatformAdapter, "generate_code")
        sig = inspect.signature(BasePlatformAdapter.generate_code)
        params = list(sig.parameters.keys())
        assert "context" in params

    def test_has_generate_tests_method(self):
        assert hasattr(BasePlatformAdapter, "generate_tests")
        sig = inspect.signature(BasePlatformAdapter.generate_tests)
        params = list(sig.parameters.keys())
        assert "context" in params

    def test_has_build_and_deploy_method(self):
        assert hasattr(BasePlatformAdapter, "build_and_deploy")
        sig = inspect.signature(BasePlatformAdapter.build_and_deploy)
        params = list(sig.parameters.keys())
        assert "context" in params

    def test_all_new_methods_are_abstract(self):
        abstract_methods = BasePlatformAdapter.__abstractmethods__
        assert "generate_requirements" in abstract_methods
        assert "generate_code" in abstract_methods
        assert "generate_tests" in abstract_methods
        assert "build_and_deploy" in abstract_methods

    def test_execute_story_still_exists(self):
        """execute_story is deprecated but still present for backwards compat."""
        assert hasattr(BasePlatformAdapter, "execute_story")
