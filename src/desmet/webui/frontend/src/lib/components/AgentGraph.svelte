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

  // Visible edges tracking
  let visibleEdgeKeys = $state(new Set<string>());
  let activeEdgeKey: string | null = $state(null);

  function edgeKey(source: string, target: string): string {
    return `${source}->${target}`;
  }

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

  // Update edges when visibility changes
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
      edges = graphData.edges.map(e => ({
        id: edgeKey(e.source, e.target),
        source: e.source,
        target: e.target,
        type: 'default',
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

  // onnodeclick receives { node, event } destructured object
  function handleNodeClick({ node }: { node: Node; event: MouseEvent | TouchEvent }) {
    const nodeId = node?.id;
    if (!nodeId) return;
    filterAgentId = filterAgentId === nodeId ? null : nodeId;
  }

  function handleCardClick(evt: TimelineEvent) {
    selectedEventIndex = evt.index;
    activeAgentId = evt.agent_id || null;
    updateVisibleEdges(evt.index);
  }

  // Scroll-driven tracking
  let observer: IntersectionObserver | null = null;

  // Svelte action for registering cards with IntersectionObserver
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
      for (const el of cardElements.values()) {
        observer.observe(el);
      }
    }
  });

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
          panOnDrag={true}
          zoomOnScroll={true}
          onnodeclick={handleNodeClick}
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

  :global(.svelte-flow) {
    background: transparent !important;
  }
</style>
