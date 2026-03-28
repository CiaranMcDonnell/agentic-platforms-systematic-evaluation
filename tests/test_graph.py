"""Tests for agent communication graph construction."""

from __future__ import annotations

from typing import Any

from desmet.harness.graph import (
    CommunicationGraph,
    GraphEdge,
    GraphNode,
    ToolCallSummary,
    build_graph,
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


def _make_trace_chain() -> dict[str, Any]:
    """Simulates a LangGraph trace: planner → executor → reviewer chain."""
    return {
        "platform_id": "langgraph",
        "story_id": "US-001",
        "stages": {
            "requirements": {
                "messages": [
                    {"role": "user", "content": "Analyse this story", "timestamp": "2026-03-28T01:00:00Z", "metadata": {}},
                    {"role": "assistant", "content": "Plan: step 1, step 2", "timestamp": "2026-03-28T01:00:01Z", "metadata": {"node": "planner"}},
                    {"role": "assistant", "content": "Wrote requirements.md", "timestamp": "2026-03-28T01:00:05Z", "metadata": {"node": "executor/write"}},
                    {"role": "assistant", "content": "Review: PASS", "timestamp": "2026-03-28T01:00:08Z", "metadata": {"node": "reviewer"}},
                ],
                "tool_calls": [
                    {"tool_name": "write_file", "arguments": {}, "success": True, "duration_ms": 10},
                    {"tool_name": "read_file", "arguments": {}, "success": True, "duration_ms": 5},
                ],
                "node_events": [
                    {"node": "planner"},
                    {"node": "executor/write"},
                    {"node": "reviewer", "validator_passed": True},
                ],
                "tokens_input": 2000,
                "tokens_output": 800,
            }
        },
    }


def test_build_graph_chain():
    trace = _make_trace_chain()
    graph = build_graph(trace)
    assert graph.platform == "langgraph"
    assert graph.story_id == "US-001"
    node_ids = {n.id for n in graph.nodes}
    assert node_ids == {"planner", "executor", "reviewer"}
    edge_pairs = {(e.source, e.target) for e in graph.edges}
    assert ("planner", "executor") in edge_pairs
    assert ("executor", "reviewer") in edge_pairs
    assert graph.topology == "chain"


def _make_trace_hub_spoke() -> dict[str, Any]:
    """Simulates an Agent Framework trace: manager orchestrates planner + executor + reviewer."""
    return {
        "platform_id": "microsoft_agent_framework",
        "story_id": "US-001",
        "stages": {
            "requirements": {
                "messages": [
                    {"role": "user", "content": "Analyse this story", "timestamp": "2026-03-28T01:00:00Z", "metadata": {}},
                    {"role": "assistant", "content": "Plan: step 1", "timestamp": "2026-03-28T01:00:01Z", "metadata": {"agent": "planner"}},
                    {"role": "assistant", "content": "Executing plan", "timestamp": "2026-03-28T01:00:03Z", "metadata": {"agent": "executor"}},
                    {"role": "assistant", "content": "Manager: next executor", "timestamp": "2026-03-28T01:00:04Z", "metadata": {"agent": "manager"}},
                    {"role": "assistant", "content": "Review: PASS", "timestamp": "2026-03-28T01:00:06Z", "metadata": {"agent": "reviewer"}},
                    {"role": "assistant", "content": "Manager: complete", "timestamp": "2026-03-28T01:00:07Z", "metadata": {"agent": "manager"}},
                ],
                "tool_calls": [],
                "node_events": [],
                "tokens_input": 3000,
                "tokens_output": 1200,
            }
        },
    }


def test_build_graph_hub_spoke():
    trace = _make_trace_hub_spoke()
    graph = build_graph(trace)
    node_ids = {n.id for n in graph.nodes}
    assert "manager" in node_ids
    assert graph.topology == "hub-spoke"
    manager_edges = [e for e in graph.edges if e.source == "manager" or e.target == "manager"]
    assert len(manager_edges) >= 3


def test_build_graph_explicit():
    """When trace contains communication_graph, use it directly."""
    trace = {
        "platform_id": "langgraph",
        "story_id": "US-002",
        "communication_graph": {
            "nodes": [
                {"id": "planner", "role": "Planner", "tokens_in": 500, "tokens_out": 200, "tool_calls": [], "iterations": 1},
                {"id": "executor", "role": "Executor", "tokens_in": 1000, "tokens_out": 400, "tool_calls": [], "iterations": 2},
            ],
            "edges": [
                {"source": "planner", "target": "executor", "message_count": 2, "token_volume": 600, "sequence": [1, 3]},
            ],
            "topology": "chain",
        },
        "stages": {},
    }
    graph = build_graph(trace)
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    assert graph.topology == "chain"
    assert graph.nodes[0].tokens_in == 500


def test_build_graph_no_metadata():
    """Traces without agent metadata return an empty graph."""
    trace = {
        "platform_id": "langgraph",
        "story_id": "US-003",
        "stages": {
            "requirements": {
                "messages": [
                    {"role": "user", "content": "Hello", "timestamp": "2026-03-28T01:00:00Z"},
                    {"role": "assistant", "content": "Hi", "timestamp": "2026-03-28T01:00:01Z"},
                ],
                "tool_calls": [],
            }
        },
    }
    graph = build_graph(trace)
    assert len(graph.nodes) == 0
    assert len(graph.edges) == 0
    assert graph.topology == "unknown"


def test_graph_to_dict():
    nodes = [
        GraphNode("planner", "Planner", 500, 200, [ToolCallSummary("write_file", 2, 1.0)], 1),
    ]
    edges = [GraphEdge("planner", "executor", 3, 700, [1, 3, 5])]
    graph = CommunicationGraph(nodes, edges, "chain", "langgraph", "US-001")
    d = graph.to_dict()
    assert d["topology"] == "chain"
    assert d["platform"] == "langgraph"
    assert len(d["nodes"]) == 1
    assert d["nodes"][0]["id"] == "planner"
    assert d["nodes"][0]["tool_calls"][0]["name"] == "write_file"
    assert len(d["edges"]) == 1
    assert d["edges"][0]["message_count"] == 3
