# Observability Multi-View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single Langfuse span-tree view with a 4-tab observability UI (Timeline, Messages, Tools, Spans) so every dimension of a framework run is immediately readable without clicking through nested folders.

**Architecture:** Backend increases content truncation 500→4000 chars. Three new Svelte 5 components (TimelineView, MessageThreadView, ToolsLogView) are imported into a refactored TraceViewer that manages tab state, expand-all state, and span type filters. SpanNode gains a reactive `expandAll` prop so the parent can drive bulk expansion. No new backend endpoints are needed — all data is already returned by `/api/langfuse/traces/{id}`.

**Tech Stack:** Svelte 5 runes (`$state`, `$derived`, `$props`, `$effect`), Python/httpx, CSS custom properties (--bg-1/2/3, --border, --yellow, --green, --red, --text-0/1/2, --mono, --sans)

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Modify | `src/desmet/webui/langfuse_client.py` | Raise `_truncate` limit 500→4000 |
| Modify | `src/desmet/webui/frontend/src/lib/api.ts` | Add `'tool'` to `LangfuseObservation.type` union |
| Create | `src/desmet/webui/frontend/src/lib/components/TimelineView.svelte` | CSS waterfall bar chart |
| Create | `src/desmet/webui/frontend/src/lib/components/MessageThreadView.svelte` | Chronological input/output thread |
| Create | `src/desmet/webui/frontend/src/lib/components/ToolsLogView.svelte` | Flat tool-call table |
| Modify | `src/desmet/webui/frontend/src/lib/components/SpanNode.svelte` | Add `expandAll` prop |
| Modify | `src/desmet/webui/frontend/src/lib/components/TraceViewer.svelte` | 4-tab orchestration, expand-all, filter chips |

---

## Task 1: Backend — increase content fidelity

**Files:**
- Modify: `src/desmet/webui/langfuse_client.py` — find the `_truncate` function (currently near bottom of file)

The current 500-char limit cuts off almost all LLM inputs/outputs, making the Messages view useless. Raise it to 4000.

- [ ] **Step 1: Update `_truncate`**

In `src/desmet/webui/langfuse_client.py`, change:

```python
def _truncate(value: Any, max_len: int = 500) -> str | None:
```
to:
```python
def _truncate(value: Any, max_len: int = 4000) -> str | None:
```

- [ ] **Step 2: Verify import works**

```bash
cd C:\Users\ciara\Documents\GitHub\Personal\DESMET_Agentic_Platforms
uv run python -c "from desmet.webui.langfuse_client import _truncate; print(_truncate('x' * 5000)[-20:])"
```
Expected output ends with `... [truncated]`

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/langfuse_client.py
git commit -m "feat(langfuse): increase observation content limit 500→4000 chars"
```

---

## Task 2: Fix TS type union

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/api.ts:132`

Langfuse returns `type: 'tool'` for tool spans. The current union only covers `'span' | 'generation'`, causing TypeScript to silently treat tool spans as `'span'`.

- [ ] **Step 1: Update the type union**

In `src/desmet/webui/frontend/src/lib/api.ts`, change:

```typescript
  type: 'span' | 'generation';
```
to:
```typescript
  type: 'span' | 'generation' | 'tool';
```

- [ ] **Step 2: Verify no TS errors**

```bash
cd src/desmet/webui/frontend
bun run check
```
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/api.ts
git commit -m "fix(frontend): add 'tool' to LangfuseObservation type union"
```

---

## Task 3: TimelineView component

**Files:**
- Create: `src/desmet/webui/frontend/src/lib/components/TimelineView.svelte`

Renders a CSS waterfall chart. Each observation is a horizontal bar:
- Position: `left = (obs_start_relative / total_ms) * 100%`
- Width: `width = (obs.latency_ms / total_ms) * 100%` (min 0.5%)
- Color: blue=LLM, amber=tool, gray=chain/span, red=error

The "relative start" is `parseMs(obs.start_time) - traceStartMs` where `traceStartMs` is `min(all obs start_times)`.

- [ ] **Step 1: Create `TimelineView.svelte`**

```svelte
<script lang="ts">
  import type { LangfuseTraceDetail, LangfuseObservation } from '../api';

  interface Props { traceData: LangfuseTraceDetail; }
  let { traceData }: Props = $props();

  interface FlatSpan {
    id: string;
    name: string;
    type: string;
    level: string;
    start_rel_ms: number;
    duration_ms: number;
    tokens_total: number;
    model: string | null | undefined;
  }

  function parseMs(s: string | null | undefined): number {
    if (!s) return 0;
    return new Date(s).getTime();
  }

  function flatten(obs: LangfuseObservation[], originMs: number): FlatSpan[] {
    const out: FlatSpan[] = [];
    for (const o of obs) {
      out.push({
        id: o.id,
        name: o.name || 'unnamed',
        type: o.type,
        level: o.level,
        start_rel_ms: Math.max(0, parseMs(o.start_time) - originMs),
        duration_ms: o.latency_ms,
        tokens_total: o.tokens.total,
        model: o.model,
      });
      out.push(...flatten(o.children, originMs));
    }
    return out;
  }

  function findOrigin(obs: LangfuseObservation[]): number {
    let min = Infinity;
    for (const o of obs) {
      const t = parseMs(o.start_time);
      if (t > 0 && t < min) min = t;
      const childMin = findOrigin(o.children);
      if (childMin < min) min = childMin;
    }
    return min === Infinity ? 0 : min;
  }

  let origin = $derived(findOrigin(traceData.observations) || parseMs(traceData.trace.timestamp));
  let totalMs = $derived(Math.max(traceData.trace.latency_ms, 1));
  let spans = $derived(
    flatten(traceData.observations, origin).sort((a, b) => a.start_rel_ms - b.start_rel_ms)
  );

  function barColor(type: string, level: string): string {
    if (level === 'ERROR') return 'var(--red)';
    if (type === 'generation') return '#4a9eff';
    if (type === 'tool') return 'var(--yellow)';
    return '#555';
  }

  function leftPct(rel: number): string {
    return ((rel / totalMs) * 100).toFixed(2) + '%';
  }
  function widthPct(dur: number): string {
    return Math.max(0.5, (dur / totalMs) * 100).toFixed(2) + '%';
  }
</script>

<div class="tl-wrap">
  <!-- Axis labels -->
  <div class="tl-axis">
    <span>0</span>
    <span>{(totalMs / 2 / 1000).toFixed(1)}s</span>
    <span>{(totalMs / 1000).toFixed(1)}s</span>
  </div>

  <!-- Gridlines overlay -->
  <div class="tl-grid">
    <div class="grid-line" style="left:0%"></div>
    <div class="grid-line" style="left:25%"></div>
    <div class="grid-line" style="left:50%"></div>
    <div class="grid-line" style="left:75%"></div>
    <div class="grid-line" style="left:100%"></div>
  </div>

  <!-- Span rows -->
  <div class="tl-rows">
    {#each spans as s (s.id)}
      <div class="tl-row">
        <div class="tl-label" title={s.name}>{s.name}</div>
        <div class="tl-track">
          <div
            class="tl-bar"
            style="left:{leftPct(s.start_rel_ms)};width:{widthPct(s.duration_ms)};background:{barColor(s.type, s.level)}"
            title="{s.name} | {(s.duration_ms/1000).toFixed(3)}s{s.tokens_total ? ' | ' + s.tokens_total + ' tok' : ''}{s.model ? ' | ' + s.model : ''}"
          ></div>
        </div>
        <div class="tl-dur">{(s.duration_ms/1000).toFixed(2)}s</div>
      </div>
    {/each}
  </div>

  <!-- Legend -->
  <div class="tl-legend">
    <span class="leg"><span class="leg-dot" style="background:#4a9eff"></span>LLM</span>
    <span class="leg"><span class="leg-dot" style="background:var(--yellow)"></span>Tool</span>
    <span class="leg"><span class="leg-dot" style="background:#555"></span>Chain</span>
    <span class="leg"><span class="leg-dot" style="background:var(--red)"></span>Error</span>
  </div>
</div>

<style>
  .tl-wrap { font-size: 12px; font-family: var(--sans); }

  .tl-axis {
    display: flex;
    justify-content: space-between;
    color: var(--text-2);
    font-size: 10px;
    font-family: var(--mono);
    margin-bottom: 4px;
    padding: 0 100px 0 140px;
  }

  .tl-grid {
    position: relative;
    height: 0;
    pointer-events: none;
    margin: 0 100px 0 140px;
  }
  .grid-line {
    position: absolute;
    top: 0;
    height: 9999px;
    width: 1px;
    background: var(--border);
    opacity: 0.4;
    transform: translateX(-50%);
  }

  .tl-rows { display: flex; flex-direction: column; gap: 3px; }

  .tl-row {
    display: flex;
    align-items: center;
    gap: 8px;
    height: 22px;
  }
  .tl-label {
    width: 132px;
    flex-shrink: 0;
    color: var(--text-1);
    font-size: 11px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    text-align: right;
    padding-right: 8px;
  }
  .tl-track {
    flex: 1;
    height: 14px;
    background: var(--bg-3);
    border-radius: 3px;
    position: relative;
    overflow: hidden;
  }
  .tl-bar {
    position: absolute;
    top: 0;
    height: 100%;
    border-radius: 3px;
    opacity: 0.8;
    transition: opacity 0.1s;
    cursor: default;
  }
  .tl-bar:hover { opacity: 1; }
  .tl-dur {
    width: 44px;
    flex-shrink: 0;
    font-family: var(--mono);
    font-size: 10px;
    color: var(--text-2);
    text-align: right;
  }

  .tl-legend {
    display: flex;
    gap: 16px;
    margin-top: 10px;
    padding-top: 8px;
    border-top: 1px solid var(--border);
    font-size: 11px;
    color: var(--text-2);
  }
  .leg { display: flex; align-items: center; gap: 5px; }
  .leg-dot { width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; }
</style>
```

- [ ] **Step 2: Verify it renders (no build errors)**

```bash
cd src/desmet/webui/frontend
bun run check
```
Expected: no errors related to `TimelineView.svelte`.

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/components/TimelineView.svelte
git commit -m "feat(frontend): add TimelineView waterfall chart component"
```

---

## Task 4: MessageThreadView component

**Files:**
- Create: `src/desmet/webui/frontend/src/lib/components/MessageThreadView.svelte`

Flattens ALL observations sorted by `start_time` and renders each with its `input` and `output` in a readable card layout. Each card is color-coded by type (LLM=blue, tool=amber, chain=gray). Input/output are shown as pre-formatted text, not truncated by default (the 4000-char backend limit is the only cap). Cards are collapsed by default — click header to expand.

- [ ] **Step 1: Create `MessageThreadView.svelte`**

```svelte
<script lang="ts">
  import type { LangfuseTraceDetail, LangfuseObservation } from '../api';

  interface Props { traceData: LangfuseTraceDetail; }
  let { traceData }: Props = $props();

  interface FlatMsg {
    id: string;
    name: string;
    type: string;
    level: string;
    start_time: string | null;
    input: string | null | undefined;
    output: string | null | undefined;
    tokens: { input: number; output: number; total: number };
    model: string | null | undefined;
    duration_ms: number;
  }

  function flatten(obs: LangfuseObservation[]): FlatMsg[] {
    const out: FlatMsg[] = [];
    for (const o of obs) {
      if (o.input || o.output) {
        out.push({
          id: o.id,
          name: o.name || 'unnamed',
          type: o.type,
          level: o.level,
          start_time: o.start_time,
          input: o.input,
          output: o.output,
          tokens: o.tokens,
          model: o.model,
          duration_ms: o.latency_ms,
        });
      }
      out.push(...flatten(o.children));
    }
    return out.sort((a, b) => (a.start_time ?? '') < (b.start_time ?? '') ? -1 : 1);
  }

  let msgs = $derived(flatten(traceData.observations));

  // Track which cards are expanded (all collapsed by default)
  let expanded = $state<Set<string>>(new Set());
  function toggle(id: string) {
    const next = new Set(expanded);
    if (next.has(id)) next.delete(id); else next.add(id);
    expanded = next;
  }
  function expandAll() { expanded = new Set(msgs.map(m => m.id)); }
  function collapseAll() { expanded = new Set(); }

  function accentColor(type: string, level: string): string {
    if (level === 'ERROR') return 'var(--red)';
    if (type === 'generation') return '#4a9eff';
    if (type === 'tool') return 'var(--yellow)';
    return 'var(--border)';
  }

  function typeLabel(type: string): string {
    if (type === 'generation') return 'LLM';
    if (type === 'tool') return 'TOOL';
    return type.toUpperCase();
  }
</script>

<div class="mt-wrap">
  <div class="mt-controls">
    <button class="ctrl-btn" onclick={expandAll}>Expand all</button>
    <button class="ctrl-btn" onclick={collapseAll}>Collapse all</button>
    <span class="mt-count">{msgs.length} observations</span>
  </div>

  {#each msgs as msg, i (msg.id)}
    {@const isOpen = expanded.has(msg.id)}
    {@const accent = accentColor(msg.type, msg.level)}
    <div class="mt-card" style="border-left-color:{accent}">
      <button class="mt-header" onclick={() => toggle(msg.id)}>
        <span class="mt-idx">#{i + 1}</span>
        <span class="mt-badge" style="color:{accent}">{typeLabel(msg.type)}</span>
        <span class="mt-name">{msg.name}</span>
        {#if msg.model}
          <span class="mt-model">{msg.model}</span>
        {/if}
        {#if msg.tokens.total > 0}
          <span class="mt-tok">{msg.tokens.input}↑ {msg.tokens.output}↓</span>
        {/if}
        <span class="mt-dur">{(msg.duration_ms / 1000).toFixed(2)}s</span>
        <span class="mt-chevron">{isOpen ? '▼' : '▶'}</span>
      </button>

      {#if isOpen}
        <div class="mt-body">
          {#if msg.input}
            <div class="io-section">
              <div class="io-label">INPUT</div>
              <pre class="io-pre">{msg.input}</pre>
            </div>
          {/if}
          {#if msg.output}
            <div class="io-section">
              <div class="io-label">OUTPUT</div>
              <pre class="io-pre output">{msg.output}</pre>
            </div>
          {/if}
        </div>
      {/if}
    </div>
  {/each}

  {#if msgs.length === 0}
    <div class="mt-empty">No observations with content found.</div>
  {/if}
</div>

<style>
  .mt-wrap { display: flex; flex-direction: column; gap: 4px; }

  .mt-controls {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }
  .ctrl-btn {
    padding: 4px 10px;
    font-size: 11px;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--bg-2);
    color: var(--text-1);
    cursor: pointer;
    font-family: var(--sans);
  }
  .ctrl-btn:hover { border-color: var(--border-hover); color: var(--text-0); }
  .mt-count { font-size: 11px; color: var(--text-2); margin-left: auto; }

  .mt-card {
    border: 1px solid var(--border);
    border-left-width: 3px;
    border-radius: 6px;
    overflow: hidden;
    background: var(--bg-1);
  }

  .mt-header {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 8px 12px;
    background: transparent;
    border: none;
    cursor: pointer;
    font-size: 12px;
    font-family: var(--sans);
    color: var(--text-1);
    text-align: left;
  }
  .mt-header:hover { background: var(--bg-2); }

  .mt-idx { font-size: 10px; color: var(--text-2); font-family: var(--mono); width: 24px; flex-shrink: 0; }
  .mt-badge { font-size: 10px; font-weight: 600; letter-spacing: 0.06em; flex-shrink: 0; width: 44px; }
  .mt-name { font-weight: 500; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .mt-model { font-size: 10px; color: var(--green); font-family: var(--mono); flex-shrink: 0; }
  .mt-tok { font-size: 10px; color: var(--yellow); font-family: var(--mono); flex-shrink: 0; }
  .mt-dur { font-size: 10px; color: var(--text-2); font-family: var(--mono); flex-shrink: 0; }
  .mt-chevron { font-size: 9px; color: var(--text-2); flex-shrink: 0; }

  .mt-body { border-top: 1px solid var(--border); }

  .io-section { padding: 10px 14px; }
  .io-section + .io-section { border-top: 1px solid var(--border); }
  .io-label {
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.08em;
    color: var(--text-2);
    margin-bottom: 6px;
  }
  .io-pre {
    margin: 0;
    font-size: 12px;
    font-family: var(--mono);
    white-space: pre-wrap;
    word-break: break-word;
    color: var(--text-1);
    line-height: 1.5;
    max-height: 400px;
    overflow-y: auto;
    background: var(--bg-2);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 8px 10px;
  }
  .io-pre.output { border-color: #4a9eff44; }

  .mt-empty { padding: 24px; text-align: center; font-size: 13px; color: var(--text-2); }
</style>
```

- [ ] **Step 2: Check build**

```bash
cd src/desmet/webui/frontend && bun run check
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/components/MessageThreadView.svelte
git commit -m "feat(frontend): add MessageThreadView chronological observation thread"
```

---

## Task 5: ToolsLogView component

**Files:**
- Create: `src/desmet/webui/frontend/src/lib/components/ToolsLogView.svelte`

Flattens all observations, keeps only `type === 'tool'`, renders them as a sortable flat table with expandable rows for full input/output. If there are no tool observations, falls back to showing any non-generation, non-root spans that have input/output (catches tool spans that Langfuse may report as `type: 'span'` with a tool-like name).

- [ ] **Step 1: Create `ToolsLogView.svelte`**

```svelte
<script lang="ts">
  import type { LangfuseTraceDetail, LangfuseObservation } from '../api';

  interface Props { traceData: LangfuseTraceDetail; }
  let { traceData }: Props = $props();

  interface ToolRow {
    id: string;
    seq: number;
    name: string;
    input: string | null | undefined;
    output: string | null | undefined;
    duration_ms: number;
    level: string;
    start_time: string | null;
  }

  function flatten(obs: LangfuseObservation[]): Omit<ToolRow, 'seq'>[] {
    const out: Omit<ToolRow, 'seq'>[] = [];
    for (const o of obs) {
      if (o.type === 'tool' || (o.type === 'span' && o.children.length === 0 && (o.input || o.output))) {
        out.push({
          id: o.id,
          name: o.name || 'unnamed',
          input: o.input,
          output: o.output,
          duration_ms: o.latency_ms,
          level: o.level,
          start_time: o.start_time,
        });
      }
      out.push(...flatten(o.children));
    }
    return out;
  }

  // Sort by start_time first, then assign seq so displayed # matches row order.
  let tools = $derived(
    flatten(traceData.observations)
      .sort((a, b) => (a.start_time ?? '') < (b.start_time ?? '') ? -1 : 1)
      .map((row, i): ToolRow => ({ ...row, seq: i + 1 }))
  );

  let expanded = $state<Set<string>>(new Set());
  function toggle(id: string) {
    const next = new Set(expanded);
    if (next.has(id)) next.delete(id); else next.add(id);
    expanded = next;
  }
</script>

<div class="tl-wrap">
  {#if tools.length === 0}
    <div class="tl-empty">No tool calls found in this trace.</div>
  {:else}
    <div class="tl-count">{tools.length} tool call{tools.length !== 1 ? 's' : ''}</div>
    <div class="tl-table">
      <div class="tl-thead">
        <span class="col-seq">#</span>
        <span class="col-name">Tool</span>
        <span class="col-input">Input</span>
        <span class="col-output">Output</span>
        <span class="col-dur">Duration</span>
        <span class="col-status">Status</span>
      </div>
      {#each tools as row (row.id)}
        {@const isOpen = expanded.has(row.id)}
        {@const isErr = row.level === 'ERROR'}
        <div class="tl-row-wrap" class:err={isErr}>
          <button class="tl-row" onclick={() => toggle(row.id)}>
            <span class="col-seq">{row.seq}</span>
            <span class="col-name" title={row.name}>{row.name}</span>
            <span class="col-input cell-pre">{row.input ? row.input.slice(0, 80) + (row.input.length > 80 ? '…' : '') : '—'}</span>
            <span class="col-output cell-pre">{row.output ? row.output.slice(0, 80) + (row.output.length > 80 ? '…' : '') : '—'}</span>
            <span class="col-dur">{(row.duration_ms / 1000).toFixed(3)}s</span>
            <span class="col-status" class:err-text={isErr}>{isErr ? 'ERROR' : 'OK'}</span>
          </button>
          {#if isOpen}
            <div class="tl-expand">
              {#if row.input}
                <div class="exp-block">
                  <div class="exp-label">INPUT</div>
                  <pre class="exp-pre">{row.input}</pre>
                </div>
              {/if}
              {#if row.output}
                <div class="exp-block">
                  <div class="exp-label">OUTPUT</div>
                  <pre class="exp-pre">{row.output}</pre>
                </div>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .tl-wrap { font-size: 12px; }
  .tl-empty { padding: 24px; text-align: center; color: var(--text-2); }
  .tl-count { font-size: 11px; color: var(--text-2); margin-bottom: 8px; }

  .tl-table { display: flex; flex-direction: column; gap: 2px; }

  .tl-thead {
    display: grid;
    grid-template-columns: 28px 140px 1fr 1fr 64px 52px;
    gap: 8px;
    padding: 4px 10px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.06em;
    color: var(--text-2);
    text-transform: uppercase;
    border-bottom: 1px solid var(--border);
    margin-bottom: 2px;
  }

  .tl-row-wrap {
    border: 1px solid var(--border);
    border-radius: 5px;
    overflow: hidden;
    background: var(--bg-1);
  }
  .tl-row-wrap.err { border-color: var(--red); }

  .tl-row {
    display: grid;
    grid-template-columns: 28px 140px 1fr 1fr 64px 52px;
    gap: 8px;
    padding: 7px 10px;
    width: 100%;
    border: none;
    background: transparent;
    cursor: pointer;
    font-size: 12px;
    font-family: var(--sans);
    color: var(--text-1);
    text-align: left;
    align-items: center;
  }
  .tl-row:hover { background: var(--bg-2); }

  .col-seq { color: var(--text-2); font-family: var(--mono); font-size: 10px; }
  .col-name { font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .cell-pre { font-family: var(--mono); font-size: 11px; color: var(--text-2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .col-dur { font-family: var(--mono); font-size: 11px; color: var(--text-2); text-align: right; }
  .col-status { font-size: 10px; font-weight: 600; color: var(--green); text-align: center; }
  .err-text { color: var(--red) !important; }

  .tl-expand { border-top: 1px solid var(--border); padding: 10px 12px; display: flex; flex-direction: column; gap: 8px; }
  .exp-block {}
  .exp-label { font-size: 9px; font-weight: 600; letter-spacing: 0.08em; color: var(--text-2); margin-bottom: 4px; }
  .exp-pre {
    margin: 0;
    font-size: 12px;
    font-family: var(--mono);
    white-space: pre-wrap;
    word-break: break-word;
    color: var(--text-1);
    line-height: 1.5;
    max-height: 300px;
    overflow-y: auto;
    background: var(--bg-2);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 8px 10px;
  }
</style>
```

- [ ] **Step 2: Check build**

```bash
cd src/desmet/webui/frontend && bun run check
```

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/components/ToolsLogView.svelte
git commit -m "feat(frontend): add ToolsLogView flat tool-call table"
```

---

## Task 6: SpanNode — add expandAll prop

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/components/SpanNode.svelte`

Add an `expandAll: boolean = false` prop. When `expandAll` is `true`, force `expanded = true`. Use `$effect` so it reacts when the prop changes at runtime (e.g. user clicks "Expand All" in TraceViewer).

- [ ] **Step 1: Update the Props interface and add `$effect`**

In `SpanNode.svelte`, change the Props block and initial effects from:

```svelte
  interface Props {
    observation: LangfuseObservation;
    rootLatency: number;
    depth?: number;
  }

  let { observation, rootLatency, depth = 0 }: Props = $props();
  let expanded = $state(false);
  $effect(() => { expanded = depth < 2; });
```

to:

```svelte
  interface Props {
    observation: LangfuseObservation;
    rootLatency: number;
    depth?: number;
    expandAll?: boolean;
  }

  let { observation, rootLatency, depth = 0, expandAll = false }: Props = $props();
  let expanded = $state(depth < 2);
  // When expandAll toggles true → open; false → reset to depth-based default.
  $effect(() => { if (expandAll) expanded = true; else expanded = depth < 2; });
```

- [ ] **Step 2: Pass `expandAll` to recursive children**

In the template where children are rendered, change:

```svelte
        <svelte:self observation={child} {rootLatency} depth={depth + 1} />
```
to:
```svelte
        <svelte:self observation={child} {rootLatency} depth={depth + 1} {expandAll} />
```

- [ ] **Step 3: Check build**

```bash
cd src/desmet/webui/frontend && bun run check
```

- [ ] **Step 4: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/components/SpanNode.svelte
git commit -m "feat(frontend): add expandAll prop to SpanNode"
```

---

## Task 7: TraceViewer — multi-tab + expand-all + filter chips

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/components/TraceViewer.svelte`

This is the orchestration task. Replace the existing single-view body with:
1. A 4-tab bar: **Timeline | Messages | Tools | Spans**
2. The selected tab renders the matching component
3. The **Spans** tab gets: an "Expand All / Collapse All" toggle button + filter chips (All | LLM | Tool | Error) that recursively filter the observation tree

The `filterObs` helper keeps parent spans that have matching children (so tree structure is preserved), and removes spans that neither match nor have matching descendants.

- [ ] **Step 1: Replace `TraceViewer.svelte` with the full multi-tab version**

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchLangfuseTrace } from '../api';
  import type { LangfuseTraceDetail, LangfuseObservation } from '../api';
  import SpanNode from './SpanNode.svelte';
  import TimelineView from './TimelineView.svelte';
  import MessageThreadView from './MessageThreadView.svelte';
  import ToolsLogView from './ToolsLogView.svelte';

  interface Message {
    role?: string;
    content?: string;
  }

  interface Props {
    messages?: Message[];
    langfuseTraceId?: string | null;
  }

  let { messages = [], langfuseTraceId = null }: Props = $props();

  let traceData = $state<LangfuseTraceDetail | null>(null);
  let loading = $state(false);
  let error = $state('');

  // Tab state
  type Tab = 'timeline' | 'messages' | 'tools' | 'spans';
  let activeTab = $state<Tab>('timeline');

  // Spans tab controls
  let expandAll = $state(false);
  type SpanFilter = 'all' | 'llm' | 'tool' | 'error';
  let spanFilter = $state<SpanFilter>('all');

  // Derived summary stats (unchanged from original)
  let tokens = $derived(traceData ? sumTokens(traceData.observations) : { input: 0, output: 0, total: 0 });
  let gens = $derived(traceData ? countGenerations(traceData.observations) : 0);
  let errs = $derived(traceData ? countErrors(traceData.observations) : 0);
  let spanCount = $derived(traceData ? countObs(traceData.observations) : 0);
  let totalCost = $derived(traceData ? (traceData.trace.cost || sumCost(traceData.observations)) : 0);

  // Filtered observations for Spans tab
  let filteredObs = $derived(traceData ? filterObs(traceData.observations, spanFilter) : []);

  onMount(async () => {
    if (!langfuseTraceId) return;
    loading = true;
    try {
      const data = await fetchLangfuseTrace(langfuseTraceId);
      if ((data as any).error) {
        error = (data as any).error;
      } else {
        traceData = data;
      }
    } catch (e) {
      error = 'Failed to load Langfuse trace';
    }
    loading = false;
  });

  // ── Helpers ────────────────────────────────────────────────

  function filterObs(obs: LangfuseObservation[], filter: SpanFilter): LangfuseObservation[] {
    if (filter === 'all') return obs;
    return obs.flatMap(o => {
      const filteredChildren = filterObs(o.children, filter);
      const matches =
        (filter === 'llm' && o.type === 'generation') ||
        (filter === 'tool' && o.type === 'tool') ||
        (filter === 'error' && o.level === 'ERROR');
      if (matches || filteredChildren.length > 0) {
        return [{ ...o, children: filteredChildren }];
      }
      return [];
    });
  }

  function countErrors(obs: LangfuseObservation[]): number {
    let n = 0;
    for (const o of obs) { if (o.level === 'ERROR') n++; n += countErrors(o.children); }
    return n;
  }
  function countObs(obs: LangfuseObservation[]): number {
    let n = obs.length;
    for (const o of obs) n += countObs(o.children);
    return n;
  }
  function sumTokens(obs: LangfuseObservation[]): { input: number; output: number; total: number } {
    let input = 0, output = 0, total = 0;
    for (const o of obs) {
      input += o.tokens.input; output += o.tokens.output; total += o.tokens.total;
      const c = sumTokens(o.children);
      input += c.input; output += c.output; total += c.total;
    }
    return { input, output, total };
  }
  function countGenerations(obs: LangfuseObservation[]): number {
    let n = 0;
    for (const o of obs) { if (o.type === 'generation') n++; n += countGenerations(o.children); }
    return n;
  }
  function sumCost(obs: LangfuseObservation[]): number {
    let c = 0;
    for (const o of obs) { c += o.cost || 0; c += sumCost(o.children); }
    return c;
  }
</script>

{#if langfuseTraceId && loading}
  <div class="trace-status">Loading Langfuse trace...</div>
{:else if langfuseTraceId && error}
  <div class="trace-status trace-err">{error}</div>
{:else if traceData}
  <div class="trace-wrap">
    <!-- Summary pills -->
    <div class="trace-pills">
      <div class="pill"><span class="pill-lbl">Tokens In</span><span class="pill-val">{tokens.input.toLocaleString()}</span></div>
      <div class="pill"><span class="pill-lbl">Tokens Out</span><span class="pill-val">{tokens.output.toLocaleString()}</span></div>
      <div class="pill"><span class="pill-lbl">Total Tokens</span><span class="pill-val">{tokens.total.toLocaleString()}</span></div>
      {#if totalCost > 0}
        <div class="pill"><span class="pill-lbl">Est. Cost</span><span class="pill-val">${totalCost.toFixed(4)}</span></div>
      {/if}
      <div class="pill"><span class="pill-lbl">LLM Calls</span><span class="pill-val">{gens}</span></div>
      <div class="pill"><span class="pill-lbl">Spans</span><span class="pill-val">{spanCount}</span></div>
      {#if errs > 0}
        <div class="pill pill-err"><span class="pill-lbl">Errors</span><span class="pill-val">{errs}</span></div>
      {/if}
    </div>

    <!-- Tab bar -->
    <div class="tab-bar">
      {#each (['timeline', 'messages', 'tools', 'spans'] as Tab[]) as tab}
        <button
          class="tab-btn"
          class:active={activeTab === tab}
          onclick={() => activeTab = tab}
        >
          {tab === 'timeline' ? '⏱ Timeline' :
           tab === 'messages' ? '💬 Messages' :
           tab === 'tools'    ? '🔧 Tools' :
                                '🌲 Spans'}
        </button>
      {/each}
    </div>

    <!-- Tab content -->
    <div class="tab-content">
      {#if activeTab === 'timeline'}
        <TimelineView {traceData} />

      {:else if activeTab === 'messages'}
        <MessageThreadView {traceData} />

      {:else if activeTab === 'tools'}
        <ToolsLogView {traceData} />

      {:else}
        <!-- Spans tab: expand-all + filter chips -->
        <div class="spans-controls">
          <button
            class="ctrl-btn"
            onclick={() => { expandAll = !expandAll; }}
          >
            {expandAll ? 'Collapse All' : 'Expand All'}
          </button>
          <div class="filter-chips">
            {#each (['all', 'llm', 'tool', 'error'] as SpanFilter[]) as f}
              <button
                class="chip"
                class:active={spanFilter === f}
                onclick={() => spanFilter = f}
              >
                {f === 'all' ? 'All' : f === 'llm' ? 'LLM' : f === 'tool' ? 'Tool' : 'Error'}
              </button>
            {/each}
          </div>
          <span class="spans-count">{countObs(filteredObs)} spans</span>
        </div>
        <div class="trace-tree">
          {#each filteredObs as obs (obs.id)}
            <SpanNode observation={obs} rootLatency={traceData.trace.latency_ms} {expandAll} />
          {/each}
        </div>
      {/if}
    </div>
  </div>

{:else if messages.length > 0}
  <!-- Legacy flat message view (no Langfuse) -->
  <div class="trace-wrap">
    {#each messages as msg}
      <div class="msg msg-{msg.role || 'system'}">
        <div class="msg-role">{msg.role || 'system'}</div>
        <div class="msg-body">{msg.content || ''}</div>
      </div>
    {/each}
  </div>
{:else}
  <div class="trace-status">No trace data available</div>
{/if}

<style>
  .trace-wrap {
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    max-height: 800px;
    overflow-y: auto;
  }

  /* ── Summary pills ─────────────── */
  .trace-pills {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 14px;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--border);
  }
  .pill {
    display: flex; flex-direction: column; gap: 2px;
    padding: 8px 14px; border-radius: 6px;
    background: var(--bg-2); border: 1px solid var(--border);
  }
  .pill-err { border-color: var(--red); }
  .pill-lbl { font-size: 10px; color: var(--text-2); text-transform: uppercase; letter-spacing: 0.06em; font-weight: 500; }
  .pill-val { font-size: 15px; font-weight: 600; font-family: var(--mono); color: var(--text-0); }
  .pill-err .pill-val { color: var(--red); }

  /* ── Tab bar ───────────────────── */
  .tab-bar {
    display: flex;
    gap: 2px;
    margin-bottom: 12px;
    background: var(--bg-2);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 3px;
  }
  .tab-btn {
    flex: 1;
    padding: 6px 10px;
    font-size: 12px;
    font-family: var(--sans);
    border: none;
    border-radius: 4px;
    background: transparent;
    color: var(--text-2);
    cursor: pointer;
    font-weight: 500;
    transition: background 0.12s, color 0.12s;
    white-space: nowrap;
  }
  .tab-btn:hover { color: var(--text-1); }
  .tab-btn.active { background: var(--bg-1); color: var(--text-0); border: 1px solid var(--border); }

  /* ── Tab content ───────────────── */
  .tab-content { min-height: 200px; }

  /* ── Spans tab controls ────────── */
  .spans-controls {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border);
  }
  .ctrl-btn {
    padding: 4px 10px; font-size: 11px;
    border: 1px solid var(--border); border-radius: 4px;
    background: var(--bg-2); color: var(--text-1);
    cursor: pointer; font-family: var(--sans);
  }
  .ctrl-btn:hover { border-color: var(--border-hover); color: var(--text-0); }

  .filter-chips { display: flex; gap: 4px; }
  .chip {
    padding: 3px 10px; font-size: 11px; border-radius: 12px;
    border: 1px solid var(--border); background: transparent;
    color: var(--text-2); cursor: pointer; font-family: var(--sans);
  }
  .chip:hover { color: var(--text-1); }
  .chip.active { background: var(--bg-2); color: var(--text-0); border-color: var(--text-2); }
  .spans-count { font-size: 11px; color: var(--text-2); margin-left: auto; }

  .trace-tree { display: flex; flex-direction: column; gap: 3px; }

  /* ── Legacy messages ───────────── */
  .msg { padding: 8px 12px; margin: 4px 0; border-radius: 6px; font-size: 13px; border-left: 2px solid var(--border); background: var(--bg-2); }
  .msg-human  { border-left-color: var(--text-0); }
  .msg-ai     { border-left-color: var(--green); }
  .msg-tool   { border-left-color: var(--yellow); font-family: var(--mono); font-size: 12px; }
  .msg-system { border-left-color: var(--text-2); }
  .msg-role { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-2); margin-bottom: 3px; }
  .msg-body { white-space: pre-wrap; word-break: break-word; color: var(--text-1); line-height: 1.5; }

  /* ── Status / error ────────────── */
  .trace-status { padding: 24px; text-align: center; font-size: 13px; color: var(--text-2); background: var(--bg-1); border: 1px solid var(--border); border-radius: 8px; }
  .trace-err { color: var(--red); border-color: var(--red); }
</style>
```

- [ ] **Step 2: Check build**

```bash
cd src/desmet/webui/frontend && bun run check
```
Expected: no type errors, no import errors.

- [ ] **Step 3: Start dev server and verify visually**

```bash
# Terminal 1 — backend
cd C:\Users\ciara\Documents\GitHub\Personal\DESMET_Agentic_Platforms
uv run desmet webui

# Terminal 2 — frontend dev server
cd src/desmet/webui/frontend
bun run dev
```

Navigate to the Scoring page, select a run that has a Langfuse trace. Verify:
- 4 tabs appear (Timeline, Messages, Tools, Spans)
- Timeline shows bars for each span
- Messages shows chronological input/output cards
- Tools shows the flat table of tool calls
- Spans tab has Expand All and filter chips working

- [ ] **Step 4: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/components/TraceViewer.svelte
git commit -m "feat(frontend): multi-tab trace viewer (Timeline/Messages/Tools/Spans)"
```

---

## Summary

After all tasks, the trace section of the Scoring page will have:

| Tab | What you see | Best for |
|-----|-------------|----------|
| **Timeline** | Waterfall bar chart: every span positioned by time | Where did the time go? Which tools blocked? |
| **Messages** | Chronological cards with full input/output | What did the agent reason? What did the LLM write? |
| **Tools** | Flat table of every tool call + expand inline | Which files were written? What commands ran? |
| **Spans** | Original tree + Expand All + type filters | Debugging, checking Langfuse metadata |
