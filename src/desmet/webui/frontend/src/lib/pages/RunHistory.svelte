<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchRuns, fetchDashboardStats } from '../api';
  import type { Run, DashboardStats } from '../api';
  import StatusBadge from '../components/StatusBadge.svelte';
  import { currentPage } from '../stores';

  let { onViewRun }: { onViewRun: (id: string) => void } = $props();

  let runs = $state<Run[]>([]);
  let stats = $state<DashboardStats | null>(null);

  async function load() {
    const [rRes, st] = await Promise.all([fetchRuns(), fetchDashboardStats()]);
    runs = (rRes as any).runs || [];
    stats = st;
  }

  onMount(load);
</script>

<div>
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
    <h1>Run History</h1>
    <div style="display: flex; gap: 8px;">
      <button class="btn btn-outline btn-sm" onclick={load}>Refresh</button>
      <button class="btn btn-primary btn-sm" onclick={() => currentPage.set('new-run')}>New Run</button>
    </div>
  </div>

  <!-- Persisted results summary -->
  {#if stats?.has_data}
    <div class="card" style="margin-bottom: 20px;">
      <h3 class="text-secondary" style="font-weight: 500; margin-bottom: 14px;">Evaluation Results (on disk)</h3>
      <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 16px;">
        <div>
          <div class="stat-number" style="font-size: 24px;">{stats.platforms_count}</div>
          <div class="stat-label">Platforms Evaluated</div>
        </div>
        <div>
          <div class="stat-number" style="font-size: 24px;">{stats.total_story_runs}</div>
          <div class="stat-label">Story Runs</div>
        </div>
        <div>
          <div class="stat-number" style="font-size: 24px; color: var(--green);">{stats.stories_completed}</div>
          <div class="stat-label">Passed</div>
        </div>
        <div>
          <div class="stat-number" style="font-size: 24px; color: var(--red);">{stats.stories_failed}</div>
          <div class="stat-label">Failed</div>
        </div>
        <div>
          <div class="stat-number" style="font-size: 24px;">{stats.unique_stories}</div>
          <div class="stat-label">Unique Stories</div>
        </div>
      </div>
      <div style="margin-top: 12px; font-size: 12px; color: var(--text-2);">
        Platforms: {stats.platforms_evaluated.join(', ')}
      </div>
      <div style="margin-top: 10px;">
        <button class="btn btn-outline btn-sm" onclick={() => currentPage.set('results-overview')}>View Detailed Results</button>
      </div>
    </div>
  {/if}

  <!-- Session runs -->
  <div style="margin-bottom: 12px;">
    <h3 class="text-secondary" style="font-weight: 500;">Session Runs</h3>
    <div style="font-size: 12px; color: var(--text-2); margin-top: 4px;">
      Runs started during the current server session. These reset on restart.
    </div>
  </div>

  {#if runs.length === 0}
    <div class="card" style="text-align: center; padding: 36px; color: var(--text-2);">
      No runs this session — <button style="color: var(--text-0); background: none; border: none; text-decoration: underline; cursor: pointer; font-family: inherit; font-size: inherit;" onclick={() => currentPage.set('new-run')}>start one</button>
    </div>
  {:else}
    <div class="table-wrap">
      <table>
        <thead><tr><th>Run ID</th><th>Status</th><th>Platforms</th><th style="text-align: right;">Started</th></tr></thead>
        <tbody>
          {#each runs as r}
            <tr style="cursor: pointer;" onclick={() => onViewRun(r.run_id)}>
              <td class="mono" style="font-size: 12px; color: var(--text-1);">{r.run_id}</td>
              <td>
                <StatusBadge status={r.status} />
                {#if r.status === 'running'}<span class="pulse text-muted" style="font-size: 11px; margin-left: 8px;">In Progress</span>{/if}
              </td>
              <td style="font-size: 13px;">{r.config?.platforms?.join(', ')}</td>
              <td class="mono" style="text-align: right; font-size: 12px; color: var(--text-2);">
                {r.started_at ? new Date(r.started_at).toLocaleString() : '—'}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
