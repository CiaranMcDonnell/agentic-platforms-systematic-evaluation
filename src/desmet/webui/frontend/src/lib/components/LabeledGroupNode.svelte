<script lang="ts">
  /**
   * Nested container for the raw span view. Svelte Flow's built-in "group"
   * type renders no label at all, which left every nested box anonymous.
   */
  type Data = { label: string; color: string; tokens: number };
  let { data, width, height }: { data: Data; width?: number; height?: number } = $props();
</script>

<div class="labeled-group" style="--group-color: {data.color}; width: {width ?? 0}px; height: {height ?? 0}px;">
  <div class="group-header">
    <span class="group-label" title={data.label}>{data.label}</span>
    {#if data.tokens > 0}
      <span class="group-tokens">{data.tokens.toLocaleString()} tok</span>
    {/if}
  </div>
</div>

<style>
  .labeled-group {
    background: rgba(255, 255, 255, 0.015);
    border: 1px solid var(--group-color);
    border-radius: 8px;
    box-sizing: content-box;
    position: relative;
  }
  .group-header {
    position: absolute;
    top: 4px;
    left: 10px;
    right: 10px;
    display: flex;
    align-items: center;
    gap: 8px;
    pointer-events: none;
  }
  .group-label {
    font-size: 10px;
    font-weight: 600;
    color: var(--group-color);
    font-family: var(--mono);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .group-tokens {
    margin-left: auto;
    font-size: 9px;
    color: var(--text-2);
    font-family: var(--mono);
    flex-shrink: 0;
  }
</style>
