"""Tests for agent communication graph construction."""

from __future__ import annotations

from desmet.harness.graph import (
    CommunicationGraph,
    GraphEdge,
    GraphNode,
    ToolCallSummary,
)


def test_graph_node_total_tokens():
    node = GraphNode(
        id="executor",
        role="Executor",
        tokens_in=1000,
        tokens_out=500,
        tool_calls=[ToolCallSummary(name="write_file", count=3, success_rate=1.0)],
        iterations=2,
    )
    assert node.tokens_in + node.tokens_out == 1500


def test_communication_graph_construction():
    nodes = [
        GraphNode("planner", "Planner", 500, 200, [], 1),
        GraphNode("executor", "Executor", 1000, 500, [], 2),
    ]
    edges = [GraphEdge("planner", "executor", message_count=3, token_volume=700, sequence=[1, 3, 5])]
    graph = CommunicationGraph(
        nodes=nodes,
        edges=edges,
        topology="chain",
        platform="langgraph",
        story_id="US-001",
    )
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    assert graph.topology == "chain"
