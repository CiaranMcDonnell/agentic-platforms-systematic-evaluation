"""Agent communication graph — data model and inference from execution traces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "ToolCallSummary",
    "GraphNode",
    "GraphEdge",
    "CommunicationGraph",
    "build_graph",
]


@dataclass
class ToolCallSummary:
    """Aggregated tool usage for one agent."""

    name: str
    count: int
    success_rate: float  # 0.0–1.0


@dataclass
class GraphNode:
    """A single agent in the communication graph."""

    id: str
    role: str
    tokens_in: int = 0
    tokens_out: int = 0
    tool_calls: list[ToolCallSummary] = field(default_factory=list)
    iterations: int = 0


@dataclass
class GraphEdge:
    """A directed communication edge between two agents."""

    source: str
    target: str
    message_count: int = 0
    token_volume: int = 0
    sequence: list[int] = field(default_factory=list)


@dataclass
class CommunicationGraph:
    """Complete agent communication graph for one evaluation run."""

    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    topology: str = "unknown"
    platform: str = ""
    story_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "nodes": [
                {
                    "id": n.id,
                    "role": n.role,
                    "tokens_in": n.tokens_in,
                    "tokens_out": n.tokens_out,
                    "tool_calls": [
                        {"name": tc.name, "count": tc.count, "success_rate": tc.success_rate}
                        for tc in n.tool_calls
                    ],
                    "iterations": n.iterations,
                }
                for n in self.nodes
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "message_count": e.message_count,
                    "token_volume": e.token_volume,
                    "sequence": e.sequence,
                }
                for e in self.edges
            ],
            "topology": self.topology,
            "platform": self.platform,
            "story_id": self.story_id,
        }


def _normalize_agent_id(metadata: dict[str, Any]) -> str | None:
    """Extract a canonical agent ID from message metadata.

    Adapters use different keys:
    - LangGraph: metadata.node ("planner", "executor/write", "reviewer")
    - Agent Framework: metadata.agent ("planner", "executor", "manager")
    - CrewAI: metadata.agent_role ("Requirements Analyst", "Code Writer")
    - OpenAI Agents SDK: metadata.node or metadata.agent
    """
    for key in ("agent", "node", "agent_role"):
        val = metadata.get(key)
        if val:
            # Normalize "executor/write" → "executor"
            base = str(val).split("/")[0].strip().lower()
            return base
    return None


def _classify_topology(nodes: list[GraphNode], edges: list[GraphEdge]) -> str:
    """Auto-classify the graph topology."""
    if len(nodes) <= 1:
        return "unknown"

    node_ids = {n.id for n in nodes}

    # Check for chain first: each node has at most 1 outgoing and 1 incoming edge.
    # A chain is a linear sequence — no node fans out or merges.
    out_degree: dict[str, int] = {}
    in_degree: dict[str, int] = {}
    for e in edges:
        out_degree[e.source] = out_degree.get(e.source, 0) + 1
        in_degree[e.target] = in_degree.get(e.target, 0) + 1
    if all(out_degree.get(n, 0) <= 1 for n in node_ids) and all(
        in_degree.get(n, 0) <= 1 for n in node_ids
    ):
        return "chain"

    # Check for hub-spoke: one node (the hub) connects to most other nodes,
    # AND the hub's edge count dominates over spoke-to-spoke edges.
    # We allow the hub to miss at most one spoke (e.g. when a spoke only
    # communicates with another spoke before the hub is introduced).
    for nid in node_ids:
        others = node_ids - {nid}
        if len(others) < 2:
            continue
        # Gather nodes the candidate hub has a direct edge to/from
        hub_connected = set()
        hub_edge_count = 0
        for e in edges:
            if e.source == nid:
                hub_connected.add(e.target)
                hub_edge_count += 1
            if e.target == nid:
                hub_connected.add(e.source)
                hub_edge_count += 1
        # Hub must connect to at least len(others)-1 spokes (allow 1 gap)
        min_required = max(2, len(others) - 1)
        if len(hub_connected) < min_required:
            continue
        # Hub edge count must exceed spoke-to-spoke edge count
        spoke_edge_count = sum(
            1 for e in edges if e.source in others and e.target in others
        )
        if hub_edge_count >= spoke_edge_count:
            return "hub-spoke"

    return "mesh"


def build_graph(trace: dict[str, Any]) -> CommunicationGraph:
    """Build a CommunicationGraph from a raw trace dict.

    Uses the explicit ``communication_graph`` key if present,
    otherwise infers from message metadata and node_events.
    """
    platform = trace.get("platform_id", "")
    story_id = trace.get("story_id", "")

    # ── Explicit path ──────────────────────────────────────────────────
    explicit = trace.get("communication_graph")
    if explicit:
        nodes = [
            GraphNode(
                id=n["id"],
                role=n.get("role", n["id"]),
                tokens_in=n.get("tokens_in", 0),
                tokens_out=n.get("tokens_out", 0),
                tool_calls=[
                    ToolCallSummary(**tc) for tc in n.get("tool_calls", [])
                ],
                iterations=n.get("iterations", 0),
            )
            for n in explicit.get("nodes", [])
        ]
        edges = [
            GraphEdge(
                source=e["source"],
                target=e["target"],
                message_count=e.get("message_count", 0),
                token_volume=e.get("token_volume", 0),
                sequence=e.get("sequence", []),
            )
            for e in explicit.get("edges", [])
        ]
        return CommunicationGraph(
            nodes=nodes,
            edges=edges,
            topology=explicit.get("topology", _classify_topology(nodes, edges)),
            platform=platform,
            story_id=story_id,
        )

    # ── Inference path ─────────────────────────────────────────────────
    all_messages: list[dict[str, Any]] = []
    all_tool_calls: list[dict[str, Any]] = []
    all_node_events: list[dict[str, Any]] = []
    stage_tokens: dict[str, tuple[int, int]] = {}

    for stage_key, stage in (trace.get("stages") or {}).items():
        msgs = stage.get("messages", [])
        all_messages.extend(msgs)
        all_tool_calls.extend(stage.get("tool_calls", []))
        all_node_events.extend(stage.get("node_events", []))
        stage_tokens[stage_key] = (
            stage.get("tokens_input", 0),
            stage.get("tokens_output", 0),
        )

    # Extract unique agents from messages
    agent_ids: dict[str, str] = {}  # id → role (display name)
    msg_agents: list[str | None] = []  # agent id per message (or None)

    for msg in all_messages:
        metadata = msg.get("metadata") or {}
        aid = _normalize_agent_id(metadata)
        msg_agents.append(aid)
        if aid and aid not in agent_ids:
            # Use the raw value (before normalization) as the display role
            raw = metadata.get("agent") or metadata.get("node") or metadata.get("agent_role") or aid
            role = str(raw).split("/")[0].strip()
            agent_ids[aid] = role.title()

    if not agent_ids:
        return CommunicationGraph(platform=platform, story_id=story_id)

    # Build nodes
    node_map: dict[str, GraphNode] = {
        aid: GraphNode(id=aid, role=role) for aid, role in agent_ids.items()
    }

    # Count iterations per agent from node_events
    for evt in all_node_events:
        nid = str(evt.get("node", "")).split("/")[0].strip().lower()
        if nid in node_map:
            node_map[nid].iterations += 1

    # Distribute stage tokens proportionally across agents in that stage
    # Simple heuristic: split evenly among agents that appear in messages
    total_in = sum(t[0] for t in stage_tokens.values())
    total_out = sum(t[1] for t in stage_tokens.values())
    agents_with_msgs = [a for a in msg_agents if a is not None]
    if agents_with_msgs:
        per_agent_counts: dict[str, int] = {}
        for a in agents_with_msgs:
            per_agent_counts[a] = per_agent_counts.get(a, 0) + 1
        total_count = sum(per_agent_counts.values())
        for aid, count in per_agent_counts.items():
            fraction = count / total_count
            node_map[aid].tokens_in = int(total_in * fraction)
            node_map[aid].tokens_out = int(total_out * fraction)

    # Aggregate tool calls — assign to the most recent agent before the tool call
    # Since tool_calls don't have per-agent attribution, use message order
    current_agent: str | None = None
    tool_agent_map: dict[str, list[dict[str, Any]]] = {aid: [] for aid in agent_ids}
    msg_idx = 0
    for msg, aid in zip(all_messages, msg_agents):
        if aid:
            current_agent = aid
        if msg.get("role") == "tool" and current_agent:
            # Find matching tool call by proximity
            if msg_idx < len(all_tool_calls):
                tool_agent_map[current_agent].append(all_tool_calls[msg_idx])
                msg_idx += 1

    # If no tool messages found, distribute tool calls by agent message frequency
    if msg_idx == 0 and all_tool_calls and current_agent:
        # Assign all tool calls to the most frequent non-user agent
        most_frequent = max(
            (a for a in agents_with_msgs),
            key=lambda a: agents_with_msgs.count(a),
        )
        tool_agent_map[most_frequent] = all_tool_calls

    for aid, tcs in tool_agent_map.items():
        if not tcs:
            continue
        tool_counts: dict[str, list[bool]] = {}
        for tc in tcs:
            name = tc.get("tool_name", "unknown")
            tool_counts.setdefault(name, []).append(tc.get("success", True))
        node_map[aid].tool_calls = [
            ToolCallSummary(
                name=name,
                count=len(results),
                success_rate=sum(results) / len(results) if results else 1.0,
            )
            for name, results in tool_counts.items()
        ]

    # Build edges from agent transition sequence
    edge_map: dict[tuple[str, str], GraphEdge] = {}
    prev_agent: str | None = None
    msg_sequence = 0
    for aid in msg_agents:
        if aid is None:
            continue
        msg_sequence += 1
        if prev_agent and prev_agent != aid:
            key = (prev_agent, aid)
            if key not in edge_map:
                edge_map[key] = GraphEdge(source=prev_agent, target=aid)
            edge_map[key].message_count += 1
            edge_map[key].sequence.append(msg_sequence)
        prev_agent = aid

    nodes = list(node_map.values())
    edges = list(edge_map.values())

    return CommunicationGraph(
        nodes=nodes,
        edges=edges,
        topology=_classify_topology(nodes, edges),
        platform=platform,
        story_id=story_id,
    )
