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
  fetchImageDetails,
} from './api';
import type { Platform, Story, AppConfig, InfraService, ImageDetail } from './api';

// ── Shared reactive store object ─────────────────────────
// Svelte 5 module context: exported $state variables cannot be reassigned,
// so all mutable state is kept in a single reactive object.
export const store = $state({
  // Static (fetched once on app init)
  platforms: [] as Platform[],
  stories: [] as Story[],
  config: null as AppConfig | null,

  // Slow-live (fetched lazily, updated in background)
  platformStatuses: {} as Record<string, string>,
  infraServices: [] as InfraService[],
  imageDetails: {} as Record<string, ImageDetail>,

  // Loading flags
  initialized: false,
  initError: null as string | null,
});

// ── Convenience re-exports for templates ─────────────────
export function getPlatforms(): Platform[] { return store.platforms; }
export function getStories(): Story[] { return store.stories; }
export function getConfig(): AppConfig | null { return store.config; }
export function isInitialized(): boolean { return store.initialized; }
export function getInitError(): string | null { return store.initError; }

// ── Init (called once from App.svelte onMount) ───────────
export async function initData(): Promise<void> {
  if (store.initialized) return;
  try {
    const [pRes, sRes, cfg] = await Promise.all([
      fetchPlatforms(),
      fetchStories(),
      fetchConfig(),
    ]);
    store.platforms = (pRes as any).platforms || [];
    store.stories = (sRes as any).stories || [];
    store.config = cfg;
    store.initialized = true;

    // Fire-and-forget: slow checks resolve in background
    refreshPlatformStatuses().catch(() => {});
    refreshInfra().catch(() => {});
    refreshImageDetails().catch(() => {});
  } catch (e) {
    store.initError = e instanceof Error ? e.message : 'Failed to load';
  }
}

// ── Background refreshers ─────────────────────────────────
export async function refreshPlatformStatuses(): Promise<void> {
  const res = await fetchPlatformStatuses();
  store.platformStatuses = res.statuses;
}

export async function refreshInfra(): Promise<void> {
  const res = await fetchInfrastructure();
  store.infraServices = res.services || [];
}

export async function refreshImageDetails(): Promise<void> {
  const res = await fetchImageDetails();
  store.imageDetails = res;
}
