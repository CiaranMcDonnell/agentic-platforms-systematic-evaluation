"""Tests for the CrewAI idiomatic adapter (multi-agent crew)."""
from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from desmet.adapters.crewai import CrewAIAdapter
from desmet.adapters._observation import ObservationCollector, ObservationRequirements
from desmet.adapters._retry import ProgressReporter
from desmet.harness.trace import (
    AgentTrace,
)


@pytest.fixture
def adapter():
    return CrewAIAdapter(config={"model": "gpt-5.2-2025-12-11"})


class TestCrewAIAdapterInterface:
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
        """_run_agent is the shared CrewAI-specific runner."""
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
        assert info.id == "crewai"
        assert info.name == "CrewAI"

    def test_has_create_trace_callbacks(self, adapter):
        assert hasattr(adapter, "_create_trace_callbacks")
        assert callable(adapter._create_trace_callbacks)

    def test_no_legacy_tool_methods(self, adapter):
        """Deleted legacy tool helpers should no longer exist."""
        assert not hasattr(adapter, "_create_tools_from_stage_context")
        assert not hasattr(adapter, "_create_tools")

    def test_run_agent_signature(self, adapter):
        sig = inspect.signature(adapter._run_agent)
        params = list(sig.parameters.keys())
        assert "stage_name" in params
        assert "prompt" in params
        assert "collector" in params
        assert "context" in params
        assert "policy" in params
        assert "progress" in params


def _make_collector(trace: AgentTrace) -> ObservationCollector:
    """Return a minimal ObservationCollector suitable for callback tests."""
    return ObservationCollector(
        trace,
        requirements=ObservationRequirements(
            usage=False,
            tool_calls=False,
            llm_duration=False,
            messages=False,
            iterations=False,
        ),
    )


def _make_progress(collector: ObservationCollector) -> ProgressReporter:
    """Return a no-op ProgressReporter for callback tests."""
    return ProgressReporter(callback=None, collector=collector)


class TestTraceCallbacks:
    """Tests for CrewAI step_callback / task_callback tracing.

    Verifies that callbacks use the shared _tracing helpers
    (record_message, record_tool_call) rather than direct append.
    """

    def test_step_callback_increments_counter(self):
        trace = AgentTrace()
        collector = _make_collector(trace)
        step_cb, _, counter = CrewAIAdapter._create_trace_callbacks(collector, _make_progress(collector))

        step_cb("first step output")
        step_cb("second step output")

        assert counter[0] == 2
        assert trace.total_iterations == 2

    def test_step_callback_records_messages(self):
        trace = AgentTrace()
        collector = _make_collector(trace)
        step_cb, _, _ = CrewAIAdapter._create_trace_callbacks(collector, _make_progress(collector))

        step_cb("thinking about the problem")

        assert len(trace.messages) == 1
        assert trace.messages[0].role == "assistant"
        assert "thinking about the problem" in trace.messages[0].content
        assert trace.messages[0].metadata["step"] == 1

    def test_step_callback_captures_tool_calls(self):
        trace = AgentTrace()
        collector = _make_collector(trace)
        step_cb, _, _ = CrewAIAdapter._create_trace_callbacks(collector, _make_progress(collector))

        # Simulate a CrewAI step output with tool attributes
        tool_step = SimpleNamespace(
            tool="read_file",
            tool_input={"path": "main.py"},
            result="file contents here",
            log="Using tool: read_file",
        )
        step_cb(tool_step)

        assert len(trace.tool_calls) == 1
        assert trace.tool_calls[0].tool_name == "read_file"
        assert trace.tool_calls[0].arguments == {"path": "main.py"}
        assert trace.tool_calls[0].result == "file contents here"
        assert trace.tool_calls[0].success is True

    def test_step_callback_wraps_non_dict_tool_input(self):
        """When tool_input is not a dict, it should be wrapped in {"input": ...}."""
        trace = AgentTrace()
        collector = _make_collector(trace)
        step_cb, _, _ = CrewAIAdapter._create_trace_callbacks(collector, _make_progress(collector))

        tool_step = SimpleNamespace(
            tool="execute_shell",
            tool_input="ls -la",
            result="total 0",
            log="Running shell command",
        )
        step_cb(tool_step)

        assert trace.tool_calls[0].arguments == {"input": "ls -la"}

    def test_step_callback_skips_tool_call_when_no_tool_attr(self):
        trace = AgentTrace()
        collector = _make_collector(trace)
        step_cb, _, _ = CrewAIAdapter._create_trace_callbacks(collector, _make_progress(collector))

        # Step without tool attributes (pure reasoning)
        step_cb("just thinking")

        assert len(trace.tool_calls) == 0
        assert len(trace.messages) == 1

    def test_task_callback_records_completion(self):
        trace = AgentTrace()
        collector = _make_collector(trace)
        _, task_cb, _ = CrewAIAdapter._create_trace_callbacks(collector, _make_progress(collector))

        task_cb("Task completed: all requirements documented")

        assert len(trace.messages) == 1
        assert trace.messages[0].metadata["event"] == "task_complete"
        assert "requirements documented" in trace.messages[0].content

    def test_step_callback_uses_log_attr_when_available(self):
        trace = AgentTrace()
        collector = _make_collector(trace)
        step_cb, _, _ = CrewAIAdapter._create_trace_callbacks(collector, _make_progress(collector))

        step = SimpleNamespace(log="Agent decided to read the file")
        step_cb(step)

        assert "Agent decided to read the file" in trace.messages[0].content

    def test_step_callback_falls_back_to_text_attr(self):
        """When log is empty/missing but text is present, use text."""
        trace = AgentTrace()
        collector = _make_collector(trace)
        step_cb, _, _ = CrewAIAdapter._create_trace_callbacks(collector, _make_progress(collector))

        step = SimpleNamespace(log="", text="Fallback text content")
        step_cb(step)

        assert "Fallback text content" in trace.messages[0].content

    def test_multiple_steps_and_task_combined(self):
        trace = AgentTrace()
        collector = _make_collector(trace)
        step_cb, task_cb, counter = CrewAIAdapter._create_trace_callbacks(collector, _make_progress(collector))

        # 3 steps then task completion
        step_cb("step 1: reasoning")
        tool_step = SimpleNamespace(
            tool="write_file",
            tool_input={"path": "out.py", "content": "print('hi')"},
            result="ok",
            log="Writing file",
        )
        step_cb(tool_step)
        step_cb("step 3: final answer")
        task_cb("Done!")

        assert counter[0] == 3
        assert len(trace.messages) == 4  # 3 steps + 1 task complete
        assert len(trace.tool_calls) == 1
        assert trace.tool_calls[0].tool_name == "write_file"

    def test_messages_have_timestamps(self):
        """Verify that record_message sets timestamps (via _tracing helpers)."""
        trace = AgentTrace()
        collector = _make_collector(trace)
        step_cb, task_cb, _ = CrewAIAdapter._create_trace_callbacks(collector, _make_progress(collector))

        step_cb("step with timestamp")
        task_cb("task with timestamp")

        assert trace.messages[0].timestamp is not None
        assert trace.messages[1].timestamp is not None


class TestCrewAIAdapterStructure:
    def test_imports(self):
        from desmet.adapters.crewai import CrewAIAdapter
        adapter = CrewAIAdapter()
        assert adapter.TOOL_FORMAT is not None

    def test_observability_reports_auto_recovery(self):
        from desmet.adapters.crewai import CrewAIAdapter
        adapter = CrewAIAdapter()
        info = adapter.get_failure_handling_info()
        assert info["has_auto_recovery"] is True

    def test_observability_reports_idempotent(self):
        from desmet.adapters.crewai import CrewAIAdapter
        adapter = CrewAIAdapter()
        info = adapter.get_failure_handling_info()
        assert info["is_idempotent"] is True

    def test_observability_notes_mention_multi_agent(self):
        from desmet.adapters.crewai import CrewAIAdapter
        adapter = CrewAIAdapter()
        info = adapter.get_observability_info()
        notes = info.get("notes", "").lower()
        assert "multi-agent" in notes or "crew" in notes

    def test_observability_notes_mention_retries(self):
        from desmet.adapters.crewai import CrewAIAdapter
        adapter = CrewAIAdapter()
        info = adapter.get_failure_handling_info()
        assert "retries" in info["notes"].lower() or "retry" in info["notes"].lower()

    def test_no_monkeypatch_method(self):
        """The OpenAI SDK monkeypatch was removed — it should no longer exist."""
        from desmet.adapters.crewai import CrewAIAdapter
        assert not hasattr(CrewAIAdapter, "_patch_tool_call_handling")
        assert not hasattr(CrewAIAdapter, "_tool_call_patch_applied")

    def test_max_retries_constant(self):
        from desmet.adapters._retry import RetryPolicy
        assert RetryPolicy().max_retries == 3

    def test_has_build_crew(self, adapter):
        """_build_crew is the crew construction helper."""
        assert hasattr(adapter, "_build_crew")
        assert callable(adapter._build_crew)


class TestIterationBudget:
    def test_budget_allocation_default_50(self):
        from desmet.adapters.crewai import _compute_iter_budget
        planner, executor, reviewer = _compute_iter_budget(50)
        assert planner == 10
        assert executor == 30
        assert reviewer == 10

    def test_budget_allocation_custom_30(self):
        from desmet.adapters.crewai import _compute_iter_budget
        planner, executor, reviewer = _compute_iter_budget(30)
        assert planner + executor + reviewer <= 30
        assert executor > planner
        assert executor > reviewer

    def test_budget_allocation_minimum(self):
        from desmet.adapters.crewai import _compute_iter_budget
        planner, executor, reviewer = _compute_iter_budget(10)
        assert planner >= 1
        assert executor >= 1
        assert reviewer >= 1

    def test_budget_allocation_retry(self):
        """On retry, planner budget is 0 and executor gets the extra allocation."""
        from desmet.adapters.crewai import _compute_iter_budget
        planner, executor, reviewer = _compute_iter_budget(50, retry=True)
        assert planner == 0
        assert reviewer == 10
        assert executor == 40

    def test_budget_allocation_retry_minimum(self):
        from desmet.adapters.crewai import _compute_iter_budget
        planner, executor, reviewer = _compute_iter_budget(5, retry=True)
        assert planner == 0
        assert executor >= 1
        assert reviewer >= 1
