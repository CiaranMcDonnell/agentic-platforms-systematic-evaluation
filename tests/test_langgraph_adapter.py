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
