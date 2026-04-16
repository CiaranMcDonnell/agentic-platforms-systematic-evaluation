<script lang="ts">
  import EChart from '../EChart.svelte';
  import { store } from '../../data.svelte';

  let { runId = null }: { runId?: string | null } = $props();

  let metric = $state<'wall_clock_seconds' | 'iterations' | 'tool_calls'>(
    'wall_clock_seconds'
  );

  const METRIC_LABELS: Record<string, string> = {
    wall_clock_seconds: 'Wall Clock (s)',
    iterations: 'Iterations',
    tool_calls: 'Tool Calls',
  };

  let endpoint = $derived.by(() => {
    const params = new URLSearchParams({ metric });
    if (runId) params.set('run_id', runId);
    return `/api/dashboard/charts/story-comparison?${params.toString()}`;
  });
</script>

{#if store.stories.length > 0}
  <div>
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
      <h2 style="font-size: 14px; font-weight: 600;">Story Comparison</h2>
      <label style="display: flex; align-items: center; gap: 8px; font-size: 12px;">
        <span class="text-muted">Metric:</span>
        <select class="input" bind:value={metric} style="padding: 4px 8px; font-size: 12px;">
          {#each Object.keys(METRIC_LABELS) as key}
            <option value={key}>{METRIC_LABELS[key]}</option>
          {/each}
        </select>
      </label>
    </div>
    {#key endpoint}
      <EChart {endpoint} height={400} />
    {/key}
  </div>
{/if}
