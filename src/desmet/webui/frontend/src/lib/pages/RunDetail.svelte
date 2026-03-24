<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { fetchRun, cancelRun, connectRunLogs } from '../api';
  import type { Run } from '../api';
  import StatusBadge from '../components/StatusBadge.svelte';
  import LogViewer from '../components/LogViewer.svelte';

  let { runId, onBack }: { runId: string; onBack: () => void } = $props();

  let run = $state<Run | null>(null);
  let logs = $state<string[]>([]);
  let loading = $state(true);
  let error = $state('');
  let ws: WebSocket | null = null;

  onMount(async () => {
    try {
      const data = await fetchRun(runId);
      if ((data as any).error) {
        error = (data as any).error;
      } else {
        run = data;
        logs = data.logs || [];
      }
    } catch (e) {
      error = 'Failed to load run details';
    }
    loading = false;
    ws = connectRunLogs(runId, (line) => {
      logs = [...logs, line];
    });
  });

  onDestroy(() => ws?.close());

  async function handleCancel() {
    await cancelRun(runId);
  }
</script>

<div>
  <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 28px;">
    <button class="btn btn-outline btn-sm" onclick={onBack}>Back</button>
    <h1>Run <span class="mono text-secondary">{runId}</span></h1>
    {#if run}<StatusBadge status={run.status} />{/if}
    {#if run?.status === 'running'}
      <button class="btn btn-danger btn-sm" onclick={handleCancel}>Cancel</button>
    {/if}
  </div>

  {#if loading}
    <div class="card" style="text-align: center; padding: 48px; color: var(--text-2);">Loading run details…</div>
  {:else if error}
    <div class="card" style="text-align: center; padding: 48px; color: var(--red);">{error}</div>
  {:else if run}
    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 24px;">
      <div class="card">
        <div class="stat-label">Platforms</div>
        <div style="margin-top: 6px; font-size: 13px;">{run.config?.platforms?.join(', ')}</div>
      </div>
      <div class="card">
        <div class="stat-label">Stages</div>
        <div style="margin-top: 6px; font-size: 13px;">{run.config?.stages?.length ? run.config.stages.join(', ') : 'all'}</div>
      </div>
      <div class="card">
        <div class="stat-label">Started</div>
        <div class="mono" style="margin-top: 6px; font-size: 13px;">
          {run.started_at ? new Date(run.started_at).toLocaleString() : '—'}
        </div>
      </div>
    </div>

    <LogViewer {logs} />
  {/if}
</div>
