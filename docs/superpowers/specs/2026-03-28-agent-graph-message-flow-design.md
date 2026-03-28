# Agent Graph Message Flow — Design Spec

## Problem

The current Agent Graph shows an aggregate force-directed graph (3 nodes, 2 edges) that summarises agent topology but doesn't let you follow the actual execution flow. The Langfuse trace (100+ sequential events) is hard to read as a flat list — you can't see which agent owns each step or where messages are communicated to.

## Solution

Replace the ECharts aggregate graph with a Svelte Flow + ELK directed graph paired with a scrollable message timeline. The graph acts as a spatial map showing agent nodes and communication edges; the message list is the sequential timeline you read through. Scrolling the list highlights the active agent and animates edges in the graph.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Replace vs. augment current graph | Replace | Aggregate info already in topology badge |
| Graph library | Svelte Flow + ELK | Purpose-built for interactive directed graphs with custom nodes |
| Message display | Condensed cards, expand on click | Like Langfuse but with better formatting control |
| Interaction model | Scrollable list + graph map | Natural reading flow, graph provides spatial orientation |
| Event naming | Normalized type + raw framework name | Consistent across platforms, preserves debug detail |
| API change | Enrich existing endpoint | No breaking change, just add `timeline` key |
| Content delivery | Full content upfront | Frontend handles display truncation in CSS/Svelte |

## Data Model

### TimelineEvent (new)

```typescript
interface TimelineEvent {
  index: number;                // 0-based sequence position
  type: "llm" | "tool" | "agent" | "routing";  // normalized category
  raw_type: string;             // framework-native name ("executor_node", "tool_node")
  agent_id: string;             // normalized owner ("executor", "planner", "reviewer")
  role: string;                 // message role ("user", "assistant", "tool", "ai")
  content: string;              // full message content
  timestamp: string;
  duration_ms: number | null;
  tokens_in: number | null;
  tokens_out: number | null;
  model: string | null;
  tool_name: string | null;     // for tool events
  tool_success: boolean | null;
  target_agent_id: string | null; // inferred: who this was communicated TO
}
```

### Enriched API response

The `/api/dashboard/graph/{platform}/{story}` endpoint returns the existing `CommunicationGraph` dict plus:

```json
{
  "nodes": [...],
  "edges": [...],
  "topology": "chain",
  "platform": "langgraph",
  "story_id": "US-001",
  "timeline": [TimelineEvent, ...]
}
```

No breaking change — existing consumers ignore `timeline`.

## Backend

### Type normalization rules

| Condition | Normalized type |
|-----------|----------------|
| role is `"ai"` or `"assistant"` | `"llm"` |
| role is `"tool"` or node contains `"tool_node"` | `"tool"` |
| node contains `"route_"` | `"routing"` |
| role is `"user"` (system prompt) | `"agent"` |
| Fallback | `"agent"` |

### target_agent_id inference

Walk the message sequence. When agent transitions from A to B, the last message from A gets `target_agent_id: B`. Messages where the agent doesn't change get `target_agent_id: null`.

### Token/model fields

Per-message token counts and model names are not in the trace files (they come from Langfuse/LangSmith). These fields are `null` for now. Can be backfilled if adapters enrich message metadata later.

### Implementation location

- New function `build_timeline(trace: dict) -> list[dict]` in `src/desmet/harness/graph.py`
- `get_agent_graph()` endpoint calls both `build_graph()` and `build_timeline()`, merges results

## Frontend

### Component structure

`AgentGraph.svelte` is rewritten. Internal structure:

```
AgentGraph.svelte
├── Graph canvas (left, ~60%)
│   └── Svelte Flow with ELK layout
│       └── AgentNode.svelte (custom node component)
├── Message list (right, ~40%)
│   └── Scrollable panel of TimelineCard items
│       └── TimelineCard.svelte (collapsed/expanded message card)
└── Topology badge (top, full width)
```

### Graph canvas — Svelte Flow + ELK

- Agent nodes laid out by ELK (top-to-bottom directed graph)
- Custom `AgentNode.svelte` component: agent name, color dot, total token count
- Node size scales with token usage
- Edges animate in as you scroll the message list
- Active agent node gets a glow highlight
- Edge pulse animation on agent transitions
- Previously-traversed edges at reduced opacity; not-yet-traversed edges hidden
- Clicking a node filters the message list to that agent

### Message list — scrollable panel

Each `TimelineCard` shows:

```
[LLM badge]  executor_node                    2,444↑ 1,327↓  0.03s
  minimax/minimax-m2.5-20260211
```

- Left color bar — agent color for visual scanning
- Type badge — LLM (blue) / TOOL (green) / AGENT (gray) / ROUTING (purple)
- Raw framework name in small text
- Right-aligned stats: tokens, duration, tool success/fail
- Click to expand: full content with markdown rendering (AI) or monospace block (tool output)
- Long content (>2000 chars) shows first 500 with "Show full" toggle

### Scroll sync

- Topmost visible message determines the active agent in the graph
- Agent transitions trigger edge pulse animations
- IntersectionObserver on each TimelineCard for efficient scroll tracking

### Filtering

- Click agent node in graph → list filters to that agent's messages
- "Showing: Executor (23 messages)" indicator with X to clear
- Client-side filtering only

### Keyboard navigation

- Arrow up/down moves through messages when list is focused
- Escape clears agent filter

### Color scheme (carried over)

```
planner:  #4ade80 (green)
executor: #4a9eff (blue)
reviewer: #ff6b6b (red)
manager:  #c084fc (purple)
fallback: #888888 (gray)
```

## Dependencies

### New (frontend)

- `@xyflow/svelte` — graph canvas with custom nodes, pan/zoom, edge rendering
- `elkjs` — automatic directed graph layout computation

### Kept (frontend)

- `echarts` — still used by `EChart.svelte` (dashboard charts); only removed from AgentGraph

### Backend

No new dependencies.

## Files changed

| File | Change |
|------|--------|
| `src/desmet/harness/graph.py` | Add `build_timeline()` function |
| `src/desmet/webui/api.py` | Enrich graph endpoint response with timeline |
| `src/desmet/webui/frontend/src/lib/api.ts` | Add `TimelineEvent` type, update `CommunicationGraph` |
| `src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte` | Full rewrite: Svelte Flow + message list |
| `src/desmet/webui/frontend/src/lib/components/AgentNode.svelte` | New: custom graph node component |
| `src/desmet/webui/frontend/src/lib/components/TimelineCard.svelte` | New: message card component |
| `src/desmet/webui/frontend/package.json` | Add @xyflow/svelte, elkjs; remove echarts |

## Out of scope

- Per-message token counts from Langfuse/LangSmith integration (future backfill)
- Playback/animation controls (play/pause auto-scroll)
- Cross-story comparison view
- Graph algorithm metrics on the trace data (Cytoscape)
