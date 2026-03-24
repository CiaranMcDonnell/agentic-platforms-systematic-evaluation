# Modular WebUI Data Loading — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-page redundant API fetches with a shared Svelte store-based data layer, splitting slow Docker checks into lazy background requests so pages render instantly.

**Architecture:** New `data.svelte.ts` module owns shared reactive state (platforms, stories, config). App.svelte calls `initData()` once on mount, gating page rendering behind `initialized`. A new `/api/platforms/status` endpoint separates Docker subprocess calls from the fast platform registry. Pages import from stores instead of fetching independently.

**Tech Stack:** Svelte 5 runes (`$state` in `.svelte.ts`), FastAPI, existing `api.ts` request helper

**Spec:** `docs/superpowers/specs/2026-03-24-modular-webui-data-loading-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/desmet/infra.py` | Modify | Add `get_docker_platform_statuses()` returning `dict[str, str]` |
| `src/desmet/webui/api.py` | Modify | Add `GET /api/platforms/status`, rewrite `GET /api/platforms` to be fast |
| `src/desmet/webui/frontend/src/lib/api.ts` | Modify | Add `fetchPlatformStatuses()`, add `res.ok` check to `request()` |
| `src/desmet/webui/frontend/src/lib/data.svelte.ts` | Create | Shared data layer with stores + `initData()` + refreshers |
| `src/desmet/webui/frontend/src/lib/App.svelte` | Modify | Call `initData()`, gate pages behind `{#if initialized}` |
| `src/desmet/webui/frontend/src/lib/pages/Dashboard.svelte` | Modify | Import from stores, remove redundant fetches, update docker handlers |
| `src/desmet/webui/frontend/src/lib/pages/NewRun.svelte` | Modify | Import from stores, keep only `fetchRuns()` |
| `src/desmet/webui/frontend/src/lib/pages/Scoring.svelte` | Modify | Import from stores, keep only `fetchRubric()` |
| `src/desmet/webui/frontend/src/lib/pages/Stories.svelte` | Modify | Import from stores, remove `onMount` fetch |
| `src/desmet/webui/frontend/src/lib/pages/StoryDetail.svelte` | Modify | Import from stores, remove `onMount` fetch |
| `src/desmet/webui/frontend/src/lib/pages/Comparison.svelte` | Modify | Import from stores, keep only `fetchScoringMatrix()` |
| `src/desmet/webui/frontend/src/lib/pages/Platforms.svelte` | Modify | Import from stores, update docker handlers to refresh stores |

---

### Task 1: Backend — Add `get_docker_platform_statuses()` to infra.py

**Files:**
- Modify: `src/desmet/infra.py:135-159`

- [ ] **Step 1: Add the new function**

Add after the existing `get_platform_statuses()` function (keep the old one — it's still used by non-migrated pages until Task 2):

```python
def get_docker_platform_statuses() -> dict[str, str]:
    """Return container status for docker-based platforms only."""
    result: dict[str, str] = {}
    for pid, container in PLATFORM_CONTAINERS.items():
        if container is not None:
            result[pid] = get_container_status(container)
    return result
```

- [ ] **Step 2: Verify import works**

Run: `cd /c/Users/ciara/Documents/GitHub/Personal/DESMET_Agentic_Platforms && uv run python -c "from desmet.infra import get_docker_platform_statuses; print(get_docker_platform_statuses())"`
Expected: dict with keys `flowise`, `langflow`, `dify`, `n8n` and status strings

- [ ] **Step 3: Commit**

```bash
git add src/desmet/infra.py
git commit -m "feat(infra): add get_docker_platform_statuses for lazy status checks"
```

---

### Task 2: Backend — Split `/api/platforms` endpoint

**Files:**
- Modify: `src/desmet/webui/api.py:195-212`

- [ ] **Step 1: Rewrite `GET /api/platforms` to use registry constants (no docker calls)**

Replace the existing `get_platforms()` function:

```python
@app.get("/api/platforms")
async def get_platforms():
    """Return all platforms with registry data (no docker calls)."""
    implemented = set(list_available_platforms())

    platforms = []
    for pid in PLATFORM_PACKAGES:
        name = PLATFORM_NAMES[pid]
        package = PLATFORM_PACKAGES[pid]
        container = PLATFORM_CONTAINERS[pid]

        if package is not None:
            status = "ready" if is_package_importable(package) else "not installed"
            infra_type = "Python SDK"
        else:
            status = "unknown"
            infra_type = "Docker"

        platforms.append({
            "id": pid,
            "name": name,
            "infra_type": infra_type,
            "status": status,
            "implemented": pid in implemented,
            "category": _get_platform_category(pid),
        })

    return {"platforms": platforms}
```

Add the required imports at the top of `api.py` (add to the existing `from desmet.infra import` line). Keep `get_platform_statuses` — it's still used by the `lifespan()` startup function:

```python
from desmet.infra import (
    PLATFORM_PACKAGES,
    PLATFORM_NAMES,
    PLATFORM_CONTAINERS,
    is_package_importable,
    get_docker_platform_statuses,
    compose_down,
    compose_up,
    get_config_status,
    get_infra_statuses,
    get_platform_statuses,  # still used by lifespan()
)
```

- [ ] **Step 2: Add `GET /api/platforms/status` endpoint**

Add after the existing `get_platforms()`:

```python
@app.get("/api/platforms/status")
async def get_platform_statuses_endpoint():
    """Return live container status for docker-based platforms (slow — docker inspect)."""
    return {"statuses": get_docker_platform_statuses()}
```

- [ ] **Step 3: Verify both endpoints work**

Run: `cd /c/Users/ciara/Documents/GitHub/Personal/DESMET_Agentic_Platforms && uv run python -c "
import asyncio
from desmet.webui.api import get_platforms, get_platform_statuses_endpoint
print(asyncio.run(get_platforms()))
print(asyncio.run(get_platform_statuses_endpoint()))
"`
Expected: First prints platform list with `status: 'unknown'` for docker platforms. Second prints `{statuses: {flowise: ..., ...}}`.

- [ ] **Step 4: Commit**

```bash
git add src/desmet/webui/api.py
git commit -m "feat(api): split /api/platforms into fast registry + lazy /api/platforms/status"
```

---

### Task 3: Frontend — Add `fetchPlatformStatuses()` and improve `request()` in api.ts

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/api.ts`

- [ ] **Step 1: Add HTTP error handling to `request()`**

Replace the `request()` function (lines 230-236):

```ts
async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}
```

- [ ] **Step 2: Add `fetchPlatformStatuses()` function**

Add after the existing `fetchPlatforms` (around line 241):

```ts
export const fetchPlatformStatuses = () =>
  request<{ statuses: Record<string, string> }>('/api/platforms/status');
```

- [ ] **Step 3: Verify build**

Run: `cd /c/Users/ciara/Documents/GitHub/Personal/DESMET_Agentic_Platforms/src/desmet/webui/frontend && bun run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/api.ts
git commit -m "feat(api-client): add fetchPlatformStatuses, add res.ok error handling"
```

---

### Task 4: Frontend — Create `data.svelte.ts` shared data layer

**Files:**
- Create: `src/desmet/webui/frontend/src/lib/data.svelte.ts`

- [ ] **Step 1: Create the file**

```ts
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
```

- [ ] **Step 2: Verify build**

Run: `cd /c/Users/ciara/Documents/GitHub/Personal/DESMET_Agentic_Platforms/src/desmet/webui/frontend && bun run build`
Expected: Build succeeds (file compiles with Svelte runes)

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/data.svelte.ts
git commit -m "feat(webui): add shared data layer with stores and lazy loading"
```

---

### Task 5: Frontend — Wire `initData()` in App.svelte with initialized gate

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/App.svelte`

- [ ] **Step 1: Add imports and onMount**

Add to the `<script>` block, after existing imports:

```ts
import { onMount } from 'svelte';
import { initData, initialized, initError } from './data.svelte';

onMount(() => {
  initData();
});
```

- [ ] **Step 2: Gate page rendering behind initialized**

Replace the `<!-- Main content -->` section (lines 84-107) with:

```svelte
  <!-- Main content -->
  <main class="main-content">
    {#if initError}
      <div style="padding: 48px; text-align: center; color: var(--text-2);">
        <p style="color: #ef4444; margin-bottom: 8px;">Failed to load</p>
        <p style="font-size: 13px;">{initError}</p>
      </div>
    {:else if !initialized}
      <div style="padding: 48px; text-align: center; color: var(--text-2);">Loading…</div>
    {:else if page === 'dashboard'}
      <Dashboard />
    {:else if page === 'platforms'}
      <Platforms />
    {:else if page === 'stories'}
      <Stories />
    {:else if page === 'new-run'}
      <NewRun />
    {:else if page === 'run-history'}
      <RunHistory onViewRun={viewRun} />
    {:else if page === 'run-detail' && runId}
      <RunDetail runId={runId} onBack={() => nav('run-history')} />
    {:else if page === 'results-overview'}
      <ResultsOverview />
    {:else if page === 'scoring'}
      <Scoring />
    {:else if page === 'comparison'}
      <Comparison />
    {:else if page === 'story-detail'}
      <StoryDetail />
    {/if}
  </main>
```

- [ ] **Step 3: Verify build**

Run: `cd /c/Users/ciara/Documents/GitHub/Personal/DESMET_Agentic_Platforms/src/desmet/webui/frontend && bun run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/App.svelte
git commit -m "feat(webui): wire initData in App.svelte with initialized gate"
```

---

### Task 6: Frontend — Migrate Dashboard.svelte

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/pages/Dashboard.svelte`

- [ ] **Step 1: Replace imports and local state with store imports**

Replace lines 1-71 (the entire `<script>` block) with:

```ts
<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchRuns, fetchDashboardStats, dockerUp, dockerDown } from '../api';
  import type { Run, DashboardStats } from '../api';
  import {
    platforms, config, stories, infraServices, platformStatuses,
    refreshInfra, refreshPlatformStatuses,
  } from '../data.svelte';
  import { currentPage, selectedRunId } from '../stores';
  import type { Page } from '../stores';
  import StatusBadge from '../components/StatusBadge.svelte';

  let runs = $state<Run[]>([]);
  let stats = $state<DashboardStats | null>(null);
  let infraAction = $state<Record<string, 'idle' | 'starting' | 'stopping' | 'success' | 'error'>>({});
  let infraError = $state<Record<string, string>>({});

  let implemented = $derived(platforms.filter(p => p.implemented).length);
  let activeRuns = $derived(runs.filter(r => r.status === 'running').length);
  let recentRuns = $derived(runs.slice(-5).reverse());

  let storyStats = $derived(() => {
    const byDiff: Record<string, number> = {};
    for (const s of stories) {
      byDiff[s.difficulty] = (byDiff[s.difficulty] || 0) + 1;
    }
    return byDiff;
  });

  let infraUp = $derived(infraServices.filter(s => s.status === 'running').length);

  async function handleInfra(action: string, serviceId: string) {
    infraAction = { ...infraAction, [serviceId]: action === 'up' ? 'starting' : 'stopping' };
    infraError = { ...infraError, [serviceId]: '' };
    try {
      const res: any = action === 'up' ? await dockerUp(serviceId) : await dockerDown(serviceId);
      if (res && !res.success) {
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
    runs = (rRes as any).runs || [];
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
```

- [ ] **Step 2: Update platform status badge rendering**

In the template, the platform status badges (around line 160-161 in the current file) use `p.status`. Update to merge in live docker status:

Find in the platform table `<tbody>`:
```svelte
<td style="text-align: right;">
  <StatusBadge status={p.status} />
</td>
```

Replace with:
```svelte
<td style="text-align: right;">
  <StatusBadge status={platformStatuses[p.id] || p.status} />
</td>
```

- [ ] **Step 3: Verify build and test manually**

Run: `cd /c/Users/ciara/Documents/GitHub/Personal/DESMET_Agentic_Platforms/src/desmet/webui/frontend && bun run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/pages/Dashboard.svelte
git commit -m "refactor(dashboard): use shared data stores, lazy docker status"
```

---

### Task 7: Frontend — Migrate NewRun.svelte

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/pages/NewRun.svelte:1-52`

- [ ] **Step 1: Replace imports and onMount**

Replace lines 1-6:
```ts
<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchPlatforms, fetchStories, fetchConfig, fetchRuns, startRun } from '../api';
  import type { Platform, Story, AppConfig, Run } from '../api';
  import { currentPage, selectedRunId } from '../stores';
  import StatusBadge from '../components/StatusBadge.svelte';
```

With:
```ts
<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchRuns, startRun } from '../api';
  import type { Run } from '../api';
  import { platforms, stories, config } from '../data.svelte';
  import { currentPage, selectedRunId } from '../stores';
  import StatusBadge from '../components/StatusBadge.svelte';
```

Remove the local state declarations for platforms, stories, config (lines 8-10):
```ts
  // DELETE these three lines:
  let platforms = $state<Platform[]>([]);
  let stories = $state<Story[]>([]);
  let config = $state<AppConfig | null>(null);
```

Replace the `onMount` (lines 40-52):
```ts
  onMount(async () => {
    const [pRes, sRes, cfg, runsRes] = await Promise.all([
      fetchPlatforms(),
      fetchStories(),
      fetchConfig(),
      fetchRuns(),
    ]);
    platforms = (pRes as any).platforms || [];
    stories = (sRes as any).stories || [];
    config = cfg;
    const allRuns = (runsRes as any).runs || [];
    recentRuns = allRuns.slice(-5).reverse();
  });
```

With:
```ts
  onMount(async () => {
    const runsRes = await fetchRuns();
    const allRuns = (runsRes as any).runs || [];
    recentRuns = allRuns.slice(-5).reverse();
  });
```

- [ ] **Step 2: Verify build**

Run: `cd /c/Users/ciara/Documents/GitHub/Personal/DESMET_Agentic_Platforms/src/desmet/webui/frontend && bun run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/pages/NewRun.svelte
git commit -m "refactor(new-run): use shared data stores"
```

---

### Task 8: Frontend — Migrate Scoring.svelte

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/pages/Scoring.svelte:1-55`

- [ ] **Step 1: Replace imports and onMount**

Replace lines 1-11:
```ts
<script lang="ts">
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { scoringTarget } from '../stores';
  import {
    fetchPlatforms, fetchStories, fetchRubric, fetchStoryScore, submitScore, fetchConfig,
    fetchLangSmithStatus,
  } from '../api';
  import type { Platform, Story, ScoringRubric, StoryScoreData, AppConfig } from '../api';
  import TraceViewer from '../components/TraceViewer.svelte';
  import LangSmithTraceViewer from '../components/LangSmithTraceViewer.svelte';
```

With:
```ts
<script lang="ts">
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { scoringTarget } from '../stores';
  import {
    fetchRubric, fetchStoryScore, submitScore,
    fetchLangSmithStatus,
  } from '../api';
  import type { ScoringRubric, StoryScoreData } from '../api';
  import { platforms, stories, config as appConfig } from '../data.svelte';
  import TraceViewer from '../components/TraceViewer.svelte';
  import LangSmithTraceViewer from '../components/LangSmithTraceViewer.svelte';
```

Remove local state declarations (lines 13-16):
```ts
  // DELETE these four lines:
  let platforms = $state<Platform[]>([]);
  let stories = $state<Story[]>([]);
  let rubric = $state<ScoringRubric | null>(null);
  let appConfig = $state<AppConfig | null>(null);
```

Keep only:
```ts
  let rubric = $state<ScoringRubric | null>(null);
```

Replace the onMount (lines 29-55):
```ts
  onMount(async () => {
    const [pRes, sRes, rub, cfg] = await Promise.all([
      fetchPlatforms(),
      fetchStories(),
      fetchRubric(),
      fetchConfig(),
    ]);
    platforms = (pRes as any).platforms || [];
    stories = (sRes as any).stories || [];
    rubric = rub;
    appConfig = cfg;
    // init scores
    if (rubric) {
      for (const dim of rubric.dimensions) {
        scores[dim] = 0;
        notes[dim] = '';
      }
    }
    // Pre-select from navigation hint
    const target = get(scoringTarget);
    if (target) {
      selectedPlatform = target.platform_id;
      selectedStory = target.story_id;
      scoringTarget.set(null);
      await loadScore();
    }
  });
```

With:
```ts
  onMount(async () => {
    rubric = await fetchRubric();
    if (rubric) {
      for (const dim of rubric.dimensions) {
        scores[dim] = 0;
        notes[dim] = '';
      }
    }
    const target = get(scoringTarget);
    if (target) {
      selectedPlatform = target.platform_id;
      selectedStory = target.story_id;
      scoringTarget.set(null);
      await loadScore();
    }
  });
```

- [ ] **Step 2: Verify build**

Run: `cd /c/Users/ciara/Documents/GitHub/Personal/DESMET_Agentic_Platforms/src/desmet/webui/frontend && bun run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/pages/Scoring.svelte
git commit -m "refactor(scoring): use shared data stores"
```

---

### Task 9: Frontend — Migrate Stories.svelte and StoryDetail.svelte

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/pages/Stories.svelte:1-59`
- Modify: `src/desmet/webui/frontend/src/lib/pages/StoryDetail.svelte:1-27`

- [ ] **Step 1: Migrate Stories.svelte**

Replace lines 1-4:
```ts
<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchStories } from '../api';
  import type { Story } from '../api';
```

With:
```ts
<script lang="ts">
  import { stories } from '../data.svelte';
```

Remove the local state declaration (line 6):
```ts
  // DELETE:
  let stories = $state<Story[]>([]);
```

Remove the onMount (lines 56-59):
```ts
  // DELETE:
  onMount(async () => {
    const res = await fetchStories();
    stories = (res as any).stories || [];
  });
```

- [ ] **Step 2: Migrate StoryDetail.svelte**

Replace lines 1-4:
```ts
<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchStories, fetchStoryDetail } from '../api';
  import type { Story, StoryDetailData } from '../api';
```

With:
```ts
<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchStoryDetail } from '../api';
  import type { StoryDetailData } from '../api';
  import { stories } from '../data.svelte';
```

Remove the local state (line 19):
```ts
  // DELETE:
  let stories = $state<Story[]>([]);
```

Remove the onMount fetch (lines 24-27):
```ts
  // DELETE:
  onMount(async () => {
    const res = await fetchStories();
    stories = (res as any).stories || [];
  });
```

Note: StoryDetail still needs `onMount` if it does other work — check if the `onMount` only fetched stories. If so, remove `onMount` import too. If StoryDetail has no other `onMount` logic, the import can be removed.

- [ ] **Step 3: Verify build**

Run: `cd /c/Users/ciara/Documents/GitHub/Personal/DESMET_Agentic_Platforms/src/desmet/webui/frontend && bun run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/pages/Stories.svelte src/desmet/webui/frontend/src/lib/pages/StoryDetail.svelte
git commit -m "refactor(stories): use shared data stores"
```

---

### Task 10: Frontend — Migrate Comparison.svelte

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/pages/Comparison.svelte:1-30`

- [ ] **Step 1: Replace imports and onMount**

Replace lines 1-6:
```ts
<script lang="ts">
  import EChart from '../components/EChart.svelte';
  import ScoreMatrix from '../components/ScoreMatrix.svelte';
  import { fetchStories, fetchScoringMatrix } from '../api';
  import type { Story, ScoringMatrixData } from '../api';
  import { onMount } from 'svelte';
```

With:
```ts
<script lang="ts">
  import EChart from '../components/EChart.svelte';
  import ScoreMatrix from '../components/ScoreMatrix.svelte';
  import { fetchScoringMatrix } from '../api';
  import type { ScoringMatrixData } from '../api';
  import { stories } from '../data.svelte';
  import { onMount } from 'svelte';
```

Remove local stories state (line 8):
```ts
  // DELETE:
  let stories = $state<Story[]>([]);
```

Replace the onMount (lines 22-30):
```ts
  onMount(async () => {
    const [storiesRes, matrix] = await Promise.all([
      fetchStories(),
      fetchScoringMatrix(),
    ]);
    stories = (storiesRes as any).stories || [];
    matrixData = matrix;
    loading = false;
  });
```

With:
```ts
  onMount(async () => {
    matrixData = await fetchScoringMatrix();
    loading = false;
  });
```

- [ ] **Step 2: Verify build**

Run: `cd /c/Users/ciara/Documents/GitHub/Personal/DESMET_Agentic_Platforms/src/desmet/webui/frontend && bun run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/pages/Comparison.svelte
git commit -m "refactor(comparison): use shared data stores"
```

---

### Task 11: Frontend — Migrate Platforms.svelte

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/pages/Platforms.svelte:1-28`

- [ ] **Step 1: Replace imports and state**

Replace lines 1-5:
```ts
<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchPlatforms, dockerUp, dockerDown } from '../api';
  import type { Platform } from '../api';
  import PlatformCard from '../components/PlatformCard.svelte';
```

With:
```ts
<script lang="ts">
  import { onMount } from 'svelte';
  import { dockerUp, dockerDown } from '../api';
  import { platforms, platformStatuses, refreshPlatformStatuses } from '../data.svelte';
  import PlatformCard from '../components/PlatformCard.svelte';
```

Remove local platforms state (line 7):
```ts
  // DELETE:
  let platforms = $state<Platform[]>([]);
```

Replace the `load()` function and `onDockerAction` (lines 9-23):
```ts
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
```

With:
```ts
  async function onDockerAction(action: string, target: string): Promise<{ success: boolean; message?: string }> {
    try {
      const res: any = action === 'up' ? await dockerUp(target) : await dockerDown(target);
      await refreshPlatformStatuses();
      return res || { success: true };
    } catch (err: any) {
      await refreshPlatformStatuses().catch(() => {});
      return { success: false, message: err?.message || `Failed to ${action === 'up' ? 'start' : 'stop'} ${target}` };
    }
  }
```

Replace the onMount (line 28):
```ts
  onMount(async () => { await load(); loading = false; });
```

With:
```ts
  onMount(() => { loading = false; });
```

Update the Refresh button (around line 34) to call `refreshPlatformStatuses`:
```svelte
<button class="btn btn-outline" onclick={refreshPlatformStatuses}>Refresh</button>
```

Note: This only refreshes Docker container statuses, not Python SDK install status. SDK statuses are checked once at init via `is_package_importable()` and won't update until the server restarts. This is acceptable — SDK installs require a server restart anyway.

- [ ] **Step 2: Update PlatformCard to use merged status**

The `PlatformCard` component receives `{platform}` as a prop and reads `platform.status`. Since docker platforms now return `status: "unknown"` from the fast endpoint, the card needs to use the live status from `platformStatuses`.

Check if PlatformCard uses the status directly. If it does, the simplest approach is to map platforms before passing to PlatformCard. In the template where platforms are iterated:

```svelte
{#each platforms.filter(p => p.category === cat) as platform}
  <PlatformCard platform={{ ...platform, status: platformStatuses[platform.id] || platform.status }} {onDockerAction} />
{/each}
```

- [ ] **Step 3: Verify build**

Run: `cd /c/Users/ciara/Documents/GitHub/Personal/DESMET_Agentic_Platforms/src/desmet/webui/frontend && bun run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/pages/Platforms.svelte
git commit -m "refactor(platforms): use shared data stores, lazy docker status"
```

---

### Task 12: Verify full build and manual smoke test

**Files:** None (verification only)

- [ ] **Step 1: Full frontend build**

Run: `cd /c/Users/ciara/Documents/GitHub/Personal/DESMET_Agentic_Platforms/src/desmet/webui/frontend && bun run build`
Expected: Build succeeds with no errors

- [ ] **Step 2: Run existing tests**

Run: `cd /c/Users/ciara/Documents/GitHub/Personal/DESMET_Agentic_Platforms && uv run pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 3: Manual smoke test**

Start the webui and verify:
1. Dashboard loads quickly — platform status badges appear as "unknown" then fill in
2. Navigate to New Run — platforms/stories/config are already populated (no flash)
3. Navigate to Stories — stories render instantly
4. Navigate to Platforms — platforms render, docker status fills in lazily
5. Docker up/down from Dashboard updates both infra and platform status badges

Run: `cd /c/Users/ciara/Documents/GitHub/Personal/DESMET_Agentic_Platforms && uv run desmet-webui`

- [ ] **Step 4: Commit any fixes**

If any issues found, fix and commit with descriptive message.
