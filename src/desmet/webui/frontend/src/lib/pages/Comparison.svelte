<script lang="ts">
  import EChart from '../components/EChart.svelte';
  import { fetchStories } from '../api';
  import type { Story } from '../api';
  import { onMount } from 'svelte';

  let stories = $state<Story[]>([]);
  let loading = $state(true);
  let selectedDimension = $state('pipeline_completeness');

  const dimensions = [
    { id: 'pipeline_completeness', label: 'Pipeline Completeness' },
    { id: 'tool_integration', label: 'Tool Integration' },
    { id: 'error_recovery', label: 'Error Recovery' },
    { id: 'time_efficiency', label: 'Time Efficiency' },
    { id: 'autonomy', label: 'Autonomy' },
    { id: 'trace_quality', label: 'Trace Quality' },
  ];

  onMount(async () => {
    const res = await fetchStories();
    stories = (res as any).stories || [];
    loading = false;
  });
</script>

<div>
  <h1 style="margin-bottom: 28px;">Platform Comparison</h1>

  {#if loading}
    <div class="card" style="text-align: center; padding: 48px; color: var(--text-2);">Loading comparison data…</div>
  {:else}

  <!-- Radar + rankings side by side -->
  <div class="grid-2" style="margin-bottom: 28px;">
    <EChart endpoint="/api/dashboard/charts/radar" height={380} />
    <EChart endpoint="/api/dashboard/charts/rankings" height={380} />
  </div>

  <!-- Per-dimension analysis -->
  <div style="margin-bottom: 28px;">
    <h2 style="font-size: 14px; font-weight: 600; margin-bottom: 12px;">Dimension Drilldown</h2>
    <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 16px;">
      {#each dimensions as dim}
        <button
          class="btn btn-sm"
          class:btn-primary={selectedDimension === dim.id}
          class:btn-outline={selectedDimension !== dim.id}
          onclick={() => selectedDimension = dim.id}
        >
          {dim.label}
        </button>
      {/each}
    </div>
    {#key selectedDimension}
      <EChart endpoint={`/api/dashboard/charts/dimension/${selectedDimension}`} height={350} />
    {/key}
  </div>

  <!-- Efficiency chart -->
  <div style="margin-bottom: 28px;">
    <h2 style="font-size: 14px; font-weight: 600; margin-bottom: 12px;">Efficiency Analysis</h2>
    <EChart endpoint="/api/dashboard/charts/efficiency" height={350} />
  </div>

  <!-- Story-level comparison -->
  {#if stories.length > 0}
    <div>
      <h2 style="font-size: 14px; font-weight: 600; margin-bottom: 12px;">Story Comparison</h2>
      <EChart endpoint="/api/dashboard/charts/story-comparison" height={400} />
    </div>
  {/if}

  {/if}
</div>
