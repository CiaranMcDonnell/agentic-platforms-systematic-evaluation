<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchLangSmithRun } from '../api';
  import type { LangSmithRunTree, LangSmithRun, LangfuseObservation } from '../api';
  import SpanNode from './SpanNode.svelte';

  interface Props {
    runId: string;
  }

  let { runId }: Props = $props();

  let loading = $state(true);
  let error = $state<string | null>(null);
  let runTree = $state<LangSmithRunTree | null>(null);

  onMount(async () => {
    try {
      runTree = await fetchLangSmithRun(runId);
      if (!runTree) error = 'Run not found or LangSmith unavailable.';
    } catch (e) {
      error = 'Failed to load LangSmith trace.';
    } finally {
      loading = false;
    }
  });

  /** Normalise a LangSmithRun into a LangfuseObservation for SpanNode. */
  function normalise(run: LangSmithRun): LangfuseObservation {
    return {
      id: run.id,
      name: run.name,
      type: run.run_type === 'llm' ? 'generation' : 'span',
      start_time: run.start_time,
      end_time: run.end_time,
      latency_ms: run.latency_ms,
      model: run.model,
      tokens: run.tokens,
      cost: 0,
      level: run.error ? 'ERROR' : 'DEFAULT',
      status_message: run.error ?? null,
      input: run.inputs,
      output: run.outputs,
      children: run.children.map(normalise),
    };
  }
</script>

{#if loading}
  <div class="ls-state">Loading LangSmith trace…</div>
{:else if error}
  <div class="ls-state ls-error">{error}</div>
{:else if runTree}
  <div class="ls-header">
    <span class="ls-name">{runTree.run.name}</span>
    <span class="ls-meta">
      {(runTree.run.latency_ms / 1000).toFixed(2)}s
      · {runTree.run.total_tokens.toLocaleString()} tokens
      {#if runTree.run.tags?.length}· {runTree.run.tags.join(', ')}{/if}
    </span>
  </div>
  <div class="ls-tree">
    {#each runTree.children as child (child.id)}
      <SpanNode observation={normalise(child)} rootLatency={runTree.run.latency_ms} />
    {/each}
  </div>
{/if}

<style>
  .ls-state {
    padding: 24px;
    color: var(--text-2);
    font-size: 13px;
    text-align: center;
  }
  .ls-error { color: var(--red, #e53e3e); }
  .ls-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 12px;
    padding: 0 2px;
  }
  .ls-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-0);
  }
  .ls-meta {
    font-size: 11px;
    font-family: var(--mono);
    color: var(--text-2);
  }
  .ls-tree { display: flex; flex-direction: column; gap: 2px; }
</style>
