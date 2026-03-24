<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchPlatforms, dockerUp, dockerDown } from '../api';
  import type { Platform } from '../api';
  import PlatformCard from '../components/PlatformCard.svelte';

  let platforms = $state<Platform[]>([]);

  async function load() {
    const res = await fetchPlatforms();
    platforms = (res as any).platforms || [];
  }

  async function onDockerAction(action: string, target: string): Promise<{ success: boolean; message?: string }> {
    try {
      const res: any = action === 'up' ? await dockerUp(target) : await dockerDown(target);
      await load();
      return res || { success: true };
    } catch (err: any) {
      await load();
      return { success: false, message: err?.message || `Failed to ${action === 'up' ? 'start' : 'stop'} ${target}` };
    }
  }

  let loading = $state(true);
  let categories = $derived([...new Set(platforms.map(p => p.category))]);

  onMount(async () => { await load(); loading = false; });
</script>

<div>
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 28px;">
    <h1>Platforms</h1>
    <button class="btn btn-outline" onclick={load}>Refresh</button>
  </div>

  {#if loading}
    <div class="card" style="text-align: center; padding: 48px; color: var(--text-2);">Loading platforms…</div>
  {:else if platforms.length === 0}
    <div class="card" style="text-align: center; padding: 48px; color: var(--text-2);">No platforms configured.</div>
  {:else}
    {#each categories as cat}
      <div style="margin-bottom: 28px;">
        <h2 style="margin-bottom: 12px;">{cat}</h2>
        <div class="grid-3">
          {#each platforms.filter(p => p.category === cat) as platform}
            <PlatformCard {platform} {onDockerAction} />
          {/each}
        </div>
      </div>
    {/each}
  {/if}
</div>
