<script lang="ts">
  import StatusBadge from './StatusBadge.svelte';
  import type { Platform } from '../api';

  let { platform, onDockerAction }: {
    platform: Platform;
    onDockerAction: (action: string, target: string) => Promise<{ success: boolean; message?: string }>;
  } = $props();

  let isDocker = $derived(platform.infra_type === 'Docker');
  let isUp = $derived(platform.status === 'running');

  let actionState = $state<'idle' | 'starting' | 'stopping' | 'success' | 'error'>('idle');
  let errorMsg = $state('');

  async function handleAction(action: string) {
    actionState = action === 'up' ? 'starting' : 'stopping';
    errorMsg = '';
    try {
      const res = await onDockerAction(action, platform.id);
      if (res && !res.success) {
        actionState = 'error';
        errorMsg = res.message || `Failed to ${action === 'up' ? 'start' : 'stop'}`;
      } else {
        actionState = 'success';
        setTimeout(() => { if (actionState === 'success') actionState = 'idle'; }, 3000);
      }
    } catch (err: any) {
      actionState = 'error';
      errorMsg = err?.message || 'Unexpected error';
    }
  }

  let busy = $derived(actionState === 'starting' || actionState === 'stopping');
</script>

<div class="card">
  <div style="display: flex; justify-content: space-between; align-items: flex-start;">
    <div>
      <h3 style="margin: 0; font-weight: 500; font-size: 14px;">{platform.name}</h3>
      <p style="margin: 4px 0 0; font-size: 12px; color: var(--text-2);">{platform.category}</p>
    </div>
    <StatusBadge status={platform.status} />
  </div>

  <div style="margin-top: 14px; display: flex; gap: 8px; align-items: center;">
    {#if platform.implemented}
      <span class="badge badge-green">Adapter Ready</span>
    {:else}
      <span class="badge badge-gray">Stub</span>
    {/if}
    <span style="font-size: 11px; color: var(--text-2);">{platform.infra_type}</span>
  </div>

  {#if isDocker}
    <div style="margin-top: 14px; display: flex; gap: 8px; align-items: center;">
      {#if actionState === 'starting'}
        <button class="btn btn-outline btn-sm" disabled style="opacity: 0.7;">
          <span class="spinner"></span> Starting…
        </button>
      {:else if actionState === 'stopping'}
        <button class="btn btn-danger btn-sm" disabled style="opacity: 0.7;">
          <span class="spinner"></span> Stopping…
        </button>
      {:else if !isUp}
        <button class="btn btn-outline btn-sm" onclick={() => handleAction('up')}>
          Start
        </button>
      {:else}
        <button class="btn btn-danger btn-sm" onclick={() => handleAction('down')}>
          Stop
        </button>
      {/if}

      {#if actionState === 'success'}
        <span style="font-size: 12px; color: var(--green);">&#10003; Done</span>
      {/if}
    </div>

    {#if actionState === 'error'}
      <div style="margin-top: 8px; padding: 8px 10px; border-radius: 6px; background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.25); font-size: 12px; color: #ef4444;">
        {errorMsg}
        <button style="background: none; border: none; color: #ef4444; text-decoration: underline; cursor: pointer; font-size: 12px; padding: 0; margin-left: 8px;" onclick={() => { actionState = 'idle'; errorMsg = ''; }}>dismiss</button>
      </div>
    {/if}
  {/if}
</div>

<style>
  .spinner {
    display: inline-block;
    width: 12px;
    height: 12px;
    border: 2px solid currentColor;
    border-right-color: transparent;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
    vertical-align: middle;
    margin-right: 4px;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
