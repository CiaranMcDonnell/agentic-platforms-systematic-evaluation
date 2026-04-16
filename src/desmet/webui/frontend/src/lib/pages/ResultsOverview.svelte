<script lang="ts">
  import { fetchOverview } from '../api';
  import type { OverviewData } from '../api';
  import EChart from '../components/EChart.svelte';
  import DimScorePills from '../components/DimScorePills.svelte';
  import RunSelector from '../components/RunSelector.svelte';
  import FrameworkMetricsTable from '../components/comparison/FrameworkMetricsTable.svelte';
  import { selectedResultsRunId } from '../stores';

  let data = $state<OverviewData | null>(null);

  let currentRunId = $state<string | null>(null);
  selectedResultsRunId.subscribe((v) => (currentRunId = v));

  $effect(() => {
    const rid = currentRunId;
    fetchOverview(rid).then((d) => (data = d));
  });

  function hasAnyScore(dimScores: Record<string, number | null | undefined> | undefined): boolean {
    if (!dimScores) return false;
    return Object.values(dimScores).some(v => v !== null && v !== undefined);
  }
</script>

<div>
  <RunSelector />
  <h1 style="margin-bottom: 28px;">Results Overview</h1>

  {#if !data}
    <div class="card" style="padding: 40px; color: var(--text-2); text-align: center;">Loading...</div>
  {:else if !data.has_data}
    <div class="card" style="padding: 48px; color: var(--text-2); text-align: center;">
      No evaluation results yet. Run a benchmark first.
    </div>
  {:else}
    <!-- Scoring progress -->
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin-bottom: 28px;">
      {#each data.platforms || [] as p}
        <div class="card" style="padding: 14px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 13px; font-weight: 500;">{p.platform_name}</span>
            <span class="mono text-muted" style="font-size: 11px;">{p.scored}/{p.total_to_score}</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" style="width: {p.total_to_score ? p.scored / p.total_to_score * 100 : 0}%; background: {p.colour};"></div>
          </div>
        </div>
      {/each}
    </div>

    <!-- Rankings table with dim score sub-rows -->
    <div class="table-wrap" style="margin-bottom: 28px;">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Platform</th>
            <th>Category</th>
            <th style="text-align: right;">Score</th>
            <th style="text-align: right;">Completion</th>
          </tr>
        </thead>
        <tbody>
          {#each data.platforms || [] as p, i}
            <tr>
              <td class="mono" style="font-weight: 600;">{i + 1}</td>
              <td>
                <span style="display: inline-flex; align-items: center; gap: 8px;">
                  <span style="width: 8px; height: 8px; border-radius: 50%; background: {p.colour}; display: inline-block;"></span>
                  {p.platform_name}
                </span>
              </td>
              <td class="text-muted" style="font-size: 12px;">{p.category}</td>
              <td class="mono" style="text-align: right;">{p.overall_score.toFixed(2)}</td>
              <td style="text-align: right;">
                <span style="display: inline-flex; align-items: center; gap: 8px;">
                  <span class="progress-bar" style="width: 64px;">
                    <span class="progress-fill" style="width: {p.completion_rate * 100}%; background: var(--text-0);"></span>
                  </span>
                  <span class="mono text-secondary" style="font-size: 12px;">{(p.completion_rate * 100).toFixed(0)}%</span>
                </span>
              </td>
            </tr>
            <!-- Dimension score sub-row -->
            <tr class="dim-subrow">
              <td colspan="5">
                {#if hasAnyScore(p.dim_scores)}
                  <DimScorePills scores={p.dim_scores ?? {}} />
                {:else}
                  <span class="no-scores">No rubric scores yet</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <!-- Charts -->
    <div class="grid-2" style="margin-bottom: 28px;">
      <EChart endpoint="/api/dashboard/charts/rankings" />
      <EChart endpoint="/api/dashboard/charts/completion" />
    </div>

    <div style="margin-bottom: 28px;">
      <EChart endpoint="/api/dashboard/charts/radar" height={400} />
    </div>

    <EChart endpoint="/api/dashboard/charts/efficiency" />

    <!-- Framework Metrics -->
    <div style="margin-top: 28px;">
      <FrameworkMetricsTable runId={currentRunId} />
    </div>
  {/if}
</div>

<style>
  .dim-subrow td {
    padding: 4px 12px 10px;
    border-top: none;
  }
  .no-scores {
    font-size: 10px;
    color: var(--text-2);
    font-style: italic;
  }
</style>
