"""Tests for CrewAI adapter's new SDLC stage methods."""
import pytest
import inspect
from types import SimpleNamespace

from desmet.adapters.crewai import CrewAIAdapter
from desmet.harness.base import (
    AgentTrace,
    StageContext,
    RequirementsResult,
    CodeResult,
    TestResult,
    DeployResult,
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

    def test_execute_story_inherited(self, adapter):
        """execute_story should exist (inherited from BasePlatformAdapter)."""
        assert hasattr(adapter, "execute_story")
        assert callable(adapter.execute_story)

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

    def test_execute_story_is_coroutine(self, adapter):
        """execute_story must remain async for backwards compat."""
        assert inspect.iscoroutinefunction(adapter.execute_story)

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
        assert "trace" in params
        assert "context" in params


class TestTraceCallbacks:
    """Tests for CrewAI step_callback / task_callback tracing.

    Verifies that callbacks use the shared _tracing helpers
    (record_message, record_tool_call) rather than direct append.
    """

    def test_step_callback_increments_counter(self):
        trace = AgentTrace()
        step_cb, _, counter = CrewAIAdapter._create_trace_callbacks(trace)

        step_cb("first step output")
        step_cb("second step output")

        assert counter[0] == 2
        assert trace.total_iterations == 2

    def test_step_callback_records_messages(self):
        trace = AgentTrace()
        step_cb, _, _ = CrewAIAdapter._create_trace_callbacks(trace)

        step_cb("thinking about the problem")

        assert len(trace.messages) == 1
        assert trace.messages[0].role == "assistant"
        assert "thinking about the problem" in trace.messages[0].content
        assert trace.messages[0].metadata["step"] == 1

    def test_step_callback_captures_tool_calls(self):
        trace = AgentTrace()
        step_cb, _, _ = CrewAIAdapter._create_trace_callbacks(trace)

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
        step_cb, _, _ = CrewAIAdapter._create_trace_callbacks(trace)

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
        step_cb, _, _ = CrewAIAdapter._create_trace_callbacks(trace)

        # Step without tool attributes (pure reasoning)
        step_cb("just thinking")

        assert len(trace.tool_calls) == 0
        assert len(trace.messages) == 1

    def test_task_callback_records_completion(self):
        trace = AgentTrace()
        _, task_cb, _ = CrewAIAdapter._create_trace_callbacks(trace)

        task_cb("Task completed: all requirements documented")

        assert len(trace.messages) == 1
        assert trace.messages[0].metadata["event"] == "task_complete"
        assert "requirements documented" in trace.messages[0].content

    def test_step_callback_uses_log_attr_when_available(self):
        trace = AgentTrace()
        step_cb, _, _ = CrewAIAdapter._create_trace_callbacks(trace)

        step = SimpleNamespace(log="Agent decided to read the file")
        step_cb(step)

        assert "Agent decided to read the file" in trace.messages[0].content

    def test_step_callback_falls_back_to_text_attr(self):
        """When log is empty/missing but text is present, use text."""
        trace = AgentTrace()
        step_cb, _, _ = CrewAIAdapter._create_trace_callbacks(trace)

        step = SimpleNamespace(log="", text="Fallback text content")
        step_cb(step)

        assert "Fallback text content" in trace.messages[0].content

    def test_multiple_steps_and_task_combined(self):
        trace = AgentTrace()
        step_cb, task_cb, counter = CrewAIAdapter._create_trace_callbacks(trace)

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
        step_cb, task_cb, _ = CrewAIAdapter._create_trace_callbacks(trace)

        step_cb("step with timestamp")
        task_cb("task with timestamp")

        assert trace.messages[0].timestamp is not None
        assert trace.messages[1].timestamp is not None
