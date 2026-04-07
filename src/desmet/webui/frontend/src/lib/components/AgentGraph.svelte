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
  let allObservations: Map<string, LangfuseObservation> = $state(new Map());
  let selectedObsId: string | null = $state(null);
  let selectedObservation = $derived(
    selectedObsId ? allObservations.get(selectedObsId) ?? null : null
  );
  let topologyStats = $state({ agents: 0, tokens: 0, observations: 0, transitions: 0 });

  // Derive nodes with selected state
  let nodes = $derived(
    baseNodes.map(n => {
      if (n.type === 'observation') {
        return { ...n, data: { ...n.data, selected: n.id === selectedObsId } };
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

  // Threshold for switching from layered DOWN to rectpacking. Compares against
  // the direct child count, which equals the leaf count only because compound
  // children always force the layered branch in pickLayoutOptions. Tunable.
  const PACK_THRESHOLD = 6;

  // DFS positional walkers used for cross-cluster transition edges. They assume
  // children are in temporal (start_time) order — currently true because the
  // Langfuse client appends children as it iterates the observation list, which
  // the API returns chronologically. If that assumption breaks, the cross-cluster
  // arrows will point at the wrong leaves.
  function firstLeaf(obs: LangfuseObservation): LangfuseObservation {
    let cur = obs;
    while (cur.children.length > 0) cur = cur.children[0];
    return cur;
  }

  function lastLeaf(obs: LangfuseObservation): LangfuseObservation {
    let cur = obs;
    while (cur.children.length > 0) cur = cur.children[cur.children.length - 1];
    return cur;
  }

  function pickLayoutOptions(
    children: LangfuseObservation[],
    headerPad: number,
  ): Record<string, string> {
    const hasCompoundChildren = children.some(c => c.children.length > 0);
    const useLayered = hasCompoundChildren || children.length <= PACK_THRESHOLD;
    if (useLayered) {
      return {
        'elk.algorithm': 'layered',
        'elk.direction': 'DOWN',
        'elk.spacing.nodeNode': '20',
        'elk.layered.spacing.nodeNodeBetweenLayers': '30',
        'elk.padding': `[top=${headerPad},left=24,bottom=24,right=24]`,
      };
    }
    return {
      'elk.algorithm': 'rectpacking',
      // Widescreen-ish target. If the bundled elkjs build doesn't honour
      // elk.aspectRatio, fall back to elk.rectpacking.targetWidth (see spec
      // risks section).
      'elk.aspectRatio': '1.6',
      'elk.spacing.nodeNode': '12',
      'elk.padding': `[top=${headerPad},left=24,bottom=24,right=24]`,
    };
  }

  type ElkNode = {
    id: string;
    width?: number;
    height?: number;
    layoutOptions?: Record<string, string>;
    children?: ElkNode[];
    edges?: { id: string; sources: string[]; targets: string[] }[];
  };

  type EdgeIdGen = (prefix: string) => string;

  function buildElkNode(
    obs: LangfuseObservation,
    depth: number,
    nextEdgeId: EdgeIdGen,
  ): ElkNode {
    if (obs.children.length === 0) {
      return {
        id: obs.id,
        width: 200,
        height: obs.model ? 56 : 44,
      };
    }

    // Compound node: recurse into children
    const headerPad = depth === 0 ? 48 : 32;
    const layoutOptions = pickLayoutOptions(obs.children, headerPad);
    const childNodes = obs.children.map(c => buildElkNode(c, depth + 1, nextEdgeId));

    // Inner sequential edges only for layered containers (rectpacking gets none)
    const edges: { id: string; sources: string[]; targets: string[] }[] = [];
    if (layoutOptions['elk.algorithm'] === 'layered') {
      for (let i = 0; i < obs.children.length - 1; i++) {
        edges.push({
          id: nextEdgeId('inner'),
          sources: [obs.children[i].id],
          targets: [obs.children[i + 1].id],
        });
      }
    }

    return {
      id: obs.id,
      layoutOptions,
      children: childNodes,
      edges,
    };
  }

  function obsStat(obs: LangfuseObservation): string {
    if (obs.type === 'generation' && obs.tokens.total > 0) {
      return `${obs.tokens.input.toLocaleString()}↑ ${obs.tokens.output.toLocaleString()}↓`;
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

      // Root's direct children are the agent clusters.
      // If there's only one root observation (the harness wrapper), use its children instead.
      let agentObs: LangfuseObservation[];
      if (rootObs.length === 1 && rootObs[0].children.length > 0) {
        agentObs = rootObs[0].children;
      } else {
        agentObs = rootObs;
      }

      // Build observation index (full DFS over each agent subtree)
      for (const agent of agentObs) {
        for (const obs of flattenObservations(agent)) {
          allObservations.set(obs.id, obs);
        }
      }

      // Build ELK compound graph recursively from the Langfuse tree.
      // Edge IDs are generated by a per-call counter so concurrent invocations
      // (e.g. rapid prop changes that re-trigger this $effect) cannot collide.
      const elk = new ELK();
      let edgeCounter = 0;
      const nextEdgeId: EdgeIdGen = (prefix) => `${prefix}-${edgeCounter++}`;

      const elkChildren: ElkNode[] = agentObs.map(agent => {
        const node = buildElkNode(agent, 0, nextEdgeId);
        // Force the agent-cluster id prefix so the visual style picker can
        // distinguish top-level agent containers from nested compound observations.
        node.id = `agent-${agent.name}`;
        return node;
      });

      // Cross-cluster edges: last leaf of agent[i] -> first leaf of agent[i+1]
      const crossClusterEdges: { source: string; target: string; sourceAgent: string }[] = [];
      const elkEdges: { id: string; sources: string[]; targets: string[] }[] = [];
      for (let i = 0; i < agentObs.length - 1; i++) {
        const fromLeaf = lastLeaf(agentObs[i]);
        const toLeaf = firstLeaf(agentObs[i + 1]);
        crossClusterEdges.push({
          source: fromLeaf.id,
          target: toLeaf.id,
          sourceAgent: agentObs[i].name,
        });
        elkEdges.push({
          id: nextEdgeId('cross'),
          sources: [fromLeaf.id],
          targets: [toLeaf.id],
        });
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

      // Convert ELK layout to Svelte Flow nodes.
      // TODO(Task 3): this loop is depth-1 only. buildElkNode produces a
      // multi-level compound graph; compound observation children are dropped
      // here and will be rendered correctly once Task 3 replaces this block
      // with a recursive emitFlowNodes walker.
      const flowNodes: Node[] = [];

      for (const agentLayout of layout.children ?? []) {
        const agentName = agentLayout.id.replace('agent-', '');
        const agentColor = roleColor(agentName);
        const agentData = agentObs.find(a => a.name === agentName);
        const agentTotalTokens = agentData
          ? flattenObservations(agentData).reduce((s, o) => s + o.tokens.total, 0)
          : 0;

        // Agent container — content-box so border doesn't eat into ELK-computed area
        flowNodes.push({
          id: agentLayout.id,
          type: 'group',
          position: { x: agentLayout.x ?? 0, y: agentLayout.y ?? 0 },
          style: `width: ${agentLayout.width}px; height: ${agentLayout.height}px; background: rgba(255,255,255,0.02); border: 2px solid ${agentColor}; border-radius: 12px; box-sizing: content-box;`,
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

      // Inner edges (sequential within clusters, using original flatObs order)
      for (const agent of agentObs) {
        const flatObs = flattenObservations(agent);
        for (let i = 0; i < flatObs.length - 1; i++) {
          flowEdges.push({
            id: `inner-${flatObs[i].id}-${flatObs[i + 1].id}`,
            source: flatObs[i].id,
            target: flatObs[i + 1].id,
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

      topologyStats = {
        agents: agentObs.length,
        tokens: langfuseData.trace.total_tokens,
        observations: allObservations.size,
        transitions: crossClusterEdges.length,
      };

    } catch (e: any) {
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
        'elk.direction': 'RIGHT',
        'elk.spacing.nodeNode': '80',
        'elk.layered.spacing.nodeNodeBetweenLayers': '100',
      },
      children: apiNodes.map(n => ({ id: n.id, width: 140, height: 80 })),
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
      if (node.type === 'observation') {
        selectedObsId = selectedObsId === node.id ? null : node.id;
      }
    } else {
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

<div class="agent-graph-container" onkeydown={handleKeydown} tabindex="0" role="region" aria-label="Agent communication graph">
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

  <div class="graph-layout" class:has-drawer={mode === 'langfuse' && !!selectedObsId}>
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
    background: color-mix(in srgb, var(--blue) 20%, transparent);
    color: var(--blue);
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 11px;
  }

  .topology-stats { color: var(--text-2); }

  .graph-layout {
    display: flex;
    gap: 0;
    height: 600px;
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
    color: var(--text-2);
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
    color: var(--text-1);
    position: sticky;
    top: 0;
    z-index: 1;
  }

  .filter-clear {
    background: none;
    border: none;
    color: var(--text-2);
    font-size: 16px;
    cursor: pointer;
    padding: 0 4px;
  }

  .filter-clear:hover { color: var(--text-1); }

  .timeline-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 200px;
    color: var(--text-2);
    font-size: 13px;
  }

  :global(.svelte-flow) {
    background: transparent !important;
  }

  :global(.svelte-flow__attribution) {
    display: none !important;
  }
</style>
