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
        assert adapter.TOOL_FORMAT == ToolFormat.GOOGLE_ADK

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

    def test_litellm_gets_call_timeout_and_retries(self):
        """LiteLLM ignores GenerateContentConfig.http_options, so the per-call
        timeout and retry count must be passed to LiteLlm (else 600 s default)."""
        pytest.importorskip("google.adk.models.lite_llm")
        from desmet.adapters.sdk.google_adk import GoogleADKAdapter
        from desmet.llm_config import LLMConfig, Provider
        cfg = LLMConfig(
            model="z-ai/glm-5.3", temperature=0.0, provider=Provider.OPENROUTER,
            api_key="test", timeout_seconds=120.0, max_retries=0,
        )
        result = GoogleADKAdapter()._resolve_model_id(cfg)
        assert result._additional_args["timeout"] == 120.0
        assert result._additional_args["num_retries"] == 0


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
        assert adapter.TOOL_FORMAT == ToolFormat.GOOGLE_ADK


def test_planner_fallback_records_plan_source():
    """Structured-planner exception handling must record trace.metadata['plan_source']."""
    import inspect

    from desmet.adapters.sdk.google_adk import GoogleADKAdapter

    src = inspect.getsource(GoogleADKAdapter._run_planner)
    assert 'plan_source' in src
    assert 'trace.metadata' in src or 'metadata["plan_source"]' in src or "metadata['plan_source']" in src
    # Must not silently swallow — either logs, records error, or narrows except.
    assert 'errors.append' in src or '_log.warning' in src


async def test_planner_spent_budget_skips_the_loop(monkeypatch, tmp_path):
    """When the planner used the whole LLM-call budget, the executor/reviewer
    loop must not run at all (max(1, remaining) allowed one call over)."""
    pytest.importorskip("google.adk")
    import google.adk.runners

    from desmet.adapters._shared.budget import budget_exhausted
    from desmet.adapters._shared.observation import (
        ObservationCollector,
        ObservationRequirements,
    )
    from desmet.adapters._shared.retry import ProgressReporter, RetryPolicy
    from desmet.adapters._shared.tracing import record_usage
    from desmet.adapters.sdk.google_adk import GoogleADKAdapter
    from desmet.harness.context import StageContext
    from desmet.adapters._shared.planning import ImplementationPlan
    from desmet.harness.story import DifficultyLevel, UserStory
    from desmet.harness.trace import AgentTrace

    runs: list = []

    class FakeRunner:
        def __init__(self, **kw):
            pass

        async def run_async(self, **kw):
            runs.append(kw["run_config"].max_llm_calls)
            return
            yield

    monkeypatch.setattr(google.adk.runners, "Runner", FakeRunner)
    adapter = GoogleADKAdapter(config={"model": "gemini-2.5-flash"})
    adapter._model_id = "gemini-2.5-flash"

    async def spend_budget(stage_name, prompt, collector, progress, temperature=0.0):
        for _ in range(context.max_iterations):
            record_usage(collector.trace, input_tokens=10)
        return ImplementationPlan(steps=["s"], files_to_create=[], files_to_modify=[])

    monkeypatch.setattr(adapter, "_run_planner", spend_budget)
    policy = RetryPolicy(max_retries=0, stage_name="requirements", workspace=tmp_path)
    monkeypatch.setattr(policy, "validate", lambda: (False, "missing"))
    story = UserStory(
        id="US-001", title="t", description="d",
        difficulty=DifficultyLevel.BASIC, category="smoke", prompt="p",
    )
    context = StageContext(
        story=story, workspace=tmp_path, platform_id="google_adk", max_iterations=4,
    )
    collector = ObservationCollector(
        AgentTrace(),
        requirements=ObservationRequirements(
            usage=False, tool_calls=False, llm_duration=False,
            messages=False, iterations=False,
        ),
    )
    _, success = await adapter._run_agent(
        "requirements", "p", None, [], collector, context, policy,
        ProgressReporter(callback=None, collector=collector),
    )
    assert runs == []
    assert budget_exhausted(collector.trace)
    assert success is False


async def test_freetext_planner_fallback_records_usage(monkeypatch):
    """When the structured planner fails, the free-text fallback's paid call
    must be counted (tokens + shared LLM-call budget), like the structured one."""
    pytest.importorskip("google.adk")
    from types import SimpleNamespace

    import google.adk.runners

    from desmet.adapters._shared.observation import ObservationCollector
    from desmet.adapters._shared.retry import ProgressReporter
    from desmet.adapters.sdk.google_adk import GoogleADKAdapter
    from desmet.harness.trace import AgentTrace

    class FakeRunner:
        def __init__(self, *, app_name, **kw):
            self.app_name = app_name

        async def run_async(self, **kw):
            if self.app_name == "desmet_planner":
                raise ValueError("structured output not supported")
            yield SimpleNamespace(
                content=SimpleNamespace(parts=[SimpleNamespace(text="1. write app.py")]),
                usage_metadata={"prompt_token_count": 50, "candidates_token_count": 7},
            )

    monkeypatch.setattr(google.adk.runners, "Runner", FakeRunner)
    adapter = GoogleADKAdapter(config={"model": "gemini-2.5-flash"})
    adapter._model_id = "gemini-2.5-flash"
    collector = ObservationCollector(AgentTrace())
    plan = await adapter._run_planner(
        "codegen", "p", collector, ProgressReporter(callback=None, collector=collector),
    )
    trace = collector.trace
    assert trace.metadata["plan_source"] == "freetext"
    assert plan.steps
    assert trace.total_tokens_input == 50 and trace.total_tokens_output == 7
    assert trace.metadata["llm_calls"] == 1
