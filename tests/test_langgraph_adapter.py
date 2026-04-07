"""Tests for the LangGraph idiomatic adapter (subgraph architecture)."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest

pytest.importorskip("langchain_core", reason="langchain_core not installed")


class TestLangGraphAdapterStructure:
    def test_imports(self):
        from desmet.adapters.langgraph import LangGraphAdapter
        adapter = LangGraphAdapter()
        assert adapter.TOOL_FORMAT is not None

    def test_observability_reports_checkpointing(self):
        from desmet.adapters.langgraph import LangGraphAdapter
        adapter = LangGraphAdapter()
        info = adapter.get_observability_info()
        assert info["has_checkpointing"] is True
        assert info["has_state_inspection"] is True

    def test_failure_handling_reports_auto_recovery(self):
        from desmet.adapters.langgraph import LangGraphAdapter
        adapter = LangGraphAdapter()
        info = adapter.get_failure_handling_info()
        assert info["has_auto_recovery"] is True
        assert info["has_checkpointing"] is True


class TestBuildGraph:
    def test_graph_has_three_subgraph_nodes(self):
        from desmet.adapters.langgraph import LangGraphAdapter
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
        from desmet.adapters.langgraph import parse_plan
        steps = parse_plan("1. Create models\n2. Create views\n3. Create templates")
        assert all(not s.get("parallel") for s in steps)
        assert len(steps) == 3

    def test_parallel_markers_detected(self):
        from desmet.adapters.langgraph import parse_plan
        plan = "1. [PARALLEL] Create models.py\n2. [PARALLEL] Create views.py\n3. Run tests"
        steps = parse_plan(plan)
        assert steps[0]["parallel"] is True
        assert steps[1]["parallel"] is True
        assert steps[2]["parallel"] is False

    def test_empty_plan_returns_empty_list(self):
        from desmet.adapters.langgraph import parse_plan
        assert parse_plan("") == []

    def test_dash_format_plan(self):
        from desmet.adapters.langgraph import parse_plan
        steps = parse_plan("- First step\n- Second step")
        assert len(steps) == 2
        assert steps[0]["text"] == "First step"
