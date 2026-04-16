<script lang="ts">
  import EChart from '../EChart.svelte';
  import ScoreMatrix from '../ScoreMatrix.svelte';
  import { fetchScoringMatrix } from '../../api';
  import type { ScoringMatrixData } from '../../api';

  let { runId = null }: { runId?: string | null } = $props();

  let matrixData = $state<ScoringMatrixData | null>(null);
  let loading = $state(true);

  $effect(() => {
    loading = true;
    fetchScoringMatrix(runId)
      .then((d) => {
        matrixData = d;
        loading = false;
      })
      .catch(() => {
        matrixData = null;
        loading = false;
      });
  });

  let hasMatrixData = $derived(
    matrixData !== null &&
      matrixData.platforms.length > 0 &&
      matrixData.platforms.some((p) =>
        Object.values(p.scores).some((v) => v !== null)
      )
  );

  let radarEndpoint = $derived(
    `/api/dashboard/charts/radar${runId ? `?run_id=${runId}` : ''}`
  );
</script>

<div>
  <h2 style="font-size: 14px; font-weight: 600; margin-bottom: 12px;">
    Rubric Score Matrix
  </h2>

  <div class="grid-2" style="margin-bottom: 8px; align-items: start;">
    <div>
      {#if loading}
        <div class="card" style="padding: 24px; color: var(--text-2); font-size: 13px; text-align: center;">
          Loading rubric matrix…
        </div>
      {:else if hasMatrixData && matrixData}
        <ScoreMatrix {matrixData} />
      {:else}
        <div class="card" style="padding: 24px; color: var(--text-2); font-size: 13px; text-align: center;">
          Score platforms in the Scoring tab to populate this matrix.
        </div>
      {/if}
    </div>
    {#key radarEndpoint}
      <EChart endpoint={radarEndpoint} height={380} />
    {/key}
  </div>
</div>
