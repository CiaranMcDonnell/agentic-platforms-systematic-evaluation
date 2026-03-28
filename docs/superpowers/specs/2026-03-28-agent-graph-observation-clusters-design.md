# Agent Graph Observation Clusters — Design Spec

## Problem

The current Agent Graph shows 3 aggregate agent nodes with transition dots. While useful for topology overview, it doesn't let you follow the detailed execution flow. Langfuse captures ~84 observations per run (every LLM call, tool invocation, routing decision, and framework span), but this data is only viewable as a flat list or nested tree in the Langfuse Trace tab. The Agent Graph should visualize all observations as nodes grouped by agent, making it easy to follow exactly what happened.

## Solution

When a Langfuse trace is available, render all observations as nodes in the Svelte Flow graph, grouped into agent clusters. Each agent (planner, executor, reviewer) becomes a visual container with its observations laid out top-to-bottom inside. Cross-cluster arrows show agent transitions. Clicking any node opens a detail drawer with full input/output.

When no Langfuse trace is available, fall back to the current view (3-node graph with transition dots + timeline list).

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Data source | Langfuse observation tree | Already flows to frontend, rich hierarchical data |
| Fallback | Current timeline view | Graceful degradation when Langfuse unavailable |
| Which observations to show | All | Framework plumbing is relevant for a framework evaluation platform |
| Agent clustering | Infer from tree hierarchy | Root's direct children are the agents, subtrees are their observations |
| Detail view | Side drawer | Keeps graph stable, click-to-reveal |
| Layout engine | ELK compound nodes | Supports parent-child grouping natively |

## Data Source

### With Langfuse (primary path)

Uses the existing `/api/langfuse/traces/{trace_id}` endpoint. Returns `LangfuseTraceDetail`:

```typescript
interface LangfuseTraceDetail {
  trace: { id, name, timestamp, total_tokens, latency_ms, cost, tags, metadata };
  observations: LangfuseObservation[];  // root-level, with recursive children
}

interface LangfuseObservation {
  id: string;
  name: string;
  type: 'span' | 'generation' | 'tool';
  start_time: string | null;
  end_time: string | null;
  latency_ms: number;
  model: string | null;
  tokens: { input: number; output: number; total: number };
  cost: number;
  level: string;
  status_message: string | null;
  input?: string | null;
  output?: string | null;
  metadata?: Record<string, unknown>;
  children: LangfuseObservation[];
}
```

**Agent clustering:** The root observation's direct children are the agent clusters. Each child's `name` is the agent ID (e.g., "planner", "executor", "reviewer"). Each child's subtree contains all observations belonging to that agent.

**No new backend endpoints or types.**

### Without Langfuse (fallback)

Uses the existing `/api/dashboard/graph/{platform}/{story}` endpoint returning `CommunicationGraph` with `timeline`. Renders the current 3-node graph with transition dots and timeline list.

## Graph Layout

### ELK compound layout

- **Agent clusters:** ELK parent nodes, arranged left-to-right following execution order
- **Observation nodes:** ELK child nodes within their agent's cluster, laid out top-to-bottom in execution order (depth-first traversal of the Langfuse subtree preserves temporal ordering)
- **ELK algorithm:** `layered`, direction `RIGHT` for cluster arrangement; `DOWN` for nodes within clusters

### Node rendering

**Observation nodes** (inside clusters) — compact cards:
- Type badge: LLM (blue `#4a9eff`), TOOL (green `#4ade80`), span (gray `#888`)
- Name (e.g., "ChatOpenAI", "execute_shell", "route_executor")
- One key stat: tokens for LLM, tool name for TOOL, duration for spans
- Error state: red border/highlight when `level === 'ERROR'`

**Agent cluster containers:**
- Colored border matching agent color (planner=#4ade80, executor=#4a9eff, reviewer=#ff6b6b, manager=#c084fc)
- Agent name header
- Total tokens for all observations in the cluster

### Edges

- **Within-cluster:** Sequential edges connecting observations in execution order. Thin, subtle (#555, 1px).
- **Cross-cluster:** Transition arrows from last node in source cluster to first node in target cluster. Thicker, colored by source agent. Transition dots accumulate on these edges (reuse existing TransitionEdge component).

### Pan/zoom

With ~84 nodes the graph is larger than viewport. Svelte Flow's built-in pan/zoom handles this. `fitView` on initial load shows the full picture.

## Interaction

### Detail drawer

- Slides in from the right (~400px width) when a node is clicked
- Shows full observation info:
  - Header: type badge, name, model, duration, tokens (in/out), cost
  - Body: input and output as collapsible blocks
  - Tool output in monospace, LLM content as preformatted text
  - Long content (>2000 chars) truncated with "Show full" toggle
- Click another node to switch content
- Close with X button or Escape key

### Hover

Subtle highlight on the node. Tooltip with name and key stat.

### Keyboard navigation

Arrow keys move between nodes following edge connections. Escape closes the drawer.

### Topology badge

Kept at top. Shows: topology type, agent count, total tokens, transition count, total observation count.

## Component Structure

### Modified files

| File | Change |
|------|--------|
| `AgentGraph.svelte` | Add Langfuse data fetching, ELK compound layout with observation nodes, detail drawer integration. Conditional: Langfuse path vs fallback path. |
| `Scoring.svelte` | Pass `langfuseTraceId` prop to AgentGraph |

### New files

| File | Purpose |
|------|---------|
| `ObservationNode.svelte` | Custom Svelte Flow node for individual observations. Compact card: type badge + name + one stat. |
| `ObservationDrawer.svelte` | Detail drawer panel. Full observation info: header stats + collapsible input/output blocks. |

### Kept unchanged

| File | Role |
|------|------|
| `AgentNode.svelte` | Used in fallback mode for 3-node aggregate graph |
| `TransitionEdge.svelte` | Transition dots on cross-cluster edges |
| `TimelineCard.svelte` | Used in fallback mode's timeline list |

## Props change

AgentGraph currently:
```typescript
let { platformId, storyId }: { platformId: string; storyId: string } = $props();
```

Becomes:
```typescript
let { platformId, storyId, langfuseTraceId = null }: {
  platformId: string;
  storyId: string;
  langfuseTraceId?: string | null;
} = $props();
```

## Fallback logic

```
if langfuseTraceId:
  → fetchLangfuseTrace(langfuseTraceId)
  → Build ELK compound layout from observation tree
  → Render clusters with all observation nodes
  → Detail drawer on click
else:
  → fetchAgentGraph(platformId, storyId)
  → Render current 3-node graph with transition dots + timeline list
```

Both paths share: Svelte Flow canvas, topology badge, TransitionEdge, color scheme, keyboard navigation.

## Backend

No changes. All data already available via existing endpoints.

## Dependencies

No new dependencies. Uses existing @xyflow/svelte, elkjs.

## Out of scope

- LangSmith observation support (only Langfuse)
- Editing/annotating observations
- Comparing traces across runs
- Time-based animation/playback
