<script lang="ts">
  import { untrack } from 'svelte';
  import { fetchExecutionModel } from '../api';
  import type { ExecutionModel, ExecutionSource, ExecutionTurn, StoryAvailability } from '../api';
  import { store } from '../data.svelte';
  import { roleColor, roleLabel, formatCost, formatDuration, formatTokens, metricTotal, runWindow } from '../execution';
  import type { UsageMetric } from '../execution';
  import ExecutionLanes from './ExecutionLanes.svelte';
  import ExecutionSummary from './ExecutionSummary.svelte';
  import TurnDrawer from './TurnDrawer.svelte';
  import AgentGraph from './AgentGraph.svelte';

  let {
    platformId,
    storyId,
    langfuseTraceId = null,
    repeatIndex = 0,
    availability = null,
  }: {
    platformId: string;
    storyId: string;
    langfuseTraceId?: string | null;
    /** Repeat of the primary run; compared platforms show their first repeat. */
    repeatIndex?: number;
    /** platform → story → run summary; lets the compare menu say what exists. */
    availability?: Record<string, Record<string, StoryAvailability>> | null;
  } = $props();

  const MAX_COMPARE = 3;
  // Width the longest compared run gets on the timeline at 1× zoom.
  const TIMELINE_W = 1400;
  const ZOOMS = [0.5, 1, 2, 4, 8];

  let model = $state<ExecutionModel | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let source = $state<'auto' | ExecutionSource>('auto');
  let selectedTurnId = $state<string | null>(null);
  let selectedTurn = $state<ExecutionTurn | null>(null);

  type CompareSlot = { model: ExecutionModel | null; error: string | null; turn: ExecutionTurn | null; seq: number };
  let compareIds = $state<string[]>([]);
  let compares = $state<Record<string, CompareSlot>>({});
  let addMenuOpen = $state(false);
  let addMenuEl = $state<HTMLDivElement | null>(null);
  let seq = 0;

  let view = $state<'lanes' | 'raw'>('lanes');
  let layoutMode = $state<'sequence' | 'timeline'>('sequence');
  let metric = $state<UsageMetric>('tokens');
  let zoomIndex = $state(1);
  let scrollX = $state(0);

  let compareOptions = $derived(
    store.platforms.filter((p) => p.implemented && p.id !== platformId && !compareIds.includes(p.id)),
  );

  // Every loaded run, primary first; the shared scales are derived from these.
  let models = $derived(
    [model, ...compareIds.map((id) => compares[id]?.model ?? null)].filter((m): m is ExecutionModel => m !== null),
  );
  let comparing = $derived(models.length > 1);

  // Stacked lane views share rows, stage columns and slot widths so the
  // same role and the same stage sit in the same place in every run.
  let sharedRoles = $derived.by(() => {
    if (!comparing) return null;
    const union = new Set(models.flatMap((m) => m.summary.roles));
    return models[0].role_order.filter((r) => union.has(r));
  });
  let sharedStageKeys = $derived.by(() => {
    if (!comparing) return null;
    const union = new Set(models.flatMap((m) => m.stages.map((s) => s.key)));
    const ordered = models[0].stage_order.filter((k) => union.has(k));
    return [...ordered, ...[...union].filter((k) => !ordered.includes(k)).sort()];
  });
  let sharedSlots = $derived.by(() => {
    if (!comparing) return null;
    const out: Record<string, number> = {};
    for (const m of models) for (const s of m.stages) out[s.key] = Math.max(out[s.key] ?? 0, s.turns.length);
    return out;
  });

  let timelineReady = $derived(models.length > 0 && models.every((m) => runWindow(m) !== null));
  let effectiveMode = $derived(timelineReady ? layoutMode : 'sequence');
  let zoom = $derived(ZOOMS[zoomIndex]);
  let maxSpanMs = $derived(
    Math.max(
      0,
      ...models.map((m) => {
        const w = runWindow(m);
        return w ? w.t1 - w.t0 : 0;
      }),
    ),
  );
  let pxPerMs = $derived(maxSpanMs > 0 ? (TIMELINE_W * zoom) / maxSpanMs : 0);
  let laneMinWidth = $derived(effectiveMode === 'timeline' && maxSpanMs > 0 ? TIMELINE_W * zoom + 24 : 0);
  let metricMax = $derived(comparing ? Math.max(0, ...models.map((m) => metricTotal(m, metric))) : 0);

  async function load() {
    loading = true;
    error = null;
    model = null;
    selectedTurnId = null;
    selectedTurn = null;
    try {
      model = await fetchExecutionModel(platformId, storyId, source, repeatIndex);
    } catch (e: any) {
      error = e?.status === 404 ? 'No trace data found for this run.' : `Failed to load execution model: ${e?.message ?? e}`;
    } finally {
      loading = false;
    }
  }

  async function loadCompare(id: string) {
    const mine = ++seq;
    compares[id] = { model: null, error: null, turn: null, seq: mine };
    let next: Partial<CompareSlot>;
    try {
      next = { model: await fetchExecutionModel(id, storyId, source) };
    } catch (e: any) {
      next = { error: e?.status === 404 ? 'No trace data for this platform on this story.' : `Failed: ${e?.message ?? e}` };
    }
    // A newer request (source or story changed meanwhile) owns the slot.
    if (compares[id]?.seq === mine) compares[id] = { ...compares[id], ...next };
  }

  function addCompare(id: string) {
    addMenuOpen = false;
    if (!id || compareIds.includes(id) || compareIds.length >= MAX_COMPARE) return;
    compareIds = [...compareIds, id];
    loadCompare(id);
  }

  function removeCompare(id: string) {
    compareIds = compareIds.filter((c) => c !== id);
    delete compares[id];
  }

  $effect(() => {
    if (platformId && storyId) {
      // Reading `source` here re-runs the load when the selector changes.
      void source;
      void repeatIndex;
      load();
    }
  });

  $effect(() => {
    // Re-fetch every comparison when the story or the source changes, and
    // drop the platform that just became the primary one.
    void source;
    void storyId;
    const pid = platformId;
    untrack(() => {
      if (compareIds.includes(pid)) removeCompare(pid);
      for (const id of compareIds) loadCompare(id);
    });
  });

  function platformName(id: string): string {
    return store.platforms.find((p) => p.id === id)?.name ?? id;
  }

  function compareStatus(pid: string): { text: string; tone: string; usable: boolean } | null {
    if (!availability) return null;
    const a = availability[pid]?.[storyId];
    if (!a) return { text: 'no run', tone: 'dim', usable: false };
    if (!a.has_trace) return { text: 'no trace', tone: 'dim', usable: false };
    if (!a.repeats) return { text: 'other run', tone: 'warn', usable: true };
    if (a.passed === a.repeats) return { text: 'passed', tone: 'ok', usable: true };
    return { text: a.passed ? `${a.passed}/${a.repeats} passed` : 'failed', tone: a.passed ? 'warn' : 'bad', usable: true };
  }

  // Platforms that ran this story first; the rest stay listed but inert.
  let menuOptions = $derived(
    compareOptions
      .map((p) => ({ p, status: compareStatus(p.id) }))
      .sort((a, b) => Number(b.status?.usable ?? true) - Number(a.status?.usable ?? true)),
  );

  function closeAddMenu(e: MouseEvent | KeyboardEvent) {
    if (!addMenuOpen) return;
    if (e instanceof KeyboardEvent ? e.key === 'Escape' : !addMenuEl?.contains(e.target as Node)) addMenuOpen = false;
  }
</script>

<svelte:window onclick={closeAddMenu} onkeydown={closeAddMenu} />

{#snippet runHeader(m: ExecutionModel, removable: boolean)}
  <div class="run-header">
    <span class="badge" class:local={m.source === 'local'}>{m.source === 'langfuse' ? 'LANGFUSE' : 'LOCAL TRACE'}</span>
    <span class="run-title">{platformName(m.platform_id)}</span>
    <span class="run-stats">
      {m.summary.turns} turns · {m.summary.llm_calls} LLM calls · {m.summary.tool_calls} tool calls
      {#if m.summary.tool_failures}<span class="bad"> ({m.summary.tool_failures} failed)</span>{/if}
      · {formatTokens(m.summary.tokens)} tokens
      {#if m.summary.cost_usd}· {formatCost(m.summary.cost_usd)}{/if}
      · {formatDuration(m.summary.duration_ms)}
      {#if m.summary.retries}<span class="warn"> · {m.summary.retries} retr{m.summary.retries === 1 ? 'y' : 'ies'}</span>{/if}
      {#if m.attempts > 1} · attempt {m.attempts} of {m.attempts}{/if}
    </span>
    {#if removable}
      <button class="remove" title="Remove from comparison" onclick={() => removeCompare(m.platform_id)}>×</button>
    {/if}
  </div>
  {#if m.notes.length}
    <div class="notes">{#each m.notes as n}<div>{n}</div>{/each}</div>
  {/if}
{/snippet}

<div class="exec-view">
  <div class="toolbar">
    <div class="toolbar-left">
      <div class="seg">
        <button class:active={view === 'lanes'} onclick={() => (view = 'lanes')}>Pipeline lanes</button>
        <button class:active={view === 'raw'} onclick={() => (view = 'raw')}>Raw spans</button>
      </div>
      {#if view === 'lanes'}
        <div class="seg">
          <button class:active={effectiveMode === 'sequence'} onclick={() => (layoutMode = 'sequence')}>Sequence</button>
          <button
            class:active={effectiveMode === 'timeline'}
            disabled={!timelineReady}
            title={timelineReady ? 'Place turns on a shared wall-clock axis' : 'A run has no timestamps'}
            onclick={() => (layoutMode = 'timeline')}>Timeline</button
          >
        </div>
        {#if effectiveMode === 'timeline'}
          <div class="seg zoom">
            <button disabled={zoomIndex === 0} onclick={() => zoomIndex--} title="Zoom out">−</button>
            <span>{zoom}×</span>
            <button disabled={zoomIndex === ZOOMS.length - 1} onclick={() => zoomIndex++} title="Zoom in">+</button>
          </div>
        {/if}
        <div class="seg">
          <button class:active={metric === 'tokens'} onclick={() => (metric = 'tokens')}>Tokens</button>
          <button class:active={metric === 'cost'} onclick={() => (metric = 'cost')}>Cost</button>
        </div>
        <label class="ctl">
          <span>Source</span>
          <select class="input small" bind:value={source}>
            <option value="auto">Auto</option>
            <option value="langfuse">Langfuse</option>
            <option value="local">Local trace</option>
          </select>
        </label>
        <div class="compare-ctl">
          <span class="ctl-label">Compare</span>
          {#each compareIds as id (id)}
            <span class="chip">
              {platformName(id)}
              <button title="Remove {platformName(id)} from comparison" onclick={() => removeCompare(id)}>×</button>
            </span>
          {/each}
          {#if compareIds.length < MAX_COMPARE && compareOptions.length}
            <div class="add-wrap" bind:this={addMenuEl}>
              <button
                class="add-btn"
                aria-haspopup="menu"
                aria-expanded={addMenuOpen}
                onclick={() => (addMenuOpen = !addMenuOpen)}
              >+ Add platform</button>
              {#if addMenuOpen}
                <div class="add-menu" role="menu">
                  <div class="menu-hint">Stacked under this run · up to {MAX_COMPARE}</div>
                  {#each menuOptions as { p, status } (p.id)}
                    <button role="menuitem" disabled={status ? !status.usable : false} onclick={() => addCompare(p.id)}>
                      <span>{p.name}</span>
                      {#if status}<span class="menu-status {status.tone}">{status.text}</span>{/if}
                    </button>
                  {/each}
                </div>
              {/if}
            </div>
          {:else if compareIds.length >= MAX_COMPARE}
            <span class="ctl-hint">max {MAX_COMPARE}</span>
          {/if}
        </div>
      {/if}
    </div>
    {#if view === 'lanes'}
      <div class="legend">
        {#each ['manager', 'planner', 'executor', 'reviewer'] as role}
          <span class="legend-item"><span class="dot" style="background: {roleColor(role)}"></span>{roleLabel(role)}</span>
        {/each}
        <span class="legend-item"><span class="line dashed"></span>retry</span>
        {#if effectiveMode === 'sequence'}
          <span class="legend-item"><span class="line dotted"></span>stage boundary</span>
        {/if}
      </div>
    {/if}
  </div>

  {#if view === 'raw'}
    <AgentGraph {platformId} {storyId} {langfuseTraceId} {repeatIndex} />
  {:else if loading}
    <div class="status">Loading execution model…</div>
  {:else if error}
    <div class="status">{error}</div>
  {:else if model}
    {#if comparing}
      <div class="scale-note">
        Shared scales across {models.length} runs: same rows and stages{effectiveMode === 'timeline'
          ? `, same time axis (longest run ${formatDuration(maxSpanMs)})`
          : ''}, same {metric === 'cost' ? 'cost' : 'token'} axis.
      </div>
    {/if}

    {@render runHeader(model, false)}
    <div class="lanes-row">
      <div class="lanes-main">
        <ExecutionLanes
          {model}
          roles={sharedRoles}
          stageKeys={sharedStageKeys}
          stageSlots={sharedSlots}
          mode={effectiveMode}
          {pxPerMs}
          minWidth={laneMinWidth}
          {metric}
          {metricMax}
          bind:selectedTurnId
          bind:scrollX
          onselect={(t) => (selectedTurn = t)}
        />
      </div>
      {#if selectedTurn}
        <TurnDrawer turn={selectedTurn} onclose={() => { selectedTurn = null; selectedTurnId = null; }} />
      {/if}
    </div>

    {#each compareIds as id (id)}
      {@const slot = compares[id]}
      <div class="compare-block">
        {#if slot?.model}
          {@render runHeader(slot.model, true)}
          <div class="lanes-row">
            <div class="lanes-main">
              <ExecutionLanes
                model={slot.model}
                roles={sharedRoles}
                stageKeys={sharedStageKeys}
                stageSlots={sharedSlots}
                mode={effectiveMode}
                {pxPerMs}
                minWidth={laneMinWidth}
                {metric}
                {metricMax}
                bind:scrollX
                onselect={(t) => (slot.turn = t)}
              />
            </div>
            {#if slot.turn}
              <TurnDrawer turn={slot.turn} onclose={() => (slot.turn = null)} />
            {/if}
          </div>
        {:else}
          <div class="run-header">
            <span class="run-title">{platformName(id)}</span>
            <button class="remove" title="Remove from comparison" onclick={() => removeCompare(id)}>×</button>
          </div>
          <div class="status small">{slot?.error ?? 'Loading comparison…'}</div>
        {/if}
      </div>
    {/each}

    <div class="summary-block">
      {#each models as m, i (m.platform_id)}
        <div class="summary-title" style:margin-top={i ? '16px' : null}>{platformName(m.platform_id)} — per stage and role</div>
        <ExecutionSummary model={m} roles={sharedRoles} />
      {/each}
    </div>
  {/if}
</div>

<style>
  .exec-view {
    display: flex;
    flex-direction: column;
    gap: 10px;
    min-width: 0;
    max-width: 100%;
  }
  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }
  .toolbar-left {
    display: flex;
    align-items: center;
    gap: 14px;
    flex-wrap: wrap;
  }
  .seg {
    display: inline-flex;
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
  }
  .seg button {
    background: none;
    border: none;
    color: var(--text-2);
    font: inherit;
    font-size: 12px;
    padding: 5px 10px;
    cursor: pointer;
  }
  .seg button.active {
    background: var(--bg-3);
    color: var(--text-0);
  }
  .seg button:disabled {
    color: var(--text-3);
    cursor: not-allowed;
  }
  .seg.zoom {
    align-items: center;
  }
  .seg.zoom span {
    font-size: 11px;
    font-family: var(--mono);
    color: var(--text-1);
    min-width: 30px;
    text-align: center;
  }
  .remove {
    margin-left: auto;
    background: none;
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text-2);
    font: inherit;
    font-size: 13px;
    line-height: 1;
    padding: 2px 7px;
    cursor: pointer;
  }
  .remove:hover {
    color: var(--text-0);
    border-color: var(--border-hover);
  }
  .compare-ctl {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }
  .ctl-label,
  .ctl-hint {
    font-size: 11px;
    color: var(--text-2);
  }
  .ctl-hint {
    color: var(--text-3);
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 4px 2px 8px;
    font-size: 12px;
    color: var(--text-0);
    background: var(--bg-3);
    border: 1px solid var(--border);
    border-radius: 999px;
  }
  .chip button {
    background: none;
    border: none;
    color: var(--text-2);
    font: inherit;
    font-size: 13px;
    line-height: 1;
    padding: 0 4px;
    cursor: pointer;
  }
  .chip button:hover {
    color: var(--text-0);
  }
  .add-wrap {
    position: relative;
  }
  .add-btn {
    background: none;
    border: 1px dashed var(--border-hover);
    border-radius: 999px;
    color: var(--text-1);
    font: inherit;
    font-size: 12px;
    padding: 3px 10px;
    cursor: pointer;
  }
  .add-btn:hover,
  .add-btn[aria-expanded='true'] {
    color: var(--text-0);
    border-style: solid;
  }
  .add-menu {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    z-index: 20;
    min-width: 200px;
    display: flex;
    flex-direction: column;
    padding: 4px;
    background: var(--bg-2);
    border: 1px solid var(--border);
    border-radius: 6px;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
  }
  .add-menu button {
    background: none;
    border: none;
    border-radius: 4px;
    color: var(--text-0);
    font: inherit;
    font-size: 12px;
    text-align: left;
    padding: 6px 8px;
    cursor: pointer;
  }
  .add-menu button {
    display: flex;
    justify-content: space-between;
    gap: 12px;
  }
  .add-menu button:hover:not(:disabled) {
    background: var(--bg-3);
  }
  .add-menu button:disabled {
    color: var(--text-3);
    cursor: default;
  }
  .menu-status {
    font-size: 10px;
    font-family: var(--mono);
  }
  .menu-status.ok {
    color: var(--green);
  }
  .menu-status.bad {
    color: var(--red);
  }
  .menu-status.warn {
    color: var(--yellow);
  }
  .menu-status.dim {
    color: var(--text-3);
  }
  .menu-hint {
    font-size: 10px;
    color: var(--text-3);
    padding: 4px 8px 6px;
  }
  .scale-note {
    font-size: 11px;
    color: var(--text-2);
  }
  .ctl {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: var(--text-2);
  }
  .input.small {
    padding: 4px 8px;
    font-size: 12px;
    width: auto;
  }
  .legend {
    display: flex;
    gap: 12px;
    font-size: 11px;
    color: var(--text-2);
    flex-wrap: wrap;
  }
  .legend-item {
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }
  .line {
    width: 16px;
    height: 0;
    border-top: 2px dashed var(--yellow);
  }
  .line.dotted {
    border-top: 2px dotted var(--text-3);
  }

  .run-header {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 12px;
    flex-wrap: wrap;
  }
  .badge {
    background: color-mix(in srgb, var(--blue) 20%, transparent);
    color: var(--blue);
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 10px;
    letter-spacing: 0.4px;
  }
  .badge.local {
    background: color-mix(in srgb, var(--text-2) 25%, transparent);
    color: var(--text-1);
  }
  .run-title {
    font-weight: 600;
    color: var(--text-0);
  }
  .run-stats {
    color: var(--text-2);
    font-family: var(--mono);
    font-size: 11px;
  }
  .notes {
    font-size: 11px;
    color: var(--yellow);
  }
  .lanes-row {
    display: flex;
    gap: 10px;
    align-items: flex-start;
  }
  .lanes-main {
    flex: 1;
    min-width: 0;
  }
  .compare-block {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding-top: 10px;
    border-top: 1px dashed var(--border);
  }
  .summary-block {
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 14px;
    overflow-x: auto;
  }
  .summary-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-1);
    margin-bottom: 8px;
  }
  .status {
    padding: 40px;
    text-align: center;
    color: var(--text-2);
    font-size: 13px;
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  .status.small {
    padding: 16px;
    font-size: 12px;
  }
  .bad {
    color: var(--red);
  }
  .warn {
    color: var(--yellow);
  }
</style>
