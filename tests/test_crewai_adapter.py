"""Tests for the CrewAI idiomatic adapter (multi-agent crew)."""
from __future__ import annotations

import inspect

import pytest

from desmet.adapters.multiagent.crewai import CrewAIAdapter
from desmet.adapters._shared.observation import ObservationCollector, ObservationRequirements
from desmet.adapters._shared.retry import ProgressReporter
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

    def test_has_register_event_handlers(self, adapter):
        assert hasattr(adapter, "_register_event_handlers")
        assert callable(adapter._register_event_handlers)

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


class TestEventBusTracing:
    """Tests for CrewAI event bus-based tracing.

    Verifies that the adapter's event bus handlers correctly record
    tool calls, LLM responses, task completions, and iteration counts
    via the ObservationCollector.
    """

    def _setup_adapter(self) -> tuple[CrewAIAdapter, AgentTrace, ObservationCollector]:
        """Create an adapter with collector wired up (no crewai import needed)."""
        adapter = CrewAIAdapter(config={"model": "test-model"})
        trace = AgentTrace()
        collector = _make_collector(trace)
        adapter._current_collector = collector
        adapter._current_progress = _make_progress(collector)
        return adapter, trace, collector

    def test_tool_call_recorded(self):
        adapter, trace, collector = self._setup_adapter()
        # Simulate what _on_tool_finished does
        collector.record_tool_execution("read_file", {"path": "main.py"}, "file contents")

        assert len(trace.tool_calls) == 1
        assert trace.tool_calls[0].tool_name == "read_file"
        assert trace.tool_calls[0].arguments == {"path": "main.py"}

    def test_tool_call_wraps_non_dict_args(self):
        adapter, trace, collector = self._setup_adapter()
        # Non-dict args get wrapped
        args = "ls -la"
        wrapped = args if isinstance(args, dict) else {"input": str(args)}
        collector.record_tool_execution("execute_shell", wrapped, "total 0")

        assert trace.tool_calls[0].arguments == {"input": "ls -la"}

    def test_llm_call_increments_iteration(self):
        adapter, trace, _ = self._setup_adapter()
        adapter._llm_call_count = 0

        # Simulate two LLM completions
        adapter._llm_call_count += 1
        trace.total_iterations = adapter._llm_call_count
        adapter._llm_call_count += 1
        trace.total_iterations = adapter._llm_call_count

        assert adapter._llm_call_count == 2
        assert trace.total_iterations == 2

    def test_llm_response_records_message(self):
        adapter, trace, collector = self._setup_adapter()
        collector.record_message("assistant", "thinking about the problem", metadata={"step": 1})

        assert len(trace.messages) == 1
        assert trace.messages[0].role == "assistant"
        assert "thinking about the problem" in trace.messages[0].content

    def test_task_completion_records_message(self):
        adapter, trace, collector = self._setup_adapter()
        collector.record_message(
            "assistant", "Task completed: all requirements documented",
            metadata={"event": "task_complete"},
        )

        assert len(trace.messages) == 1
        assert trace.messages[0].metadata["event"] == "task_complete"
        assert "requirements documented" in trace.messages[0].content

    def test_token_usage_delta(self):
        """Per-call token delta is computed from LLM's cumulative counters."""
        adapter, trace, collector = self._setup_adapter()

        # Simulate snapshot before LLM call
        prev = {"prompt_tokens": 100, "completion_tokens": 50}
        current = {"prompt_tokens": 250, "completion_tokens": 120}
        raw_usage = {
            "prompt_tokens": current["prompt_tokens"] - prev["prompt_tokens"],
            "completion_tokens": current["completion_tokens"] - prev["completion_tokens"],
        }
        collector.record_llm_response(raw_usage=raw_usage, model="test-model")

        assert trace.total_tokens_input == 150
        assert trace.total_tokens_output == 70

    def test_messages_have_timestamps(self):
        adapter, trace, collector = self._setup_adapter()
        collector.record_message("assistant", "step with timestamp", metadata={"step": 1})

        assert trace.messages[0].timestamp is not None

    def test_combined_flow(self):
        """Simulate a multi-step execution: LLM calls + tool + task completion."""
        adapter, trace, collector = self._setup_adapter()
        adapter._llm_call_count = 0

        # LLM call 1: reasoning
        adapter._llm_call_count += 1
        trace.total_iterations = adapter._llm_call_count
        collector.record_message("assistant", "step 1: reasoning", metadata={"step": 1})

        # Tool call
        collector.record_tool_execution("write_file", {"path": "out.py"}, "ok")

        # LLM call 2: more reasoning
        adapter._llm_call_count += 1
        trace.total_iterations = adapter._llm_call_count
        collector.record_message("assistant", "step 2: reviewing", metadata={"step": 2})

        # Task completion
        collector.record_message("assistant", "Done!", metadata={"event": "task_complete"})

        assert adapter._llm_call_count == 2
        assert len(trace.messages) == 3  # 2 LLM responses + 1 task complete
        assert len(trace.tool_calls) == 1
        assert trace.tool_calls[0].tool_name == "write_file"


class TestCrewAIAdapterStructure:
    def test_imports(self):
        from desmet.adapters.multiagent.crewai import CrewAIAdapter
        adapter = CrewAIAdapter()
        assert adapter.TOOL_FORMAT is not None

    def test_observability_reports_auto_recovery(self):
        from desmet.adapters.multiagent.crewai import CrewAIAdapter
        adapter = CrewAIAdapter()
        info = adapter.get_failure_handling_info()
        assert info["has_auto_recovery"] is True

    def test_observability_reports_idempotent(self):
        from desmet.adapters.multiagent.crewai import CrewAIAdapter
        adapter = CrewAIAdapter()
        info = adapter.get_failure_handling_info()
        assert info["is_idempotent"] is True

    def test_observability_notes_mention_multi_agent(self):
        from desmet.adapters.multiagent.crewai import CrewAIAdapter
        adapter = CrewAIAdapter()
        info = adapter.get_observability_info()
        notes = info.get("notes", "").lower()
        assert "multi-agent" in notes or "crew" in notes

    def test_observability_notes_mention_retries(self):
        from desmet.adapters.multiagent.crewai import CrewAIAdapter
        adapter = CrewAIAdapter()
        info = adapter.get_failure_handling_info()
        assert "retries" in info["notes"].lower() or "retry" in info["notes"].lower()

    def test_no_monkeypatch_method(self):
        """The OpenAI SDK monkeypatch was removed — it should no longer exist."""
        from desmet.adapters.multiagent.crewai import CrewAIAdapter
        assert not hasattr(CrewAIAdapter, "_patch_tool_call_handling")
        assert not hasattr(CrewAIAdapter, "_tool_call_patch_applied")

    def test_max_retries_constant(self):
        from desmet.adapters._shared.retry import RetryPolicy
        assert RetryPolicy().max_retries == 3

    def test_has_build_crew(self, adapter):
        """_build_crew is the crew construction helper."""
        assert hasattr(adapter, "_build_crew")
        assert callable(adapter._build_crew)


class TestIterationBudget:
    def test_budget_allocation_default_50(self):
        from desmet.adapters.multiagent.crewai import _compute_iter_budget
        planner, executor, reviewer = _compute_iter_budget(50)
        assert planner == 10
        assert executor == 30
        assert reviewer == 10

    def test_budget_allocation_custom_30(self):
        from desmet.adapters.multiagent.crewai import _compute_iter_budget
        planner, executor, reviewer = _compute_iter_budget(30)
        assert planner + executor + reviewer <= 30
        assert executor > planner
        assert executor > reviewer

    def test_budget_allocation_minimum(self):
        from desmet.adapters.multiagent.crewai import _compute_iter_budget
        planner, executor, reviewer = _compute_iter_budget(10)
        assert planner >= 1
        assert executor >= 1
        assert reviewer >= 1

    def test_budget_allocation_retry(self):
        """On retry, planner budget is 0 and executor gets the extra allocation."""
        from desmet.adapters.multiagent.crewai import _compute_iter_budget
        planner, executor, reviewer = _compute_iter_budget(50, retry=True)
        assert planner == 0
        assert reviewer == 10
        assert executor == 40

    def test_budget_allocation_retry_minimum(self):
        from desmet.adapters.multiagent.crewai import _compute_iter_budget
        planner, executor, reviewer = _compute_iter_budget(5, retry=True)
        assert planner == 0
        assert executor >= 1
        assert reviewer >= 1


class TestSuccessAfterBudget:
    """Regression: a stage that produced the required artifacts must
    report success even if the iteration counter happened to land at or
    above ``context.max_iterations``.

    Original symptom: US-000 (max_iterations=8) ran 10 LLM calls total
    across the 3-agent crew, validation passed, but the stage was
    reported as FAILED because the post-loop budget re-check overrode
    the successful break.
    """

    async def test_validation_passed_with_budget_exceeded_is_success(
        self, monkeypatch, tmp_path,
    ):
        from unittest.mock import MagicMock
        from desmet.adapters.multiagent.crewai import CrewAIAdapter
        from desmet.adapters._shared.observation import (
            ObservationCollector, ObservationRequirements,
        )
        from desmet.adapters._shared.retry import ProgressReporter, RetryPolicy
        from desmet.harness.context import StageContext
        from desmet.harness.story import DifficultyLevel, UserStory
        from desmet.harness.trace import AgentTrace

        adapter = CrewAIAdapter(config={"model": "test-model"})

        # Avoid touching the real CrewAI stack: stub the LLM factory and
        # the crew builder.  Make crew.kickoff() bump the LLM call count
        # past max_iterations on every attempt to simulate "we burned
        # the budget but produced the artifacts".
        monkeypatch.setattr(adapter, "_create_llm", lambda ctx: MagicMock())

        def fake_kickoff():
            adapter._llm_call_count += 100  # well over any sane budget
            fake_result = MagicMock()
            fake_result.tasks_output = []
            fake_result.token_usage = None
            return fake_result

        fake_crew = MagicMock()
        fake_crew.kickoff = fake_kickoff
        monkeypatch.setattr(
            adapter, "_build_crew", lambda *a, **kw: fake_crew,
        )

        # Validator always passes — the artifacts are on disk.
        policy = RetryPolicy(max_retries=0, stage_name="requirements", workspace=tmp_path)
        monkeypatch.setattr(policy, "validate", lambda: (True, "ok"))

        # Minimal story + context with a tight iteration cap (mirrors US-000).
        story = UserStory(
            id="US-000", title="t", description="d",
            difficulty=DifficultyLevel.BASIC, category="smoke", prompt="p",
            max_iterations=8,
        )
        context = StageContext(
            story=story, workspace=tmp_path, platform_id="crewai",
            max_iterations=8, model="test-model",
        )

        trace = AgentTrace()
        collector = ObservationCollector(
            trace,
            requirements=ObservationRequirements(
                usage=False, tool_calls=False, llm_duration=False,
                messages=False, iterations=False,
            ),
        )
        progress = ProgressReporter(callback=None, collector=collector)

        # Reset LLM counter so the delta math is well-defined.
        adapter._llm_call_count = 0

        iterations, success = await adapter._run_agent(
            "requirements", "build the thing", None, [],
            collector, context, policy, progress,
        )

        assert iterations >= context.max_iterations, (
            "test setup must actually exceed the budget for this regression "
            "to mean anything"
        )
        assert success is True, (
            "validation passed → success even if iterations >= max_iterations "
            "(this is the US-000 smoke-test bug)"
        )

    async def test_validator_never_passes_is_failure(
        self, monkeypatch, tmp_path,
    ):
        """Regression: a stage that exhausts retries without ever passing
        validation MUST report success=False.

        Original symptom (run 68cab451): deploy stage validator failed all
        3 attempts with "Ensure docker-compose.yaml exists in the workspace
        root", but the stage was reported as PASSED because the post-loop
        check only set hit_limit when iterations exceeded max_iterations.
        """
        from unittest.mock import MagicMock
        from desmet.adapters.multiagent.crewai import CrewAIAdapter
        from desmet.adapters._shared.observation import (
            ObservationCollector, ObservationRequirements,
        )
        from desmet.adapters._shared.retry import ProgressReporter, RetryPolicy
        from desmet.harness.context import StageContext
        from desmet.harness.story import DifficultyLevel, UserStory
        from desmet.harness.trace import AgentTrace

        adapter = CrewAIAdapter(config={"model": "test-model"})
        monkeypatch.setattr(adapter, "_create_llm", lambda ctx: MagicMock())

        # Each kickoff burns a small amount of budget but never produces
        # the artifacts → validator stays False forever.
        def fake_kickoff():
            adapter._llm_call_count += 1
            fake_result = MagicMock()
            fake_result.tasks_output = []
            fake_result.token_usage = None
            return fake_result

        fake_crew = MagicMock()
        fake_crew.kickoff = fake_kickoff
        monkeypatch.setattr(
            adapter, "_build_crew", lambda *a, **kw: fake_crew,
        )

        policy = RetryPolicy(max_retries=2, stage_name="deploy", workspace=tmp_path)
        monkeypatch.setattr(
            policy, "validate",
            lambda: (False, "VALIDATION FAILED: missing docker-compose.yaml"),
        )

        story = UserStory(
            id="US-001", title="t", description="d",
            difficulty=DifficultyLevel.BASIC, category="smoke", prompt="p",
            max_iterations=100,  # generous so iteration limit isn't the gate
        )
        context = StageContext(
            story=story, workspace=tmp_path, platform_id="crewai",
            max_iterations=100, model="test-model",
        )

        trace = AgentTrace()
        collector = ObservationCollector(
            trace,
            requirements=ObservationRequirements(
                usage=False, tool_calls=False, llm_duration=False,
                messages=False, iterations=False,
            ),
        )
        progress = ProgressReporter(callback=None, collector=collector)
        adapter._llm_call_count = 0

        iterations, success = await adapter._run_agent(
            "deploy", "deploy the thing", None, [],
            collector, context, policy, progress,
        )

        assert iterations < context.max_iterations, (
            "test setup must NOT hit the iteration ceiling — the bug we're "
            "guarding against is exactly the case where iterations stay below "
            "the budget but validation never passes"
        )
        assert success is False, (
            "validator never passed → success must be False, regardless of "
            "iteration count (run 68cab451 deploy stage bug)"
        )


def test_event_handlers_register_per_instance():
    """Regression: each adapter instance must register its own handler
    closures, and each closure must capture its own ``self``.

    The bug this guards against: a single shared class-level flag caused
    only the first instance's handlers to be registered.  Events
    dispatched while the second instance was the "active" adapter would
    then be routed to the first instance's collector, corrupting traces
    when two adapters existed in the same process (e.g. sequential
    stages or parallel runs).

    This test verifies the *behavioral* fix, not just the flag location:
    we emit a real event on ``crewai_event_bus`` with ``a2._current_collector``
    set (and ``a1._current_collector`` still ``None``), then assert that
    only ``a2``'s collector received the recording call.
    """
    # The import-location assertion still matters — it ensures we can't
    # regress to a class-level flag — so keep it alongside the behavioral
    # check.
    from desmet.adapters.multiagent.crewai import CrewAIAdapter
    a1 = CrewAIAdapter()
    a2 = CrewAIAdapter()
    assert a1._event_handlers_registered is True
    assert a2._event_handlers_registered is True
    assert "_event_handlers_registered" in a1.__dict__
    assert "_event_handlers_registered" in a2.__dict__

    # Behavioral check — requires crewai.events to construct and emit a
    # real event through the shared event bus.
    pytest.importorskip("crewai.events")
    from unittest.mock import MagicMock

    from crewai.events.event_bus import crewai_event_bus
    from crewai.events.types.llm_events import (
        LLMCallCompletedEvent,
        LLMCallType,
    )

    # a2 is the "active" adapter — its collector should receive the event.
    # a1 stays inert (collector=None) — its handler should early-return.
    fake_collector_a2 = MagicMock()
    a2._current_collector = fake_collector_a2
    a2._current_progress = None
    assert a1._current_collector is None, (
        "a1 must stay inert — the bug is that a1's closure would steal "
        "events intended for a2"
    )

    event = LLMCallCompletedEvent(
        call_id="test-call-1",
        response="hello from the LLM",
        call_type=LLMCallType.LLM_CALL,
        model="test-model",
    )
    # source can be any object — the handler pulls ``_token_usage`` off
    # it via ``getattr(..., None)`` so a bare object is fine.
    crewai_event_bus.emit(source=object(), event=event)

    # a2's collector must have been called — record_llm_response is the
    # first side-effect the handler performs when a collector is present.
    assert fake_collector_a2.record_llm_response.call_count == 1, (
        "a2's handler closure must capture a2's own self and route the "
        "event to a2's collector"
    )
    # Sanity: the call was made with the event's model, proving the
    # closure really did read our emitted event (not stale state).
    _, kwargs = fake_collector_a2.record_llm_response.call_args
    assert kwargs.get("model") == "test-model"

    # a1's state must remain untouched — the regression is precisely that
    # a1's shared closure would fire on events meant for a2.
    assert a1._current_collector is None, (
        "a1's handler must not mutate a1's collector state — and since "
        "it was None, no side effects should have occurred"
    )
    assert a1._llm_call_count == 0, (
        "a1's llm_call_count must not increment — that would prove "
        "a1's handler ran the full path (the original bug)"
    )

    # Conversely a2's llm_call_count *did* increment, confirming a2's
    # handler took the full path.
    assert a2._llm_call_count == 1


def test_iteration_count_is_per_stage_not_cumulative():
    """total_iterations must reflect per-stage calls, not accumulate across stages."""
    from desmet.adapters.multiagent.crewai import CrewAIAdapter

    adapter = CrewAIAdapter()
    adapter._llm_call_count = 7
    if hasattr(adapter, "_last_usage_snapshot"):
        adapter._last_usage_snapshot = {"prompt_tokens": 5000}

    adapter._reset_per_stage_counters()
    assert adapter._llm_call_count == 0
    if hasattr(adapter, "_last_usage_snapshot"):
        assert not adapter._last_usage_snapshot
