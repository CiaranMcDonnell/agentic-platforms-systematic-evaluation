"""Tests for the Microsoft Agent Framework adapter (MagenticOne orchestration)."""
from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

import pytest

from desmet.adapters.multiagent.agent_framework import AgentFrameworkAdapter
from desmet.adapters._shared.observation import ObservationCollector
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
        from desmet.adapters._shared.tools import ToolFormat
        assert adapter.TOOL_FORMAT == ToolFormat.AGENT_FRAMEWORK

    def test_run_agent_signature(self, adapter):
        sig = inspect.signature(adapter._run_agent)
        params = list(sig.parameters.keys())
        assert "stage_name" in params
        assert "prompt" in params
        assert "collector" in params
        assert "context" in params
        assert "policy" in params
        assert "progress" in params


class TestAgentFrameworkAdapterStructure:
    def test_imports(self):
        from desmet.adapters.multiagent.agent_framework import AgentFrameworkAdapter
        adapter = AgentFrameworkAdapter()
        assert adapter.TOOL_FORMAT is not None

    def test_max_stall_count_constant(self):
        from desmet.adapters.multiagent.agent_framework import MAX_STALL_COUNT
        assert MAX_STALL_COUNT == 3

    def test_has_create_client(self, adapter):
        """_create_client builds the chat client."""
        assert hasattr(adapter, "_create_client")
        assert callable(adapter._create_client)

    def test_has_implementation_plan_model(self):
        from desmet.adapters.multiagent.agent_framework import ImplementationPlan
        plan = ImplementationPlan(
            steps=["step 1", "step 2"],
            files_to_create=["main.py"],
            files_to_modify=[],
        )
        assert len(plan.steps) == 2
        assert plan.files_to_create == ["main.py"]


class TestLifecycle:
    def test_initialize_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.initialize)

    def test_shutdown_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.shutdown)

    def test_health_check_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.health_check)

    @pytest.mark.asyncio
    async def test_shutdown_clears_state(self, adapter):
        """shutdown() should reset client and initialized flag."""
        await adapter.shutdown()
        assert adapter._client is None
        assert adapter._initialized is False


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
    def test_factory_exists(self):
        from desmet.adapters.multiagent.agent_framework import _build_usage_middleware
        assert _build_usage_middleware is not None

    def test_factory_returns_chat_middleware_subclass(self):
        """The middleware must subclass ``agent_framework.ChatMiddleware``
        or the framework silently ignores it."""
        pytest.importorskip("agent_framework")
        from agent_framework import ChatMiddleware
        from desmet.adapters.multiagent.agent_framework import _build_usage_middleware
        trace = AgentTrace()
        collector = ObservationCollector(trace)
        mw = _build_usage_middleware(collector)
        assert isinstance(mw, ChatMiddleware)
        assert callable(getattr(mw, "process", None))


class TestRegistryIntegration:
    def test_agent_framework_in_implemented_platforms(self):
        from desmet.adapters.registry import list_available_platforms
        platforms = list_available_platforms()
        assert "microsoft_agent_framework" in platforms

    def test_registry_returns_correct_adapter(self):
        from desmet.adapters.registry import get_adapter
        adapter = get_adapter("microsoft_agent_framework")
        assert isinstance(adapter, AgentFrameworkAdapter)

    def test_registry_adapter_has_correct_tool_format(self):
        from desmet.adapters.registry import get_adapter
        from desmet.adapters._shared.tools import ToolFormat
        adapter = get_adapter("microsoft_agent_framework")
        assert adapter.TOOL_FORMAT == ToolFormat.AGENT_FRAMEWORK


def test_planner_fallback_records_plan_source():
    """Structured-planner exception handling must record trace.metadata['plan_source']."""
    import inspect

    from desmet.adapters.multiagent.agent_framework import AgentFrameworkAdapter

    src = inspect.getsource(AgentFrameworkAdapter._run_agent)
    assert 'plan_source' in src
    assert 'trace.metadata' in src or 'metadata["plan_source"]' in src or "metadata['plan_source']" in src
    # Must not silently swallow — either logs, records error, or narrows except.
    assert 'errors.append' in src or '_log.warning' in src


def test_maf_does_not_double_record_llm_duration():
    """End-of-run record_llm_response(raw_usage=None, duration_ms=llm_time_estimate)
    must be gone — middleware already records per-call durations authoritatively."""
    import inspect
    from desmet.adapters.multiagent import agent_framework as maf

    src = inspect.getsource(maf.AgentFrameworkAdapter._run_agent)
    assert "llm_time_estimate" not in src, (
        "End-of-run llm_time_estimate catch-up still present; middleware "
        "already records per-call durations, so this inflates total duration ~2x."
    )
