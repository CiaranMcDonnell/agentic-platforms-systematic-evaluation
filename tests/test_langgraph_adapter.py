"""Tests for LangGraph StateGraph adapter."""
import inspect
import pytest
from desmet.adapters.langgraph import LangGraphAdapter


@pytest.fixture
def adapter():
    return LangGraphAdapter(config={"model": "gpt-5.2-2025-12-11"})


class TestLangGraphAdapterInterface:
    def test_has_generate_requirements(self, adapter):
        assert callable(adapter.generate_requirements)

    def test_has_generate_code(self, adapter):
        assert callable(adapter.generate_code)

    def test_has_generate_tests(self, adapter):
        assert callable(adapter.generate_tests)

    def test_has_build_and_deploy(self, adapter):
        assert callable(adapter.build_and_deploy)

    def test_generate_requirements_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.generate_requirements)

    def test_generate_code_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.generate_code)

    def test_generate_tests_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.generate_tests)

    def test_build_and_deploy_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.build_and_deploy)


class TestStateGraphStructure:
    def test_build_graph_returns_compiled_state_graph(self, adapter):
        """_build_graph() must return a compiled LangGraph StateGraph."""
        from langgraph.graph.state import CompiledStateGraph
        from unittest.mock import MagicMock
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        graph = adapter._build_graph(mock_llm, tools=[])
        assert isinstance(graph, CompiledStateGraph)

    def test_build_graph_has_planner_node(self, adapter):
        from unittest.mock import MagicMock
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        graph = adapter._build_graph(mock_llm, tools=[])
        assert "planner_node" in graph.get_graph().nodes

    def test_build_graph_has_executor_node(self, adapter):
        from unittest.mock import MagicMock
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        graph = adapter._build_graph(mock_llm, tools=[])
        assert "executor_node" in graph.get_graph().nodes

    def test_build_graph_has_validator_node(self, adapter):
        from unittest.mock import MagicMock
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        graph = adapter._build_graph(mock_llm, tools=[])
        assert "validator_node" in graph.get_graph().nodes

    def test_no_legacy_create_agent_import(self):
        """Adapter must not import the legacy langchain.agents.create_agent."""
        import ast, pathlib
        src = pathlib.Path("src/desmet/adapters/langgraph.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mod = getattr(node, "module", "") or ""
                assert "create_agent" not in mod, "Legacy create_agent import found"


