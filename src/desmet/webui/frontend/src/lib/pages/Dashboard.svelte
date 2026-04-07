<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchRuns, fetchDashboardStats, dockerUp, dockerDown } from '../api';
  import type { Run, DashboardStats } from '../api';
  import { store, refreshInfra, refreshPlatformStatuses } from '../data.svelte';
  import { currentPage, selectedRunId } from '../stores';
  import type { Page } from '../stores';
  import StatusBadge from '../components/StatusBadge.svelte';

  let runs = $state<Run[]>([]);
  let stats = $state<DashboardStats | null>(null);
  let infraAction = $state<Record<string, 'idle' | 'starting' | 'stopping' | 'success' | 'error'>>({});
  let infraError = $state<Record<string, string>>({});

  let implemented = $derived(store.platforms.filter(p => p.implemented).length);
  let activeRuns = $derived(runs.filter(r => r.status === 'running').length);
  let recentRuns = $derived(runs.slice(-5).reverse());

  let storyStats = $derived.by(() => {
    const byDiff: Record<string, number> = {};
    for (const s of store.stories) {
      byDiff[s.difficulty] = (byDiff[s.difficulty] || 0) + 1;
    }
    return byDiff;
  });

  // Infra health: count running vs total
  let infraUp = $derived(store.infraServices.filter(s => s.status === 'running').length);

  async function handleInfra(action: string, serviceId: string) {
    infraAction = { ...infraAction, [serviceId]: action === 'up' ? 'starting' : 'stopping' };
    infraError = { ...infraError, [serviceId]: '' };
    try {
      const res = action === 'up' ? await dockerUp(serviceId) : await dockerDown(serviceId);
      if (!res.success) {
        infraAction = { ...infraAction, [serviceId]: 'error' };
        infraError = { ...infraError, [serviceId]: res.message || 'Failed' };
      } else {
        infraAction = { ...infraAction, [serviceId]: 'success' };
        setTimeout(() => { infraAction = { ...infraAction, [serviceId]: 'idle' }; }, 3000);
      }
      await Promise.all([refreshInfra(), refreshPlatformStatuses()]);
    } catch (err: any) {
      infraAction = { ...infraAction, [serviceId]: 'error' };
      infraError = { ...infraError, [serviceId]: err?.message || 'Unexpected error' };
    }
  }

  onMount(async () => {
    const [rRes, st] = await Promise.all([
      fetchRuns(),
      fetchDashboardStats(),
    ]);
    runs = rRes.runs ?? [];
    stats = st;
  });

  function viewRun(id: string) {
    selectedRunId.set(id);
    currentPage.set('run-detail');
  }

  function goTo(page: Page) {
    currentPage.set(page);
  }
</script>

<div class="dash">
  <h1 style="margin-bottom: 20px;">Dashboard</h1>

  <!-- ── Stats row ──────────────────────────────────────────── -->
  <div class="stats-row">
    <div class="stat-card">
      <div class="stat-number">{store.platforms.length}</div>
      <div class="stat-label">Platforms</div>
      <div class="stat-sub">{implemented} ready · {stats?.platforms_count || 0} evaluated</div>
    </div>
    <div class="stat-card">
      <div class="stat-number">{store.stories.length}</div>
      <div class="stat-label">Stories</div>
      <div class="stat-sub">
        {#each Object.entries(storyStats) as [diff, count]}
          <span class="stat-diff">
            <span class="diff-dot {diff}"></span>{count}
          </span>
        {/each}
      </div>
    </div>
    <div class="stat-card">
      <div class="stat-number">{stats?.total_story_runs || 0}</div>
      <div class="stat-label">Story Runs</div>
      <div class="stat-sub">
        {#if stats?.stories_completed}<span style="color: var(--green);">{stats.stories_completed} passed</span>{/if}
        {#if stats?.stories_failed}<span style="color: var(--red);">{stats.stories_failed} failed</span>{/if}
        {#if !stats?.total_story_runs}<span>no results yet</span>{/if}
      </div>
    </div>
    <div class="stat-card">
      <div class="stat-number" style="font-size: 18px; padding-top: 6px;">
        {#if store.config}
          <span class="mono">{store.config.model}</span>
        {:else}
          —
        {/if}
      </div>
      <div class="stat-label">Default Model</div>
      <div class="stat-sub" style="text-transform: capitalize;">{store.config?.provider || '—'}</div>
    </div>
  </div>

  <!-- ── Main content: 2 columns ────────────────────────────── -->
  <div class="dash-grid">
    <!-- Left: Platform status table -->
    <div class="card" style="overflow: hidden;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
        <h3 class="text-secondary" style="font-weight: 500;">Platform Status</h3>
        <button class="btn btn-outline btn-sm" onclick={() => goTo('platforms')}>Manage</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Platform</th>
              <th>Category</th>
              <th>Type</th>
              <th style="text-align: center;">Results</th>
              <th style="text-align: right;">Status</th>
            </tr>
          </thead>
          <tbody>
            {#each store.platforms as p}
              <tr style={p.implemented ? '' : 'opacity: 0.45;'}>
                <td style="font-weight: 500;">{p.name}</td>
                <td style="font-size: 12px; color: var(--text-2);">{p.category}</td>
                <td>
                  <span class="badge badge-gray" style="font-size: 10px;">{p.infra_type}</span>
                </td>
                <td style="text-align: center; font-size: 12px; color: var(--text-2);">
                  {#if stats?.platforms_evaluated?.includes(p.id)}
                    <span style="color: var(--green);">&#10003;</span>
                  {:else}
                    —
                  {/if}
                </td>
                <td style="text-align: right;">
                  <StatusBadge status={store.platformStatuses[p.id] || p.status} />
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Right column -->
    <div style="display: flex; flex-direction: column; gap: 16px;">

      <!-- ── System Status (combined card) ──────────────────── -->
      <div class="card system-card">
        <h3 class="text-secondary" style="font-weight: 500; margin-bottom: 14px;">System Status</h3>

        <!-- Provider Keys section -->
        <div class="section-label">Provider Keys</div>
        <div class="status-list">
          {#each ['openrouter', 'openai', 'anthropic', 'google'] as provider}
            <div class="status-row">
              <span class="status-dot {store.config?.api_keys_set?.includes(provider) ? 'dot-on' : 'dot-off'}"></span>
              <span class="status-name">{provider}</span>
              <span class="status-detail {store.config?.api_keys_set?.includes(provider) ? 'detail-ok' : ''}">
                {store.config?.api_keys_set?.includes(provider) ? 'configured' : 'missing'}
              </span>
            </div>
          {/each}
        </div>

        <!-- Divider -->
        <div class="section-divider"></div>

        <!-- Infrastructure section -->
        <div class="section-label">
          Infrastructure
          <span class="section-badge {infraUp === store.infraServices.length && store.infraServices.length > 0 ? 'badge-ok' : infraUp > 0 ? 'badge-partial' : 'badge-off'}">
            {infraUp}/{store.infraServices.length} up
          </span>
        </div>
        <div class="status-list">
          {#each store.infraServices as svc}
            <div class="infra-item">
              <div class="status-row">
                <span class="status-dot {svc.status === 'running' ? 'dot-on' : 'dot-off'}"></span>
                <span class="status-name">{svc.name}</span>
                {#if svc.managed}
                  <span class="infra-btn" style="color: var(--text-2); font-size: 11px;">auto</span>
                {:else if infraAction[svc.id] === 'starting'}
                  <span class="infra-btn infra-btn-busy"><span class="spinner"></span>Starting</span>
                {:else if infraAction[svc.id] === 'stopping'}
                  <span class="infra-btn infra-btn-busy"><span class="spinner"></span>Stopping</span>
                {:else if infraAction[svc.id] === 'success'}
                  <span class="infra-btn" style="color: var(--green);">&#10003;</span>
                {:else if svc.status === 'running'}
                  <button class="infra-btn infra-btn-stop" onclick={() => handleInfra('down', svc.id)}>Stop</button>
                {:else}
                  <button class="infra-btn infra-btn-start" onclick={() => handleInfra('up', svc.id)}>Start</button>
                {/if}
              </div>
              <div class="infra-meta">
                {svc.description}{#if svc.id === 'langfuse' && store.config?.langfuse_status}
                  &nbsp;· keys {store.config.langfuse_status}
                {/if}
              </div>
              {#if infraAction[svc.id] === 'error' && infraError[svc.id]}
                <div class="infra-error">
                  {infraError[svc.id]}
                  <button class="infra-error-dismiss" onclick={() => { infraAction = { ...infraAction, [svc.id]: 'idle' }; infraError = { ...infraError, [svc.id]: '' }; }}>dismiss</button>
                </div>
              {/if}
            </div>
          {/each}
        </div>

      </div>

      <!-- Session runs (in-memory) -->
      <div class="card" style="flex: 1;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <h3 class="text-secondary" style="font-weight: 500;">
            Session Runs
            {#if activeRuns}
              <span class="badge badge-yellow" style="margin-left: 6px;">{activeRuns} active</span>
            {/if}
          </h3>
          <button class="btn btn-outline btn-sm" onclick={() => goTo('run-history')}>History</button>
        </div>
        {#if recentRuns.length}
          <div style="display: flex; flex-direction: column; gap: 6px;">
            {#each recentRuns as r}
              <button class="run-row" onclick={() => viewRun(r.run_id)}>
                <span class="mono" style="font-size: 12px; color: var(--text-1);">{r.run_id}</span>
                <span class="badge badge-{r.status === 'completed' ? 'green' : r.status === 'failed' ? 'red' : r.status === 'running' ? 'yellow' : 'gray'}">
                  {r.status}
                </span>
                <span style="font-size: 11px; color: var(--text-2); margin-left: auto;">
                  {r.started_at ? new Date(r.started_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
                </span>
              </button>
            {/each}
          </div>
        {:else}
          <div style="font-size: 13px; color: var(--text-2); padding: 24px 0; text-align: center;">
            No runs this session — <button style="color: var(--text-0); background: none; border: none; text-decoration: underline; cursor: pointer; font-family: inherit; font-size: inherit;" onclick={() => goTo('new-run')}>start one</button>
          </div>
        {/if}
      </div>

      <!-- Quick actions -->
      <div class="card">
        <h3 class="text-secondary" style="font-weight: 500; margin-bottom: 12px;">Quick Actions</h3>
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
          <button class="btn btn-primary btn-sm" onclick={() => goTo('new-run')}>New Run</button>
          <button class="btn btn-outline btn-sm" onclick={() => goTo('results-overview')}>Results</button>
          <button class="btn btn-outline btn-sm" onclick={() => goTo('scoring')}>Scoring</button>
          <button class="btn btn-outline btn-sm" onclick={() => goTo('stories')}>Stories</button>
        </div>
      </div>
    </div>
  </div>
</div>

<style>
  .dash {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  /* ── Stats row ──────────────────────── */
  .stats-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
  }
  .stat-card {
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px 20px;
  }
  .stat-card .stat-number {
    font-size: 28px;
    font-weight: 600;
    letter-spacing: -0.02em;
  }
  .stat-card .stat-label {
    font-size: 11px;
    color: var(--text-2);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: 2px;
  }
  .stat-sub {
    font-size: 12px;
    color: var(--text-2);
    margin-top: 6px;
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }
  .stat-diff {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .diff-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }
  .diff-dot.basic { background: var(--green); }
  .diff-dot.intermediate { background: var(--yellow); }
  .diff-dot.advanced { background: var(--red); }

  /* ── Main grid ──────────────────────── */
  .dash-grid {
    display: grid;
    grid-template-columns: 1fr 320px;
    gap: 16px;
    align-items: start;
  }
  @media (max-width: 900px) {
    .dash-grid {
      grid-template-columns: 1fr;
    }
  }

  /* ── System Status card ──────────────── */
  .system-card {
    padding-bottom: 16px;
  }
  .section-label {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-2);
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .section-badge {
    font-size: 10px;
    font-weight: 500;
    padding: 1px 6px;
    border-radius: 4px;
    letter-spacing: 0;
    text-transform: none;
  }
  .badge-ok { background: rgba(74, 222, 128, 0.12); color: var(--green); }
  .badge-partial { background: rgba(250, 204, 21, 0.12); color: var(--yellow); }
  .badge-off { background: rgba(255, 255, 255, 0.04); color: var(--text-2); }
  .section-divider {
    height: 1px;
    background: var(--border);
    margin: 12px 0;
  }
  .status-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .status-row {
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 24px;
  }
  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .dot-on { background: var(--green); }
  .dot-off { background: #ef4444; opacity: 0.5; }
  .status-name {
    font-size: 13px;
    text-transform: capitalize;
  }
  .status-detail {
    font-size: 11px;
    color: var(--text-2);
    margin-left: auto;
  }
  .detail-ok {
    color: var(--green);
    opacity: 0.7;
  }

  /* ── Infra items ─────────────────────── */
  .infra-item {
    margin-bottom: 2px;
  }
  .infra-meta {
    font-size: 11px;
    color: var(--text-2);
    opacity: 0.7;
    margin-left: 15px;
    margin-top: 1px;
  }
  .infra-btn {
    margin-left: auto;
    font-size: 11px;
    font-weight: 500;
    background: none;
    border: none;
    padding: 2px 8px;
    border-radius: 4px;
    cursor: pointer;
    font-family: inherit;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    white-space: nowrap;
  }
  .infra-btn-start {
    color: var(--text-1);
    border: 1px solid var(--border);
    transition: border-color 0.12s;
  }
  .infra-btn-start:hover {
    border-color: var(--border-hover);
    color: var(--text-0);
  }
  .infra-btn-stop {
    color: #ef4444;
    border: 1px solid rgba(239,68,68,0.2);
    transition: border-color 0.12s;
  }
  .infra-btn-stop:hover {
    border-color: rgba(239,68,68,0.5);
  }
  .infra-btn-busy {
    color: var(--text-2);
    cursor: default;
    border: none;
    padding: 2px 0;
  }
  .infra-error {
    margin-left: 15px;
    margin-top: 4px;
    padding: 4px 8px;
    border-radius: 4px;
    background: rgba(239,68,68,0.08);
    border: 1px solid rgba(239,68,68,0.2);
    font-size: 11px;
    color: #ef4444;
    max-width: 100%;
    max-height: 160px;
    overflow-y: auto;
    overflow-x: hidden;
    overflow-wrap: break-word;
    word-break: break-word;
    white-space: pre-wrap;
    line-height: 1.5;
  }
  .infra-error-dismiss {
    background: none;
    border: none;
    color: #ef4444;
    text-decoration: underline;
    cursor: pointer;
    font-size: 11px;
    padding: 0;
    margin-left: 6px;
    font-family: inherit;
  }

  /* ── Spinner ─────────────────────────── */
  .spinner {
    display: inline-block;
    width: 10px;
    height: 10px;
    border: 1.5px solid currentColor;
    border-right-color: transparent;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
    vertical-align: middle;
  }

  /* ── Run rows ───────────────────────── */
  .run-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: transparent;
    cursor: pointer;
    transition: border-color 0.12s ease;
    font-family: inherit;
    color: var(--text-0);
    text-align: left;
  }
  .run-row:hover {
    border-color: var(--border-hover);
  }
</style>
