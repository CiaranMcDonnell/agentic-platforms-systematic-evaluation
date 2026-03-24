/**
 * Shared reactive data layer for the DESMET WebUI.
 *
 * Static data (platforms, stories, config) is fetched once on app init.
 * Slow-live data (docker statuses, infra health) loads in the background.
 * Session data (runs, stats) is always fetched fresh by each page.
 */
import {
  fetchPlatforms, fetchStories, fetchConfig,
  fetchPlatformStatuses, fetchInfrastructure,
} from './api';
import type { Platform, Story, AppConfig, InfraService } from './api';

// ── Static stores (fetched once on app init) ──────────────
export let platforms: Platform[] = $state([]);
export let stories: Story[] = $state([]);
export let config: AppConfig | null = $state(null);

// ── Slow-live stores (fetched lazily, updated in background) ──
export let platformStatuses: Record<string, string> = $state({});
export let infraServices: InfraService[] = $state([]);

// ── Loading flags ─────────────────────────────────────────
export let initialized = $state(false);
export let initError: string | null = $state(null);

// ── Init (called once from App.svelte onMount) ───────────
export async function initData(): Promise<void> {
  if (initialized) return;
  try {
    const [pRes, sRes, cfg] = await Promise.all([
      fetchPlatforms(),
      fetchStories(),
      fetchConfig(),
    ]);
    platforms = (pRes as any).platforms || [];
    stories = (sRes as any).stories || [];
    config = cfg;
    initialized = true;

    // Fire-and-forget: slow checks resolve in background
    refreshPlatformStatuses().catch(() => {});
    refreshInfra().catch(() => {});
  } catch (e) {
    initError = e instanceof Error ? e.message : 'Failed to load';
  }
}

// ── Background refreshers ─────────────────────────────────
export async function refreshPlatformStatuses(): Promise<void> {
  const res = await fetchPlatformStatuses();
  platformStatuses = res.statuses;
}

export async function refreshInfra(): Promise<void> {
  const res = await fetchInfrastructure();
  infraServices = res.services || [];
}
