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

  function truncate(s: string, showFull: boolean): string {
    if (showFull || s.length <= TRUNCATE_AT) return s;
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
          <pre class="section-content">{truncate(formattedInput, inputShowFull)}</pre>
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
          <pre class="section-content">{truncate(formattedOutput, outputShowFull)}</pre>
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
    flex-shrink: 0;
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
