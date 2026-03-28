# Agent Graph Message Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the aggregate ECharts agent graph with a Svelte Flow + ELK interactive message flow explorer that lets you step through agent execution traces with spatial orientation.

**Architecture:** Backend adds `build_timeline()` to extract ordered `TimelineEvent` items from trace JSON, served alongside the existing `CommunicationGraph` from the same endpoint. Frontend replaces the ECharts component with Svelte Flow (graph canvas with ELK layout) + a scrollable message list panel. Scroll sync highlights the active agent node and animates edges.

**Tech Stack:** Python (backend), Svelte 5 + @xyflow/svelte + elkjs (frontend)

**Spec:** `docs/superpowers/specs/2026-03-28-agent-graph-message-flow-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/desmet/harness/graph.py` | Modify | Add `TimelineEvent` dataclass and `build_timeline()` function |
| `src/desmet/webui/api.py` | Modify | Enrich graph endpoint response with `timeline` key |
| `tests/test_graph.py` | Modify | Add tests for `build_timeline()` |
| `src/desmet/webui/frontend/package.json` | Modify | Add `@xyflow/svelte`, `elkjs` |
| `src/desmet/webui/frontend/src/lib/api.ts` | Modify | Add `TimelineEvent` type, update `CommunicationGraph` |
| `src/desmet/webui/frontend/src/lib/components/AgentNode.svelte` | Create | Custom Svelte Flow node component |
| `src/desmet/webui/frontend/src/lib/components/TimelineCard.svelte` | Create | Collapsible message card component |
| `src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte` | Rewrite | Svelte Flow graph + message list layout |

---

### Task 1: Backend — `build_timeline()` with tests

**Files:**
- Modify: `src/desmet/harness/graph.py`
- Modify: `tests/test_graph.py`

- [ ] **Step 1: Write failing tests for `build_timeline()`**

Add to `tests/test_graph.py`:

```python
from desmet.harness.graph import build_timeline, TimelineEvent


def test_build_timeline_basic():
    """Timeline extracts ordered events from trace messages."""
    trace = _make_trace_chain()  # existing helper
    timeline = build_timeline(trace)
    assert len(timeline) == 4  # user, planner, executor, reviewer
    assert all(isinstance(e, TimelineEvent) for e in timeline)

    # First event is the system prompt (user role, no agent)
    assert timeline[0].type == "agent"
    assert timeline[0].role == "user"
    assert timeline[0].agent_id == ""

    # Second event is the planner
    assert timeline[1].type == "llm"
    assert timeline[1].agent_id == "planner"
    assert timeline[1].raw_type == "planner"

    # Third is executor
    assert timeline[2].type == "llm"
    assert timeline[2].agent_id == "executor"
    assert timeline[2].raw_type == "executor/write"

    # Fourth is reviewer
    assert timeline[3].type == "llm"
    assert timeline[3].agent_id == "reviewer"
    assert timeline[3].raw_type == "reviewer"


def test_build_timeline_indices():
    """Timeline events have sequential 0-based indices."""
    trace = _make_trace_chain()
    timeline = build_timeline(trace)
    for i, event in enumerate(timeline):
        assert event.index == i


def test_build_timeline_target_agent():
    """target_agent_id is set on the last message before an agent transition."""
    trace = _make_trace_chain()
    timeline = build_timeline(trace)
    # planner (idx 1) → executor: target is executor
    assert timeline[1].target_agent_id == "executor"
    # executor (idx 2) → reviewer: target is reviewer
    assert timeline[2].target_agent_id == "reviewer"
    # reviewer (idx 3) is last: target is None
    assert timeline[3].target_agent_id is None


def test_build_timeline_tool_events():
    """Tool messages get type='tool' and tool_name from matching tool_calls."""
    trace = {
        "platform_id": "langgraph",
        "story_id": "US-001",
        "stages": {
            "requirements": {
                "messages": [
                    {"role": "assistant", "content": "Let me write the file",
                     "timestamp": "2026-03-28T01:00:01Z",
                     "metadata": {"node": "executor/executor_node"}},
                    {"role": "tool", "content": "(no output)",
                     "timestamp": "2026-03-28T01:00:02Z",
                     "metadata": {"node": "executor/tool_node"}},
                    {"role": "tool", "content": "total 0\ndrwx...",
                     "timestamp": "2026-03-28T01:00:03Z",
                     "metadata": {"node": "executor/tool_node"}},
                ],
                "tool_calls": [
                    {"tool_name": "write_file", "arguments": {}, "success": True, "duration_ms": 10},
                    {"tool_name": "execute_shell", "arguments": {}, "success": False, "duration_ms": 5},
                ],
                "node_events": [],
                "tokens_input": 1000,
                "tokens_output": 400,
            }
        },
    }
    timeline = build_timeline(trace)
    tool_events = [e for e in timeline if e.type == "tool"]
    assert len(tool_events) == 2
    assert tool_events[0].tool_name == "write_file"
    assert tool_events[0].tool_success is True
    assert tool_events[1].tool_name == "execute_shell"
    assert tool_events[1].tool_success is False


def test_build_timeline_routing_events():
    """Messages with 'route_' in node name get type='routing'."""
    trace = {
        "platform_id": "langgraph",
        "story_id": "US-001",
        "stages": {
            "requirements": {
                "messages": [
                    {"role": "assistant", "content": "Plan done",
                     "timestamp": "2026-03-28T01:00:01Z",
                     "metadata": {"node": "executor/executor_node"}},
                    {"role": "assistant", "content": "",
                     "timestamp": "2026-03-28T01:00:02Z",
                     "metadata": {"node": "route_executor"}},
                ],
                "tool_calls": [],
                "node_events": [],
                "tokens_input": 500,
                "tokens_output": 200,
            }
        },
    }
    timeline = build_timeline(trace)
    routing = [e for e in timeline if e.type == "routing"]
    assert len(routing) == 1
    assert routing[0].raw_type == "route_executor"


def test_build_timeline_empty_trace():
    """Empty trace returns empty timeline."""
    trace = {"platform_id": "langgraph", "story_id": "US-001", "stages": {}}
    timeline = build_timeline(trace)
    assert timeline == []


def test_build_timeline_serialization():
    """TimelineEvent.to_dict() produces JSON-compatible dict."""
    trace = _make_trace_chain()
    timeline = build_timeline(trace)
    d = timeline[1].to_dict()
    assert d["index"] == 1
    assert d["type"] == "llm"
    assert d["agent_id"] == "planner"
    assert isinstance(d["content"], str)
    assert "timestamp" in d
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_graph.py -v -k "timeline"`
Expected: FAIL — `ImportError: cannot import name 'build_timeline'`

- [ ] **Step 3: Implement `TimelineEvent` dataclass and `build_timeline()`**

Add to `src/desmet/harness/graph.py` after the existing imports:

```python
@dataclass
class TimelineEvent:
    """A single event in the agent execution timeline."""

    index: int
    type: str  # "llm", "tool", "agent", "routing"
    raw_type: str  # framework-native name
    agent_id: str  # normalized owner
    role: str  # message role
    content: str
    timestamp: str
    duration_ms: float | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    model: str | None = None
    tool_name: str | None = None
    tool_success: bool | None = None
    target_agent_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "type": self.type,
            "raw_type": self.raw_type,
            "agent_id": self.agent_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "model": self.model,
            "tool_name": self.tool_name,
            "tool_success": self.tool_success,
            "target_agent_id": self.target_agent_id,
        }
```

Update `__all__` to include `"TimelineEvent"` and `"build_timeline"`.

Then add the `build_timeline` function:

```python
def _classify_event_type(role: str, raw_node: str) -> str:
    """Classify a message into a normalized event type."""
    if "route_" in raw_node or "route" == raw_node:
        return "routing"
    if role in ("tool",) or "tool_node" in raw_node:
        return "tool"
    if role in ("ai", "assistant"):
        return "llm"
    return "agent"


def build_timeline(trace: dict[str, Any]) -> list[TimelineEvent]:
    """Build an ordered timeline of events from a raw trace dict."""
    all_messages: list[dict[str, Any]] = []
    all_tool_calls: list[dict[str, Any]] = []

    for stage in (trace.get("stages") or {}).values():
        all_messages.extend(stage.get("messages", []))
        all_tool_calls.extend(stage.get("tool_calls", []))

    if not all_messages:
        return []

    # Build events list
    events: list[TimelineEvent] = []
    tool_call_idx = 0

    for i, msg in enumerate(all_messages):
        metadata = msg.get("metadata") or {}
        raw_node = metadata.get("node") or metadata.get("agent") or metadata.get("agent_role") or ""
        raw_node_str = str(raw_node)
        agent_id = _normalize_agent_id(metadata) or ""
        role = msg.get("role", "")
        event_type = _classify_event_type(role, raw_node_str)

        # Match tool calls to tool messages
        tool_name: str | None = None
        tool_success: bool | None = None
        duration_ms: float | None = None
        if event_type == "tool" and tool_call_idx < len(all_tool_calls):
            tc = all_tool_calls[tool_call_idx]
            tool_name = tc.get("tool_name")
            tool_success = tc.get("success")
            duration_ms = tc.get("duration_ms")
            tool_call_idx += 1

        events.append(TimelineEvent(
            index=i,
            type=event_type,
            raw_type=raw_node_str,
            agent_id=agent_id,
            role=role,
            content=msg.get("content", ""),
            timestamp=msg.get("timestamp", ""),
            duration_ms=duration_ms,
            tokens_in=metadata.get("tokens_in"),
            tokens_out=metadata.get("tokens_out"),
            model=metadata.get("model"),
            tool_name=tool_name,
            tool_success=tool_success,
        ))

    # Infer target_agent_id from agent transitions
    for i in range(len(events)):
        if not events[i].agent_id:
            continue
        # Look ahead for next event with a different agent
        for j in range(i + 1, len(events)):
            next_agent = events[j].agent_id
            if not next_agent:
                continue
            if next_agent != events[i].agent_id:
                events[i].target_agent_id = next_agent
            break  # stop at first event with any agent_id

    return events
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_graph.py -v -k "timeline"`
Expected: All 7 timeline tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/desmet/harness/graph.py tests/test_graph.py
git commit -m "feat: add build_timeline() for agent message flow extraction"
```

---

### Task 2: Backend — Enrich API endpoint

**Files:**
- Modify: `src/desmet/webui/api.py:856-864`

- [ ] **Step 1: Update the graph endpoint to include timeline**

In `src/desmet/webui/api.py`, change the `get_agent_graph` function:

```python
from desmet.harness.graph import build_graph, build_timeline

@app.get("/api/dashboard/graph/{platform_id}/{story_id}")
async def get_agent_graph(platform_id: str, story_id: str):
    """Build and return the agent communication graph and timeline for a run."""
    trace_files = list_trace_files(platform_id, story_id)
    if not trace_files:
        raise HTTPException(status_code=404, detail="No trace files found")
    raw_trace = load_trace(trace_files[-1])
    graph = build_graph(raw_trace)
    timeline = build_timeline(raw_trace)
    result = graph.to_dict()
    result["timeline"] = [e.to_dict() for e in timeline]
    return result
```

- [ ] **Step 2: Verify the import is correct**

Check that `build_timeline` is in the `__all__` export of `graph.py` (done in Task 1).

- [ ] **Step 3: Smoke test with the dev server**

Run: `cd src/desmet/webui && uv run uvicorn api:app --reload`
Then: `curl http://localhost:8000/api/dashboard/graph/langgraph/US-001 | python -m json.tool | head -20`
Expected: JSON response with `nodes`, `edges`, `topology`, `platform`, `story_id`, and `timeline` keys.

- [ ] **Step 4: Commit**

```bash
git add src/desmet/webui/api.py
git commit -m "feat: serve timeline data from agent graph endpoint"
```

---

### Task 3: Frontend — Install dependencies

**Files:**
- Modify: `src/desmet/webui/frontend/package.json`

- [ ] **Step 1: Install @xyflow/svelte and elkjs**

```bash
cd src/desmet/webui/frontend && bun add @xyflow/svelte elkjs
```

- [ ] **Step 2: Verify installation**

```bash
cd src/desmet/webui/frontend && bun run build
```
Expected: Build succeeds with no errors.

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/frontend/package.json src/desmet/webui/frontend/bun.lock
git commit -m "deps: add @xyflow/svelte and elkjs for agent graph"
```

---

### Task 4: Frontend — TypeScript types

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/api.ts`

- [ ] **Step 1: Add `TimelineEvent` interface and update `CommunicationGraph`**

After the existing `GraphEdge` interface (~line 147), add:

```typescript
export interface TimelineEvent {
  index: number;
  type: 'llm' | 'tool' | 'agent' | 'routing';
  raw_type: string;
  agent_id: string;
  role: string;
  content: string;
  timestamp: string;
  duration_ms: number | null;
  tokens_in: number | null;
  tokens_out: number | null;
  model: string | null;
  tool_name: string | null;
  tool_success: boolean | null;
  target_agent_id: string | null;
}
```

Update the existing `CommunicationGraph` interface to include `timeline`:

```typescript
export interface CommunicationGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  topology: string;
  platform: string;
  story_id: string;
  timeline: TimelineEvent[];
}
```

- [ ] **Step 2: Verify build**

```bash
cd src/desmet/webui/frontend && bun run build
```
Expected: Build succeeds (AgentGraph.svelte will have type errors since it still uses ECharts — that's fine, we'll rewrite it next).

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/api.ts
git commit -m "feat: add TimelineEvent type and update CommunicationGraph"
```

---

### Task 5: Frontend — AgentNode component

**Files:**
- Create: `src/desmet/webui/frontend/src/lib/components/AgentNode.svelte`

- [ ] **Step 1: Create the custom Svelte Flow node component**

```svelte
<script lang="ts">
  import { Handle, Position } from '@xyflow/svelte';

  let { data }: { data: { label: string; color: string; tokens: number; active: boolean } } = $props();
</script>

<div class="agent-node" class:active={data.active} style="--agent-color: {data.color}">
  <Handle type="target" position={Position.Top} />
  <div class="agent-dot"></div>
  <div class="agent-label">{data.label}</div>
  <div class="agent-tokens">{data.tokens.toLocaleString()} tok</div>
  <Handle type="source" position={Position.Bottom} />
</div>

<style>
  .agent-node {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    padding: 12px 16px;
    background: rgba(255, 255, 255, 0.06);
    border: 2px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    cursor: pointer;
    transition: border-color 0.2s, box-shadow 0.2s;
  }

  .agent-node.active {
    border-color: var(--agent-color);
    box-shadow: 0 0 16px color-mix(in srgb, var(--agent-color) 40%, transparent);
  }

  .agent-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--agent-color);
  }

  .agent-label {
    font-size: 13px;
    font-weight: 600;
    color: #e0e0e0;
    text-transform: capitalize;
  }

  .agent-tokens {
    font-size: 11px;
    color: #888;
  }

  :global(.svelte-flow__handle) {
    width: 6px;
    height: 6px;
    background: #555;
    border: none;
  }
</style>
```

- [ ] **Step 2: Verify build**

```bash
cd src/desmet/webui/frontend && bun run build
```
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/components/AgentNode.svelte
git commit -m "feat: add AgentNode custom component for Svelte Flow"
```

---

### Task 6: Frontend — TimelineCard component

**Files:**
- Create: `src/desmet/webui/frontend/src/lib/components/TimelineCard.svelte`

- [ ] **Step 1: Create the message card component**

```svelte
<script lang="ts">
  import type { TimelineEvent } from '../api';

  let { event, agentColor = '#888', selected = false, onclick }: {
    event: TimelineEvent;
    agentColor?: string;
    selected?: boolean;
    onclick?: () => void;
  } = $props();

  let expanded = $state(false);
  let showFull = $state(false);

  const TYPE_COLORS: Record<string, string> = {
    llm: '#4a9eff',
    tool: '#4ade80',
    agent: '#888',
    routing: '#c084fc',
  };

  const CONTENT_TRUNCATE = 500;
  const CONTENT_EXPAND_THRESHOLD = 2000;

  function formatDuration(ms: number | null): string {
    if (ms === null) return '';
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  }

  function formatTokens(n: number | null): string {
    if (n === null) return '';
    return n.toLocaleString();
  }

  let displayContent = $derived(
    !showFull && event.content.length > CONTENT_EXPAND_THRESHOLD
      ? event.content.slice(0, CONTENT_TRUNCATE) + '...'
      : event.content
  );
</script>

<div
  class="timeline-card"
  class:selected
  class:expanded
  style="--agent-color: {agentColor}; --type-color: {TYPE_COLORS[event.type] ?? '#888'}"
  role="button"
  tabindex="0"
  onclick={() => { expanded = !expanded; onclick?.(); }}
  onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { expanded = !expanded; onclick?.(); } }}
>
  <div class="card-color-bar"></div>
  <div class="card-body">
    <div class="card-header">
      <span class="type-badge">{event.type.toUpperCase()}</span>
      <span class="raw-type">{event.raw_type}</span>
      <span class="card-stats">
        {#if event.tokens_in !== null}
          <span class="stat-tokens">{formatTokens(event.tokens_in)}&uarr;</span>
        {/if}
        {#if event.tokens_out !== null}
          <span class="stat-tokens">{formatTokens(event.tokens_out)}&darr;</span>
        {/if}
        {#if event.tool_name}
          <span class="stat-tool">{event.tool_name}</span>
          {#if event.tool_success === false}
            <span class="stat-fail">FAIL</span>
          {/if}
        {/if}
        {#if event.duration_ms !== null}
          <span class="stat-duration">{formatDuration(event.duration_ms)}</span>
        {/if}
      </span>
    </div>
    {#if event.model}
      <div class="card-model">{event.model}</div>
    {/if}
    {#if expanded}
      <div class="card-content" class:monospace={event.type === 'tool'}>
        {displayContent}
        {#if !showFull && event.content.length > CONTENT_EXPAND_THRESHOLD}
          <button class="show-full-btn" onclick|stopPropagation={() => showFull = true}>
            Show full ({event.content.length.toLocaleString()} chars)
          </button>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .timeline-card {
    display: flex;
    gap: 0;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.03);
    cursor: pointer;
    transition: background 0.15s;
    overflow: hidden;
  }

  .timeline-card:hover {
    background: rgba(255, 255, 255, 0.06);
  }

  .timeline-card.selected {
    background: rgba(255, 255, 255, 0.08);
    outline: 1px solid rgba(255, 255, 255, 0.15);
  }

  .card-color-bar {
    width: 3px;
    flex-shrink: 0;
    background: var(--agent-color);
  }

  .card-body {
    flex: 1;
    padding: 8px 12px;
    min-width: 0;
  }

  .card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
  }

  .type-badge {
    background: color-mix(in srgb, var(--type-color) 20%, transparent);
    color: var(--type-color);
    padding: 1px 6px;
    border-radius: 3px;
    font-weight: 600;
    font-size: 10px;
    letter-spacing: 0.5px;
    flex-shrink: 0;
  }

  .raw-type {
    color: #aaa;
    font-family: monospace;
    font-size: 11px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .card-stats {
    margin-left: auto;
    display: flex;
    gap: 8px;
    flex-shrink: 0;
    font-size: 11px;
    color: #888;
  }

  .stat-tokens {
    color: #4a9eff;
  }

  .stat-tool {
    color: #4ade80;
    font-family: monospace;
  }

  .stat-fail {
    color: #ff6b6b;
    font-weight: 600;
  }

  .stat-duration {
    color: #888;
  }

  .card-model {
    font-size: 11px;
    color: #666;
    padding-top: 2px;
    font-family: monospace;
  }

  .card-content {
    margin-top: 8px;
    padding: 8px;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 4px;
    font-size: 12px;
    color: #ccc;
    line-height: 1.5;
    max-height: 300px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .card-content.monospace {
    font-family: monospace;
    font-size: 11px;
  }

  .show-full-btn {
    display: block;
    margin-top: 8px;
    background: rgba(74, 158, 255, 0.15);
    color: #4a9eff;
    border: none;
    padding: 4px 8px;
    border-radius: 3px;
    font-size: 11px;
    cursor: pointer;
  }

  .show-full-btn:hover {
    background: rgba(74, 158, 255, 0.25);
  }
</style>
```

- [ ] **Step 2: Verify build**

```bash
cd src/desmet/webui/frontend && bun run build
```
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/components/TimelineCard.svelte
git commit -m "feat: add TimelineCard component for message flow display"
```

---

### Task 7: Frontend — Rewrite AgentGraph.svelte

**Files:**
- Rewrite: `src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte`

This is the main integration task. The component connects Svelte Flow (graph canvas) with the message list and manages scroll sync.

- [ ] **Step 1: Rewrite AgentGraph.svelte**

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import {
    SvelteFlow,
    type Node,
    type Edge,
    type NodeTypes,
    Background,
    BackgroundVariant,
  } from '@xyflow/svelte';
  import '@xyflow/svelte/dist/style.css';
  import ELK from 'elkjs/lib/elk.bundled.js';
  import { fetchAgentGraph } from '../api';
  import type { CommunicationGraph, TimelineEvent, GraphNode as ApiGraphNode } from '../api';
  import AgentNode from './AgentNode.svelte';
  import TimelineCard from './TimelineCard.svelte';

  let { platformId, storyId }: { platformId: string; storyId: string } = $props();

  let graphData: CommunicationGraph | null = $state(null);
  let loading = $state(true);
  let error: string | null = $state(null);
  let activeAgentId: string | null = $state(null);
  let filterAgentId: string | null = $state(null);
  let selectedEventIndex: number | null = $state(null);
  let listContainer: HTMLDivElement | undefined = $state();
  let cardElements: Map<number, HTMLDivElement> = new Map();

  // Svelte Flow state
  let nodes: Node[] = $state([]);
  let edges: Edge[] = $state([]);

  const ROLE_COLORS: Record<string, string> = {
    planner: '#4ade80',
    executor: '#4a9eff',
    reviewer: '#ff6b6b',
    manager: '#c084fc',
  };

  function roleColor(id: string): string {
    return ROLE_COLORS[id] ?? '#888888';
  }

  const nodeTypes: NodeTypes = { agent: AgentNode as any };

  // Visible edges: only show edges for transitions up to the active scroll position
  let visibleEdgeKeys = $state(new Set<string>());
  let activeEdgeKey: string | null = $state(null);

  function edgeKey(source: string, target: string): string {
    return `${source}->${target}`;
  }

  // Compute which edges are visible based on the selected/active event
  function updateVisibleEdges(upToIndex: number) {
    const timeline = graphData?.timeline ?? [];
    const seen = new Set<string>();
    let currentAgent: string | null = null;
    let lastActiveKey: string | null = null;

    for (let i = 0; i <= upToIndex && i < timeline.length; i++) {
      const evt = timeline[i];
      if (!evt.agent_id) continue;
      if (currentAgent && currentAgent !== evt.agent_id) {
        const key = edgeKey(currentAgent, evt.agent_id);
        seen.add(key);
        lastActiveKey = key;
      }
      currentAgent = evt.agent_id;
    }

    visibleEdgeKeys = seen;
    activeEdgeKey = lastActiveKey;
  }

  // Filtered timeline for display
  let displayTimeline = $derived(
    filterAgentId
      ? (graphData?.timeline ?? []).filter(e => e.agent_id === filterAgentId)
      : (graphData?.timeline ?? [])
  );

  let filterAgentName = $derived(
    filterAgentId
      ? graphData?.nodes.find(n => n.id === filterAgentId)?.role ?? filterAgentId
      : null
  );

  let filterCount = $derived(displayTimeline.length);

  // Update Svelte Flow edges when visibility changes
  $effect(() => {
    if (!graphData) return;
    edges = graphData.edges.map(e => {
      const key = edgeKey(e.source, e.target);
      const visible = visibleEdgeKeys.has(key);
      const active = key === activeEdgeKey;
      return {
        id: key,
        source: e.source,
        target: e.target,
        type: 'default',
        animated: active,
        style: visible
          ? `stroke: ${active ? '#4a9eff' : '#555'}; stroke-width: ${active ? 2.5 : 1.5}; opacity: ${active ? 1 : 0.5};`
          : 'stroke: transparent; stroke-width: 0;',
        label: visible ? `${e.message_count}` : '',
        labelStyle: 'fill: #888; font-size: 10px;',
      };
    });
  });

  // Update node active state
  $effect(() => {
    if (!graphData) return;
    nodes = nodes.map(n => ({
      ...n,
      data: { ...n.data, active: n.id === activeAgentId },
    }));
  });

  async function layoutWithELK(apiNodes: ApiGraphNode[], apiEdges: typeof graphData.edges) {
    const elk = new ELK();

    const elkGraph = {
      id: 'root',
      layoutOptions: {
        'elk.algorithm': 'layered',
        'elk.direction': 'DOWN',
        'elk.spacing.nodeNode': '80',
        'elk.layered.spacing.nodeNodeBetweenLayers': '100',
      },
      children: apiNodes.map(n => ({
        id: n.id,
        width: 120,
        height: 80,
      })),
      edges: apiEdges.map((e, i) => ({
        id: `elk-edge-${i}`,
        sources: [e.source],
        targets: [e.target],
      })),
    };

    const layout = await elk.layout(elkGraph);

    return (layout.children ?? []).map(child => ({
      id: child.id,
      type: 'agent',
      position: { x: child.x ?? 0, y: child.y ?? 0 },
      data: {
        label: apiNodes.find(n => n.id === child.id)?.role ?? child.id,
        color: roleColor(child.id),
        tokens: (() => {
          const n = apiNodes.find(n => n.id === child.id);
          return n ? n.tokens_in + n.tokens_out : 0;
        })(),
        active: false,
      },
    }));
  }

  async function loadGraph() {
    loading = true;
    error = null;
    activeAgentId = null;
    filterAgentId = null;
    selectedEventIndex = null;
    visibleEdgeKeys = new Set();
    activeEdgeKey = null;

    try {
      graphData = await fetchAgentGraph(platformId, storyId);
      if (graphData.nodes.length === 0) {
        error = 'No agent data available for this run.';
        return;
      }
      nodes = await layoutWithELK(graphData.nodes, graphData.edges);
      // Initialize all edges as hidden
      edges = graphData.edges.map(e => ({
        id: edgeKey(e.source, e.target),
        source: e.source,
        target: e.target,
        type: 'default',
        style: 'stroke: transparent; stroke-width: 0;',
        label: '',
      }));
      // If timeline has events, show all edges by default
      if (graphData.timeline.length > 0) {
        updateVisibleEdges(graphData.timeline.length - 1);
      }
    } catch (e: any) {
      error = e.status === 404 ? 'No trace data found.' : `Failed to load graph: ${e.message}`;
    } finally {
      loading = false;
    }
  }

  function handleNodeClick(event: CustomEvent) {
    const nodeId = event.detail.node?.id;
    if (!nodeId) return;
    // Toggle filter
    filterAgentId = filterAgentId === nodeId ? null : nodeId;
  }

  function handleCardClick(evt: TimelineEvent) {
    selectedEventIndex = evt.index;
    activeAgentId = evt.agent_id || null;
    updateVisibleEdges(evt.index);
  }

  // Scroll-driven tracking via IntersectionObserver
  let observer: IntersectionObserver | null = null;

  onMount(() => {
    if (listContainer) {
      observer = new IntersectionObserver(
        (entries) => {
          // Find the topmost visible card
          let topEntry: IntersectionObserverEntry | null = null;
          for (const entry of entries) {
            if (entry.isIntersecting) {
              if (!topEntry || entry.boundingClientRect.top < topEntry.boundingClientRect.top) {
                topEntry = entry;
              }
            }
          }
          if (topEntry) {
            const idx = Number((topEntry.target as HTMLElement).dataset.eventIndex);
            if (!isNaN(idx) && graphData?.timeline) {
              const evt = graphData.timeline[idx];
              if (evt?.agent_id) {
                activeAgentId = evt.agent_id;
                updateVisibleEdges(idx);
              }
            }
          }
        },
        { root: listContainer, threshold: 0.5 }
      );
    }
  });

  function registerCard(el: HTMLDivElement, index: number) {
    cardElements.set(index, el);
    observer?.observe(el);
    return {
      destroy() {
        observer?.unobserve(el);
        cardElements.delete(index);
      },
    };
  }

  // Keyboard navigation
  function handleListKeydown(e: KeyboardEvent) {
    if (!graphData?.timeline) return;
    const filtered = displayTimeline;
    if (!filtered.length) return;

    if (e.key === 'Escape') {
      filterAgentId = null;
      return;
    }

    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const currentIdx = filtered.findIndex(ev => ev.index === selectedEventIndex);
      let nextIdx: number;
      if (e.key === 'ArrowDown') {
        nextIdx = currentIdx < filtered.length - 1 ? currentIdx + 1 : currentIdx;
      } else {
        nextIdx = currentIdx > 0 ? currentIdx - 1 : 0;
      }
      const nextEvent = filtered[nextIdx];
      handleCardClick(nextEvent);
      // Scroll card into view
      const el = cardElements.get(nextEvent.index);
      el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }

  $effect(() => {
    if (platformId && storyId) {
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
        {graphData.edges.reduce((s, e) => s + e.message_count, 0)} transitions
        {#if graphData.timeline.length > 0}
          &middot; {graphData.timeline.length} events
        {/if}
      </span>
    </div>
  {/if}

  <div class="graph-layout">
    <div class="graph-panel">
      {#if loading}
        <div class="graph-status">Loading graph...</div>
      {:else if error}
        <div class="graph-status">{error}</div>
      {:else}
        <SvelteFlow
          {nodes}
          {edges}
          {nodeTypes}
          fitView
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag
          zoomOnScroll
          on:nodeclick={handleNodeClick}
          colorMode="dark"
        >
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
        </SvelteFlow>
      {/if}
    </div>

    <div
      class="timeline-panel"
      bind:this={listContainer}
      onkeydown={handleListKeydown}
      tabindex="0"
      role="listbox"
    >
      {#if filterAgentId}
        <div class="filter-bar">
          <span>Showing: <strong style="color: {roleColor(filterAgentId)}">{filterAgentName}</strong> ({filterCount} messages)</span>
          <button class="filter-clear" onclick={() => filterAgentId = null}>&times;</button>
        </div>
      {/if}
      {#each displayTimeline as evt (evt.index)}
        <div
          data-event-index={evt.index}
          use:registerCard={evt.index}
        >
          <TimelineCard
            event={evt}
            agentColor={roleColor(evt.agent_id)}
            selected={selectedEventIndex === evt.index}
            onclick={() => handleCardClick(evt)}
          />
        </div>
      {/each}
      {#if displayTimeline.length === 0 && !loading}
        <div class="timeline-empty">No events to display</div>
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
    height: 500px;
  }

  .graph-panel {
    flex: 3;
    position: relative;
    background: rgba(255, 255, 255, 0.03);
    border-radius: 8px;
    overflow: hidden;
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

  .timeline-panel {
    flex: 2;
    display: flex;
    flex-direction: column;
    gap: 4px;
    overflow-y: auto;
    padding: 4px;
    background: rgba(255, 255, 255, 0.02);
    border-radius: 8px;
    outline: none;
  }

  .timeline-panel:focus-visible {
    outline: 1px solid rgba(74, 158, 255, 0.3);
  }

  .filter-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 10px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 4px;
    font-size: 12px;
    color: #ccc;
    position: sticky;
    top: 0;
    z-index: 1;
  }

  .filter-clear {
    background: none;
    border: none;
    color: #888;
    font-size: 16px;
    cursor: pointer;
    padding: 0 4px;
  }

  .filter-clear:hover {
    color: #ccc;
  }

  .timeline-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 200px;
    color: #666;
    font-size: 13px;
  }

  /* Override Svelte Flow dark mode background */
  :global(.svelte-flow) {
    background: transparent !important;
  }
</style>
```

Note: The `registerCard` function above is already written as a Svelte action (returns `{ destroy() }`) — the `use:registerCard={evt.index}` directive will call it with the element and the index parameter.

- [ ] **Step 2: Verify build**

```bash
cd src/desmet/webui/frontend && bun run build
```
Expected: Build succeeds with no errors.

- [ ] **Step 3: Smoke test in browser**

```bash
cd src/desmet/webui/frontend && bun run dev
```

Open the Scoring page, select a platform/story with trace data, click "Agent Graph" tab. Verify:
- Graph shows agent nodes in a layered layout
- Message list shows timeline events with colored bars and type badges
- Clicking a message highlights the corresponding node
- Clicking a node filters the message list
- Scrolling updates the active node
- Arrow keys navigate messages
- Escape clears filter

- [ ] **Step 4: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte
git commit -m "feat: rewrite AgentGraph with Svelte Flow + message timeline"
```

---

### Task 8: Integration verification and polish

**Files:**
- Possibly modify: `src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte` (fixes from smoke test)

- [ ] **Step 1: Run all backend tests**

```bash
uv run pytest tests/test_graph.py -v
```
Expected: All tests pass (existing + new timeline tests).

- [ ] **Step 2: Run frontend build**

```bash
cd src/desmet/webui/frontend && bun run build
```
Expected: Clean build, no errors.

- [ ] **Step 3: End-to-end verification**

Start the full stack:
```bash
cd src/desmet/webui && uv run uvicorn api:app --reload
```
```bash
cd src/desmet/webui/frontend && bun run dev
```

Test with multiple platforms:
1. LangGraph US-001 — should show chain topology (planner → executor → reviewer)
2. Agent Framework US-001 — should show hub-spoke topology (manager hub)
3. CrewAI US-001 — verify events display correctly

For each, verify:
- Topology badge shows correct stats including event count
- Graph renders with ELK layout
- Message list is scrollable and cards expand/collapse
- Scroll sync highlights active agent
- Node click filters work
- Keyboard navigation (arrows + escape) works

- [ ] **Step 4: Fix any issues found, commit**

```bash
git add -A
git commit -m "fix: polish agent graph integration"
```
