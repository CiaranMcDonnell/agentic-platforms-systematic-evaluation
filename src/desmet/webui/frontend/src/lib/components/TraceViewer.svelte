<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchLangfuseTrace } from '../api';
  import type { LangfuseTraceDetail, LangfuseObservation } from '../api';
  import SpanNode from './SpanNode.svelte';
  import TimelineView from './TimelineView.svelte';
  import MessageThreadView from './MessageThreadView.svelte';
  import ToolsLogView from './ToolsLogView.svelte';

  interface Message {
    role?: string;
    content?: string;
  }

  interface Props {
    messages?: Message[];
    langfuseTraceId?: string | null;
  }

  let { messages = [], langfuseTraceId = null }: Props = $props();

  let traceData = $state<LangfuseTraceDetail | null>(null);
  let loading = $state(false);
  let error = $state('');

  // Tab state
  type Tab = 'timeline' | 'messages' | 'tools' | 'spans';
  let activeTab = $state<Tab>('timeline');

  // Spans tab controls
  let expandAll = $state(false);
  type SpanFilter = 'all' | 'llm' | 'tool' | 'error';
  let spanFilter = $state<SpanFilter>('all');

  // Derived summary stats (unchanged from original)
  let tokens = $derived(traceData ? sumTokens(traceData.observations) : { input: 0, output: 0, total: 0 });
  let gens = $derived(traceData ? countGenerations(traceData.observations) : 0);
  let errs = $derived(traceData ? countErrors(traceData.observations) : 0);
  let spanCount = $derived(traceData ? countObs(traceData.observations) : 0);
  let totalCost = $derived(traceData ? (traceData.trace.cost || sumCost(traceData.observations)) : 0);

  // Filtered observations for Spans tab
  let filteredObs = $derived(traceData ? filterObs(traceData.observations, spanFilter) : []);

  onMount(async () => {
    if (!langfuseTraceId) return;
    loading = true;
    try {
      const data = await fetchLangfuseTrace(langfuseTraceId);
      if ((data as any).error) {
        error = (data as any).error;
      } else {
        traceData = data;
      }
    } catch (e) {
      error = 'Failed to load Langfuse trace';
    }
    loading = false;
  });

  // ── Helpers ────────────────────────────────────────────────

  function filterObs(obs: LangfuseObservation[], filter: SpanFilter): LangfuseObservation[] {
    if (filter === 'all') return obs;
    return obs.flatMap(o => {
      const filteredChildren = filterObs(o.children, filter);
      const matches =
        (filter === 'llm' && o.type === 'generation') ||
        (filter === 'tool' && o.type === 'tool') ||
        (filter === 'error' && o.level === 'ERROR');
      if (matches || filteredChildren.length > 0) {
        return [{ ...o, children: filteredChildren }];
      }
      return [];
    });
  }

  function countErrors(obs: LangfuseObservation[]): number {
    let n = 0;
    for (const o of obs) { if (o.level === 'ERROR') n++; n += countErrors(o.children); }
    return n;
  }
  function countObs(obs: LangfuseObservation[]): number {
    let n = obs.length;
    for (const o of obs) n += countObs(o.children);
    return n;
  }
  function sumTokens(obs: LangfuseObservation[]): { input: number; output: number; total: number } {
    let input = 0, output = 0, total = 0;
    for (const o of obs) {
      input += o.tokens.input; output += o.tokens.output; total += o.tokens.total;
      const c = sumTokens(o.children);
      input += c.input; output += c.output; total += c.total;
    }
    return { input, output, total };
  }
  function countGenerations(obs: LangfuseObservation[]): number {
    let n = 0;
    for (const o of obs) { if (o.type === 'generation') n++; n += countGenerations(o.children); }
    return n;
  }
  function sumCost(obs: LangfuseObservation[]): number {
    let c = 0;
    for (const o of obs) { c += o.cost || 0; c += sumCost(o.children); }
    return c;
  }
</script>

{#if langfuseTraceId && loading}
  <div class="trace-status">Loading Langfuse trace...</div>
{:else if langfuseTraceId && error}
  <div class="trace-status trace-err">{error}</div>
{:else if traceData}
  <div class="trace-wrap">
    <!-- Summary pills -->
    <div class="trace-pills">
      <div class="pill"><span class="pill-lbl">Tokens In</span><span class="pill-val">{tokens.input.toLocaleString()}</span></div>
      <div class="pill"><span class="pill-lbl">Tokens Out</span><span class="pill-val">{tokens.output.toLocaleString()}</span></div>
      <div class="pill"><span class="pill-lbl">Total Tokens</span><span class="pill-val">{tokens.total.toLocaleString()}</span></div>
      {#if totalCost > 0}
        <div class="pill"><span class="pill-lbl">Est. Cost</span><span class="pill-val">${totalCost.toFixed(4)}</span></div>
      {/if}
      <div class="pill"><span class="pill-lbl">LLM Calls</span><span class="pill-val">{gens}</span></div>
      <div class="pill"><span class="pill-lbl">Spans</span><span class="pill-val">{spanCount}</span></div>
      {#if errs > 0}
        <div class="pill pill-err"><span class="pill-lbl">Errors</span><span class="pill-val">{errs}</span></div>
      {/if}
    </div>

    <!-- Tab bar -->
    <div class="tab-bar">
      {#each (['timeline', 'messages', 'tools', 'spans'] as Tab[]) as tab}
        <button
          class="tab-btn"
          class:active={activeTab === tab}
          onclick={() => activeTab = tab}
        >
          {tab === 'timeline' ? '⏱ Timeline' :
           tab === 'messages' ? '💬 Messages' :
           tab === 'tools'    ? '🔧 Tools' :
                                '🌲 Spans'}
        </button>
      {/each}
    </div>

    <!-- Tab content -->
    <div class="tab-content">
      {#if activeTab === 'timeline'}
        <TimelineView {traceData} />

      {:else if activeTab === 'messages'}
        <MessageThreadView {traceData} />

      {:else if activeTab === 'tools'}
        <ToolsLogView {traceData} />

      {:else}
        <!-- Spans tab: expand-all + filter chips -->
        <div class="spans-controls">
          <button
            class="ctrl-btn"
            onclick={() => { expandAll = !expandAll; }}
          >
            {expandAll ? 'Collapse All' : 'Expand All'}
          </button>
          <div class="filter-chips">
            {#each (['all', 'llm', 'tool', 'error'] as SpanFilter[]) as f}
              <button
                class="chip"
                class:active={spanFilter === f}
                onclick={() => spanFilter = f}
              >
                {f === 'all' ? 'All' : f === 'llm' ? 'LLM' : f === 'tool' ? 'Tool' : 'Error'}
              </button>
            {/each}
          </div>
          <span class="spans-count">{countObs(filteredObs)} spans</span>
        </div>
        <div class="trace-tree">
          {#each filteredObs as obs (obs.id)}
            <SpanNode observation={obs} rootLatency={traceData.trace.latency_ms} {expandAll} />
          {/each}
        </div>
      {/if}
    </div>
  </div>

{:else if messages.length > 0}
  <!-- Legacy flat message view (no Langfuse) -->
  <div class="trace-wrap">
    {#each messages as msg}
      <div class="msg msg-{msg.role || 'system'}">
        <div class="msg-role">{msg.role || 'system'}</div>
        <div class="msg-body">{msg.content || ''}</div>
      </div>
    {/each}
  </div>
{:else}
  <div class="trace-status">No trace data available</div>
{/if}

<style>
  .trace-wrap {
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    max-height: 800px;
    overflow-y: auto;
  }

  /* ── Summary pills ─────────────── */
  .trace-pills {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 14px;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--border);
  }
  .pill {
    display: flex; flex-direction: column; gap: 2px;
    padding: 8px 14px; border-radius: 6px;
    background: var(--bg-2); border: 1px solid var(--border);
  }
  .pill-err { border-color: var(--red); }
  .pill-lbl { font-size: 10px; color: var(--text-2); text-transform: uppercase; letter-spacing: 0.06em; font-weight: 500; }
  .pill-val { font-size: 15px; font-weight: 600; font-family: var(--mono); color: var(--text-0); }
  .pill-err .pill-val { color: var(--red); }

  /* ── Tab bar ───────────────────── */
  .tab-bar {
    display: flex;
    gap: 2px;
    margin-bottom: 12px;
    background: var(--bg-2);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 3px;
  }
  .tab-btn {
    flex: 1;
    padding: 6px 10px;
    font-size: 12px;
    font-family: var(--sans);
    border: none;
    border-radius: 4px;
    background: transparent;
    color: var(--text-2);
    cursor: pointer;
    font-weight: 500;
    transition: background 0.12s, color 0.12s;
    white-space: nowrap;
  }
  .tab-btn:hover { color: var(--text-1); }
  .tab-btn.active { background: var(--bg-1); color: var(--text-0); border: 1px solid var(--border); }

  /* ── Tab content ───────────────── */
  .tab-content { min-height: 200px; }

  /* ── Spans tab controls ────────── */
  .spans-controls {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border);
  }
  .ctrl-btn {
    padding: 4px 10px; font-size: 11px;
    border: 1px solid var(--border); border-radius: 4px;
    background: var(--bg-2); color: var(--text-1);
    cursor: pointer; font-family: var(--sans);
  }
  .ctrl-btn:hover { border-color: var(--border-hover); color: var(--text-0); }

  .filter-chips { display: flex; gap: 4px; }
  .chip {
    padding: 3px 10px; font-size: 11px; border-radius: 12px;
    border: 1px solid var(--border); background: transparent;
    color: var(--text-2); cursor: pointer; font-family: var(--sans);
  }
  .chip:hover { color: var(--text-1); }
  .chip.active { background: var(--bg-2); color: var(--text-0); border-color: var(--text-2); }
  .spans-count { font-size: 11px; color: var(--text-2); margin-left: auto; }

  .trace-tree { display: flex; flex-direction: column; gap: 3px; }

  /* ── Legacy messages ───────────── */
  .msg { padding: 8px 12px; margin: 4px 0; border-radius: 6px; font-size: 13px; border-left: 2px solid var(--border); background: var(--bg-2); }
  .msg-human  { border-left-color: var(--text-0); }
  .msg-ai     { border-left-color: var(--green); }
  .msg-tool   { border-left-color: var(--yellow); font-family: var(--mono); font-size: 12px; }
  .msg-system { border-left-color: var(--text-2); }
  .msg-role { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-2); margin-bottom: 3px; }
  .msg-body { white-space: pre-wrap; word-break: break-word; color: var(--text-1); line-height: 1.5; }

  /* ── Status / error ────────────── */
  .trace-status { padding: 24px; text-align: center; font-size: 13px; color: var(--text-2); background: var(--bg-1); border: 1px solid var(--border); border-radius: 8px; }
  .trace-err { color: var(--red); border-color: var(--red); }
</style>
