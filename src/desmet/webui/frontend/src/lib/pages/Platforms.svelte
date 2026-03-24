<script lang="ts">
  import { onMount } from 'svelte';
  import { dockerUp, dockerDown } from '../api';
  import { store, refreshPlatformStatuses } from '../data.svelte';
  import PlatformCard from '../components/PlatformCard.svelte';

  async function onDockerAction(action: string, target: string): Promise<{ success: boolean; message?: string }> {
    try {
      const res: any = action === 'up' ? await dockerUp(target) : await dockerDown(target);
      await refreshPlatformStatuses();
      return res || { success: true };
    } catch (err: any) {
      await refreshPlatformStatuses();
      return { success: false, message: err?.message || `Failed to ${action === 'up' ? 'start' : 'stop'} ${target}` };
    }
  }

  let loading = $state(true);
  let categories = $derived([...new Set(store.platforms.map(p => p.category))]);

  onMount(() => { loading = false; });
</script>

<div>
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 28px;">
    <h1>Platforms</h1>
    <button class="btn btn-outline" onclick={refreshPlatformStatuses}>Refresh</button>
  </div>

  {#if loading}
    <div class="card" style="text-align: center; padding: 48px; color: var(--text-2);">Loading platforms…</div>
  {:else if store.platforms.length === 0}
    <div class="card" style="text-align: center; padding: 48px; color: var(--text-2);">No platforms configured.</div>
  {:else}
    {#each categories as cat}
      <div style="margin-bottom: 28px;">
        <h2 style="margin-bottom: 12px;">{cat}</h2>
        <div class="grid-3">
          {#each store.platforms.filter(p => p.category === cat) as platform}
            <PlatformCard platform={{ ...platform, status: store.platformStatuses[platform.id] || platform.status }} {onDockerAction} />
          {/each}
        </div>
      </div>
    {/each}
  {/if}
</div>
