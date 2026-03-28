"""Tests for the Microsoft Agent Framework adapter (MagenticOne orchestration)."""
from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

import pytest

from desmet.adapters.agent_framework import AgentFrameworkAdapter
from desmet.harness.trace import AgentTrace


@pytest.fixture
def adapter():
    return AgentFrameworkAdapter(config={"model": "gpt-5.2-2025-12-11"})


class TestAgentFrameworkAdapterInterface:
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

    def test_has_run_agent(self, adapter):
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

    def test_platform_info(self, adapter):
        info = adapter.platform_info
        assert info.id == "microsoft_agent_framework"
        assert info.name == "Microsoft Agent Framework"

    def test_no_legacy_stub(self, adapter):
        """The adapter should not be a stub anymore."""
        from desmet.adapters._tools import ToolFormat
        assert adapter.TOOL_FORMAT == ToolFormat.AGENT_FRAMEWORK

    def test_run_agent_signature(self, adapter):
        sig = inspect.signature(adapter._run_agent)
        params = list(sig.parameters.keys())
        assert "stage_name" in params
        assert "prompt" in params
        assert "trace" in params
        assert "context" in params


class TestAgentFrameworkAdapterStructure:
    def test_imports(self):
        from desmet.adapters.agent_framework import AgentFrameworkAdapter
        adapter = AgentFrameworkAdapter()
        assert adapter.TOOL_FORMAT is not None

    def test_max_stall_count_constant(self):
        from desmet.adapters.agent_framework import MAX_STALL_COUNT
        assert MAX_STALL_COUNT == 3

    def test_has_create_model(self, adapter):
        """_create_model builds the chat client."""
        assert hasattr(adapter, "_create_model")
        assert callable(adapter._create_model)

    def test_has_implementation_plan_model(self):
        from desmet.adapters.agent_framework import ImplementationPlan
        plan = ImplementationPlan(
            steps=["step 1", "step 2"],
            files_to_create=["main.py"],
            files_to_modify=[],
        )
        assert len(plan.steps) == 2
        assert plan.files_to_create == ["main.py"]


class TestObservabilityMetadata:
    def test_observability_reports_stall_detection(self):
        adapter = AgentFrameworkAdapter()
        info = adapter.get_observability_info()
        assert info["has_stall_detection"] is True

    def test_observability_reports_checkpointing(self):
        adapter = AgentFrameworkAdapter()
        info = adapter.get_observability_info()
        assert info["has_checkpointing"] is True

    def test_observability_trace_format_is_otel(self):
        adapter = AgentFrameworkAdapter()
        info = adapter.get_observability_info()
        assert info["trace_format"] == "opentelemetry"

    def test_failure_handling_reports_auto_recovery(self):
        adapter = AgentFrameworkAdapter()
        info = adapter.get_failure_handling_info()
        assert info["has_auto_recovery"] is True

    def test_failure_handling_mentions_manager(self):
        adapter = AgentFrameworkAdapter()
        info = adapter.get_failure_handling_info()
        notes = info.get("notes", "").lower()
        assert "manager" in notes or "magentic" in notes

    def test_failure_handling_mentions_stall(self):
        adapter = AgentFrameworkAdapter()
        info = adapter.get_failure_handling_info()
        notes = info.get("notes", "").lower()
        assert "stall" in notes


class TestUsageTrackingMiddleware:
    def test_middleware_class_exists(self):
        from desmet.adapters.agent_framework import UsageTrackingMiddleware
        assert UsageTrackingMiddleware is not None

    def test_middleware_initializes_with_trace(self):
        from desmet.adapters.agent_framework import UsageTrackingMiddleware
        trace = AgentTrace()
        mw = UsageTrackingMiddleware(trace, model_name="gpt-5.2")
        assert mw._trace is trace
        assert mw._model_name == "gpt-5.2"

    def test_middleware_is_thread_safe(self):
        """Middleware uses a lock for concurrent agent access."""
        from desmet.adapters.agent_framework import UsageTrackingMiddleware
        trace = AgentTrace()
        mw = UsageTrackingMiddleware(trace, model_name="gpt-5.2")
        assert hasattr(mw, "_lock")
