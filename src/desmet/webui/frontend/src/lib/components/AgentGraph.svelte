<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import * as echarts from 'echarts';
  import { fetchAgentGraph } from '../api';
  import type { CommunicationGraph, GraphNode } from '../api';

  let { platformId, storyId }: { platformId: string; storyId: string } = $props();

  let container: HTMLDivElement | undefined = $state();
  let chart: echarts.ECharts | null = null;
  let resizeObserver: ResizeObserver | null = null;
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

  function esc(s: string): string {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
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
      message_count: e.message_count,
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
            return `<b>${esc(n.role)}</b><br/>Tokens: ${(n.tokens_in + n.tokens_out).toLocaleString()}<br/>Iterations: ${n.iterations}`;
          }
          if (params.dataType === 'edge') {
            return `${esc(params.data.source)} → ${esc(params.data.target)}<br/>Messages: ${params.data.message_count ?? 0}`;
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
      resizeObserver = new ResizeObserver(() => chart?.resize());
      resizeObserver.observe(container);
      chart.on('click', (params: any) => {
        if (params.dataType === 'node' && graphData) {
          selectedNode = graphData.nodes.find(n => n.id === params.data.id) ?? null;
        }
      });
    }
  });

  onDestroy(() => {
    resizeObserver?.disconnect();
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
