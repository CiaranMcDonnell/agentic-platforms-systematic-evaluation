"""Tests for the LangGraph idiomatic adapter (subgraph architecture)."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

pytest.importorskip("langchain_core", reason="langchain_core not installed")


class TestLangGraphAdapterStructure:
    def test_imports(self):
        from desmet.adapters.multiagent.langgraph import LangGraphAdapter
        adapter = LangGraphAdapter()
        assert adapter.TOOL_FORMAT is not None

    def test_observability_reports_checkpointing(self):
        from desmet.adapters.multiagent.langgraph import LangGraphAdapter
        adapter = LangGraphAdapter()
        info = adapter.get_observability_info()
        assert info["has_checkpointing"] is True
        assert info["has_state_inspection"] is True

    def test_failure_handling_reports_auto_recovery(self):
        from desmet.adapters.multiagent.langgraph import LangGraphAdapter
        adapter = LangGraphAdapter()
        info = adapter.get_failure_handling_info()
        assert info["has_auto_recovery"] is True
        assert info["has_checkpointing"] is True


class TestBuildGraph:
    def test_graph_has_three_subgraph_nodes(self):
        from desmet.adapters.multiagent.langgraph import LangGraphAdapter
        adapter = LangGraphAdapter()
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        adapter._llm = mock_llm
        adapter._model_name = "test-model"
        graph = adapter._build_graph(mock_llm, [])
        node_names = set(graph.nodes.keys())
        assert "planner" in node_names
        assert "executor" in node_names
        assert "reviewer" in node_names


class TestPlanParsing:
    def test_serial_plan_returns_no_parallel_groups(self):
        from desmet.adapters.multiagent.langgraph import parse_plan
        steps = parse_plan("1. Create models\n2. Create views\n3. Create templates")
        assert all(not s.get("parallel") for s in steps)
        assert len(steps) == 3

    def test_parallel_markers_detected(self):
        from desmet.adapters.multiagent.langgraph import parse_plan
        plan = "1. [PARALLEL] Create models.py\n2. [PARALLEL] Create views.py\n3. Run tests"
        steps = parse_plan(plan)
        assert steps[0]["parallel"] is True
        assert steps[1]["parallel"] is True
        assert steps[2]["parallel"] is False

    def test_empty_plan_returns_empty_list(self):
        from desmet.adapters.multiagent.langgraph import parse_plan
        assert parse_plan("") == []

    def test_dash_format_plan(self):
        from desmet.adapters.multiagent.langgraph import parse_plan
        steps = parse_plan("- First step\n- Second step")
        assert len(steps) == 2
        assert steps[0]["text"] == "First step"


class TestStreamHeartbeat:
    """The _aiter_with_heartbeat helper races each chunk against an
    asyncio sleep so a slow LLM call inside an executor node still
    emits 'waiting on LLM' progress every few seconds.

    Regression target: a deploy-stage benchmark sat at
    '[executor] step 12 (45s, 41,506 tokens)' for 2m43s before the user
    cancelled, because LangGraph's astream(stream_mode='updates')
    doesn't emit anything until a node completes.
    """

    async def test_heartbeat_fires_during_slow_chunk(self):
        import asyncio
        from desmet.adapters.multiagent.langgraph import _aiter_with_heartbeat

        class FakeProgress:
            def __init__(self):
                self.calls: list[tuple[str, int]] = []
            def waiting(self, label: str, seconds: int) -> None:
                self.calls.append((label, seconds))

        async def slow_stream():
            await asyncio.sleep(0.6)
            yield "chunk-1"
            yield "chunk-2"

        progress = FakeProgress()
        chunks = []
        async for chunk in _aiter_with_heartbeat(
            slow_stream(), "executor", progress, interval=0.2,
        ):
            chunks.append(chunk)

        assert chunks == ["chunk-1", "chunk-2"]
        # We expect at least 2 heartbeats during the 0.6s sleep at 0.2s intervals
        assert len(progress.calls) >= 2, (
            f"expected ≥2 heartbeats during slow chunk, got {progress.calls}"
        )
        assert all(label == "executor" for label, _ in progress.calls)

    async def test_heartbeat_silent_when_stream_is_fast(self):
        """Fast streams should NOT emit heartbeats — that would spam
        progress on healthy runs."""
        import asyncio
        from desmet.adapters.multiagent.langgraph import _aiter_with_heartbeat

        class FakeProgress:
            def __init__(self):
                self.calls = []
            def waiting(self, label, seconds):
                self.calls.append((label, seconds))

        async def fast_stream():
            yield "a"
            yield "b"
            yield "c"

        progress = FakeProgress()
        chunks = [
            c async for c in _aiter_with_heartbeat(
                fast_stream(), "executor", progress, interval=1.0,
            )
        ]
        assert chunks == ["a", "b", "c"]
        assert progress.calls == []

    async def test_heartbeat_works_with_none_progress(self):
        """Helper must not crash when progress=None (early init paths)."""
        import asyncio
        from desmet.adapters.multiagent.langgraph import _aiter_with_heartbeat

        async def stream():
            await asyncio.sleep(0.3)
            yield "x"

        chunks = [
            c async for c in _aiter_with_heartbeat(
                stream(), "executor", None, interval=0.1,
            )
        ]
        assert chunks == ["x"]


def test_planner_fallback_records_plan_source():
    """Structured-planner exception handling must record trace.metadata['plan_source']."""
    import inspect

    from desmet.adapters.multiagent.langgraph import LangGraphAdapter

    src = inspect.getsource(LangGraphAdapter._build_planner_subgraph)
    assert 'plan_source' in src
    assert 'trace.metadata' in src or 'metadata["plan_source"]' in src or "metadata['plan_source']" in src
    # Must not silently swallow — either logs, records error, or narrows except.
    assert 'errors.append' in src or '_log.warning' in src


def test_run_reviewer_does_not_double_record_duration():
    """Reviewer must not UNCONDITIONALLY call record_llm_response(raw_usage=None,
    duration_ms=X) after already recording per-message usage — that double-counts
    duration. The only permitted catch-up is the guarded fallback for the
    empty-messages edge case (see test_run_reviewer_records_duration_on_empty_messages)."""
    import inspect
    from desmet.adapters.multiagent import langgraph as lg

    # reviewer_wrapper is a nested function inside _build_graph; inspect the
    # outer method's source to catch the anti-pattern wherever it appears.
    src = inspect.getsource(lg.LangGraphAdapter._build_graph)
    # Any record_llm_response(raw_usage=None, ...) call must be guarded by
    # `if first` (the empty-messages fallback). If it appears outside such a
    # guard, we're back to the double-counting anti-pattern.
    for idx, line in enumerate(src.splitlines()):
        if "record_llm_response(raw_usage=None" in line:
            # Look back up to 3 lines for the `if first` guard.
            window = "\n".join(src.splitlines()[max(0, idx - 3):idx])
            assert "if first" in window, (
                "Reviewer calls record_llm_response(raw_usage=None, ...) without "
                "an `if first` guard — double-counts duration."
            )


def test_structured_planner_preserves_token_usage():
    """with_structured_output must be called with include_raw=True so usage_metadata
    from the raw response is preserved and recorded by _extract_and_record_usage."""
    import inspect
    from desmet.adapters.multiagent import langgraph as lg

    src = inspect.getsource(lg.LangGraphAdapter._build_planner_subgraph)
    assert "include_raw=True" in src, (
        "with_structured_output must be called with include_raw=True — otherwise "
        "the structured-planner path discards usage_metadata, under-counting "
        "planner tokens vs the free-text fallback."
    )
    assert "usage_metadata" in src, (
        "Synthesized AIMessage must carry usage_metadata copied from raw response."
    )


def test_run_reviewer_records_duration_on_empty_messages():
    """Empty messages list must still record reviewer duration (fallback path)."""
    import inspect
    from desmet.adapters.multiagent import langgraph as lg

    src = inspect.getsource(lg.LangGraphAdapter._build_graph)
    # The fallback recording must exist for the empty-messages case.
    assert "if first" in src and "record_llm_response(raw_usage=None" in src, (
        "Missing fallback that records reviewer_duration when message loop "
        "does not execute — _llm_duration_total_ms would silently undercount."
    )


def _usage_msg(content="x", tool_calls=None):
    from langchain_core.messages import AIMessage

    return AIMessage(
        content=content,
        tool_calls=tool_calls or [],
        response_metadata={"token_usage": {"prompt_tokens": 10, "completion_tokens": 5}},
    )


def _collector():
    from desmet.adapters._shared.observation import (
        ObservationCollector,
        ObservationRequirements,
    )
    from desmet.harness.trace import AgentTrace

    return ObservationCollector(
        AgentTrace(),
        requirements=ObservationRequirements(
            usage=False, tool_calls=False, llm_duration=False,
            messages=False, iterations=False,
        ),
    )


async def test_budget_exhausted_reviewer_still_records_its_calls():
    """GraphRecursionError inside the reviewer must not discard the calls it
    already made: their tokens and LLM-call count stay on the trace."""
    from types import SimpleNamespace

    from langgraph.errors import GraphRecursionError

    from desmet.adapters._shared.budget import budget_exhausted, llm_calls_used
    from desmet.adapters.multiagent.langgraph import LangGraphAdapter

    class FakePlanner:
        async def ainvoke(self, state, config=None):
            return {"messages": [_usage_msg("1. do it")]}

    class FakeExecutor:
        async def astream(self, state, config=None, stream_mode=None):
            yield {"executor_node": {"messages": [_usage_msg("done")]}}

    class FakeReviewer:
        """Two reviewer calls, then the recursion limit (the budget) hits."""

        async def _updates(self):
            tc = [{"name": "read_file", "args": {"path": "a"}, "id": "t1"}]
            yield {"review": {"messages": [_usage_msg("", tc)]}}
            yield {"review": {"messages": [_usage_msg("looks wrong")]}}
            raise GraphRecursionError("limit")

        def astream(self, state, config=None, stream_mode=None):
            return self._updates()

        async def ainvoke(self, state, config=None):
            async for _ in self._updates():
                pass

    adapter = LangGraphAdapter()
    adapter._build_planner_subgraph = lambda llm, collector=None: FakePlanner()
    adapter._build_executor_subgraph = lambda llm, tools: FakeExecutor()
    adapter._build_reviewer_subgraph = lambda llm, tools: FakeReviewer()
    collector = _collector()
    policy = SimpleNamespace(
        max_retries=3, total_attempts=lambda: 4, validate=lambda: (False, "missing"),
    )
    graph = adapter._build_graph(
        object(), [], collector=collector, policy=policy, budget=50,
    )
    await graph.ainvoke(
        {
            "prompt": "p", "system_msg": None, "plan": "", "plan_obj": None,
            "stage": "codegen", "workspace": "/w", "retry_count": 0,
            "validator_passed": False, "last_validator_feedback": "", "iterations": 0,
        },
        config={"configurable": {"thread_id": "t"}},
    )

    trace = collector.trace
    assert budget_exhausted(trace)
    # planner 1 + executor 1 + reviewer 2
    assert llm_calls_used(trace) == 4
    assert (trace.total_tokens_input, trace.total_tokens_output) == (40, 20)
    assert [tc.tool_name for tc in trace.tool_calls] == ["read_file"]


async def test_structured_planner_parse_failure_records_its_call():
    """A structured attempt that returned a response but no parsed plan was
    a paid LLM call; the free-text retry must not hide it."""
    from langchain_core.messages import HumanMessage

    from desmet.adapters._shared.budget import llm_calls_used
    from desmet.adapters.multiagent.langgraph import LangGraphAdapter

    class FakeStructured:
        async def ainvoke(self, messages):
            return {"raw": _usage_msg("not json"), "parsed": None, "parsing_error": "bad"}

    class FakeLLM:
        def with_structured_output(self, schema, include_raw=False):
            return FakeStructured()

        async def ainvoke(self, messages):
            return _usage_msg("1. free text plan")

    collector = _collector()
    planner = LangGraphAdapter()._build_planner_subgraph(FakeLLM(), collector=collector)
    result = await planner.ainvoke({"messages": [HumanMessage(content="p")]})

    assert result["messages"][-1].content == "1. free text plan"
    # The structured call is recorded in the node; the wrapper records
    # the returned free-text message as before.
    assert llm_calls_used(collector.trace) == 1
    assert collector.trace.total_tokens_input == 10
