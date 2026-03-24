<script lang="ts">
  import type { LangfuseObservation } from '../api';

  interface Props {
    observation: LangfuseObservation;
    rootLatency: number;
    depth?: number;
  }

  let { observation, rootLatency, depth = 0 }: Props = $props();
  let expanded = $state(false);
  $effect(() => { expanded = depth < 2; });

  let barWidth = $derived(rootLatency > 0 ? Math.max(2, (observation.latency_ms / rootLatency) * 100) : 0);
  let isError = $derived(observation.level === 'ERROR');
  let isGeneration = $derived(observation.type === 'generation');
  let hasTokens = $derived(observation.tokens.total > 0);
</script>

<div class="span-node" style="margin-left: {depth * 20}px;">
  <button class="span-header" class:error={isError} onclick={() => expanded = !expanded}>
    <span class="span-icon">{isGeneration ? '\u2728' : '\u{1F4C2}'}</span>
    <span class="span-name">{observation.name || 'unnamed'}</span>
    <div class="span-bar-track">
      <div class="span-bar-fill" style="width: {barWidth}%;"></div>
    </div>
    <span class="span-stat">{(observation.latency_ms / 1000).toFixed(2)}s</span>
    {#if hasTokens}
      <span class="span-stat tok">{observation.tokens.total.toLocaleString()} tok</span>
    {/if}
    {#if observation.model}
      <span class="span-stat model">{observation.model}</span>
    {/if}
    <span class="span-chevron">{expanded ? '\u25BC' : '\u25B6'}</span>
  </button>

  {#if expanded}
    <div class="span-body">
      <div class="span-meta">
        <div class="meta-cell">
          <span class="meta-label">Type</span>
          <span class="meta-value">{observation.type}</span>
        </div>
        <div class="meta-cell">
          <span class="meta-label">Duration</span>
          <span class="meta-value mono">{(observation.latency_ms / 1000).toFixed(3)}s</span>
        </div>
        {#if hasTokens}
          <div class="meta-cell">
            <span class="meta-label">Tokens In</span>
            <span class="meta-value mono">{observation.tokens.input.toLocaleString()}</span>
          </div>
          <div class="meta-cell">
            <span class="meta-label">Tokens Out</span>
            <span class="meta-value mono">{observation.tokens.output.toLocaleString()}</span>
          </div>
        {/if}
        {#if observation.model}
          <div class="meta-cell">
            <span class="meta-label">Model</span>
            <span class="meta-value">{observation.model}</span>
          </div>
        {/if}
        {#if observation.status_message}
          <div class="meta-cell wide">
            <span class="meta-label">Status</span>
            <span class="meta-value" class:err-text={isError}>{observation.status_message}</span>
          </div>
        {/if}
      </div>

      {#if observation.input}
        <details class="io-block">
          <summary>Input</summary>
          <pre class="io-pre">{observation.input}</pre>
        </details>
      {/if}
      {#if observation.output}
        <details class="io-block">
          <summary>Output</summary>
          <pre class="io-pre">{observation.output}</pre>
        </details>
      {/if}
    </div>

    {#if observation.children.length > 0}
      {#each observation.children as child (child.id)}
        <svelte:self observation={child} {rootLatency} depth={depth + 1} />
      {/each}
    {/if}
  {/if}
</div>

<style>
  .span-node { margin-bottom: 3px; }

  .span-header {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 8px 12px;
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    font-family: var(--sans);
    color: var(--text-0);
    text-align: left;
    transition: border-color 0.12s ease;
  }
  .span-header:hover { border-color: var(--border-hover); }
  .span-header.error { border-color: var(--red); }

  .span-icon { font-size: 13px; flex-shrink: 0; }
  .span-name { font-weight: 500; flex-shrink: 0; white-space: nowrap; }

  .span-bar-track {
    flex: 1;
    height: 4px;
    background: var(--bg-3);
    border-radius: 2px;
    min-width: 40px;
    overflow: hidden;
  }
  .span-bar-fill {
    height: 100%;
    background: var(--yellow);
    border-radius: 2px;
    opacity: 0.6;
  }

  .span-stat {
    font-size: 11px;
    font-family: var(--mono);
    color: var(--text-2);
    flex-shrink: 0;
    white-space: nowrap;
  }
  .span-stat.tok { color: var(--yellow); }
  .span-stat.model { color: var(--green); }
  .span-chevron { font-size: 9px; color: var(--text-2); flex-shrink: 0; }

  .span-body {
    margin: 4px 0 4px 24px;
    padding: 10px 14px;
    background: var(--bg-2);
    border-radius: 6px;
    border-left: 2px solid var(--border);
  }

  .span-meta {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 8px 20px;
  }
  .meta-cell { display: flex; flex-direction: column; gap: 2px; }
  .meta-cell.wide { grid-column: 1 / -1; }
  .meta-label {
    font-size: 10px;
    color: var(--text-2);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 500;
  }
  .meta-value { font-size: 13px; color: var(--text-0); }
  .meta-value.mono { font-family: var(--mono); }
  .err-text { color: var(--red); }

  .io-block { margin-top: 10px; }
  .io-block summary {
    font-size: 12px;
    color: var(--text-2);
    cursor: pointer;
    padding: 4px 0;
    user-select: none;
    font-weight: 500;
  }
  .io-block summary:hover { color: var(--text-1); }
  .io-pre {
    font-size: 12px;
    font-family: var(--mono);
    padding: 10px 12px;
    margin: 4px 0 0;
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 280px;
    overflow-y: auto;
    color: var(--text-1);
    line-height: 1.5;
  }
</style>
