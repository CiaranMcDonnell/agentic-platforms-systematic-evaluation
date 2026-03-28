# Agent Graph Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a directed graph visualization of agent communication to the Scoring page, with a backend inference engine, ECharts rendering, and side-panel detail view.

**Architecture:** A new Python module (`harness/graph.py`) builds a `CommunicationGraph` from trace data — either explicitly provided by adapters or inferred from message metadata. A new API endpoint serves the graph JSON. A new Svelte component renders it as an ECharts force-directed graph with a detail side panel. Prerequisites: trace serialization must include message `metadata` and `node_events` (currently dropped).

**Tech Stack:** Python dataclasses, FastAPI, Svelte 5, ECharts graph series

---

## File Structure

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `src/desmet/harness/graph.py` | Graph data model + inference logic |
| Create | `tests/test_graph.py` | Unit tests for graph module |
| Modify | `src/desmet/harness/runner.py:649-673` | Serialize `metadata` and `node_events` to trace JSON |
| Modify | `src/desmet/webui/api.py:852` | Add graph endpoint after scoring endpoint |
| Modify | `src/desmet/webui/frontend/src/lib/api.ts:316` | Add graph types + fetch function |
| Create | `src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte` | ECharts graph + side panel component |
| Modify | `src/desmet/webui/frontend/src/lib/pages/Scoring.svelte:244-276` | Add "Agent Graph" tab |

---

### Task 1: Enhance Trace Serialization

**Files:**
- Modify: `src/desmet/harness/runner.py:649-673`
- Test: `tests/test_graph.py` (verified manually against existing trace files)

The trace JSON currently drops `metadata` from messages and `node_events` from the trace. Without these, graph inference has no agent identity signals. This task adds them to the serialized output.

- [ ] **Step 1: Add `metadata` to message serialization**

In `src/desmet/harness/runner.py`, find the message serialization block (lines 649-661). Add `metadata` to each message dict:

```python
            # Include message trace when available
            if sr.trace and sr.trace.messages:
                stage_entry["messages"] = [
                    {
                        "role": msg.role,
                        "content": (
                            msg.content[:500] + "..."
                            if len(msg.content) > 500
                            else msg.content
                        ),
                        "timestamp": msg.timestamp.isoformat(),
                        "metadata": msg.metadata if msg.metadata else {},
                    }
                    for msg in sr.trace.messages
                ]
```

- [ ] **Step 2: Add `node_events` to stage serialization**

In the same function, after the tool_calls block (after line 673), add node_events serialization:

```python
            if sr.trace and sr.trace.node_events:
                stage_entry["node_events"] = sr.trace.node_events
```

- [ ] **Step 3: Verify the change doesn't break existing trace loading**

Run: `uv run pytest tests/test_runner.py -v -x`
Expected: All existing tests pass (serialization is additive — new fields don't break readers).

- [ ] **Step 4: Commit**

```bash
git add src/desmet/harness/runner.py
git commit -m "feat(trace): serialize message metadata and node_events to trace JSON"
```

---

### Task 2: Graph Data Model

**Files:**
- Create: `src/desmet/harness/graph.py`
- Test: `tests/test_graph.py`

- [ ] **Step 1: Write failing test for data model**

Create `tests/test_graph.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_graph.py -v -x`
Expected: FAIL with `ModuleNotFoundError: No module named 'desmet.harness.graph'`

- [ ] **Step 3: Implement data model**

Create `src/desmet/harness/graph.py`:

```python
"""Agent communication graph — data model and inference from execution traces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_graph.py -v -x`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/desmet/harness/graph.py tests/test_graph.py
git commit -m "feat(graph): add communication graph data model"
```

---

### Task 3: Graph Inference Logic

**Files:**
- Modify: `src/desmet/harness/graph.py`
- Test: `tests/test_graph.py`

- [ ] **Step 1: Write failing test for chain inference (LangGraph pattern)**

Append to `tests/test_graph.py`:

```python
from desmet.harness.graph import build_graph


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
    # Should have 3 nodes: planner, executor, reviewer
    node_ids = {n.id for n in graph.nodes}
    assert node_ids == {"planner", "executor", "reviewer"}
    # Should have edges: planner→executor, executor→reviewer
    edge_pairs = {(e.source, e.target) for e in graph.edges}
    assert ("planner", "executor") in edge_pairs
    assert ("executor", "reviewer") in edge_pairs
    assert graph.topology == "chain"
```

Add the import at the top of the file:

```python
from typing import Any
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_graph.py::test_build_graph_chain -v -x`
Expected: FAIL with `ImportError: cannot import name 'build_graph'`

- [ ] **Step 3: Write failing test for hub-spoke inference (Agent Framework pattern)**

Append to `tests/test_graph.py`:

```python
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
    # Manager should have edges to/from most other agents
    manager_edges = [e for e in graph.edges if e.source == "manager" or e.target == "manager"]
    assert len(manager_edges) >= 3
```

- [ ] **Step 4: Write failing test for explicit graph passthrough**

Append to `tests/test_graph.py`:

```python
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
```

- [ ] **Step 5: Write failing test for empty/missing metadata fallback**

Append to `tests/test_graph.py`:

```python
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
```

- [ ] **Step 6: Implement `build_graph` function**

Add to `src/desmet/harness/graph.py`:

```python
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

    # Check for hub-spoke: one node connects to all others
    for nid in node_ids:
        others = node_ids - {nid}
        connected = set()
        for e in edges:
            if e.source == nid:
                connected.add(e.target)
            if e.target == nid:
                connected.add(e.source)
        if connected >= others and len(others) >= 2:
            return "hub-spoke"

    # Check for chain: each node has at most 1 outgoing and 1 incoming
    out_degree: dict[str, int] = {}
    in_degree: dict[str, int] = {}
    for e in edges:
        out_degree[e.source] = out_degree.get(e.source, 0) + 1
        in_degree[e.target] = in_degree.get(e.target, 0) + 1
    if all(out_degree.get(n, 0) <= 1 for n in node_ids) and all(
        in_degree.get(n, 0) <= 1 for n in node_ids
    ):
        return "chain"

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
```

- [ ] **Step 7: Run all graph tests**

Run: `uv run pytest tests/test_graph.py -v`
Expected: All 5 tests pass.

- [ ] **Step 8: Commit**

```bash
git add src/desmet/harness/graph.py tests/test_graph.py
git commit -m "feat(graph): add inference engine for agent communication graphs"
```

---

### Task 4: Graph Serialization Helper

**Files:**
- Modify: `src/desmet/harness/graph.py`
- Test: `tests/test_graph.py`

The API endpoint needs to return JSON. Add a `to_dict` method to `CommunicationGraph`.

- [ ] **Step 1: Write failing test**

Append to `tests/test_graph.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_graph.py::test_graph_to_dict -v -x`
Expected: FAIL with `AttributeError: 'CommunicationGraph' object has no attribute 'to_dict'`

- [ ] **Step 3: Implement `to_dict`**

Add to the `CommunicationGraph` class in `src/desmet/harness/graph.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_graph.py -v`
Expected: All 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/desmet/harness/graph.py tests/test_graph.py
git commit -m "feat(graph): add to_dict serialization for API responses"
```

---

### Task 5: API Endpoint

**Files:**
- Modify: `src/desmet/webui/api.py:852`

- [ ] **Step 1: Add import**

At the top of `src/desmet/webui/api.py`, add the graph import alongside existing dashboard imports (around line 36-43):

```python
from desmet.harness.graph import build_graph
```

- [ ] **Step 2: Add the endpoint**

Insert after the `get_story_score` endpoint (after line 852 in `api.py`), before the `submit_score` endpoint:

```python
@app.get("/api/dashboard/graph/{platform_id}/{story_id}")
async def get_agent_graph(platform_id: str, story_id: str):
    """Build and return the agent communication graph for a run."""
    trace_files = list_trace_files(platform_id, story_id)
    if not trace_files:
        raise HTTPException(status_code=404, detail="No trace files found")
    raw_trace = load_trace(trace_files[-1])
    graph = build_graph(raw_trace)
    return graph.to_dict()
```

- [ ] **Step 3: Verify the endpoint works**

Start the dev server and test manually:

Run: `uv run python -c "from desmet.harness.graph import build_graph; from desmet.dashboard.data import list_trace_files, load_trace; files = list_trace_files('langgraph', 'US-001'); print('files:', len(files)); t = load_trace(files[-1]) if files else {}; g = build_graph(t); print('nodes:', len(g.nodes), 'edges:', len(g.edges), 'topology:', g.topology)"`

Expected: Prints node/edge counts (may be 0 for older traces without metadata — this is expected until new runs are executed).

- [ ] **Step 4: Commit**

```bash
git add src/desmet/webui/api.py
git commit -m "feat(api): add /api/dashboard/graph endpoint"
```

---

### Task 6: Frontend Types and Fetch Function

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/api.ts:316`

- [ ] **Step 1: Add TypeScript interfaces**

Add after the existing `StoryScoreData` interface (around line 124) in `src/desmet/webui/frontend/src/lib/api.ts`:

```typescript
export interface ToolCallSummary {
  name: string;
  count: number;
  success_rate: number;
}

export interface GraphNode {
  id: string;
  role: string;
  tokens_in: number;
  tokens_out: number;
  tool_calls: ToolCallSummary[];
  iterations: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  message_count: number;
  token_volume: number;
  sequence: number[];
}

export interface CommunicationGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  topology: string;
  platform: string;
  story_id: string;
}
```

- [ ] **Step 2: Add fetch function**

Add after the existing `fetchStoryScore` function (around line 316):

```typescript
export const fetchAgentGraph = (pid: string, sid: string) =>
  request<CommunicationGraph>(`/api/dashboard/graph/${pid}/${sid}`);
```

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/api.ts
git commit -m "feat(frontend): add agent graph types and fetch function"
```

---

### Task 7: AgentGraph Svelte Component

**Files:**
- Create: `src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte`

- [ ] **Step 1: Create the component**

Create `src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte`:

```svelte
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import * as echarts from 'echarts';
  import { fetchAgentGraph } from '../api';
  import type { CommunicationGraph, GraphNode } from '../api';

  let { platformId, storyId }: { platformId: string; storyId: string } = $props();

  let container: HTMLDivElement | undefined = $state();
  let chart: echarts.ECharts | null = null;
  let graphData: CommunicationGraph | null = $state(null);
  let selectedNode: GraphNode | null = $state(null);
  let loading = $state(true);
  let error: string | null = $state(null);

  const ROLE_COLORS: Record<string, string> = {
    planner: '#4ade80',
    executor: '#4a9eff',
    reviewer: '#ff6b6b',
    manager: '#c084fc',
  };

  function roleColor(id: string): string {
    return ROLE_COLORS[id] ?? '#888888';
  }

  function buildChartOption(data: CommunicationGraph): echarts.EChartsOption {
    const maxTokens = Math.max(...data.nodes.map(n => n.tokens_in + n.tokens_out), 1);

    const nodes = data.nodes.map(n => ({
      id: n.id,
      name: n.role,
      symbolSize: 30 + 40 * ((n.tokens_in + n.tokens_out) / maxTokens),
      itemStyle: { color: roleColor(n.id), borderColor: roleColor(n.id), borderWidth: 2 },
      label: { show: true, color: '#e0e0e0', fontSize: 12, fontWeight: 'bold' as const },
    }));

    const maxMsgCount = Math.max(...data.edges.map(e => e.message_count), 1);

    const links = data.edges.map(e => ({
      source: e.source,
      target: e.target,
      lineStyle: { width: 1 + 4 * (e.message_count / maxMsgCount), curveness: 0.2 },
      label: { show: true, formatter: `${e.message_count}`, fontSize: 10, color: '#888' },
    }));

    return {
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          if (params.dataType === 'node') {
            const n = data.nodes.find(n => n.id === params.data.id);
            if (!n) return '';
            return `<b>${n.role}</b><br/>Tokens: ${(n.tokens_in + n.tokens_out).toLocaleString()}<br/>Iterations: ${n.iterations}`;
          }
          if (params.dataType === 'edge') {
            return `${params.data.source} → ${params.data.target}<br/>Messages: ${params.data.lineStyle ? '' : ''}${data.edges.find(e => e.source === params.data.source && e.target === params.data.target)?.message_count ?? 0}`;
          }
          return '';
        },
      },
      toolbox: {
        show: true,
        right: 10,
        top: 10,
        feature: {
          saveAsImage: { title: 'Export', pixelRatio: 2 },
        },
        iconStyle: { borderColor: '#888' },
      },
      series: [
        {
          type: 'graph',
          layout: 'force',
          roam: true,
          draggable: true,
          force: { repulsion: 300, gravity: 0.1, edgeLength: [100, 200] },
          edgeSymbol: ['none', 'arrow'],
          edgeSymbolSize: 8,
          data: nodes,
          links,
        },
      ],
    };
  }

  async function loadGraph() {
    loading = true;
    error = null;
    selectedNode = null;
    try {
      graphData = await fetchAgentGraph(platformId, storyId);
      if (graphData.nodes.length === 0) {
        error = 'No agent data available for this run.';
        return;
      }
      if (chart && container) {
        chart.setOption(buildChartOption(graphData), true);
        chart.on('click', (params: any) => {
          if (params.dataType === 'node' && graphData) {
            selectedNode = graphData.nodes.find(n => n.id === params.data.id) ?? null;
          }
        });
      }
    } catch (e: any) {
      error = e.status === 404 ? 'No trace data found.' : `Failed to load graph: ${e.message}`;
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (container) {
      chart = echarts.init(container, 'dark', { renderer: 'canvas' });
      const ro = new ResizeObserver(() => chart?.resize());
      ro.observe(container);
    }
    loadGraph();
  });

  onDestroy(() => {
    chart?.dispose();
  });

  // Reload when platform/story changes
  $effect(() => {
    if (platformId && storyId && chart) {
      loadGraph();
    }
  });
</script>

<div class="agent-graph-container">
  {#if graphData && !error}
    <div class="topology-badge">
      <span class="topology-label">{graphData.topology}</span>
      <span class="topology-stats">
        {graphData.nodes.length} agents &middot;
        {graphData.nodes.reduce((s, n) => s + n.tokens_in + n.tokens_out, 0).toLocaleString()} tokens &middot;
        {graphData.edges.reduce((s, e) => s + e.message_count, 0)} messages
      </span>
    </div>
  {/if}

  <div class="graph-layout">
    <div class="graph-panel">
      {#if loading}
        <div class="graph-status">Loading graph...</div>
      {:else if error}
        <div class="graph-status">{error}</div>
      {/if}
      <div bind:this={container} class="chart-container"></div>
    </div>

    <div class="detail-panel">
      {#if selectedNode}
        <div class="detail-section">
          <div class="detail-label">Agent</div>
          <div class="detail-value" style="color: {roleColor(selectedNode.id)}">
            {selectedNode.role}
          </div>
        </div>
        <div class="detail-section">
          <div class="detail-label">Tokens</div>
          <div class="detail-row">
            <span>In:</span> <span class="detail-num">{selectedNode.tokens_in.toLocaleString()}</span>
          </div>
          <div class="detail-row">
            <span>Out:</span> <span class="detail-num">{selectedNode.tokens_out.toLocaleString()}</span>
          </div>
        </div>
        <div class="detail-section">
          <div class="detail-label">Iterations</div>
          <div class="detail-num">{selectedNode.iterations}</div>
        </div>
        {#if selectedNode.tool_calls.length > 0}
          <div class="detail-section">
            <div class="detail-label">Tool Calls</div>
            {#each selectedNode.tool_calls as tc}
              <div class="tool-row">
                <span class="tool-name">{tc.name}</span>
                <span class="tool-count">
                  &times;{tc.count}
                  {#if tc.success_rate < 1}
                    <span class="tool-fail">({Math.round((1 - tc.success_rate) * tc.count)} fail)</span>
                  {/if}
                </span>
              </div>
            {/each}
          </div>
        {/if}
      {:else}
        <div class="detail-placeholder">
          {#if graphData && graphData.nodes.length > 0}
            <p>Click a node to see details</p>
            <div class="detail-section">
              <div class="detail-label">Summary</div>
              <div class="detail-row"><span>Agents:</span> <span class="detail-num">{graphData.nodes.length}</span></div>
              <div class="detail-row"><span>Topology:</span> <span class="detail-num">{graphData.topology}</span></div>
              <div class="detail-row">
                <span>Total tokens:</span>
                <span class="detail-num">{graphData.nodes.reduce((s, n) => s + n.tokens_in + n.tokens_out, 0).toLocaleString()}</span>
              </div>
            </div>
          {:else}
            <p>No graph data</p>
          {/if}
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .agent-graph-container {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .topology-badge {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 6px 12px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 6px;
    font-size: 12px;
  }

  .topology-label {
    background: rgba(74, 158, 255, 0.2);
    color: #4a9eff;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 11px;
  }

  .topology-stats {
    color: #888;
  }

  .graph-layout {
    display: flex;
    gap: 12px;
  }

  .graph-panel {
    flex: 2;
    position: relative;
    background: rgba(255, 255, 255, 0.03);
    border-radius: 8px;
    min-height: 400px;
  }

  .chart-container {
    width: 100%;
    height: 400px;
  }

  .graph-status {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #888;
    font-size: 13px;
    z-index: 1;
  }

  .detail-panel {
    flex: 1;
    background: rgba(255, 255, 255, 0.03);
    border-radius: 8px;
    padding: 16px;
    min-height: 400px;
    overflow-y: auto;
  }

  .detail-section {
    margin-bottom: 16px;
  }

  .detail-label {
    font-size: 11px;
    color: #888;
    text-transform: uppercase;
    margin-bottom: 6px;
    letter-spacing: 0.5px;
  }

  .detail-value {
    font-size: 16px;
    font-weight: 600;
  }

  .detail-row {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    padding: 2px 0;
    color: #ccc;
  }

  .detail-num {
    color: #4a9eff;
    font-weight: 500;
  }

  .detail-placeholder {
    color: #666;
    font-size: 13px;
    padding-top: 20px;
  }

  .detail-placeholder p {
    text-align: center;
    margin-bottom: 20px;
  }

  .tool-row {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    font-size: 13px;
    color: #ccc;
  }

  .tool-name {
    font-family: monospace;
    font-size: 12px;
  }

  .tool-count {
    color: #4ade80;
  }

  .tool-fail {
    color: #ff6b6b;
    font-size: 11px;
  }
</style>
```

- [ ] **Step 2: Verify the component compiles**

Run: `cd src/desmet/webui/frontend && bun run build`
Expected: Build succeeds with no errors.

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte
git commit -m "feat(frontend): add AgentGraph component with ECharts graph and side panel"
```

---

### Task 8: Tab Integration in Scoring Page

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/pages/Scoring.svelte`

- [ ] **Step 1: Add import**

Add to the imports at the top of `Scoring.svelte` (after the LangSmithTraceViewer import, around line 11):

```typescript
import AgentGraph from '../components/AgentGraph.svelte';
```

- [ ] **Step 2: Update activeTab type and default**

Find the `activeTab` state declaration (around line 24). Change:

```typescript
let activeTab = $state<'langfuse' | 'langsmith'>('langfuse');
```

To:

```typescript
let activeTab = $state<'langfuse' | 'langsmith' | 'graph'>('langfuse');
```

- [ ] **Step 3: Add the Agent Graph tab button**

In the trace tabs area (around lines 254-265), replace the conditional tab bar with one that always shows (since Agent Graph is always available). Find:

```svelte
      {#if showLangSmithTab}
        <div class="trace-tabs">
          <button class="trace-tab" class:active={activeTab === 'langfuse'}
            onclick={() => activeTab = 'langfuse'}>Langfuse Trace</button>
          <button class="trace-tab" class:active={activeTab === 'langsmith'}
            onclick={() => activeTab = 'langsmith'}>LangSmith Graph</button>
        </div>
      {/if}
```

Replace with:

```svelte
        <div class="trace-tabs">
          <button class="trace-tab" class:active={activeTab === 'langfuse'}
            onclick={() => activeTab = 'langfuse'}>Langfuse Trace</button>
          {#if showLangSmithTab}
            <button class="trace-tab" class:active={activeTab === 'langsmith'}
              onclick={() => activeTab = 'langsmith'}>LangSmith Graph</button>
          {/if}
          <button class="trace-tab" class:active={activeTab === 'graph'}
            onclick={() => activeTab = 'graph'}>Agent Graph</button>
        </div>
```

- [ ] **Step 4: Add the Agent Graph content block**

Find the trace content area (around lines 268-276). Add the Agent Graph block. Find:

```svelte
    {#if showLangSmithTab && activeTab === 'langsmith'}
      <LangSmithTraceViewer runId={scoreData.langsmith_run_id!} />
    {:else if scoreData.langfuse_trace_id}
```

Replace with:

```svelte
    {#if activeTab === 'graph'}
      <AgentGraph platformId={selectedPlatform} storyId={selectedStory} />
    {:else if showLangSmithTab && activeTab === 'langsmith'}
      <LangSmithTraceViewer runId={scoreData.langsmith_run_id!} />
    {:else if scoreData.langfuse_trace_id}
```

Note: `selectedPlatform` and `selectedStory` are the reactive variables already used in `Scoring.svelte` that hold the current platform_id and story_id. Verify the exact variable names by checking the file — they may be named differently (e.g., `$scoringTarget.platform` and `$scoringTarget.story`). Use the same values passed to `fetchStoryScore`.

- [ ] **Step 5: Build and verify**

Run: `cd src/desmet/webui/frontend && bun run build`
Expected: Build succeeds.

- [ ] **Step 6: Manual verification**

Start the dev server: `uv run desmet-eval webui`

Open the Scoring page, select a platform and story, and verify:
1. The "Agent Graph" tab appears alongside Langfuse (and LangSmith if applicable)
2. Clicking it shows the graph or "No agent data available" for older traces
3. The topology badge displays above the graph
4. Clicking a node populates the side panel

- [ ] **Step 7: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/pages/Scoring.svelte
git commit -m "feat(scoring): integrate Agent Graph tab into Scoring page"
```
