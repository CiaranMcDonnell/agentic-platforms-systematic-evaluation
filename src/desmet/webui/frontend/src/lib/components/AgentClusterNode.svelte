<script lang="ts">
  import { Handle, Position } from '@xyflow/svelte';

  type Data = { label: string; color: string; tokens: number };
  let { data, width, height }: { data: Data; width?: number; height?: number } = $props();
</script>

<div
  class="agent-cluster"
  style="--agent-color: {data.color}; width: {width ?? 0}px; height: {height ?? 0}px;"
>
  <Handle type="target" position={Position.Left} class="cluster-handle" />
  <div class="cluster-header">
    <span class="cluster-dot"></span>
    <span class="cluster-label">{data.label}</span>
    {#if data.tokens > 0}
      <span class="cluster-tokens">{data.tokens.toLocaleString()} tok</span>
    {/if}
  </div>
  <Handle type="source" position={Position.Right} class="cluster-handle" />
</div>

<style>
  .agent-cluster {
    background: rgba(255, 255, 255, 0.02);
    border: 2px solid var(--agent-color);
    border-radius: 12px;
    box-sizing: content-box;
    position: relative;
  }

  .cluster-header {
    position: absolute;
    top: 8px;
    left: 16px;
    right: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
    pointer-events: none;
  }

  .cluster-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--agent-color);
    flex-shrink: 0;
  }

  .cluster-label {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-0);
    text-transform: capitalize;
  }

  .cluster-tokens {
    font-size: 11px;
    color: var(--text-2);
    margin-left: auto;
    font-family: var(--mono);
  }

  :global(.cluster-handle) {
    width: 8px !important;
    height: 8px !important;
    background: var(--text-3) !important;
    border: none !important;
    opacity: 0.6;
  }
</style>
