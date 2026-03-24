# Scoring Views Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the 6-dimension rubric scores in Overview (dimension pill row per platform), Comparison (score matrix replacing per-button charts), and Story Detail (dim score sub-row per platform with "Score this" link).

**Architecture:** Backend adds a `get_rubric_dim_averages()` helper (avg of each dim across scored stories per platform), extends the overview endpoint to include per-platform dim averages, and adds a new `/api/dashboard/scoring/matrix` endpoint. Two new Svelte components (`DimScorePills`, `ScoreMatrix`) are used by all three pages. Story Detail already receives `{dim}_score` fields from the backend; only the frontend needs updating there.

**Tech Stack:** Python / FastAPI (`src/desmet/webui/api.py`, `src/desmet/dashboard/data.py`), Svelte 5 with runes, TypeScript. Tooling: `uv` (Python), `bun` (JS — never npm/npx/pnpm).

---

## File Map

| File | Change |
|---|---|
| `src/desmet/dashboard/data.py` | Add `get_rubric_dim_averages()` |
| `src/desmet/webui/api.py` | Extend `/api/dashboard/overview`; add `GET /api/dashboard/scoring/matrix` |
| `tests/test_dashboard_data.py` | New — unit tests for `get_rubric_dim_averages()` |
| `src/desmet/webui/frontend/src/lib/api.ts` | Add `dim_scores` to `OverviewPlatform`; add `ScoringMatrix*` types; add `fetchScoringMatrix()` |
| `src/desmet/webui/frontend/src/lib/components/DimScorePills.svelte` | New shared dim score pill row |
| `src/desmet/webui/frontend/src/lib/components/ScoreMatrix.svelte` | New platform × dimension grid |
| `src/desmet/webui/frontend/src/lib/pages/ResultsOverview.svelte` | Add dim pills sub-row to rankings table |
| `src/desmet/webui/frontend/src/lib/pages/Comparison.svelte` | Add ScoreMatrix above dimension drilldown |
| `src/desmet/webui/frontend/src/lib/pages/StoryDetail.svelte` | Add DimScorePills sub-row + "Score this" link |

---

## Task 1: Backend — rubric dim averages helper + extend overview endpoint

**Files:**
- Modify: `src/desmet/dashboard/data.py`
- Modify: `src/desmet/webui/api.py:560-593`
- Create: `tests/test_dashboard_data.py`

### Context

`data.py` already has `SCORING_DIMENSIONS` and `is_story_scored()`. Story metrics rows store individual dimension scores as `{dim}_score` fields (e.g. `pipeline_completeness_score`). The overview endpoint needs to expose per-platform averages of these 6 scores.

- [ ] **Step 1: Write failing tests for `get_rubric_dim_averages()`**

Create `tests/test_dashboard_data.py`:

```python
"""Unit tests for desmet.dashboard.data helper functions."""

import pytest
from desmet.dashboard.data import get_rubric_dim_averages, SCORING_DIMENSIONS


def _make_data(platform_scored_stories: dict) -> dict:
    """Build a minimal results dict for testing.

    platform_scored_stories: {platform_id: list of {dim: score, scored: bool}}
    """
    platforms = {}
    for pid, stories in platform_scored_stories.items():
        metrics = []
        for s in stories:
            sm: dict = {"story_id": f"story_{len(metrics)}", "scored": s.get("scored", True)}
            for dim in SCORING_DIMENSIONS:
                if dim in s:
                    sm[f"{dim}_score"] = s[dim]
            metrics.append(sm)
        platforms[pid] = {"platform_name": pid, "story_metrics": metrics}
    return {"platforms": platforms}


def test_all_scored_returns_averages():
    data = _make_data({
        "langgraph": [
            {"pipeline_completeness": 3, "tool_integration": 2, "error_recovery": 3,
             "time_efficiency": 2, "autonomy": 3, "trace_quality": 2},
            {"pipeline_completeness": 1, "tool_integration": 2, "error_recovery": 1,
             "time_efficiency": 2, "autonomy": 1, "trace_quality": 2},
        ]
    })
    result = get_rubric_dim_averages(data)
    assert "langgraph" in result
    assert result["langgraph"]["pipeline_completeness"] == 2.0
    assert result["langgraph"]["tool_integration"] == 2.0
    assert result["langgraph"]["autonomy"] == 2.0


def test_unscored_stories_excluded():
    data = _make_data({
        "crewai": [
            {"pipeline_completeness": 3, "scored": True},
            {"pipeline_completeness": 1, "scored": False},  # should be excluded
        ]
    })
    result = get_rubric_dim_averages(data)
    assert result["crewai"]["pipeline_completeness"] == 3.0  # only scored one counts


def test_no_scored_stories_returns_none():
    data = _make_data({
        "flowise": [
            {"pipeline_completeness": 2, "scored": False},
        ]
    })
    result = get_rubric_dim_averages(data)
    assert result["flowise"]["pipeline_completeness"] is None


def test_empty_platforms():
    result = get_rubric_dim_averages({"platforms": {}})
    assert result == {}


def test_all_six_dims_present():
    data = _make_data({
        "test": [
            {dim: 2 for dim in SCORING_DIMENSIONS}
        ]
    })
    result = get_rubric_dim_averages(data)
    for dim in SCORING_DIMENSIONS:
        assert dim in result["test"]
        assert result["test"][dim] == 2.0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_dashboard_data.py -v
```

Expected: `ImportError` or `AttributeError` — `get_rubric_dim_averages` does not exist yet.

- [ ] **Step 3: Implement `get_rubric_dim_averages()` in `data.py`**

Add after the `get_scoring_progress()` function (around line 347):

```python
def get_rubric_dim_averages(
    data: dict[str, Any],
) -> dict[str, dict[str, float | None]]:
    """Per-platform average of each 6-dimension rubric score across scored stories.

    Only scored stories (``sm["scored"] == True``) contribute to the average.
    Returns ``{platform_id: {dimension: avg_or_None}}``.
    None means the platform has no scored stories for that dimension.
    """
    result: dict[str, dict[str, float | None]] = {}
    for pid, pdata in data.get("platforms", {}).items():
        scored = [sm for sm in pdata.get("story_metrics", []) if is_story_scored(sm)]
        avgs: dict[str, float | None] = {}
        for dim in SCORING_DIMENSIONS:
            values = [
                sm[f"{dim}_score"]
                for sm in scored
                if sm.get(f"{dim}_score") is not None
            ]
            avgs[dim] = round(sum(values) / len(values), 2) if values else None
        result[pid] = avgs
    return result
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
uv run pytest tests/test_dashboard_data.py -v
```

Expected: 5/5 passing.

- [ ] **Step 5: Extend `dashboard_overview` endpoint in `api.py`**

In `api.py`, the `dashboard_overview` function imports `get_rubric_dim_averages` from data and adds it to each platform row.

First, add the import in the existing import block at the top of `api.py` (find the `from desmet.dashboard.data import (` block and add `get_rubric_dim_averages`):

```python
from desmet.dashboard.data import (
    CATEGORY_COLOURS,
    SCORING_DIMENSIONS,
    SCORING_RUBRIC,
    get_dimension_scores_df,
    get_platform_colour,
    get_platform_colours,
    get_platform_ids,
    get_platform_summary_df,
    get_rubric_dim_averages,        # ← add this
    get_scoring_progress,
    get_story_metrics_df,
    is_story_scored,
    list_trace_files,
    load_results_raw,
    load_trace,
    save_results,
    update_story_scores,
)
```

Then update the `dashboard_overview` function body — add `dim_avgs` computation and include it in each row:

```python
@app.get("/api/dashboard/overview")
async def dashboard_overview():
    """Overview page data: summary table, scoring progress, colours."""
    data = load_results_raw()
    platform_ids = get_platform_ids(data)

    if not platform_ids:
        return {"has_data": False}

    summary_df = get_platform_summary_df(data)
    progress = get_scoring_progress(data)
    colours = get_platform_colours(platform_ids)
    dim_avgs = get_rubric_dim_averages(data)        # ← new

    summary_rows = []
    for _, row in summary_df.iterrows():
        pid = row["platform_id"]
        scored, total = progress.get(pid, (0, 0))
        summary_rows.append({
            "platform_id": pid,
            "platform_name": row["platform_name"],
            "category": row["category"],
            "overall_score": round(row["overall_score"], 2),
            "stories_total": int(row["stories_total"]),
            "stories_completed": int(row["stories_completed"]),
            "completion_rate": round(row["completion_rate"], 3),
            "scored": scored,
            "total_to_score": total,
            "colour": colours.get(pid, "#666"),
            "dim_scores": dim_avgs.get(pid, {}),    # ← new
        })

    summary_rows.sort(key=lambda r: r["overall_score"], reverse=True)
    return {"has_data": True, "platforms": summary_rows, "category_colours": CATEGORY_COLOURS}
```

- [ ] **Step 6: Run the existing tests to confirm nothing broken**

```bash
uv run pytest tests/ -v --ignore=tests/adapters -x -q 2>&1 | tail -20
```

Expected: all previously-passing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add src/desmet/dashboard/data.py src/desmet/webui/api.py tests/test_dashboard_data.py
git commit -m "feat(dashboard): add rubric dim averages helper + expose in overview endpoint"
```

---

## Task 2: Backend — scoring matrix endpoint

**Files:**
- Modify: `src/desmet/webui/api.py` (add one new route)
- Modify: `tests/test_dashboard_data.py` (add integration test for the endpoint)

### Context

The Comparison page needs per-platform averaged rubric scores in a single call. `get_rubric_dim_averages()` (Task 1) provides the data. This task adds a `GET /api/dashboard/scoring/matrix` route that returns all platforms × 6 dimensions, sorted by total score descending.

- [ ] **Step 1: Write failing integration test**

Add to `tests/test_dashboard_data.py`:

```python
from fastapi.testclient import TestClient
from unittest.mock import patch


def test_scoring_matrix_endpoint_empty():
    """Matrix endpoint returns empty list when no results exist."""
    from desmet.webui.api import app
    client = TestClient(app)
    with patch("desmet.webui.api.load_results_raw", return_value={"platforms": {}}):
        resp = client.get("/api/dashboard/scoring/matrix")
    assert resp.status_code == 200
    body = resp.json()
    assert body["platforms"] == []
    assert "dimensions" in body


def test_scoring_matrix_endpoint_with_data():
    """Matrix endpoint returns correct structure and sorted order."""
    from desmet.dashboard.data import SCORING_DIMENSIONS
    from desmet.webui.api import app
    client = TestClient(app)

    fake_data = _make_data({
        "langgraph": [{dim: 3 for dim in SCORING_DIMENSIONS}],
        "crewai": [{dim: 1 for dim in SCORING_DIMENSIONS}],
    })
    with patch("desmet.webui.api.load_results_raw", return_value=fake_data):
        resp = client.get("/api/dashboard/scoring/matrix")
    assert resp.status_code == 200
    body = resp.json()
    # langgraph has higher total score, should come first
    assert body["platforms"][0]["platform_id"] == "langgraph"
    assert body["platforms"][0]["scores"]["pipeline_completeness"] == 3.0
    assert body["platforms"][0]["scored_count"] == 1
    assert body["dimensions"] == SCORING_DIMENSIONS
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_dashboard_data.py::test_scoring_matrix_endpoint_empty tests/test_dashboard_data.py::test_scoring_matrix_endpoint_with_data -v
```

Expected: FAIL (route does not exist yet).

- [ ] **Step 3: Add the matrix endpoint to `api.py`**

Add after the `scoring_progress` endpoint (around line 776, before the `# ── Story detail endpoint` comment):

```python
@app.get("/api/dashboard/scoring/matrix")
async def scoring_matrix():
    """Platform × 6-dimension rubric average score matrix.

    Returns all platforms sorted by sum of dimension averages (highest first).
    Platforms with no scored stories have None for all dimensions.
    """
    data = load_results_raw()
    pids = get_platform_ids(data)
    if not pids:
        return {"platforms": [], "dimensions": SCORING_DIMENSIONS}

    colours = get_platform_colours(pids)
    avgs = get_rubric_dim_averages(data)

    rows = []
    for pid in pids:
        pdata = data["platforms"][pid]
        scored_count = sum(
            1 for sm in pdata.get("story_metrics", []) if is_story_scored(sm)
        )
        rows.append({
            "platform_id": pid,
            "platform_name": pdata.get("platform_name", pid),
            "colour": colours.get(pid, "#666"),
            "scores": avgs.get(pid, {}),
            "scored_count": scored_count,
        })

    # Sort highest total first (None counts as 0)
    rows.sort(key=lambda r: -sum(v or 0.0 for v in r["scores"].values()))
    return {"platforms": rows, "dimensions": SCORING_DIMENSIONS}
```

- [ ] **Step 4: Run tests — confirm passing**

```bash
uv run pytest tests/test_dashboard_data.py -v
```

Expected: all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/desmet/webui/api.py tests/test_dashboard_data.py
git commit -m "feat(api): add GET /api/dashboard/scoring/matrix endpoint"
```

---

## Task 3: Frontend — API types + DimScorePills component

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/api.ts`
- Create: `src/desmet/webui/frontend/src/lib/components/DimScorePills.svelte`

### Context

`OverviewPlatform` needs a `dim_scores` field. New types `ScoringMatrixPlatform` and `ScoringMatrixData` are needed. `DimScorePills` is a shared component used in Overview and StoryDetail — it renders 6 colored pills (`PC:2 TI:3 …`).

Score color thresholds (same used in all components):
- `null` / no score → `var(--bg-3)` grey, text `var(--text-2)`
- `< 0.5` → `#ef4444` red
- `0.5 – 1.49` → `#f59e0b` amber
- `1.5 – 2.49` → `#84cc16` lime
- `≥ 2.5` → `#22c55e` green

- [ ] **Step 1: Update `api.ts` types and add `fetchScoringMatrix()`**

In `api.ts`, update `OverviewPlatform` to add `dim_scores`:

```typescript
export interface OverviewPlatform {
  platform_id: string;
  platform_name: string;
  category: string;
  overall_score: number;
  stories_total: number;
  stories_completed: number;
  completion_rate: number;
  scored: number;
  total_to_score: number;
  colour: string;
  dim_scores?: Record<string, number | null>;   // ← add this line
}
```

Add new types after `OverviewData`:

```typescript
export interface ScoringMatrixPlatform {
  platform_id: string;
  platform_name: string;
  colour: string;
  scores: Record<string, number | null>;
  scored_count: number;
}

export interface ScoringMatrixData {
  platforms: ScoringMatrixPlatform[];
  dimensions: string[];
}
```

Add `fetchScoringMatrix` function in the `// ── Dashboard / Results` section:

```typescript
export const fetchScoringMatrix = () =>
  request<ScoringMatrixData>('/api/dashboard/scoring/matrix');
```

- [ ] **Step 2: Build frontend to confirm types compile**

```bash
cd src/desmet/webui/frontend && bun run build 2>&1 | tail -20
```

Expected: clean build, no type errors.

- [ ] **Step 3: Create `DimScorePills.svelte`**

Create `src/desmet/webui/frontend/src/lib/components/DimScorePills.svelte`:

```svelte
<script lang="ts">
  /**
   * DimScorePills — compact colored pills for 6 rubric dimension scores.
   *
   * Each pill shows an abbreviated label (PC, TI, ER, TE, AU, TQ) and score.
   * Color encodes the score level: grey=unscored, red=0, amber=1, lime=2, green=3.
   * Tooltip shows the full dimension name and score.
   */

  const DIM_ABBR: Record<string, string> = {
    pipeline_completeness: 'PC',
    tool_integration: 'TI',
    error_recovery: 'ER',
    time_efficiency: 'TE',
    autonomy: 'AU',
    trace_quality: 'TQ',
  };

  const DIM_FULL: Record<string, string> = {
    pipeline_completeness: 'Pipeline Completeness',
    tool_integration: 'Tool Integration',
    error_recovery: 'Error Recovery',
    time_efficiency: 'Time Efficiency',
    autonomy: 'Autonomy',
    trace_quality: 'Trace Quality',
  };

  const ALL_DIMS = Object.keys(DIM_ABBR);

  interface Props {
    /** Map of dimension id → score (0–3 int or float avg, or null if unscored). */
    scores: Record<string, number | null | undefined>;
    /** Subset of dims to show. Defaults to all 6. */
    dims?: string[];
  }

  let { scores, dims = ALL_DIMS }: Props = $props();

  function pillBg(score: number | null | undefined): string {
    if (score === null || score === undefined) return 'var(--bg-3)';
    if (score < 0.5)  return '#ef4444';
    if (score < 1.5)  return '#f59e0b';
    if (score < 2.5)  return '#84cc16';
    return '#22c55e';
  }

  function pillText(score: number | null | undefined): string {
    return (score === null || score === undefined) ? 'var(--text-2)' : '#fff';
  }

  function displayScore(score: number | null | undefined): string {
    if (score === null || score === undefined) return '—';
    // Integer scores (0/1/2/3) → no decimal; averages → 1 dp
    return Number.isInteger(score) ? String(score) : score.toFixed(1);
  }
</script>

<div class="pills">
  {#each dims as dim}
    {@const score = scores?.[dim] ?? null}
    <span
      class="pill"
      style="background:{pillBg(score)};color:{pillText(score)};"
      title="{DIM_FULL[dim] ?? dim}: {displayScore(score)}"
    >
      {DIM_ABBR[dim] ?? dim}:{displayScore(score)}
    </span>
  {/each}
</div>

<style>
  .pills {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
  .pill {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 10px;
    font-family: var(--mono);
    font-weight: 600;
    white-space: nowrap;
    line-height: 1.6;
  }
</style>
```

- [ ] **Step 4: Build to confirm no compile errors**

```bash
cd src/desmet/webui/frontend && bun run build 2>&1 | tail -20
```

Expected: clean build.

- [ ] **Step 5: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/api.ts src/desmet/webui/frontend/src/lib/components/DimScorePills.svelte
git commit -m "feat(webui): add ScoringMatrix types, fetchScoringMatrix, DimScorePills component"
```

---

## Task 4: Frontend — ResultsOverview dim pills sub-row

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/pages/ResultsOverview.svelte`

### Context

The rankings table has rows: `# | Platform | Category | Score | Completion`. After each platform `<tr>`, add a second `<tr>` with `colspan=5` that contains `<DimScorePills scores={p.dim_scores ?? {}} />`. If `p.dim_scores` is empty or all null, show a muted "No scores yet" note instead.

- [ ] **Step 1: Update `ResultsOverview.svelte`**

Replace the full file content:

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchOverview } from '../api';
  import type { OverviewData } from '../api';
  import EChart from '../components/EChart.svelte';
  import DimScorePills from '../components/DimScorePills.svelte';

  let data = $state<OverviewData | null>(null);

  onMount(async () => {
    data = await fetchOverview();
  });

  function hasAnyScore(dimScores: Record<string, number | null | undefined> | undefined): boolean {
    if (!dimScores) return false;
    return Object.values(dimScores).some(v => v !== null && v !== undefined);
  }
</script>

<div>
  <h1 style="margin-bottom: 28px;">Results Overview</h1>

  {#if !data}
    <div class="card" style="padding: 40px; color: var(--text-2); text-align: center;">Loading...</div>
  {:else if !data.has_data}
    <div class="card" style="padding: 48px; color: var(--text-2); text-align: center;">
      No evaluation results yet. Run a benchmark first.
    </div>
  {:else}
    <!-- Scoring progress -->
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin-bottom: 28px;">
      {#each data.platforms || [] as p}
        <div class="card" style="padding: 14px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 13px; font-weight: 500;">{p.platform_name}</span>
            <span class="mono text-muted" style="font-size: 11px;">{p.scored}/{p.total_to_score}</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" style="width: {p.total_to_score ? p.scored / p.total_to_score * 100 : 0}%; background: {p.colour};"></div>
          </div>
        </div>
      {/each}
    </div>

    <!-- Rankings table with dim score sub-rows -->
    <div class="table-wrap" style="margin-bottom: 28px;">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Platform</th>
            <th>Category</th>
            <th style="text-align: right;">Score</th>
            <th style="text-align: right;">Completion</th>
          </tr>
        </thead>
        <tbody>
          {#each data.platforms || [] as p, i}
            <tr>
              <td class="mono" style="font-weight: 600;">{i + 1}</td>
              <td>
                <span style="display: inline-flex; align-items: center; gap: 8px;">
                  <span style="width: 8px; height: 8px; border-radius: 50%; background: {p.colour}; display: inline-block;"></span>
                  {p.platform_name}
                </span>
              </td>
              <td class="text-muted" style="font-size: 12px;">{p.category}</td>
              <td class="mono" style="text-align: right;">{p.overall_score.toFixed(2)}</td>
              <td style="text-align: right;">
                <span style="display: inline-flex; align-items: center; gap: 8px;">
                  <span class="progress-bar" style="width: 64px;">
                    <span class="progress-fill" style="width: {p.completion_rate * 100}%; background: var(--text-0);"></span>
                  </span>
                  <span class="mono text-secondary" style="font-size: 12px;">{(p.completion_rate * 100).toFixed(0)}%</span>
                </span>
              </td>
            </tr>
            <!-- Dimension score sub-row -->
            <tr class="dim-subrow">
              <td colspan="5">
                {#if hasAnyScore(p.dim_scores)}
                  <DimScorePills scores={p.dim_scores ?? {}} />
                {:else}
                  <span class="no-scores">No rubric scores yet</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <!-- Charts -->
    <div class="grid-2" style="margin-bottom: 28px;">
      <EChart endpoint="/api/dashboard/charts/rankings" />
      <EChart endpoint="/api/dashboard/charts/completion" />
    </div>

    <div style="margin-bottom: 28px;">
      <EChart endpoint="/api/dashboard/charts/radar" height={400} />
    </div>

    <EChart endpoint="/api/dashboard/charts/efficiency" />
  {/if}
</div>

<style>
  .dim-subrow td {
    padding: 4px 12px 10px;
    border-top: none;
  }
  .no-scores {
    font-size: 10px;
    color: var(--text-2);
    font-style: italic;
  }
</style>
```

- [ ] **Step 2: Build to confirm no errors**

```bash
cd src/desmet/webui/frontend && bun run build 2>&1 | tail -20
```

Expected: clean build.

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/pages/ResultsOverview.svelte
git commit -m "feat(webui): add rubric dim score pills to ResultsOverview rankings table"
```

---

## Task 5: Frontend — ScoreMatrix component + Comparison update

**Files:**
- Create: `src/desmet/webui/frontend/src/lib/components/ScoreMatrix.svelte`
- Modify: `src/desmet/webui/frontend/src/lib/pages/Comparison.svelte`

### Context

`ScoreMatrix` renders a compact CSS-grid table: platforms as rows, 6 dims as columns, each cell a colored block with the score. The same color logic as `DimScorePills`. `Comparison.svelte` calls `fetchScoringMatrix()` on mount and shows the matrix above the existing dimension drilldown buttons. If no platform has scores yet, show a muted "Score platforms to see the matrix" notice instead of the component.

- [ ] **Step 1: Create `ScoreMatrix.svelte`**

Create `src/desmet/webui/frontend/src/lib/components/ScoreMatrix.svelte`:

```svelte
<script lang="ts">
  /**
   * ScoreMatrix — platform × 6-dimension rubric score grid.
   *
   * Rows = platforms (sorted by total score desc).
   * Cols = 6 rubric dimensions (abbreviated).
   * Cells = colored score value (null = grey "—").
   */
  import type { ScoringMatrixData } from '../api';

  const DIM_ABBR: Record<string, string> = {
    pipeline_completeness: 'PC',
    tool_integration: 'TI',
    error_recovery: 'ER',
    time_efficiency: 'TE',
    autonomy: 'AU',
    trace_quality: 'TQ',
  };

  const DIM_FULL: Record<string, string> = {
    pipeline_completeness: 'Pipeline Completeness',
    tool_integration: 'Tool Integration',
    error_recovery: 'Error Recovery',
    time_efficiency: 'Time Efficiency',
    autonomy: 'Autonomy',
    trace_quality: 'Trace Quality',
  };

  interface Props { matrixData: ScoringMatrixData; }
  let { matrixData }: Props = $props();

  function cellBg(score: number | null | undefined): string {
    if (score === null || score === undefined) return 'var(--bg-2)';
    if (score < 0.5)  return '#ef444430';
    if (score < 1.5)  return '#f59e0b30';
    if (score < 2.5)  return '#84cc1630';
    return '#22c55e30';
  }

  function cellBorder(score: number | null | undefined): string {
    if (score === null || score === undefined) return 'var(--border)';
    if (score < 0.5)  return '#ef4444';
    if (score < 1.5)  return '#f59e0b';
    if (score < 2.5)  return '#84cc16';
    return '#22c55e';
  }

  function cellColor(score: number | null | undefined): string {
    if (score === null || score === undefined) return 'var(--text-2)';
    if (score < 0.5)  return '#ef4444';
    if (score < 1.5)  return '#f59e0b';
    if (score < 2.5)  return '#84cc16';
    return '#22c55e';
  }

  function displayScore(score: number | null | undefined): string {
    if (score === null || score === undefined) return '—';
    return Number.isInteger(score) ? String(score) : score.toFixed(1);
  }
</script>

<div class="matrix-wrap">
  <!-- Column headers -->
  <div class="matrix-grid" style="grid-template-columns: 160px repeat({matrixData.dimensions.length}, 1fr) 60px;">
    <div class="hdr-cell platform-hdr">Platform</div>
    {#each matrixData.dimensions as dim}
      <div class="hdr-cell dim-hdr" title={DIM_FULL[dim] ?? dim}>
        {DIM_ABBR[dim] ?? dim}
      </div>
    {/each}
    <div class="hdr-cell scored-hdr" title="Number of scored stories">Scored</div>
  </div>

  <!-- Platform rows -->
  {#each matrixData.platforms as p}
    <div class="matrix-grid" style="grid-template-columns: 160px repeat({matrixData.dimensions.length}, 1fr) 60px;">
      <!-- Platform name -->
      <div class="platform-cell">
        <span class="dot" style="background:{p.colour};"></span>
        <span class="platform-name" title={p.platform_name}>{p.platform_name}</span>
      </div>
      <!-- Dimension score cells -->
      {#each matrixData.dimensions as dim}
        {@const score = p.scores[dim] ?? null}
        <div
          class="score-cell"
          style="background:{cellBg(score)};border-color:{cellBorder(score)};color:{cellColor(score)};"
          title="{DIM_FULL[dim] ?? dim}: {displayScore(score)}"
        >
          {displayScore(score)}
        </div>
      {/each}
      <!-- Scored count -->
      <div class="scored-cell">{p.scored_count}</div>
    </div>
  {/each}
</div>

<style>
  .matrix-wrap {
    display: flex;
    flex-direction: column;
    gap: 3px;
    font-size: 12px;
  }

  .matrix-grid {
    display: grid;
    gap: 3px;
    align-items: center;
  }

  .hdr-cell {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-2);
    text-align: center;
    padding: 4px 4px 8px;
  }
  .platform-hdr { text-align: left; }

  .platform-cell {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 8px;
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: 4px;
    min-width: 0;
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .platform-name {
    font-size: 12px;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .score-cell {
    padding: 6px 4px;
    border: 1px solid;
    border-radius: 4px;
    text-align: center;
    font-family: var(--mono);
    font-size: 12px;
    font-weight: 600;
    cursor: default;
  }

  .scored-cell {
    text-align: center;
    font-family: var(--mono);
    font-size: 11px;
    color: var(--text-2);
    padding: 6px 4px;
  }
</style>
```

- [ ] **Step 2: Update `Comparison.svelte`**

Replace the full file content:

```svelte
<script lang="ts">
  import EChart from '../components/EChart.svelte';
  import ScoreMatrix from '../components/ScoreMatrix.svelte';
  import { fetchStories, fetchScoringMatrix } from '../api';
  import type { Story, ScoringMatrixData } from '../api';
  import { onMount } from 'svelte';

  let stories = $state<Story[]>([]);
  let loading = $state(true);
  let selectedDimension = $state('pipeline_completeness');
  let matrixData = $state<ScoringMatrixData | null>(null);

  const dimensions = [
    { id: 'pipeline_completeness', label: 'Pipeline Completeness' },
    { id: 'tool_integration', label: 'Tool Integration' },
    { id: 'error_recovery', label: 'Error Recovery' },
    { id: 'time_efficiency', label: 'Time Efficiency' },
    { id: 'autonomy', label: 'Autonomy' },
    { id: 'trace_quality', label: 'Trace Quality' },
  ];

  onMount(async () => {
    const [storiesRes, matrix] = await Promise.all([
      fetchStories(),
      fetchScoringMatrix(),
    ]);
    stories = (storiesRes as any).stories || [];
    matrixData = matrix;
    loading = false;
  });

  let hasMatrixData = $derived(
    matrixData !== null &&
    matrixData.platforms.length > 0 &&
    matrixData.platforms.some(p => Object.values(p.scores).some(v => v !== null))
  );
</script>

<div>
  <h1 style="margin-bottom: 28px;">Platform Comparison</h1>

  {#if loading}
    <div class="card" style="text-align: center; padding: 48px; color: var(--text-2);">Loading comparison data…</div>
  {:else}

  <!-- Radar + rankings side by side -->
  <div class="grid-2" style="margin-bottom: 28px;">
    <EChart endpoint="/api/dashboard/charts/radar" height={380} />
    <EChart endpoint="/api/dashboard/charts/rankings" height={380} />
  </div>

  <!-- Score matrix -->
  <div style="margin-bottom: 28px;">
    <h2 style="font-size: 14px; font-weight: 600; margin-bottom: 12px;">Rubric Score Matrix</h2>
    {#if hasMatrixData && matrixData}
      <ScoreMatrix {matrixData} />
    {:else}
      <div class="card" style="padding: 24px; color: var(--text-2); font-size: 13px; text-align: center;">
        Score platforms in the Scoring tab to populate this matrix.
      </div>
    {/if}
  </div>

  <!-- Per-dimension analysis -->
  <div style="margin-bottom: 28px;">
    <h2 style="font-size: 14px; font-weight: 600; margin-bottom: 12px;">Dimension Drilldown</h2>
    <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 16px;">
      {#each dimensions as dim}
        <button
          class="btn btn-sm"
          class:btn-primary={selectedDimension === dim.id}
          class:btn-outline={selectedDimension !== dim.id}
          onclick={() => selectedDimension = dim.id}
        >
          {dim.label}
        </button>
      {/each}
    </div>
    {#key selectedDimension}
      <EChart endpoint={`/api/dashboard/charts/dimension/${selectedDimension}`} height={350} />
    {/key}
  </div>

  <!-- Efficiency chart -->
  <div style="margin-bottom: 28px;">
    <h2 style="font-size: 14px; font-weight: 600; margin-bottom: 12px;">Efficiency Analysis</h2>
    <EChart endpoint="/api/dashboard/charts/efficiency" height={350} />
  </div>

  <!-- Story-level comparison -->
  {#if stories.length > 0}
    <div>
      <h2 style="font-size: 14px; font-weight: 600; margin-bottom: 12px;">Story Comparison</h2>
      <EChart endpoint="/api/dashboard/charts/story-comparison" height={400} />
    </div>
  {/if}

  {/if}
</div>
```

- [ ] **Step 3: Build**

```bash
cd src/desmet/webui/frontend && bun run build 2>&1 | tail -20
```

Expected: clean build.

- [ ] **Step 4: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/components/ScoreMatrix.svelte src/desmet/webui/frontend/src/lib/pages/Comparison.svelte
git commit -m "feat(webui): add ScoreMatrix component and rubric matrix to Comparison page"
```

---

## Task 6: Frontend — StoryDetail rubric score sub-rows + "Score this" link

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/pages/StoryDetail.svelte`

### Context

The backend `GET /api/dashboard/story/{story_id}` already returns `{dim}_score` fields in each platform row (via `StoryPlatformRow`'s `[key: string]: unknown` catch-all). No backend change needed.

For each platform row:
- If any `{dim}_score` is non-null → show `<DimScorePills>` in a sub-row
- If all `{dim}_score` are null → show "Not scored — " + a button that navigates to the Scoring page

Navigation to Scoring: import `currentPage` and a new `scoringTarget` store (or use `selectedRunId` store as a hack). Simplest approach: add a `scoringHint` writable store in `stores.ts` holding `{platform_id, story_id} | null`, read it in `Scoring.svelte` on mount to pre-select.

Actually, stores approach adds complexity. Simpler: just show "Go to Scoring →" as a styled link button that sets `currentPage` to `'scoring'` — the user can then select manually. This keeps the change minimal.

- [ ] **Step 1: Update `stores.ts` to add a scoring target hint**

In `src/desmet/webui/frontend/src/lib/stores.ts`, add a `scoringTarget` store:

```typescript
import { writable } from 'svelte/store';

export type Page = 'dashboard' | 'platforms' | 'stories' | 'new-run' |
                  'run-history' | 'run-detail' | 'results-overview' |
                  'scoring' | 'comparison' | 'story-detail'

export const currentPage = writable<Page>('dashboard')
export const selectedRunId = writable<string | null>(null)

// Pre-select platform+story when navigating from Story Detail to Scoring
export const scoringTarget = writable<{ platform_id: string; story_id: string } | null>(null)
```

- [ ] **Step 2: Update `Scoring.svelte` to read `scoringTarget` on mount**

In `Scoring.svelte`, import `scoringTarget` and apply it after loading.

> **Note:** `$store` auto-subscription only works in Svelte template markup and reactive contexts. Inside an `onMount` async callback (plain TS scope), use `get(store)` from `svelte/store` to read the current value imperatively.

After the existing `import { fetchPlatforms, ... } from '../api';` block, add:

```typescript
import { get } from 'svelte/store';
import { scoringTarget } from '../stores';
```

At the end of the existing `onMount` async callback, after all data is loaded, add:

```typescript
    // Pre-select from navigation hint (e.g. "Score this" from Story Detail)
    const target = get(scoringTarget);   // get() reads store value imperatively
    if (target) {
      selectedPlatform = target.platform_id;
      selectedStory = target.story_id;
      scoringTarget.set(null);
      await loadScore();
    }
```

The full `onMount` in `Scoring.svelte` becomes:

```typescript
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
    if (rubric) {
      for (const dim of rubric.dimensions) {
        scores[dim] = 0;
        notes[dim] = '';
      }
    }
    // Pre-select from navigation hint (e.g. "Score this" from Story Detail)
    const target = get(scoringTarget);   // get() reads store value imperatively
    if (target) {
      selectedPlatform = target.platform_id;
      selectedStory = target.story_id;
      scoringTarget.set(null);
      await loadScore();
    }
  });
```

- [ ] **Step 3: Update `StoryDetail.svelte`**

Replace the full file content:

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchStories, fetchStoryDetail } from '../api';
  import type { Story, StoryDetailData } from '../api';
  import TraceViewer from '../components/TraceViewer.svelte';
  import EChart from '../components/EChart.svelte';
  import DimScorePills from '../components/DimScorePills.svelte';
  import { currentPage, scoringTarget } from '../stores';

  const SCORING_DIMS = [
    'pipeline_completeness',
    'tool_integration',
    'error_recovery',
    'time_efficiency',
    'autonomy',
    'trace_quality',
  ];

  let stories = $state<Story[]>([]);
  let selectedStory = $state('');
  let detail = $state<StoryDetailData | null>(null);
  let expandedTrace = $state<string | null>(null);

  onMount(async () => {
    const res = await fetchStories();
    stories = (res as any).stories || [];
  });

  async function loadDetail() {
    if (!selectedStory) return;
    expandedTrace = null;
    detail = await fetchStoryDetail(selectedStory);
  }

  function dimScores(platform: Record<string, unknown>): Record<string, number | null> {
    const out: Record<string, number | null> = {};
    for (const dim of SCORING_DIMS) {
      const v = platform[`${dim}_score`];
      out[dim] = (v !== undefined && v !== null) ? Number(v) : null;
    }
    return out;
  }

  function hasAnyDimScore(scores: Record<string, number | null>): boolean {
    return Object.values(scores).some(v => v !== null);
  }

  function goToScoring(platformId: string) {
    scoringTarget.set({ platform_id: platformId, story_id: selectedStory });
    currentPage.set('scoring');
  }
</script>

<div>
  <h1 style="margin-bottom: 28px;">Story Detail</h1>

  <!-- Story selector -->
  <div style="display: grid; grid-template-columns: 1fr auto; gap: 12px; margin-bottom: 28px; max-width: 500px;">
    <div>
      <label class="label" for="detail-story">Story</label>
      <select id="detail-story" class="input" bind:value={selectedStory} onchange={loadDetail}>
        <option value="">Select story…</option>
        {#each stories as s}
          <option value={s.id}>{s.title}</option>
        {/each}
      </select>
    </div>
    <div style="display: flex; align-items: flex-end;">
      <button class="btn btn-primary" onclick={loadDetail} disabled={!selectedStory}>Load</button>
    </div>
  </div>

  {#if detail && detail.platforms.length > 0}
    <!-- Metrics chart for this story -->
    {#key selectedStory}
      <div style="margin-bottom: 28px;">
        <EChart endpoint={`/api/dashboard/charts/story-comparison`} height={300} />
      </div>
    {/key}

    <!-- Platform performance table -->
    <div class="table-wrap" style="margin-bottom: 28px;">
      <table>
        <thead>
          <tr>
            <th>Platform</th>
            <th style="text-align: center;">Success</th>
            <th style="text-align: right;">Wall Clock</th>
            <th style="text-align: right;">Iterations</th>
            <th style="text-align: right;">Tool Calls</th>
            <th style="text-align: center;">Trace</th>
          </tr>
        </thead>
        <tbody>
          {#each detail.platforms as p}
            {@const scores = dimScores(p)}
            {@const scored = hasAnyDimScore(scores)}
            <tr>
              <td>
                <span style="display: inline-flex; align-items: center; gap: 8px;">
                  <span style="width: 8px; height: 8px; border-radius: 50%; background: {p.colour}; display: inline-block;"></span>
                  {p.platform_name}
                </span>
              </td>
              <td style="text-align: center;">
                {#if p.success}
                  <span class="badge badge-green">Pass</span>
                {:else}
                  <span class="badge badge-red">Fail</span>
                {/if}
              </td>
              <td class="mono" style="text-align: right;">{p.wall_clock_seconds?.toFixed(1) ?? '—'}s</td>
              <td class="mono" style="text-align: right;">{p.iterations ?? '—'}</td>
              <td class="mono" style="text-align: right;">{p.tool_calls ?? '—'}</td>
              <td style="text-align: center;">
                {#if detail.traces[p.platform_id]?.messages?.length}
                  <button
                    class="btn btn-outline btn-sm"
                    onclick={() => expandedTrace = expandedTrace === p.platform_id ? null : p.platform_id}
                  >
                    {expandedTrace === p.platform_id ? 'Hide' : 'View'}
                  </button>
                {:else}
                  <span class="text-muted" style="font-size: 11px;">—</span>
                {/if}
              </td>
            </tr>
            <!-- Dim score sub-row -->
            <tr class="dim-subrow">
              <td colspan="6">
                {#if scored}
                  <DimScorePills {scores} />
                {:else}
                  <span class="no-scores">
                    Not scored —
                    <button class="score-link" onclick={() => goToScoring(p.platform_id)}>
                      Score this →
                    </button>
                  </span>
                {/if}
              </td>
            </tr>
            {#if expandedTrace === p.platform_id}
              <tr>
                <td colspan="6" style="padding: 0;">
                  <div style="padding: 12px;">
                    <TraceViewer
                      langfuseTraceId={detail.langfuse_trace_ids?.[p.platform_id]}
                      messages={detail.traces[p.platform_id]?.messages || []}
                    />
                  </div>
                </td>
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>
    </div>
  {:else if detail && detail.platforms.length === 0}
    <div class="card" style="padding: 48px; color: var(--text-2); text-align: center;">
      No evaluation results for this story yet. Run a benchmark that includes it first.
    </div>
  {:else if selectedStory && !detail}
    <div class="card" style="padding: 40px; color: var(--text-2); text-align: center;">Loading…</div>
  {/if}
</div>

<style>
  .dim-subrow td {
    padding: 4px 12px 10px;
    border-top: none;
  }
  .no-scores {
    font-size: 11px;
    color: var(--text-2);
  }
  .score-link {
    background: none;
    border: none;
    cursor: pointer;
    font-size: 11px;
    color: var(--text-1);
    padding: 0;
    font-family: var(--sans);
    text-decoration: underline;
  }
  .score-link:hover { color: var(--text-0); }
</style>
```

- [ ] **Step 4: Build**

```bash
cd src/desmet/webui/frontend && bun run build 2>&1 | tail -20
```

Expected: clean build, no type errors.

- [ ] **Step 5: Run all backend tests**

```bash
uv run pytest tests/ -v --ignore=tests/adapters -x -q 2>&1 | tail -20
```

Expected: all passing.

- [ ] **Step 6: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/stores.ts src/desmet/webui/frontend/src/lib/pages/Scoring.svelte src/desmet/webui/frontend/src/lib/pages/StoryDetail.svelte
git commit -m "feat(webui): add rubric dim score sub-rows and Score-this link to Story Detail"
```

---

## Manual Verification Checklist

After all tasks complete, start the webui and verify:

```bash
uv run python -m desmet.webui.api
# In another terminal:
cd src/desmet/webui/frontend && bun run dev
```

- [ ] **Overview** → Rankings table has a dim pill row under each platform. Platforms with scored stories show colored pills; unscored show "No rubric scores yet".
- [ ] **Comparison** → "Rubric Score Matrix" section appears above the Dimension Drilldown buttons. Platforms with scores show colored cells; empty shows placeholder card.
- [ ] **Story Detail** → Select a story → each platform row has a dim sub-row. Scored platforms show pills; unscored show "Not scored — Score this →". Clicking "Score this →" navigates to Scoring page with that platform + story pre-selected.
- [ ] **Scoring page** → When navigated to via "Score this →", the platform and story dropdowns are pre-populated and the score form loads immediately.
