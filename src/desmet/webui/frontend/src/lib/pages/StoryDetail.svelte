<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchStories, fetchStoryDetail } from '../api';
  import type { Story, StoryDetailData } from '../api';
  import TraceViewer from '../components/TraceViewer.svelte';
  import EChart from '../components/EChart.svelte';
  import DimScorePills from '../components/DimScorePills.svelte';
  import { currentPage, scoringTarget } from '../stores';

  const SCORING_DIMS = [
    'pipeline_completeness',
    'tool_integration',
    'error_recovery',
    'time_efficiency',
    'autonomy',
    'trace_quality',
  ];

  let stories = $state<Story[]>([]);
  let selectedStory = $state('');
  let detail = $state<StoryDetailData | null>(null);
  let expandedTrace = $state<string | null>(null);

  onMount(async () => {
    const res = await fetchStories();
    stories = (res as any).stories || [];
  });

  async function loadDetail() {
    if (!selectedStory) return;
    expandedTrace = null;
    detail = await fetchStoryDetail(selectedStory);
  }

  function dimScores(platform: Record<string, unknown>): Record<string, number | null> {
    const out: Record<string, number | null> = {};
    for (const dim of SCORING_DIMS) {
      const v = platform[`${dim}_score`];
      out[dim] = (v !== undefined && v !== null) ? Number(v) : null;
    }
    return out;
  }

  function hasAnyDimScore(scores: Record<string, number | null>): boolean {
    return Object.values(scores).some(v => v !== null);
  }

  function goToScoring(platformId: string) {
    scoringTarget.set({ platform_id: platformId, story_id: selectedStory });
    currentPage.set('scoring');
  }
</script>

<div>
  <h1 style="margin-bottom: 28px;">Story Detail</h1>

  <!-- Story selector -->
  <div style="display: grid; grid-template-columns: 1fr auto; gap: 12px; margin-bottom: 28px; max-width: 500px;">
    <div>
      <label class="label" for="detail-story">Story</label>
      <select id="detail-story" class="input" bind:value={selectedStory} onchange={loadDetail}>
        <option value="">Select story…</option>
        {#each stories as s}
          <option value={s.id}>{s.title}</option>
        {/each}
      </select>
    </div>
    <div style="display: flex; align-items: flex-end;">
      <button class="btn btn-primary" onclick={loadDetail} disabled={!selectedStory}>Load</button>
    </div>
  </div>

  {#if detail && detail.platforms.length > 0}
    <!-- Metrics chart for this story -->
    {#key selectedStory}
      <div style="margin-bottom: 28px;">
        <EChart endpoint={`/api/dashboard/charts/story-comparison`} height={300} />
      </div>
    {/key}

    <!-- Platform performance table -->
    <div class="table-wrap" style="margin-bottom: 28px;">
      <table>
        <thead>
          <tr>
            <th>Platform</th>
            <th style="text-align: center;">Success</th>
            <th style="text-align: right;">Wall Clock</th>
            <th style="text-align: right;">Iterations</th>
            <th style="text-align: right;">Tool Calls</th>
            <th style="text-align: center;">Trace</th>
          </tr>
        </thead>
        <tbody>
          {#each detail.platforms as p}
            {@const scores = dimScores(p)}
            {@const scored = hasAnyDimScore(scores)}
            <tr>
              <td>
                <span style="display: inline-flex; align-items: center; gap: 8px;">
                  <span style="width: 8px; height: 8px; border-radius: 50%; background: {p.colour}; display: inline-block;"></span>
                  {p.platform_name}
                </span>
              </td>
              <td style="text-align: center;">
                {#if p.success}
                  <span class="badge badge-green">Pass</span>
                {:else}
                  <span class="badge badge-red">Fail</span>
                {/if}
              </td>
              <td class="mono" style="text-align: right;">{p.wall_clock_seconds?.toFixed(1) ?? '—'}s</td>
              <td class="mono" style="text-align: right;">{p.iterations ?? '—'}</td>
              <td class="mono" style="text-align: right;">{p.tool_calls ?? '—'}</td>
              <td style="text-align: center;">
                {#if detail.traces[p.platform_id]?.messages?.length}
                  <button
                    class="btn btn-outline btn-sm"
                    onclick={() => expandedTrace = expandedTrace === p.platform_id ? null : p.platform_id}
                  >
                    {expandedTrace === p.platform_id ? 'Hide' : 'View'}
                  </button>
                {:else}
                  <span class="text-muted" style="font-size: 11px;">—</span>
                {/if}
              </td>
            </tr>
            <!-- Dim score sub-row -->
            <tr class="dim-subrow">
              <td colspan="6">
                {#if scored}
                  <DimScorePills {scores} />
                {:else}
                  <span class="no-scores">
                    Not scored —
                    <button class="score-link" onclick={() => goToScoring(p.platform_id)}>
                      Score this →
                    </button>
                  </span>
                {/if}
              </td>
            </tr>
            {#if expandedTrace === p.platform_id}
              <tr>
                <td colspan="6" style="padding: 0;">
                  <div style="padding: 12px;">
                    <TraceViewer
                      langfuseTraceId={detail.langfuse_trace_ids?.[p.platform_id]}
                      messages={detail.traces[p.platform_id]?.messages || []}
                    />
                  </div>
                </td>
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>
    </div>
  {:else if detail && detail.platforms.length === 0}
    <div class="card" style="padding: 48px; color: var(--text-2); text-align: center;">
      No evaluation results for this story yet. Run a benchmark that includes it first.
    </div>
  {:else if selectedStory && !detail}
    <div class="card" style="padding: 40px; color: var(--text-2); text-align: center;">Loading…</div>
  {/if}
</div>

<style>
  .dim-subrow td {
    padding: 4px 12px 10px;
    border-top: none;
  }
  .no-scores {
    font-size: 11px;
    color: var(--text-2);
  }
  .score-link {
    background: none;
    border: none;
    cursor: pointer;
    font-size: 11px;
    color: var(--text-1);
    padding: 0;
    font-family: var(--sans);
    text-decoration: underline;
  }
  .score-link:hover { color: var(--text-0); }
</style>
