<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchLangfuseTrace } from '../api';
  import type { LangfuseTraceDetail, LangfuseObservation } from '../api';
  import SpanNode from './SpanNode.svelte';

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

  let tokens = $derived(traceData ? sumTokens(traceData.observations) : { input: 0, output: 0, total: 0 });
  let gens = $derived(traceData ? countGenerations(traceData.observations) : 0);
  let errs = $derived(traceData ? countErrors(traceData.observations) : 0);
  let spanCount = $derived(traceData ? countObs(traceData.observations) : 0);
  let totalCost = $derived(traceData ? (traceData.trace.cost || sumCost(traceData.observations)) : 0);

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

  function countErrors(obs: LangfuseObservation[]): number {
    let n = 0;
    for (const o of obs) {
      if (o.level === 'ERROR') n++;
      n += countErrors(o.children);
    }
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
      input += o.tokens.input;
      output += o.tokens.output;
      total += o.tokens.total;
      const child = sumTokens(o.children);
      input += child.input;
      output += child.output;
      total += child.total;
    }
    return { input, output, total };
  }

  function maxLatency(obs: LangfuseObservation[]): number {
    let max = 0;
    for (const o of obs) {
      if (o.latency_ms > max) max = o.latency_ms;
      const childMax = maxLatency(o.children);
      if (childMax > max) max = childMax;
    }
    return max;
  }

  function countGenerations(obs: LangfuseObservation[]): number {
    let n = 0;
    for (const o of obs) {
      if (o.type === 'generation') n++;
      n += countGenerations(o.children);
    }
    return n;
  }

  function sumCost(obs: LangfuseObservation[]): number {
    let c = 0;
    for (const o of obs) {
      c += o.cost || 0;
      c += sumCost(o.children);
    }
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
      <div class="pill">
        <span class="pill-lbl">Tokens In</span>
        <span class="pill-val">{tokens.input.toLocaleString()}</span>
      </div>
      <div class="pill">
        <span class="pill-lbl">Tokens Out</span>
        <span class="pill-val">{tokens.output.toLocaleString()}</span>
      </div>
      <div class="pill">
        <span class="pill-lbl">Total Tokens</span>
        <span class="pill-val">{tokens.total.toLocaleString()}</span>
      </div>
      {#if totalCost > 0}
        <div class="pill">
          <span class="pill-lbl">Est. Cost</span>
          <span class="pill-val">${totalCost.toFixed(4)}</span>
        </div>
      {/if}
      <div class="pill">
        <span class="pill-lbl">LLM Calls</span>
        <span class="pill-val">{gens}</span>
      </div>
      <div class="pill">
        <span class="pill-lbl">Spans</span>
        <span class="pill-val">{spanCount}</span>
      </div>
      {#if errs > 0}
        <div class="pill pill-err">
          <span class="pill-lbl">Errors</span>
          <span class="pill-val">{errs}</span>
        </div>
      {/if}
    </div>

    <!-- Span tree -->
    <div class="trace-tree">
      {#each traceData.observations as obs (obs.id)}
        <SpanNode observation={obs} rootLatency={traceData.trace.latency_ms} />
      {/each}
    </div>
  </div>
{:else if messages.length > 0}
  <!-- Legacy flat message view -->
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
    max-height: 640px;
    overflow-y: auto;
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
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
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 8px 14px;
    border-radius: 6px;
    background: var(--bg-2);
    border: 1px solid var(--border);
  }
  .pill-err { border-color: var(--red); }
  .pill-lbl {
    font-size: 10px;
    color: var(--text-2);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 500;
  }
  .pill-val {
    font-size: 15px;
    font-weight: 600;
    font-family: var(--mono);
    color: var(--text-0);
  }
  .pill-err .pill-val { color: var(--red); }

  /* ── Span tree ─────────────────── */
  .trace-tree {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  /* ── Legacy messages ───────────── */
  .msg {
    padding: 8px 12px;
    margin: 4px 0;
    border-radius: 6px;
    font-size: 13px;
    border-left: 2px solid var(--border);
    background: var(--bg-2);
  }
  .msg-human  { border-left-color: var(--text-0); }
  .msg-ai     { border-left-color: var(--green); }
  .msg-tool   { border-left-color: var(--yellow); font-family: var(--mono); font-size: 12px; }
  .msg-system { border-left-color: var(--text-2); }
  .msg-role {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-2);
    margin-bottom: 3px;
  }
  .msg-body {
    white-space: pre-wrap;
    word-break: break-word;
    color: var(--text-1);
    line-height: 1.5;
  }

  /* ── Status / error ────────────── */
  .trace-status {
    padding: 24px;
    text-align: center;
    font-size: 13px;
    color: var(--text-2);
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  .trace-err {
    color: var(--red);
    border-color: var(--red);
  }
</style>
