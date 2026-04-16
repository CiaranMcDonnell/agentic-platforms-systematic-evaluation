<script lang="ts">
  import EChart from '../EChart.svelte';

  let { runId = null }: { runId?: string | null } = $props();

  let rankingsEndpoint = $derived(
    `/api/dashboard/charts/rankings${runId ? `?run_id=${runId}` : ''}`
  );
  let completionEndpoint = $derived(
    `/api/dashboard/charts/completion${runId ? `?run_id=${runId}` : ''}`
  );
</script>

<div class="grid-2">
  {#key rankingsEndpoint}
    <EChart endpoint={rankingsEndpoint} height={380} />
  {/key}
  {#key completionEndpoint}
    <EChart endpoint={completionEndpoint} height={380} />
  {/key}
</div>
