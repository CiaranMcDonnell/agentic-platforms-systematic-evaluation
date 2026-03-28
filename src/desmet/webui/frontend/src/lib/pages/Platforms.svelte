<script lang="ts">
  import { onMount } from 'svelte';
  import { dockerUp, dockerDown, connectImageBuild } from '../api';
  import type { ImageBuildMessage } from '../api';
  import { store, refreshPlatformStatuses, refreshImageDetails } from '../data.svelte';
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

  async function onBuildImage(platformId: string): Promise<{ success: boolean; message?: string }> {
    return { success: true };
  }

  let buildingAll = $state(false);
  let buildAllResult = $state<string | null>(null);

  function onBuildAll() {
    buildingAll = true;
    buildAllResult = null;

    const ws = connectImageBuild(undefined, (msg: ImageBuildMessage) => {
      if (msg.done && msg.summary) {
        const s = msg.summary;
        const parts: string[] = [];
        if (s.built) parts.push(`${s.built} built`);
        if (s.exists) parts.push(`${s.exists} already exist`);
        if (s.failed) parts.push(`${s.failed} failed`);
        buildAllResult = parts.join(', ') || 'No SDK platforms found';
        buildingAll = false;
        ws.close();
        refreshPlatformStatuses();
        refreshImageDetails();
      }
    });
  }

  let loading = $state(true);
  let categories = $derived([...new Set(store.platforms.map(p => p.category))]);
  let hasUnbuilt = $derived(store.platforms.some(p =>
    (p.infra_type === 'Docker (isolated)' || p.infra_type === 'Python SDK') &&
    (store.platformStatuses[p.id] === 'not built' || p.status === 'not built')
  ));

  onMount(() => { loading = false; });
</script>

<div>
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 28px;">
    <h1>Platforms</h1>
    <div style="display: flex; gap: 8px; align-items: center;">
      {#if hasUnbuilt}
        <button class="btn btn-outline" onclick={onBuildAll} disabled={buildingAll}>
          {#if buildingAll}
            <span style="display: inline-block; width: 12px; height: 12px; border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%; animation: spin 0.6s linear infinite; vertical-align: middle; margin-right: 4px;"></span>
            Building All…
          {:else}
            Build All Images
          {/if}
        </button>
      {/if}
      {#if buildAllResult}
        <span style="font-size: 12px; color: var(--text-2);">{buildAllResult}</span>
      {/if}
      <button class="btn btn-outline" onclick={refreshPlatformStatuses}>Refresh</button>
    </div>
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
            <PlatformCard
              platform={{ ...platform, status: store.platformStatuses[platform.id] || platform.status }}
              imageDetail={store.imageDetails[platform.id]}
              {onDockerAction}
              {onBuildImage}
            />
          {/each}
        </div>
      </div>
    {/each}
  {/if}
</div>
