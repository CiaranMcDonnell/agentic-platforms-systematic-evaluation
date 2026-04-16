<script lang="ts">
  import EChart from '../EChart.svelte';

  let { runId = null }: { runId?: string | null } = $props();

  let endpoint = $derived(
    `/api/dashboard/charts/efficiency${runId ? `?run_id=${runId}` : ''}`
  );
</script>

<div>
  <h2 style="font-size: 14px; font-weight: 600; margin-bottom: 12px;">
    Efficiency Analysis
  </h2>
  {#key endpoint}
    <EChart {endpoint} height={350} />
  {/key}
</div>
