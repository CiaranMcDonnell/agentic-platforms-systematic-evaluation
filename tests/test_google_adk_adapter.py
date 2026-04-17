"""Tests for the Google ADK adapter (SequentialAgent + LoopAgent orchestration)."""
from __future__ import annotations

import inspect

import pytest

from desmet.adapters._shared.tools import ToolFormat


@pytest.fixture
def adapter():
    from desmet.adapters.sdk.google_adk import GoogleADKAdapter
    return GoogleADKAdapter(config={"model": "gemini-2.5-flash"})


class TestGoogleADKAdapterInterface:
    def test_imports(self):
        from desmet.adapters.sdk.google_adk import GoogleADKAdapter
        adapter = GoogleADKAdapter()
        assert adapter.TOOL_FORMAT == ToolFormat.CALLABLE

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

    def test_run_agent_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter._run_agent)

    def test_has_execute_stage(self, adapter):
        assert hasattr(adapter, "_execute_stage")
        assert callable(adapter._execute_stage)

    def test_generate_requirements_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.generate_requirements)

    def test_generate_code_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.generate_code)

    def test_generate_tests_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.generate_tests)

    def test_build_and_deploy_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.build_and_deploy)

    def test_run_agent_signature(self, adapter):
        sig = inspect.signature(adapter._run_agent)
        params = list(sig.parameters.keys())
        assert "stage_name" in params
        assert "prompt" in params
        assert "collector" in params
        assert "context" in params
        assert "policy" in params
        assert "progress" in params

    def test_no_legacy_stub(self, adapter):
        """Adapter must not raise NotImplementedError on stage methods."""
        import ast
        import pathlib
        src = pathlib.Path("src/desmet/adapters/sdk/google_adk.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise):
                for child in ast.walk(node):
                    if isinstance(child, ast.Name) and child.id == "NotImplementedError":
                        pytest.fail("Adapter still contains NotImplementedError stubs")


class TestGoogleADKAdapterStructure:
    def test_platform_info(self):
        from desmet.adapters.sdk.google_adk import GoogleADKAdapter
        adapter = GoogleADKAdapter()
        info = adapter.platform_info
        assert info.id == "google_adk"
        assert info.name == "Google ADK"

    def test_resolve_model_google(self):
        from desmet.adapters.sdk.google_adk import GoogleADKAdapter
        from desmet.llm_config import LLMConfig, Provider
        adapter = GoogleADKAdapter()
        cfg = LLMConfig(
            model="gemini-2.5-flash", temperature=0.0,
            provider=Provider.GOOGLE, api_key="test",
        )
        assert adapter._resolve_model_id(cfg) == "gemini-2.5-flash"

    def test_resolve_model_openai(self):
        pytest.importorskip("google.adk.models.lite_llm")
        from desmet.adapters.sdk.google_adk import GoogleADKAdapter
        from desmet.llm_config import LLMConfig, Provider
        adapter = GoogleADKAdapter()
        cfg = LLMConfig(
            model="gpt-5.4-2026-03-05", temperature=0.0,
            provider=Provider.OPENAI, api_key="test",
        )
        result = adapter._resolve_model_id(cfg)
        # Non-Gemini models are wrapped in a LiteLlm instance so ADK routes
        # them through LiteLLM — ADK does not recognise a bare provider/model
        # string.  Inspect the wrapper's ``.model`` attribute.
        assert getattr(result, "model", None) == "openai/gpt-5.4-2026-03-05"

    def test_resolve_model_anthropic(self):
        pytest.importorskip("google.adk.models.lite_llm")
        from desmet.adapters.sdk.google_adk import GoogleADKAdapter
        from desmet.llm_config import LLMConfig, Provider
        adapter = GoogleADKAdapter()
        cfg = LLMConfig(
            model="claude-sonnet-4-20250514", temperature=0.0,
            provider=Provider.ANTHROPIC, api_key="test",
        )
        result = adapter._resolve_model_id(cfg)
        assert getattr(result, "model", None) == "anthropic/claude-sonnet-4-20250514"

    def test_resolve_model_openrouter(self):
        pytest.importorskip("google.adk.models.lite_llm")
        from desmet.adapters.sdk.google_adk import GoogleADKAdapter
        from desmet.llm_config import LLMConfig, Provider
        adapter = GoogleADKAdapter()
        cfg = LLMConfig(
            model="anthropic/claude-sonnet-4", temperature=0.0,
            provider=Provider.OPENROUTER, api_key="test",
        )
        result = adapter._resolve_model_id(cfg)
        assert getattr(result, "model", None) == "openrouter/anthropic/claude-sonnet-4"


class TestObservabilityMetadata:
    def test_observability_reports_replay(self):
        from desmet.adapters.sdk.google_adk import GoogleADKAdapter
        info = GoogleADKAdapter().get_observability_info()
        assert info["has_replay"] is True

    def test_observability_reports_state_inspection(self):
        from desmet.adapters.sdk.google_adk import GoogleADKAdapter
        info = GoogleADKAdapter().get_observability_info()
        assert info["has_state_inspection"] is True

    def test_observability_trace_format(self):
        from desmet.adapters.sdk.google_adk import GoogleADKAdapter
        info = GoogleADKAdapter().get_observability_info()
        assert info["trace_format"] == "Event stream"

    def test_observability_mentions_sequential(self):
        from desmet.adapters.sdk.google_adk import GoogleADKAdapter
        info = GoogleADKAdapter().get_observability_info()
        assert "sequential" in info.get("notes", "").lower()

    def test_failure_handling_reports_auto_recovery(self):
        from desmet.adapters.sdk.google_adk import GoogleADKAdapter
        info = GoogleADKAdapter().get_failure_handling_info()
        assert info["has_auto_recovery"] is True

    def test_failure_handling_mentions_loop(self):
        from desmet.adapters.sdk.google_adk import GoogleADKAdapter
        info = GoogleADKAdapter().get_failure_handling_info()
        assert "loop" in info.get("notes", "").lower()

    def test_failure_handling_mentions_exit_loop(self):
        from desmet.adapters.sdk.google_adk import GoogleADKAdapter
        info = GoogleADKAdapter().get_failure_handling_info()
        assert "exit_loop" in info.get("notes", "").lower()


class TestLifecycle:
    def test_initialize_is_coroutine(self):
        from desmet.adapters.sdk.google_adk import GoogleADKAdapter
        assert inspect.iscoroutinefunction(GoogleADKAdapter().initialize)

    def test_shutdown_is_coroutine(self):
        from desmet.adapters.sdk.google_adk import GoogleADKAdapter
        assert inspect.iscoroutinefunction(GoogleADKAdapter().shutdown)

    def test_health_check_is_coroutine(self):
        from desmet.adapters.sdk.google_adk import GoogleADKAdapter
        assert inspect.iscoroutinefunction(GoogleADKAdapter().health_check)

    @pytest.mark.asyncio
    async def test_shutdown_clears_state(self):
        from desmet.adapters.sdk.google_adk import GoogleADKAdapter
        adapter = GoogleADKAdapter()
        await adapter.shutdown()
        assert adapter._model_id is None
        assert adapter._initialized is False


class TestRegistryIntegration:
    def test_google_adk_in_implemented_platforms(self):
        from desmet.adapters.registry import list_available_platforms
        platforms = list_available_platforms()
        assert "google_adk" in platforms

    def test_registry_returns_correct_adapter(self):
        from desmet.adapters.registry import get_adapter
        from desmet.adapters.sdk.google_adk import GoogleADKAdapter
        adapter = get_adapter("google_adk")
        assert isinstance(adapter, GoogleADKAdapter)

    def test_registry_adapter_has_correct_tool_format(self):
        from desmet.adapters.registry import get_adapter
        from desmet.adapters._shared.tools import ToolFormat
        adapter = get_adapter("google_adk")
        assert adapter.TOOL_FORMAT == ToolFormat.CALLABLE
