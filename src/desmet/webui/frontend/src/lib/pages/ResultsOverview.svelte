<script lang="ts">
  import { fetchOverview, fetchFrameworkMetrics } from '../api';
  import type { OverviewData, FrameworkMetricsPlatform } from '../api';
  import EChart from '../components/EChart.svelte';
  import DimScorePills from '../components/DimScorePills.svelte';
  import RunSelector from '../components/RunSelector.svelte';
  import { selectedResultsRunId } from '../stores';

  let data = $state<OverviewData | null>(null);
  let fmPlatforms = $state<FrameworkMetricsPlatform[]>([]);

  let currentRunId = $state<string | null>(null);
  selectedResultsRunId.subscribe((v) => (currentRunId = v));

  $effect(() => {
    const rid = currentRunId;
    fetchOverview(rid).then((d) => (data = d));
    fetchFrameworkMetrics().then((fm) => (fmPlatforms = fm.platforms)).catch(() => (fmPlatforms = []));
  });

  function hasAnyScore(dimScores: Record<string, number | null | undefined> | undefined): boolean {
    if (!dimScores) return false;
    return Object.values(dimScores).some(v => v !== null && v !== undefined);
  }

  const FM_KEYS = [
    'tokens_per_stage',
    'iteration_ratio',
    'first_action_latency_ms',
    'redundant_tool_call_rate',
    'tool_failure_rate',
    'framework_overhead_ms',
  ] as const;

  const FM_LABELS: Record<string, string> = {
    tokens_per_stage: 'Tokens / Stage',
    iteration_ratio: 'Iteration Ratio',
    first_action_latency_ms: 'First-Action Latency',
    redundant_tool_call_rate: 'Redundant Calls',
    tool_failure_rate: 'Tool Failure Rate',
    framework_overhead_ms: 'Framework Overhead',
  };

  function fmFormat(key: string, val: number | null | undefined): string {
    if (val === null || val === undefined) return 'N/A';
    if (key === 'tokens_per_stage') return val.toLocaleString();
    if (key === 'iteration_ratio' || key === 'redundant_tool_call_rate' || key === 'tool_failure_rate') {
      return (val * 100).toFixed(1) + '%';
    }
    if (key === 'first_action_latency_ms' || key === 'framework_overhead_ms') {
      return val.toLocaleString() + ' ms';
    }
    return String(val);
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
    {#if fmPlatforms.length > 0}
      <div class="card" style="margin-top: 28px;">
        <h2 style="font-size: 14px; font-weight: 600; margin-bottom: 16px;">Framework Metrics (per-stage averages)</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Metric</th>
                {#each fmPlatforms as p}
                  <th style="text-align: right;">{p.platform_name}</th>
                {/each}
              </tr>
            </thead>
            <tbody>
              {#each FM_KEYS as key}
                <tr>
                  <td style="font-size: 12px; font-weight: 500;">{FM_LABELS[key]}</td>
                  {#each fmPlatforms as p}
                    <td class="mono" style="text-align: right; font-size: 12px;">
                      {fmFormat(key, p.metrics[key])}
                    </td>
                  {/each}
                </tr>
              {/each}
              <tr style="border-top: 1px solid var(--border);">
                <td style="font-size: 11px; color: var(--text-2);">Stories</td>
                {#each fmPlatforms as p}
                  <td class="mono text-muted" style="text-align: right; font-size: 11px;">{p.story_count}</td>
                {/each}
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    {/if}
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
