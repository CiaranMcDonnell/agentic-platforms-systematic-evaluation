# Agent Graph Visualization — Design Spec

## Overview

A directed graph visualization of agent-to-agent communication during evaluation runs, displayed as a new "Agent Graph" tab in the Scoring page. Nodes represent agents (planner, executor, reviewer, manager); edges represent message flow between them, sized by token volume. Clicking a node reveals tool call detail in a side panel.

## Goals

1. **Interactive exploration** — Zoomable, clickable graph for understanding a single run's orchestration
2. **Thesis figures** — SVG/PNG export for publication-quality diagrams differentiating orchestration patterns
3. **Cross-platform comparison** — Future Dashboard view tiling graphs for the same story across platforms (out of scope for v1)

## Architecture

### Approach: Backend Graph Endpoint

A new Python module builds the graph from trace data and serves it via a dedicated API endpoint. The frontend renders the pre-built graph using ECharts (already installed). This follows the existing pattern where `dashboard/charts.py` builds chart configs and the API serves them.

```
Trace JSON → graph.py (infer or deserialize) → API endpoint → AgentGraph.svelte → ECharts
```

### Data Model

```python
@dataclass
class ToolCallSummary:
    name: str              # tool name
    count: int             # invocation count
    success_rate: float    # 0.0–1.0

@dataclass
class GraphNode:
    id: str                          # e.g. "planner", "executor", "reviewer"
    role: str                        # agent role label
    tokens_in: int                   # total input tokens for this agent
    tokens_out: int                  # total output tokens
    tool_calls: list[ToolCallSummary]
    iterations: int                  # how many times this agent ran

@dataclass
class GraphEdge:
    source: str                      # node id
    target: str                      # node id
    message_count: int               # number of messages along this edge
    token_volume: int                # total tokens transferred
    sequence: list[int]              # ordering indices for animation/replay

@dataclass
class CommunicationGraph:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    topology: str                    # "chain", "hub-spoke", "mesh"
    platform: str
    story_id: str
```

### Graph Inference Logic

New module: `src/desmet/harness/graph.py`

Two paths:

**Explicit path** — If trace JSON contains `communication_graph` key, deserialize directly into `CommunicationGraph`. No inference needed.

**Inference path** — For traces without explicit graph data:

1. **Extract agents** — Scan `node_events` for unique node names. Fall back to `messages[].metadata.node` or `messages[].metadata.agent_role`. Each unique agent becomes a `GraphNode`.
2. **Build edges** — Walk messages in timestamp order. When the active agent changes (message N from agent A, message N+1 from agent B), record edge A→B. Accumulate message counts and token volumes per edge.
3. **Aggregate tool calls** — Group `tool_calls` by the agent that invoked them via timestamp correlation with agent messages. Attach as `ToolCallSummary` on each node.
4. **Classify topology**:
   - All edges form a single path → `"chain"`
   - One node connects to all others, others don't interconnect → `"hub-spoke"`
   - Otherwise → `"mesh"`

### Adapter-Specific Inference

No adapter code changes in v1. The inference module handles quirks per-platform:

| Adapter | Agent ID source | Expected topology |
|---------|----------------|-------------------|
| LangGraph | `node_events` node names, `metadata.node` | chain |
| CrewAI | `metadata.agent_role` in LLM call events | chain (sequential crew) |
| Agent Framework | `node_events` node names, `metadata.node` | hub-spoke (MagenticOne manager) |
| OpenAI Agents SDK | `metadata.node` | hub-spoke or chain |

### Future Explicit Graph Contract

Adapters can opt in to emitting a `communication_graph` key in the trace JSON:

```json
{
  "communication_graph": {
    "nodes": [{"id": "planner", "role": "Planner", "tokens_in": 500, ...}],
    "edges": [{"source": "planner", "target": "executor", "message_count": 3, ...}]
  }
}
```

When present, `graph.py` skips inference and deserializes directly. This is a documented convention, not enforced.

## API

### Endpoint

`GET /api/dashboard/graph/{platform_id}/{story_id}`

**Response** (JSON):
```json
{
  "nodes": [...],
  "edges": [...],
  "topology": "chain",
  "platform": "langgraph",
  "story_id": "basic-todo"
}
```

**Error cases**:
- No trace file found → 404
- Trace exists but no agent metadata extractable → 200 with empty nodes/edges (frontend shows "No agent data available")

## Frontend

### Component: `AgentGraph.svelte`

New Svelte component placed in `src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte`.

**Layout**: Graph + Side Panel
- Left (2/3 width): ECharts graph with force-directed layout
- Right (1/3 width): Detail panel populated on node click

**Graph rendering** (ECharts `graph` series):
- Nodes: Circles sized by total tokens (in + out), colored by role (planner=green, executor=blue, reviewer=red, manager=purple)
- Edges: Directed arrows, width proportional to `message_count`, labeled with message count
- Zoom/pan enabled
- Force-directed layout with gravity pulling toward center

**Side panel** (on node click):
- Agent name and role
- Token counts (in/out)
- Iteration count
- Tool calls list with name, count, success rate
- When no node selected: summary stats (total agents, tokens, topology)

**Topology badge**: Chip above the graph showing auto-classified topology + summary stats (agent count, total tokens, total messages).

**Export**: Download icon in top-right of graph area using ECharts `toolbox.saveAsImage` (PNG and SVG).

### Tab Integration

Added as a third tab in the Scoring page trace section (`Scoring.svelte`), alongside Langfuse and LangSmith. The tab is always visible (not conditional like LangSmith). Tab label: "Agent Graph".

### TypeScript Types

Add to `api.ts`:
```typescript
interface ToolCallSummary {
  name: string;
  count: number;
  success_rate: number;
}

interface GraphNode {
  id: string;
  role: string;
  tokens_in: number;
  tokens_out: number;
  tool_calls: ToolCallSummary[];
  iterations: number;
}

interface GraphEdge {
  source: string;
  target: string;
  message_count: number;
  token_volume: number;
  sequence: number[];
}

interface CommunicationGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  topology: string;
  platform: string;
  story_id: string;
}
```

## Testing

- **Unit tests for `graph.py`**: Test inference from sample trace data for each adapter pattern (chain, hub-spoke). Test topology classification. Test explicit graph deserialization. Test edge cases (single agent, no metadata).
- **API test**: Verify endpoint returns valid `CommunicationGraph` JSON for a known trace file.
- **Frontend**: Manual verification — load Scoring page, switch to Agent Graph tab, verify graph renders with correct nodes/edges for each platform.

## Scope Boundaries

**In scope (v1)**:
- Backend graph module with inference logic
- API endpoint
- AgentGraph.svelte component with ECharts graph + side panel
- Tab integration in Scoring page
- Export button (PNG/SVG)
- Topology badge

**Out of scope (future)**:
- Dashboard comparison view (tiled graphs across platforms)
- Adapter changes to emit explicit graph data
- Animated message replay along edges
- Edge click detail (message content preview)
