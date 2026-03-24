# Modular WebUI Data Loading

**Date:** 2026-03-24
**Status:** Draft

## Problem

Every page independently fetches its data on mount via `Promise.all`. There is no shared state — navigating from Dashboard to New Run re-fetches platforms, stories, and config that were already loaded seconds ago. Worse, some endpoints mix fast data (env var reads, YAML) with slow operations (docker subprocess calls, external HTTP) into a single response, so the entire page blocks on the slowest check.

Redundant fetches per page navigation:

| Endpoint | Dashboard | NewRun | Scoring | Platforms | Stories | StoryDetail | Comparison | RunHistory |
|---|---|---|---|---|---|---|---|---|
| `/api/platforms` | x | x | x | x | | | | |
| `/api/config` | x | x | x | | | | | |
| `/api/stories` | x | x | x | | x | x | x | |
| `/api/runs` | x | x | | | | | | x |
| `/api/dashboard/stats` | x | | | | | | | x |
| `/api/infrastructure` | x | | | | | | | |

## Design

### Principle: separate data by volatility

Three tiers:

1. **Static** — changes only on server restart: platform registry, stories, config (model, API keys, stages, difficulty levels). Fetch once on app init, cache in stores.
2. **Slow-live** — changes infrequently but involves expensive checks: docker container status, LangSmith availability, infra health. Fetch lazily in the background, update stores reactively. Never blocks page render.
3. **Fast-live** — changes during a session: runs, dashboard stats, scoring data. Fetch on page mount (no caching — always fresh).

### Backend: split mixed-speed endpoints

**`/api/platforms`** currently calls `get_platform_statuses()` which does `docker inspect` for 4 visual platforms (400-500ms). Split into:

- **`/api/platforms`** — returns registry data only (id, name, category, infra_type, implemented, status). No docker calls. ~5ms. Iterates `PLATFORM_PACKAGES` / `PLATFORM_NAMES` / `PLATFORM_CONTAINERS` directly (not `get_platform_statuses()`). For Python SDK platforms, `status` is `"ready"` or `"not installed"` via `is_package_importable()`. For docker-based platforms, `status` is `"unknown"` (placeholder — the real status comes from `/api/platforms/status`). The `_get_platform_category()` helper and `list_available_platforms()` are still used for `category` and `implemented` fields.
- **`/api/platforms/status`** — returns `{statuses: {[platform_id]: string}}` with live container status for docker-based platforms only. ~400ms. Called lazily by the frontend. The frontend merges these into `platformStatuses` store, which pages use to render status badges.

**`/api/config`** — already fast after removing the LangSmith check. No further changes needed.

**`/api/infrastructure`** currently calls `get_container_status()` per service (200-500ms). Keep as-is since it's only called by Dashboard, but the frontend will call it lazily after the page renders instead of blocking on it.

### Frontend: store-based data layer

New file: **`src/desmet/webui/frontend/src/lib/data.svelte.ts`**

Must use the `.svelte.ts` extension — `$state` runes are only compiled in `.svelte` and `.svelte.ts` files. A plain `.ts` file would fail to compile.

This module owns all shared data. It exposes Svelte 5 reactive state and loading functions. Pages import from `data.svelte` instead of calling `api.ts` directly for shared data.

```ts
// data.svelte.ts — shared data layer

// ── Static stores (fetched once on app init) ──────────────
export let platforms: Platform[] = $state([]);
export let stories: Story[] = $state([]);
export let config: AppConfig | null = $state(null);

// ── Slow-live stores (fetched lazily, updated in background) ──
export let platformStatuses: Record<string, string> = $state({});
export let infraServices: InfraService[] = $state([]);
export let langsmithAvailable: boolean | null = $state(null);

// ── Loading flags ─────────────────────────────────────────
export let initialized = $state(false);
export let initError: string | null = $state(null);

// ── Init (called once from App.svelte onMount) ───────────
export async function initData(): Promise<void> {
  if (initialized) return;  // dedup guard (HMR, double-mount)
  try {
    const [pRes, sRes, cfg] = await Promise.all([
      fetchPlatforms(),       // fast: registry only
      fetchStories(),         // fast: YAML read
      fetchConfig(),          // fast: env vars
    ]);
    platforms = pRes.platforms;
    stories = sRes.stories;
    config = cfg;
    initialized = true;

    // Fire-and-forget: slow checks resolve in background, fail silently
    refreshPlatformStatuses().catch(() => {});
    refreshInfra().catch(() => {});
  } catch (e) {
    initError = e instanceof Error ? e.message : 'Failed to load';
  }
}

// ── Background refreshers ─────────────────────────────────
// When called from docker up/down handlers, await these and
// let errors propagate so the UI can show feedback.
// When called from initData, errors are caught silently.
export async function refreshPlatformStatuses(): Promise<void> {
  const res = await fetchPlatformStatuses();  // new endpoint
  platformStatuses = res.statuses;
}

export async function refreshInfra(): Promise<void> {
  const res = await fetchInfrastructure();
  infraServices = res.services;
}
```

### Page changes

Each page shifts from "fetch everything on mount" to "read from stores + fetch page-specific data".

**Dashboard.svelte:**
```ts
// Before:
onMount(async () => {
  const [pRes, cfg, rRes, sRes, st] = await Promise.all([
    fetchPlatforms(), fetchConfig(), fetchRuns(),
    fetchStories(), fetchDashboardStats(), loadInfra(),
  ]);
  // ...assign all
});

// After:
import { platforms, config, stories, infraServices, platformStatuses,
         refreshInfra, refreshPlatformStatuses } from '../data.svelte';

onMount(async () => {
  // Only fetch session-specific data
  const [rRes, st] = await Promise.all([
    fetchRuns(),
    fetchDashboardStats(),
  ]);
  runs = rRes.runs;
  stats = st;
});

// Docker action handlers must refresh shared stores:
async function handleInfra(action: string, serviceId: string) {
  // ... docker up/down call ...
  // After docker operation completes, refresh both stores (await, show errors):
  await Promise.all([refreshInfra(), refreshPlatformStatuses()]);
}
```

Platform status badges render immediately with platform registry data (name, category, implemented) and show a subtle loading indicator where the status badge goes. When `platformStatuses` resolves, badges update reactively.

**NewRun.svelte:**
```ts
// Before: 4 fetches. After: 1 fetch (runs only)
import { platforms, stories, config } from '../data.svelte';

onMount(async () => {
  const rRes = await fetchRuns();
  runs = rRes.runs;
});
```

**Scoring.svelte:**
```ts
// Before: 4 fetches. After: 1 fetch (rubric only — page-specific)
import { platforms, stories, config } from '../data.svelte';

onMount(async () => {
  rubric = await fetchRubric();
});
```

**Stories.svelte, StoryDetail.svelte:**
```ts
// Before: fetchStories(). After: read from store
import { stories } from '../data.svelte';
// No onMount fetch needed for stories
```

**Comparison.svelte:**
```ts
// Before: fetchStories() + fetchScoringMatrix(). After: 1 fetch
import { stories } from '../data.svelte';

onMount(async () => {
  matrix = await fetchScoringMatrix();
});
```

**Platforms.svelte:**
```ts
// Before: fetchPlatforms() (slow — includes docker status). After: read from store
import { platforms, platformStatuses, refreshPlatformStatuses } from '../data.svelte';
// Platforms render instantly; docker status fills in when ready
// Manual refresh button calls refreshPlatformStatuses()
// Docker up/down handlers: await refreshPlatformStatuses() to show updated status
```

**RunHistory.svelte:**
```ts
// No change needed — only fetches runs + stats (session-specific)
```

### App.svelte initialization

```ts
import { initData, initialized, initError } from '../data.svelte';

onMount(() => {
  initData();  // fast — only static data
});
```

App.svelte gates page rendering behind `initialized`:

```svelte
{#if initError}
  <div class="init-error">Failed to load: {initError}</div>
{:else if !initialized}
  <!-- brief skeleton / spinner while static data loads (<50ms) -->
{:else}
  <!-- render sidebar + current page -->
{/if}
```

This prevents pages from mounting with empty stores. Since `initData` only fetches fast endpoints, the gate resolves in <50ms — no perceptible flash.

### Backend changes summary

| Change | File | Description |
|---|---|---|
| New endpoint | `api.py` | `GET /api/platforms/status` — returns `{statuses: {pid: status_string}}` for docker-based platforms only |
| Modify endpoint | `api.py` | `GET /api/platforms` — remove `get_platform_statuses()` call, use registry data + `list_available_platforms()` only |
| New function | `infra.py` | `get_docker_platform_statuses()` — returns `dict[str, str]` mapping platform_id to container status, only for docker-based platforms (flowise, langflow, dify, n8n) |

### Frontend changes summary

| Change | File | Description |
|---|---|---|
| New file | `data.svelte.ts` | Shared data layer with stores, `initData()`, and background refreshers |
| New function | `api.ts` | `fetchPlatformStatuses()` — calls new `/api/platforms/status` endpoint |
| Modify | `api.ts` | Update `Platform` type — `status` becomes optional (filled by separate fetch) |
| Modify | `App.svelte` | Call `initData()` on mount, gate page rendering behind `initialized` |
| Modify | All 8 page components | Replace per-page fetches with store imports for shared data |

### Data flow

```
App mount
  ├─ initData()                          [parallel, <50ms]
  │   ├─ GET /api/platforms              [registry only, ~5ms]
  │   ├─ GET /api/stories                [YAML read, ~20ms]
  │   └─ GET /api/config                 [env vars, ~5ms]
  │
  ├─ refreshPlatformStatuses()           [fire-and-forget, ~400ms]
  │   └─ GET /api/platforms/status       [docker inspect × 4]
  │
  └─ refreshInfra()                      [fire-and-forget, ~300ms]
      └─ GET /api/infrastructure         [docker inspect × 2]

Page mount (e.g., Dashboard)
  ├─ reads platforms, config, stories from stores (instant)
  └─ fetches session data: runs, stats  [parallel, <30ms]
```

### What stays the same

- `api.ts` request helper — no caching at the HTTP level. Stores are the cache.
- Dashboard chart endpoints — already lazy-loaded per component, not worth batching for this change.
- WebSocket for run logs — unchanged.
- Scoring `loadScore()`, StoryDetail `loadDetail()` — these are user-triggered lazy loads, not page-mount fetches. Stay in the pages.
- `fetchRuns()` and `fetchDashboardStats()` — session-scoped, always fetched fresh. No store.

### Error handling

Error handling is split by context:

- **`initData()`** — catches failures and sets `initError`. App.svelte shows an error state. See the `data.svelte.ts` code above.
- **Background refreshers on init** — fire-and-forget with `.catch(() => {})`. Platform status badges stay in "unknown"/"loading" state. Infrastructure section shows empty until resolved.
- **User-triggered refreshers** (docker up/down handlers) — called with `await`, errors propagate to the handler which shows UI feedback (error toast, inline message, etc.). Users expect feedback when they click a button.
- **`request()` helper** — currently does not check `res.ok`. As a small improvement, add `if (!res.ok) throw new Error(...)` to `api.ts` so that HTTP errors surface as meaningful messages rather than JSON parse failures.

### Migration path

This is a refactor, not a rewrite. Each page can be migrated independently:

1. Create `data.svelte.ts` with stores + `initData()`
2. Wire `initData()` in `App.svelte` with `{#if initialized}` gate
3. Add `GET /api/platforms/status` endpoint
4. Modify `GET /api/platforms` to return registry only (docker platforms get `status: "unknown"`)
5. Migrate pages one at a time (remove redundant fetches, import from stores)
6. Add `fetchPlatformStatuses()` to `api.ts`
7. Update `Platform` type to make `status` optional

Each step is independently deployable. Pages not yet migrated continue working — they just do redundant fetches against the (now faster) endpoints.
