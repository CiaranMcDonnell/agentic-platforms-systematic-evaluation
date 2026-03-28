# Agent Graph Observation Clusters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a Langfuse trace is available, render all observations as nodes in the Agent Graph, grouped into agent clusters with a detail drawer, falling back to the current timeline view otherwise.

**Architecture:** AgentGraph.svelte gains a `langfuseTraceId` prop. When present, it fetches the Langfuse observation tree, flattens each agent subtree into Svelte Flow nodes inside ELK compound parent nodes, and renders cross-cluster transition edges with dots. Clicking a node opens an ObservationDrawer. When no trace ID, the existing 3-node + timeline list view is used unchanged.

**Tech Stack:** Svelte 5, @xyflow/svelte, elkjs (all already installed), existing Langfuse API client

**Spec:** `docs/superpowers/specs/2026-03-28-agent-graph-observation-clusters-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/desmet/webui/frontend/src/lib/components/ObservationNode.svelte` | Create | Custom Svelte Flow node for individual Langfuse observations |
| `src/desmet/webui/frontend/src/lib/components/ObservationDrawer.svelte` | Create | Side drawer showing full observation detail (input/output/stats) |
| `src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte` | Modify | Add langfuseTraceId prop, Langfuse data path, compound ELK layout, drawer integration |
| `src/desmet/webui/frontend/src/lib/pages/Scoring.svelte` | Modify | Pass langfuseTraceId prop to AgentGraph |

---

### Task 1: ObservationNode component

**Files:**
- Create: `src/desmet/webui/frontend/src/lib/components/ObservationNode.svelte`

- [ ] **Step 1: Create the ObservationNode component**

This is a custom Svelte Flow node that renders a single Langfuse observation as a compact card.

```svelte
<script lang="ts">
  import { Handle, Position } from '@xyflow/svelte';

  let { data }: { data: {
    name: string;
    obsType: 'span' | 'generation' | 'tool';
    stat: string;
    model: string | null;
    isError: boolean;
    selected: boolean;
  } } = $props();

  const TYPE_COLORS: Record<string, string> = {
    generation: '#4a9eff',
    tool: '#4ade80',
    span: '#888',
  };

  let typeColor = $derived(TYPE_COLORS[data.obsType] ?? '#888');
  let typeLabel = $derived(
    data.obsType === 'generation' ? 'LLM'
    : data.obsType === 'tool' ? 'TOOL'
    : 'SPAN'
  );
</script>

<div
  class="obs-node"
  class:selected={data.selected}
  class:error={data.isError}
  style="--type-color: {typeColor}"
  title="{data.name} — {data.stat}"
>
  <Handle type="target" position={Position.Top} />
  <div class="obs-header">
    <span class="obs-type-badge">{typeLabel}</span>
    <span class="obs-name" title={data.name}>{data.name}</span>
  </div>
  <div class="obs-stat">{data.stat}</div>
  {#if data.model}
    <div class="obs-model">{data.model}</div>
  {/if}
  <Handle type="source" position={Position.Bottom} />
</div>

<style>
  .obs-node {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 6px 10px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    cursor: pointer;
    min-width: 120px;
    max-width: 200px;
    transition: border-color 0.15s, box-shadow 0.15s;
  }

  .obs-node:hover {
    border-color: rgba(255, 255, 255, 0.25);
  }

  .obs-node.selected {
    border-color: var(--type-color);
    box-shadow: 0 0 10px color-mix(in srgb, var(--type-color) 30%, transparent);
  }

  .obs-node.error {
    border-color: #ff6b6b;
  }

  .obs-header {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .obs-type-badge {
    background: color-mix(in srgb, var(--type-color) 20%, transparent);
    color: var(--type-color);
    padding: 0 4px;
    border-radius: 2px;
    font-weight: 600;
    font-size: 8px;
    letter-spacing: 0.5px;
    flex-shrink: 0;
  }

  .obs-name {
    font-size: 10px;
    color: #ccc;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .obs-stat {
    font-size: 9px;
    color: #888;
  }

  .obs-model {
    font-size: 8px;
    color: #666;
    font-family: monospace;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  :global(.svelte-flow__handle) {
    width: 4px;
    height: 4px;
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
git add src/desmet/webui/frontend/src/lib/components/ObservationNode.svelte
git commit -m "feat: add ObservationNode component for Langfuse trace graph"
```

---

### Task 2: ObservationDrawer component

**Files:**
- Create: `src/desmet/webui/frontend/src/lib/components/ObservationDrawer.svelte`

- [ ] **Step 1: Create the ObservationDrawer component**

This is a side drawer that shows full observation details when a node is clicked.

```svelte
<script lang="ts">
  import type { LangfuseObservation } from '../api';
  import { formatContent } from '../format';

  let { observation = null, onclose }: {
    observation: LangfuseObservation | null;
    onclose: () => void;
  } = $props();

  const TYPE_COLORS: Record<string, string> = {
    generation: '#4a9eff',
    tool: '#4ade80',
    span: '#888',
  };

  function typeLabel(t: string): string {
    return t === 'generation' ? 'LLM' : t === 'tool' ? 'TOOL' : 'SPAN';
  }

  function formatDuration(ms: number): string {
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  }

  function formatCost(usd: number): string {
    if (usd === 0) return '';
    return `$${usd.toFixed(4)}`;
  }

  let inputExpanded = $state(false);
  let outputExpanded = $state(false);
  let inputShowFull = $state(false);
  let outputShowFull = $state(false);

  const TRUNCATE_AT = 2000;
  const SHOW_AT = 500;

  function truncate(s: string): string {
    if (inputShowFull || s.length <= TRUNCATE_AT) return s;
    return s.slice(0, SHOW_AT) + '...';
  }

  // Reset expand state when observation changes
  $effect(() => {
    if (observation) {
      inputExpanded = false;
      outputExpanded = false;
      inputShowFull = false;
      outputShowFull = false;
    }
  });

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') onclose();
  }
</script>

{#if observation}
  {@const obs = observation}
  {@const color = TYPE_COLORS[obs.type] ?? '#888'}
  {@const formattedInput = formatContent(obs.input)}
  {@const formattedOutput = formatContent(obs.output)}
  <div class="drawer" onkeydown={handleKeydown} tabindex="-1" role="complementary">
    <div class="drawer-header">
      <div class="drawer-title">
        <span class="type-badge" style="--type-color: {color}">{typeLabel(obs.type)}</span>
        <span class="drawer-name">{obs.name}</span>
      </div>
      <button class="drawer-close" onclick={onclose}>&times;</button>
    </div>

    <div class="drawer-stats">
      {#if obs.model}
        <div class="stat-row">
          <span class="stat-label">Model</span>
          <span class="stat-value model">{obs.model}</span>
        </div>
      {/if}
      <div class="stat-row">
        <span class="stat-label">Duration</span>
        <span class="stat-value">{formatDuration(obs.latency_ms)}</span>
      </div>
      {#if obs.tokens.total > 0}
        <div class="stat-row">
          <span class="stat-label">Tokens In</span>
          <span class="stat-value tokens">{obs.tokens.input.toLocaleString()}</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">Tokens Out</span>
          <span class="stat-value tokens">{obs.tokens.output.toLocaleString()}</span>
        </div>
      {/if}
      {#if obs.cost > 0}
        <div class="stat-row">
          <span class="stat-label">Cost</span>
          <span class="stat-value">{formatCost(obs.cost)}</span>
        </div>
      {/if}
      {#if obs.level === 'ERROR'}
        <div class="stat-row error">
          <span class="stat-label">Status</span>
          <span class="stat-value">ERROR{obs.status_message ? `: ${obs.status_message}` : ''}</span>
        </div>
      {/if}
    </div>

    {#if formattedInput}
      <div class="drawer-section">
        <button class="section-toggle" onclick={() => inputExpanded = !inputExpanded}>
          <span class="chevron" class:open={inputExpanded}>&#9654;</span>
          Input
        </button>
        {#if inputExpanded}
          <pre class="section-content">{inputShowFull ? formattedInput : truncate(formattedInput)}</pre>
          {#if !inputShowFull && formattedInput.length > TRUNCATE_AT}
            <button class="show-full-btn" onclick={() => inputShowFull = true}>
              Show full ({formattedInput.length.toLocaleString()} chars)
            </button>
          {/if}
        {/if}
      </div>
    {/if}

    {#if formattedOutput}
      <div class="drawer-section">
        <button class="section-toggle" onclick={() => outputExpanded = !outputExpanded}>
          <span class="chevron" class:open={outputExpanded}>&#9654;</span>
          Output
        </button>
        {#if outputExpanded}
          <pre class="section-content">{outputShowFull ? formattedOutput : truncate(formattedOutput)}</pre>
          {#if !outputShowFull && formattedOutput.length > TRUNCATE_AT}
            <button class="show-full-btn" onclick={() => outputShowFull = true}>
              Show full ({formattedOutput.length.toLocaleString()} chars)
            </button>
          {/if}
        {/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .drawer {
    width: 400px;
    height: 100%;
    overflow-y: auto;
    background: rgba(20, 20, 25, 0.95);
    border-left: 1px solid rgba(255, 255, 255, 0.1);
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    outline: none;
  }

  .drawer-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .drawer-title {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }

  .type-badge {
    background: color-mix(in srgb, var(--type-color) 20%, transparent);
    color: var(--type-color);
    padding: 2px 6px;
    border-radius: 3px;
    font-weight: 600;
    font-size: 10px;
    letter-spacing: 0.5px;
    flex-shrink: 0;
  }

  .drawer-name {
    font-size: 14px;
    font-weight: 600;
    color: #e0e0e0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .drawer-close {
    background: none;
    border: none;
    color: #888;
    font-size: 20px;
    cursor: pointer;
    padding: 0 4px;
    flex-shrink: 0;
  }

  .drawer-close:hover { color: #ccc; }

  .drawer-stats {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .stat-row {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    padding: 2px 0;
  }

  .stat-label { color: #888; }
  .stat-value { color: #ccc; }
  .stat-value.tokens { color: #4a9eff; }
  .stat-value.model { color: #4ade80; font-family: monospace; font-size: 11px; }
  .stat-row.error .stat-value { color: #ff6b6b; }

  .drawer-section {
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    padding-top: 8px;
  }

  .section-toggle {
    background: none;
    border: none;
    color: #aaa;
    font-size: 12px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 0;
    width: 100%;
    text-align: left;
  }

  .section-toggle:hover { color: #ccc; }

  .chevron {
    font-size: 8px;
    transition: transform 0.15s;
    display: inline-block;
  }

  .chevron.open { transform: rotate(90deg); }

  .section-content {
    margin-top: 6px;
    padding: 8px;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 4px;
    font-size: 11px;
    font-family: monospace;
    color: #ccc;
    line-height: 1.5;
    max-height: 300px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .show-full-btn {
    display: block;
    margin-top: 6px;
    background: rgba(74, 158, 255, 0.15);
    color: #4a9eff;
    border: none;
    padding: 3px 8px;
    border-radius: 3px;
    font-size: 10px;
    cursor: pointer;
  }

  .show-full-btn:hover { background: rgba(74, 158, 255, 0.25); }
</style>
```

- [ ] **Step 2: Verify build**

```bash
cd src/desmet/webui/frontend && bun run build
```
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/components/ObservationDrawer.svelte
git commit -m "feat: add ObservationDrawer for trace detail display"
```

---

### Task 3: Pass langfuseTraceId to AgentGraph

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/pages/Scoring.svelte:275`

- [ ] **Step 1: Update Scoring.svelte to pass langfuseTraceId**

Find line 275 in `Scoring.svelte`:
```svelte
        <AgentGraph platformId={selectedPlatform} storyId={selectedStory} />
```

Change to:
```svelte
        <AgentGraph platformId={selectedPlatform} storyId={selectedStory} langfuseTraceId={scoreData.langfuse_trace_id} />
```

- [ ] **Step 2: Verify build**

```bash
cd src/desmet/webui/frontend && bun run build
```
Expected: Build succeeds (AgentGraph doesn't accept this prop yet — but Svelte won't error on extra props, it'll just be ignored until Task 4).

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/pages/Scoring.svelte
git commit -m "feat: pass langfuseTraceId to AgentGraph component"
```

---

### Task 4: Rewrite AgentGraph with Langfuse observation clusters

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte`

This is the main integration task. AgentGraph gains two modes: Langfuse mode (observation clusters) and fallback mode (existing 3-node + timeline).

- [ ] **Step 1: Rewrite AgentGraph.svelte**

Replace the entire content of `src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte`:

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import {
    SvelteFlow,
    type Node,
    type Edge,
    type NodeTypes,
    type EdgeTypes,
    Background,
    BackgroundVariant,
  } from '@xyflow/svelte';
  import '@xyflow/svelte/dist/style.css';
  import ELK from 'elkjs/lib/elk.bundled.js';
  import { fetchAgentGraph, fetchLangfuseTrace } from '../api';
  import type {
    CommunicationGraph, TimelineEvent, GraphNode as ApiGraphNode,
    LangfuseObservation, LangfuseTraceDetail,
  } from '../api';
  import AgentNode from './AgentNode.svelte';
  import ObservationNode from './ObservationNode.svelte';
  import TransitionEdge from './TransitionEdge.svelte';
  import TimelineCard from './TimelineCard.svelte';
  import ObservationDrawer from './ObservationDrawer.svelte';

  let { platformId, storyId, langfuseTraceId = null }: {
    platformId: string;
    storyId: string;
    langfuseTraceId?: string | null;
  } = $props();

  // ── Shared state ──────────────────────────────────────────────
  let loading = $state(true);
  let error: string | null = $state(null);
  let mode: 'langfuse' | 'fallback' = $state('fallback');

  let baseNodes: Node[] = $state([]);
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

  const nodeTypes: NodeTypes = {
    agent: AgentNode as any,
    observation: ObservationNode as any,
  };
  const edgeTypes: EdgeTypes = { transition: TransitionEdge as any };

  // ── Langfuse mode state ───────────────────────────────────────
  let langfuseData: LangfuseTraceDetail | null = $state(null);
  let allObservations: Map<string, LangfuseObservation> = new Map();
  let selectedObsId: string | null = $state(null);
  let selectedObservation = $derived(
    selectedObsId ? allObservations.get(selectedObsId) ?? null : null
  );
  let agentNames: string[] = $state([]);
  let topologyStats = $state({ agents: 0, tokens: 0, observations: 0, transitions: 0 });

  // Derive nodes with selected state for Langfuse mode
  let nodes = $derived(
    baseNodes.map(n => {
      if (n.type === 'observation') {
        return { ...n, data: { ...n.data, selected: n.id === selectedObsId } };
      }
      if (n.type === 'agent') {
        return { ...n, data: { ...n.data, active: false } };
      }
      return n;
    })
  );

  // ── Fallback mode state ───────────────────────────────────────
  let graphData: CommunicationGraph | null = $state(null);
  let activeAgentId: string | null = $state(null);
  let filterAgentId: string | null = $state(null);
  let selectedEventIndex: number | null = $state(null);
  let listContainer: HTMLDivElement | undefined = $state();
  let cardElements: Map<number, HTMLDivElement> = new Map();

  let visibleEdgeKeys = $state(new Set<string>());
  let activeEdgeKey: string | null = $state(null);
  let edgeDotCounts = $state(new Map<string, number>());

  function edgeKey(source: string, target: string): string {
    return `${source}->${target}`;
  }

  // ── Langfuse layout ───────────────────────────────────────────

  function flattenObservations(obs: LangfuseObservation): LangfuseObservation[] {
    const result: LangfuseObservation[] = [obs];
    for (const child of obs.children) {
      result.push(...flattenObservations(child));
    }
    return result;
  }

  function obsStat(obs: LangfuseObservation): string {
    if (obs.type === 'generation' && obs.tokens.total > 0) {
      return `${obs.tokens.input.toLocaleString()}↑ ${obs.tokens.output.toLocaleString()}↓`;
    }
    if (obs.type === 'tool') {
      return `${(obs.latency_ms / 1000).toFixed(2)}s`;
    }
    return `${(obs.latency_ms / 1000).toFixed(2)}s`;
  }

  async function loadLangfuseGraph(traceId: string) {
    loading = true;
    error = null;
    mode = 'langfuse';
    selectedObsId = null;
    allObservations = new Map();

    try {
      langfuseData = await fetchLangfuseTrace(traceId);
      const rootObs = langfuseData.observations;

      if (rootObs.length === 0) {
        error = 'No observations found in trace.';
        return;
      }

      // Root's direct children are the agent clusters
      // If there's only one root observation (the harness wrapper), use its children
      let agentObs: LangfuseObservation[];
      if (rootObs.length === 1 && rootObs[0].children.length > 0) {
        agentObs = rootObs[0].children;
      } else {
        agentObs = rootObs;
      }

      agentNames = agentObs.map(a => a.name);

      // Build observation index
      for (const agent of agentObs) {
        for (const obs of flattenObservations(agent)) {
          allObservations.set(obs.id, obs);
        }
      }

      // Build ELK compound graph
      const elk = new ELK();

      const elkChildren: any[] = [];
      const elkEdges: any[] = [];
      let edgeIdx = 0;

      for (const agent of agentObs) {
        const flatObs = flattenObservations(agent);
        const agentNode: any = {
          id: `agent-${agent.name}`,
          layoutOptions: {
            'elk.algorithm': 'layered',
            'elk.direction': 'DOWN',
            'elk.spacing.nodeNode': '20',
            'elk.layered.spacing.nodeNodeBetweenLayers': '30',
            'elk.padding': '[top=40,left=15,bottom=15,right=15]',
          },
          children: flatObs.map(obs => ({
            id: obs.id,
            width: 160,
            height: obs.model ? 52 : 40,
          })),
          edges: [] as any[],
        };

        // Sequential edges within cluster
        for (let i = 0; i < flatObs.length - 1; i++) {
          agentNode.edges.push({
            id: `inner-${edgeIdx++}`,
            sources: [flatObs[i].id],
            targets: [flatObs[i + 1].id],
          });
        }

        elkChildren.push(agentNode);
      }

      // Cross-cluster edges (last obs of cluster N → first obs of cluster N+1)
      const crossClusterEdges: { source: string; target: string; sourceAgent: string }[] = [];
      for (let i = 0; i < agentObs.length - 1; i++) {
        const fromFlat = flattenObservations(agentObs[i]);
        const toFlat = flattenObservations(agentObs[i + 1]);
        if (fromFlat.length > 0 && toFlat.length > 0) {
          const src = fromFlat[fromFlat.length - 1].id;
          const tgt = toFlat[0].id;
          crossClusterEdges.push({
            source: src,
            target: tgt,
            sourceAgent: agentObs[i].name,
          });
          elkEdges.push({
            id: `cross-${edgeIdx++}`,
            sources: [src],
            targets: [tgt],
          });
        }
      }

      const elkGraph = {
        id: 'root',
        layoutOptions: {
          'elk.algorithm': 'layered',
          'elk.direction': 'RIGHT',
          'elk.spacing.nodeNode': '40',
          'elk.layered.spacing.nodeNodeBetweenLayers': '60',
        },
        children: elkChildren,
        edges: elkEdges,
      };

      const layout = await elk.layout(elkGraph);

      // Convert ELK layout to Svelte Flow nodes
      const flowNodes: Node[] = [];

      for (const agentLayout of layout.children ?? []) {
        const agentName = agentLayout.id.replace('agent-', '');
        const agentColor = roleColor(agentName);
        const agentTotalTokens = agentObs
          .find(a => a.name === agentName)
          ?.children ? flattenObservations(agentObs.find(a => a.name === agentName)!)
            .reduce((s, o) => s + o.tokens.total, 0) : 0;

        // Agent container as a Svelte Flow parent node
        flowNodes.push({
          id: agentLayout.id,
          type: 'group',
          position: { x: agentLayout.x ?? 0, y: agentLayout.y ?? 0 },
          style: `width: ${agentLayout.width}px; height: ${agentLayout.height}px; background: rgba(255,255,255,0.02); border: 2px solid ${agentColor}; border-radius: 12px;`,
          data: {
            label: agentName.charAt(0).toUpperCase() + agentName.slice(1),
            color: agentColor,
            tokens: agentTotalTokens,
          },
        });

        // Observation nodes inside the container
        for (const obsLayout of agentLayout.children ?? []) {
          const obs = allObservations.get(obsLayout.id);
          if (!obs) continue;
          flowNodes.push({
            id: obs.id,
            type: 'observation',
            position: { x: obsLayout.x ?? 0, y: obsLayout.y ?? 0 },
            parentId: agentLayout.id,
            extent: 'parent' as const,
            data: {
              name: obs.name,
              obsType: obs.type,
              stat: obsStat(obs),
              model: obs.model,
              isError: obs.level === 'ERROR',
              selected: false,
            },
          });
        }
      }

      baseNodes = flowNodes;

      // Build edges
      const flowEdges: Edge[] = [];

      // Inner edges (sequential within clusters) — thin, subtle
      for (const agentLayout of layout.children ?? []) {
        const agentFlat = agentLayout.children ?? [];
        for (let i = 0; i < agentFlat.length - 1; i++) {
          flowEdges.push({
            id: `inner-${agentFlat[i].id}-${agentFlat[i + 1].id}`,
            source: agentFlat[i].id,
            target: agentFlat[i + 1].id,
            style: 'stroke: #444; stroke-width: 1; opacity: 0.5;',
          });
        }
      }

      // Cross-cluster edges with transition dots
      for (const ce of crossClusterEdges) {
        flowEdges.push({
          id: `cross-${ce.source}-${ce.target}`,
          source: ce.source,
          target: ce.target,
          type: 'transition',
          data: { dots: 1, sourceColor: roleColor(ce.sourceAgent) },
          style: `stroke: ${roleColor(ce.sourceAgent)}; stroke-width: 2; opacity: 0.8;`,
        });
      }

      edges = flowEdges;

      // Compute stats
      topologyStats = {
        agents: agentObs.length,
        tokens: langfuseData.trace.total_tokens,
        observations: allObservations.size,
        transitions: crossClusterEdges.length,
      };

    } catch (e: any) {
      // Fall back to timeline mode
      console.warn('Langfuse trace failed, falling back:', e);
      mode = 'fallback';
      await loadFallbackGraph();
    } finally {
      loading = false;
    }
  }

  // ── Fallback layout (existing logic) ──────────────────────────

  function updateVisibleEdges(upToIndex: number) {
    const timeline = graphData?.timeline ?? [];
    const seen = new Set<string>();
    const counts = new Map<string, number>();
    let currentAgent: string | null = null;
    let lastActiveKey: string | null = null;

    for (let i = 0; i <= upToIndex && i < timeline.length; i++) {
      const evt = timeline[i];
      if (!evt.agent_id) continue;
      if (currentAgent && currentAgent !== evt.agent_id) {
        const key = edgeKey(currentAgent, evt.agent_id);
        seen.add(key);
        counts.set(key, (counts.get(key) ?? 0) + 1);
        lastActiveKey = key;
      }
      currentAgent = evt.agent_id;
    }

    visibleEdgeKeys = seen;
    activeEdgeKey = lastActiveKey;
    edgeDotCounts = counts;
  }

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

  // Update fallback edges when visibility changes
  $effect(() => {
    if (mode !== 'fallback' || !graphData) return;
    edges = graphData.edges.map(e => {
      const key = edgeKey(e.source, e.target);
      const visible = visibleEdgeKeys.has(key);
      const active = key === activeEdgeKey;
      const dots = edgeDotCounts.get(key) ?? 0;
      return {
        id: key,
        source: e.source,
        target: e.target,
        type: 'transition',
        animated: active,
        data: { dots: visible ? dots : 0, sourceColor: roleColor(e.source) },
        style: visible
          ? `stroke: ${active ? '#4a9eff' : '#555'}; stroke-width: ${active ? 2.5 : 1.5}; opacity: ${active ? 1 : 0.5};`
          : 'stroke: transparent; stroke-width: 0;',
        label: visible ? `${dots}` : '',
        labelStyle: 'fill: #888; font-size: 10px;',
      };
    });
  });

  async function layoutFallbackWithELK(apiNodes: ApiGraphNode[], apiEdges: typeof graphData.edges) {
    const elk = new ELK();
    const elkGraph = {
      id: 'root',
      layoutOptions: {
        'elk.algorithm': 'layered',
        'elk.direction': 'DOWN',
        'elk.spacing.nodeNode': '80',
        'elk.layered.spacing.nodeNodeBetweenLayers': '100',
      },
      children: apiNodes.map(n => ({ id: n.id, width: 120, height: 80 })),
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

  async function loadFallbackGraph() {
    loading = true;
    error = null;
    mode = 'fallback';
    activeAgentId = null;
    filterAgentId = null;
    selectedEventIndex = null;
    visibleEdgeKeys = new Set();
    activeEdgeKey = null;
    edgeDotCounts = new Map();

    try {
      graphData = await fetchAgentGraph(platformId, storyId);
      if (graphData.nodes.length === 0) {
        error = 'No agent data available for this run.';
        return;
      }
      baseNodes = await layoutFallbackWithELK(graphData.nodes, graphData.edges);
      edges = graphData.edges.map(e => ({
        id: edgeKey(e.source, e.target),
        source: e.source,
        target: e.target,
        type: 'transition',
        data: { dots: 0, sourceColor: roleColor(e.source) },
        style: 'stroke: transparent; stroke-width: 0;',
        label: '',
      }));
      if (graphData.timeline.length > 0) {
        updateVisibleEdges(graphData.timeline.length - 1);
      }
    } catch (e: any) {
      error = e.status === 404 ? 'No trace data found.' : `Failed to load graph: ${e.message}`;
    } finally {
      loading = false;
    }
  }

  // ── Interaction handlers ──────────────────────────────────────

  function handleNodeClick({ node }: { node: Node; event: MouseEvent | TouchEvent }) {
    if (mode === 'langfuse') {
      // Toggle observation selection for drawer
      if (node.type === 'observation') {
        selectedObsId = selectedObsId === node.id ? null : node.id;
      }
    } else {
      // Fallback: toggle agent filter
      const nodeId = node?.id;
      if (!nodeId) return;
      filterAgentId = filterAgentId === nodeId ? null : nodeId;
    }
  }

  function handleCardClick(evt: TimelineEvent) {
    selectedEventIndex = evt.index;
    activeAgentId = evt.agent_id || null;
    updateVisibleEdges(evt.index);
  }

  // Fallback scroll tracking
  let observer: IntersectionObserver | null = null;

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

  onMount(() => {
    if (listContainer) {
      observer = new IntersectionObserver(
        (entries) => {
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
    return () => { observer?.disconnect(); };
  });

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      if (mode === 'langfuse') {
        selectedObsId = null;
      } else {
        filterAgentId = null;
      }
      return;
    }

    if (mode === 'fallback') {
      if (!graphData?.timeline) return;
      const filtered = displayTimeline;
      if (!filtered.length) return;

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
        const el = cardElements.get(nextEvent.index);
        el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    }
  }

  // ── Load on prop change ───────────────────────────────────────

  $effect(() => {
    if (platformId && storyId) {
      if (langfuseTraceId) {
        loadLangfuseGraph(langfuseTraceId);
      } else {
        loadFallbackGraph();
      }
    }
  });
</script>

<div class="agent-graph-container" onkeydown={handleKeydown} tabindex="0" role="application">
  <!-- Topology badge -->
  {#if mode === 'langfuse' && langfuseData && !error}
    <div class="topology-badge">
      <span class="topology-label">TRACE</span>
      <span class="topology-stats">
        {topologyStats.agents} agents &middot;
        {topologyStats.tokens.toLocaleString()} tokens &middot;
        {topologyStats.transitions} transitions &middot;
        {topologyStats.observations} observations
      </span>
    </div>
  {:else if mode === 'fallback' && graphData && !error}
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

  <div class="graph-layout" class:has-drawer={mode === 'langfuse' && selectedObsId}>
    <!-- Graph canvas (shared) -->
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
          {edgeTypes}
          fitView
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag={true}
          zoomOnScroll={true}
          onnodeclick={handleNodeClick}
          colorMode="dark"
        >
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
        </SvelteFlow>
      {/if}
    </div>

    <!-- Right panel: drawer (Langfuse) or timeline list (fallback) -->
    {#if mode === 'langfuse'}
      <ObservationDrawer
        observation={selectedObservation}
        onclose={() => selectedObsId = null}
      />
    {:else}
      <div
        class="timeline-panel"
        bind:this={listContainer}
        tabindex="0"
        role="listbox"
      >
        {#if filterAgentId}
          <div class="filter-bar">
            <span>Showing: <strong style="color: {roleColor(filterAgentId)}">{filterAgentName}</strong> ({displayTimeline.length} messages)</span>
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
    {/if}
  </div>
</div>

<style>
  .agent-graph-container {
    display: flex;
    flex-direction: column;
    gap: 8px;
    outline: none;
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

  .topology-stats { color: #888; }

  .graph-layout {
    display: flex;
    gap: 0;
    height: 600px;
  }

  .graph-layout.has-drawer {
    gap: 0;
  }

  .graph-panel {
    flex: 1;
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
    width: 350px;
    flex-shrink: 0;
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

  .filter-clear:hover { color: #ccc; }

  .timeline-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 200px;
    color: #666;
    font-size: 13px;
  }

  :global(.svelte-flow) {
    background: transparent !important;
  }

  :global(.svelte-flow__attribution) {
    display: none !important;
  }
</style>
```

- [ ] **Step 2: Verify build**

```bash
cd src/desmet/webui/frontend && bun run build
```
Expected: Build succeeds.

- [ ] **Step 3: Smoke test**

Start the dev servers and verify:
1. **With Langfuse trace**: Select a platform/story that has Langfuse data. The Agent Graph tab should show agent clusters (colored containers) with observation nodes inside, connected by edges. Click a node to see the detail drawer.
2. **Without Langfuse trace**: The graph should fall back to the 3-node view with timeline list.

```bash
cd src/desmet/webui && uv run uvicorn api:app --reload &
cd src/desmet/webui/frontend && bun run dev
```

- [ ] **Step 4: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/components/AgentGraph.svelte
git commit -m "feat: rewrite AgentGraph with Langfuse observation clusters

When a Langfuse trace is available, renders all observations as
nodes grouped into agent clusters with ELK compound layout. Falls
back to existing 3-node + timeline view when no trace available."
```

---

### Task 5: Integration verification

**Files:**
- Possibly modify: any of the above for fixes

- [ ] **Step 1: Run backend tests**

```bash
uv run pytest tests/test_graph.py -v
```
Expected: All 15 tests pass (no backend changes, just verifying no regressions).

- [ ] **Step 2: Build frontend**

```bash
cd src/desmet/webui/frontend && bun run build
```
Expected: Clean build.

- [ ] **Step 3: End-to-end verification**

Start both servers and test:

1. **LangGraph with Langfuse** — Should show ~84 observation nodes in 3 clusters (planner, executor, reviewer). Cross-cluster arrows with dots. Click any node to see detail drawer with input/output.
2. **CrewAI with Langfuse** — Should show different cluster structure.
3. **Any platform without Langfuse** — Should fall back to 3-node graph + timeline list.

Verify:
- Agent clusters have colored borders matching their role colors
- Observation nodes show type badge (LLM/TOOL/SPAN), name, stat
- Detail drawer shows full info (model, tokens, duration, input/output)
- Escape closes drawer
- Pan/zoom works on the graph
- fitView shows the full picture on load

- [ ] **Step 4: Fix any issues, commit**

```bash
git add -A
git commit -m "fix: polish observation cluster integration"
```
