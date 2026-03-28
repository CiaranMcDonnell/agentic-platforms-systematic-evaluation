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
