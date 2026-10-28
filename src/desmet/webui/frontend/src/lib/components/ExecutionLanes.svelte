<script lang="ts">
  import type { ExecutionModel, ExecutionStage, ExecutionTurn } from '../api';
  import {
    roleColor,
    roleLabel,
    stageLabel,
    formatCost,
    formatDuration,
    formatMetric,
    formatTokens,
    orderedSteps,
    parseTs,
    runWindow,
    stageWindow,
    tickInterval,
    turnWindow,
    usageEvents,
  } from '../execution';
  import type { UsageMetric } from '../execution';

  let {
    model,
    roles = null,
    stageKeys = null,
    stageSlots = null,
    mode = 'sequence',
    pxPerMs = 0,
    minWidth = 0,
    metric = 'tokens',
    metricMax = 0,
    selectedTurnId = $bindable(null),
    scrollX = $bindable(0),
    onselect,
  }: {
    model: ExecutionModel;
    /** Row override so stacked lane views share identical rows. */
    roles?: string[] | null;
    /** Column override so stacked views show the same stages in the same order. */
    stageKeys?: string[] | null;
    /** Minimum slots per stage, so a stage lines up across stacked views. */
    stageSlots?: Record<string, number> | null;
    /** ``timeline`` places turns by wall-clock time on a ``pxPerMs`` scale. */
    mode?: 'sequence' | 'timeline';
    pxPerMs?: number;
    minWidth?: number;
    metric?: UsageMetric;
    /** Shared y-scale top for the cumulative strip (0 = this run's own total). */
    metricMax?: number;
    selectedTurnId?: string | null;
    scrollX?: number;
    onselect?: (turn: ExecutionTurn | null) => void;
  } = $props();

  // ── Fixed geometry: the layout is computed, not measured ───────────
  const SLOT_W = 152;
  const NODE_W = 136;
  const NODE_H = 64;
  const ROW_H = 84;
  const HEADER_H = 48;
  const STAGE_PAD = 14;
  const LABEL_W = 96;
  const CHART_H = 112;
  const CHART_TOP = 14;
  const CHART_BOTTOM = 20;
  const TL_PAD = 12;
  const TL_MIN_W = 6;
  const TL_GAP = 4;

  type Placed = { turn: ExecutionTurn; x: number; y: number; w: number; h: number; compact: boolean };
  type StageCol = {
    key: string;
    x: number;
    width: number;
    success: boolean | null;
    duration_ms: number;
    tokens: number;
    cost: number;
    error: string | null;
    empty: boolean;
    missing: boolean;
  };

  let rowRoles = $derived.by(() => {
    const present = model.summary.roles;
    const chosen = roles ?? present;
    return model.role_order.filter((r) => chosen.includes(r));
  });

  let win = $derived(runWindow(model));
  let timeline = $derived(mode === 'timeline' && win !== null && pxPerMs > 0);
  let chartTop = $derived(HEADER_H + Math.max(1, rowRoles.length) * ROW_H);

  function tx(ms: number): number {
    return TL_PAD + (ms - (win?.t0 ?? 0)) * pxPerMs;
  }

  function stageCol(key: string, stage: ExecutionStage | undefined, x: number, width: number): StageCol {
    return {
      key,
      x,
      width,
      success: stage?.success ?? null,
      duration_ms: stage?.duration_ms ?? 0,
      tokens: stage?.tokens ?? 0,
      cost: stage?.cost_usd ?? 0,
      error: stage?.error ?? null,
      empty: !!stage && stage.turns.length === 0,
      missing: !stage,
    };
  }

  function rowY(role: string): number {
    return HEADER_H + Math.max(0, (rowRoles as string[]).indexOf(role)) * ROW_H;
  }

  let layout = $derived.by(() => {
    const cols: StageCol[] = [];
    const placed: Placed[] = [];
    const byId = new Map<string, Placed>();
    const stageByKey = new Map(model.stages.map((s) => [s.key, s]));
    const keys = stageKeys ?? model.stages.map((s) => s.key);
    let right = 0;

    if (!timeline) {
      let x = 0;
      for (const key of keys) {
        const stage = stageByKey.get(key);
        const n = stage?.turns.length ?? 0;
        const slots = Math.max(1, n, stageSlots?.[key] ?? 0);
        const width = slots * SLOT_W + STAGE_PAD * 2;
        cols.push(stageCol(key, stage, x, width));
        stage?.turns.forEach((turn, slot) => {
          const p: Placed = {
            turn,
            x: x + STAGE_PAD + slot * SLOT_W + (SLOT_W - NODE_W) / 2,
            y: rowY(turn.role) + (ROW_H - NODE_H) / 2,
            w: NODE_W,
            h: NODE_H,
            compact: false,
          };
          placed.push(p);
          byId.set(turn.id, p);
        });
        x += width;
      }
      right = x;
    } else {
      for (const key of keys) {
        const stage = stageByKey.get(key);
        const sw = stage ? stageWindow(stage) : null;
        if (!stage || !sw) continue;
        const x = tx(sw.t0);
        cols.push(stageCol(key, stage, x, Math.max(2, (sw.t1 - sw.t0) * pxPerMs)));
      }
      // Turns of one role can overlap in time (parallel agents, nested
      // retries): stack them on sub-tracks inside the role's row.
      const tracks = new Map<string, number[]>();
      const assigned: Array<{ turn: ExecutionTurn; x: number; w: number; track: number }> = [];
      const turns = model.stages.flatMap((s) => {
        const sw = stageWindow(s);
        return s.turns.map((turn) => ({ turn, w: turnWindow(turn) ?? (sw ? { t0: sw.t0, t1: sw.t0 } : null) }));
      });
      turns.sort((a, b) => (a.w?.t0 ?? 0) - (b.w?.t0 ?? 0));
      for (const { turn, w: tw } of turns) {
        const x = tw ? tx(tw.t0) : TL_PAD;
        const w = Math.max(TL_MIN_W, tw ? (tw.t1 - tw.t0) * pxPerMs : 0);
        const ends = tracks.get(turn.role) ?? [];
        let track = ends.findIndex((end) => end <= x - 2);
        if (track === -1) {
          track = ends.length;
          ends.push(0);
        }
        ends[track] = x + w;
        tracks.set(turn.role, ends);
        assigned.push({ turn, x, w, track });
      }
      for (const a of assigned) {
        const n = tracks.get(a.turn.role)?.length ?? 1;
        const h = Math.min(NODE_H, (ROW_H - 16 - (n - 1) * TL_GAP) / n);
        const p: Placed = {
          turn: a.turn,
          x: a.x,
          y: rowY(a.turn.role) + 8 + a.track * (h + TL_GAP),
          w: a.w,
          h,
          compact: a.w < 90 || h < 30,
        };
        placed.push(p);
        byId.set(a.turn.id, p);
      }
      right = Math.max(win ? tx(win.t1) : 0, ...cols.map((c) => c.x + c.width), ...placed.map((p) => p.x + p.w)) + TL_PAD;
    }

    const height = chartTop + CHART_H;
    return { cols, placed, byId, width: Math.max(right, minWidth), right, height };
  });

  type EdgePath = { d: string; kind: string; mid: { x: number; y: number } };

  let edges = $derived.by((): EdgePath[] => {
    const out: EdgePath[] = [];
    for (const tr of model.transitions) {
      // On the timeline, order is already the x-axis; only loops need a line.
      if (timeline && tr.kind !== 'retry') continue;
      const a = layout.byId.get(tr.source);
      const b = layout.byId.get(tr.target);
      if (!a || !b) continue;
      const x1 = a.x + a.w;
      const y1 = a.y + a.h / 2;
      const x2 = b.x;
      const y2 = b.y + b.h / 2;
      const dx = Math.max(24, (x2 - x1) * 0.5);
      out.push({
        d: `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`,
        kind: tr.kind,
        mid: { x: (x1 + x2) / 2, y: (y1 + y2) / 2 },
      });
    }
    return out;
  });

  // ── Cumulative usage strip ─────────────────────────────────────────

  type ChartPoint = { x: number; cum: number; delta: number; turn: ExecutionTurn | null; label: string };

  let usage = $derived(usageEvents(model, metric));

  let chart = $derived.by(() => {
    const colByKey = new Map(layout.cols.map((c) => [c.key, c]));
    const stepIndex = new Map<string, { i: number; n: number }>();
    for (const s of model.stages)
      for (const t of s.turns) {
        const steps = orderedSteps(t);
        steps.forEach((st, i) => stepIndex.set(st.id, { i, n: steps.length }));
      }

    const raw = usage.events.map((e, order) => {
      let x: number;
      const p = e.turn ? layout.byId.get(e.turn.id) : undefined;
      if (e.step && p) {
        const t = timeline ? (parseTs(e.step.end_time) ?? parseTs(e.step.start_time)) : null;
        if (t !== null) x = tx(t);
        else {
          const idx = stepIndex.get(e.step.id) ?? { i: 0, n: 1 };
          x = p.x + (p.w * (idx.i + 1)) / idx.n;
        }
      } else {
        const col = colByKey.get(e.stageKey);
        x = col ? col.x + col.width - (timeline ? 0 : STAGE_PAD) : 0;
      }
      return { e, x, order };
    });
    raw.sort((a, b) => a.x - b.x || a.order - b.order);

    let cum = 0;
    const points: ChartPoint[] = raw.map(({ e, x }) => {
      cum += e.delta;
      const who = e.turn ? `${roleLabel(e.turn.role)} · ${e.step?.model ?? e.step?.name ?? 'llm'}` : `${stageLabel(e.stageKey)} (stage total)`;
      return { x, cum, delta: e.delta, turn: e.turn, label: who };
    });

    const total = cum;
    const top = metricMax > 0 ? metricMax : total || 1;
    const plotH = CHART_H - CHART_TOP - CHART_BOTTOM;
    const y = (v: number) => CHART_TOP + (1 - Math.min(1, v / top)) * plotH;
    const base = y(0);
    const x0 = layout.cols[0]?.x ?? 0;
    const xEnd = Math.max(points.at(-1)?.x ?? x0, layout.right - (timeline ? TL_PAD : 0));

    let line = `M ${x0} ${base}`;
    let prev = base;
    for (const p of points) {
      const py = y(p.cum);
      line += ` L ${p.x} ${prev} L ${p.x} ${py}`;
      prev = py;
    }
    line += ` L ${xEnd} ${prev}`;
    const area = `${line} L ${xEnd} ${base} L ${x0} ${base} Z`;

    const retries = layout.placed.filter((p) => p.turn.is_retry).map((p) => p.x);

    const ticks: Array<{ x: number; label: string }> = [];
    if (timeline && win) {
      const step = tickInterval(pxPerMs);
      for (let t = 0; t <= win.t1 - win.t0; t += step) ticks.push({ x: tx(win.t0 + t), label: formatDuration(t) });
    }

    return { points, total, top, line, area, base, y, xEnd, retries, ticks, plotTop: CHART_TOP };
  });

  let orderedTurns = $derived(model.stages.flatMap((s) => s.turns));

  function select(turn: ExecutionTurn | null) {
    selectedTurnId = turn?.id ?? null;
    onselect?.(turn);
  }

  function handleKeydown(e: KeyboardEvent) {
    // Keyboard navigation is only live while a turn is selected, so the
    // arrows never steal focus from inputs elsewhere on the page.
    if (!selectedTurnId) return;
    const target = e.target as HTMLElement | null;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'SELECT' || target.tagName === 'TEXTAREA')) return;
    if (e.key === 'Escape') {
      select(null);
      return;
    }
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    e.preventDefault();
    const idx = orderedTurns.findIndex((t) => t.id === selectedTurnId);
    const next = e.key === 'ArrowRight' ? Math.min(orderedTurns.length - 1, idx + 1) : Math.max(0, idx - 1);
    if (orderedTurns[next]) select(orderedTurns[next]);
  }

  function edgeColor(kind: string): string {
    if (kind === 'retry') return 'var(--yellow)';
    if (kind === 'stage') return 'var(--text-3)';
    return 'var(--text-2)';
  }

  // Stacked views scroll together: follow the shared offset, report our own.
  let scrollEl = $state<HTMLDivElement | null>(null);
  $effect(() => {
    const x = scrollX;
    if (scrollEl && Math.abs(scrollEl.scrollLeft - x) > 1) scrollEl.scrollLeft = x;
  });
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="lanes" role="region" aria-label="Execution lanes">
  <div class="row-labels" style="padding-top: {HEADER_H}px; width: {LABEL_W}px;">
    {#each rowRoles as role}
      <div class="row-label" style="height: {ROW_H}px; --role-color: {roleColor(role)}">
        <span class="role-dot"></span>
        <span>{roleLabel(role)}</span>
      </div>
    {/each}
    <div class="chart-label" style="height: {CHART_H}px;">
      <span class="axis-max" style="top: {chart.plotTop - 6}px;">{formatMetric(metric, chart.top)}</span>
      <span class="chart-name">
        {metric === 'cost' ? 'Cost' : 'Tokens'}<br /><span class="dim">cumulative</span>
        {#if usage.estimated}
          <br /><span
            class="est"
            title="Some stages report only a stage total; it is spread over that stage's LLM calls ({metric === 'cost'
              ? 'by token share'
              : 'evenly'})."
          >estimated</span>
        {/if}
      </span>
      <span class="axis-zero" style="top: {chart.base - 6}px;">0</span>
    </div>
  </div>

  <div class="scroll" bind:this={scrollEl} onscroll={() => scrollEl && (scrollX = scrollEl.scrollLeft)}>
    <div class="canvas" style="width: {layout.width}px; height: {layout.height}px;">
      {#each layout.cols as col, i}
        {@const narrow = col.width < 150}
        <div
          class="stage-col"
          class:alt={i % 2 === 1}
          class:failed={col.success === false}
          class:timeline
          style="left: {col.x}px; width: {col.width}px; height: {layout.height}px;"
          title="{stageLabel(col.key)} — {formatTokens(col.tokens)} tokens{col.cost ? ` · ${formatCost(col.cost)}` : ''} · {formatDuration(col.duration_ms)}"
        >
          <div class="stage-header" class:narrow style="height: {HEADER_H}px;">
            <span class="stage-name">
              {#if col.success === true}
                <span class="stage-status ok" title="Stage validated">●</span>
              {:else if col.success === false}
                <span class="stage-status fail" title={col.error ?? 'Stage failed'}>●</span>
              {/if}
              {stageLabel(col.key)}
            </span>
            {#if !narrow}
              <span class="stage-meta">
                {#if col.tokens}{formatTokens(col.tokens)} tok ·&nbsp;{/if}{formatDuration(col.duration_ms)}
              </span>
            {/if}
          </div>
          {#if col.missing}
            <div class="stage-empty" style="top: {HEADER_H}px;">not run</div>
          {:else if col.empty}
            <div class="stage-empty" style="top: {HEADER_H}px;">no agent turns</div>
          {/if}
        </div>
      {/each}

      {#each rowRoles as _role, r}
        <div class="row-line" style="top: {HEADER_H + (r + 1) * ROW_H}px; width: {layout.width}px;"></div>
      {/each}

      <svg class="edges" width={layout.width} height={layout.height} aria-hidden="true">
        <defs>
          <marker id="arrow-seq" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 8 4 L 0 8 z" fill="var(--text-2)"></path>
          </marker>
          <marker id="arrow-retry" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 8 4 L 0 8 z" fill="var(--yellow)"></path>
          </marker>
          <marker id="arrow-stage" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 8 4 L 0 8 z" fill="var(--text-3)"></path>
          </marker>
        </defs>
        {#each edges as e}
          <path
            d={e.d}
            fill="none"
            stroke={edgeColor(e.kind)}
            stroke-width={e.kind === 'retry' ? 2 : 1.5}
            stroke-dasharray={e.kind === 'retry' ? '5 4' : e.kind === 'stage' ? '2 4' : undefined}
            marker-end="url(#arrow-{e.kind === 'sequence' ? 'seq' : e.kind})"
            opacity={e.kind === 'stage' ? 0.9 : 0.8}
          ></path>
          {#if e.kind === 'retry' && !timeline}
            <text x={e.mid.x} y={e.mid.y - 6} class="edge-label" text-anchor="middle">retry</text>
          {/if}
        {/each}
      </svg>

      {#each layout.placed as p (p.turn.id)}
        {@const t = p.turn}
        <button
          type="button"
          class="turn"
          class:compact={p.compact}
          class:selected={t.id === selectedTurnId}
          class:retry={t.is_retry}
          class:error={!!t.error}
          style="left: {p.x}px; top: {p.y}px; width: {p.w}px; height: {p.h}px; --role-color: {roleColor(t.role)}"
          title="{t.raw_name} — {t.llm_calls} LLM calls, {t.tool_calls} tool calls, {formatTokens(t.tokens)} tokens, {formatDuration(t.duration_ms)}"
          onclick={() => select(t.id === selectedTurnId ? null : t)}
        >
          {#if !p.compact}
            <div class="turn-head">
              <span class="role-dot"></span>
              <span class="turn-role">{roleLabel(t.role)}</span>
              {#if t.is_retry}<span class="flag retry-flag" title="Retry / fallback">↺</span>{/if}
              {#if t.error}<span class="flag error-flag" title={t.error}>!</span>{/if}
            </div>
            {#if !timeline && t.raw_name.toLowerCase() !== t.role}
              <div class="turn-raw">{t.raw_name}</div>
            {/if}
            <div class="turn-stats">
              <span>{t.llm_calls} LLM</span>
              <span class:bad={t.tool_failures > 0}>{t.tool_calls} tool{t.tool_calls === 1 ? '' : 's'}{t.tool_failures ? ` (${t.tool_failures} fail)` : ''}</span>
            </div>
            {#if !timeline}
              <div class="turn-stats dim">
                <span>{t.tokens ? formatTokens(t.tokens) : '—'} tok</span>
                <span>{formatDuration(t.duration_ms)}</span>
              </div>
            {/if}
          {/if}
        </button>
      {/each}

      <svg class="chart" style="top: {chartTop}px;" width={layout.width} height={CHART_H} aria-label="Cumulative {metric}">
        <line class="grid" x1="0" x2={layout.width} y1={chart.y(chart.top)} y2={chart.y(chart.top)}></line>
        <line class="baseline" x1="0" x2={layout.width} y1={chart.base} y2={chart.base}></line>
        {#each chart.ticks as tk}
          <line class="tick" x1={tk.x} x2={tk.x} y1={chart.plotTop} y2={chart.base + 4}></line>
          <text class="tick-label" x={tk.x} y={CHART_H - 5} text-anchor="middle">{tk.label}</text>
        {/each}
        {#each chart.retries as rx}
          <line class="retry-mark" x1={rx} x2={rx} y1={chart.plotTop} y2={chart.base}></line>
        {/each}
        <path class="area" d={chart.area}></path>
        <path class="line" d={chart.line}></path>
        {#if chart.points.length <= 400}
          {#each chart.points as pt}
            <circle
              class="pt"
              class:selected={pt.turn !== null && pt.turn.id === selectedTurnId}
              cx={pt.x}
              cy={chart.y(pt.cum)}
              r="3"
              role="presentation"
              onclick={() => pt.turn && select(pt.turn)}
            >
              <title>{pt.label}: +{formatMetric(metric, pt.delta)} → {formatMetric(metric, pt.cum)}</title>
            </circle>
          {/each}
        {/if}
        {#if chart.total > 0}
          <text class="end-label" x={chart.xEnd - 4} y={chart.y(chart.total) - 6} text-anchor="end">{formatMetric(metric, chart.total)}</text>
        {/if}
      </svg>
    </div>
  </div>
</div>

<style>
  .lanes {
    display: flex;
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: 8px;
    min-height: 120px;
  }

  .row-labels {
    flex-shrink: 0;
    border-right: 1px solid var(--border);
    box-sizing: border-box;
  }
  .row-label {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 12px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-1);
    box-sizing: border-box;
  }
  .chart-label {
    position: relative;
    border-top: 1px solid var(--border);
    box-sizing: border-box;
    font-size: 11px;
    color: var(--text-1);
  }
  .chart-name {
    position: absolute;
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    font-weight: 600;
    line-height: 1.3;
  }
  .chart-name .dim {
    font-weight: 400;
    color: var(--text-2);
  }
  .est {
    font-weight: 400;
    color: var(--yellow);
    cursor: help;
    border-bottom: 1px dotted var(--yellow);
  }
  .axis-max,
  .axis-zero {
    position: absolute;
    right: 6px;
    font-family: var(--mono);
    font-size: 10px;
    color: var(--text-3);
  }

  .scroll {
    flex: 1;
    min-width: 0; /* flex items default to content width, which would widen the page */
    overflow-x: auto;
    overflow-y: hidden;
  }
  .canvas {
    position: relative;
  }

  .stage-col {
    position: absolute;
    top: 0;
    box-sizing: border-box;
    border-right: 1px solid var(--border);
  }
  .stage-col.timeline {
    border-left: 1px solid var(--border);
  }
  .stage-col.alt {
    background: rgba(255, 255, 255, 0.015);
  }
  .stage-col.failed {
    background: color-mix(in srgb, var(--red) 5%, transparent);
  }
  .stage-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
    padding: 0 14px;
    border-bottom: 1px solid var(--border);
    box-sizing: border-box;
    overflow: hidden;
  }
  .stage-header.narrow {
    padding: 0 6px;
  }
  .stage-name {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-0);
    text-transform: uppercase;
    letter-spacing: 0.4px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .stage-meta {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: var(--text-2);
    font-family: var(--mono);
    white-space: nowrap;
  }
  .stage-status {
    font-size: 9px;
  }
  .stage-status.ok {
    color: var(--green);
  }
  .stage-status.fail {
    color: var(--red);
  }
  .stage-empty {
    position: absolute;
    left: 0;
    right: 0;
    padding: 28px 12px;
    text-align: center;
    font-size: 11px;
    color: var(--text-3);
  }

  .row-line {
    position: absolute;
    left: 0;
    height: 1px;
    background: var(--border);
    opacity: 0.6;
  }

  .edges {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }
  .edge-label {
    font-size: 9px;
    fill: var(--yellow);
    font-family: var(--mono);
  }

  .turn {
    position: absolute;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 2px;
    padding: 6px 10px;
    box-sizing: border-box;
    background: var(--bg-2);
    border: 1.5px solid color-mix(in srgb, var(--role-color) 55%, transparent);
    border-radius: 8px;
    color: var(--text-0);
    text-align: left;
    cursor: pointer;
    font: inherit;
    overflow: hidden;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  .turn.compact {
    padding: 0;
    border-radius: 3px;
    background: color-mix(in srgb, var(--role-color) 35%, var(--bg-2));
  }
  .turn:hover {
    border-color: var(--role-color);
  }
  .turn.selected {
    border-color: var(--role-color);
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--role-color) 35%, transparent);
  }
  .turn.retry {
    border-style: dashed;
  }
  .turn.error {
    border-color: var(--red);
  }

  .turn-head {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 600;
    line-height: 1.1;
  }
  .role-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--role-color);
    flex-shrink: 0;
  }
  .flag {
    margin-left: auto;
    font-size: 11px;
    font-weight: 700;
    line-height: 1;
  }
  .retry-flag {
    color: var(--yellow);
  }
  .error-flag {
    color: var(--red);
  }
  .turn-raw {
    font-size: 9px;
    color: var(--text-2);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-family: var(--mono);
  }
  .turn-stats {
    display: flex;
    justify-content: space-between;
    gap: 6px;
    font-size: 10px;
    color: var(--text-1);
    font-family: var(--mono);
    white-space: nowrap;
  }
  .turn-stats.dim {
    color: var(--text-2);
  }
  .bad {
    color: var(--red);
  }

  .chart {
    position: absolute;
    left: 0;
    border-top: 1px solid var(--border);
    pointer-events: none;
    overflow: visible;
  }
  .chart .grid {
    stroke: var(--border);
    stroke-dasharray: 2 4;
  }
  .chart .baseline {
    stroke: var(--border);
  }
  .chart .tick {
    stroke: var(--border);
    opacity: 0.7;
  }
  .chart .tick-label {
    font-size: 9px;
    fill: var(--text-3);
    font-family: var(--mono);
  }
  .chart .retry-mark {
    stroke: var(--yellow);
    stroke-dasharray: 3 3;
    opacity: 0.55;
  }
  .chart .area {
    fill: color-mix(in srgb, var(--text-1) 10%, transparent);
  }
  .chart .line {
    fill: none;
    stroke: var(--text-1);
    stroke-width: 1.5;
  }
  .chart .pt {
    fill: var(--bg-1);
    stroke: var(--text-1);
    stroke-width: 1.2;
    pointer-events: auto;
    cursor: pointer;
  }
  .chart .pt:hover,
  .chart .pt.selected {
    fill: var(--text-0);
  }
  .chart .end-label {
    font-size: 10px;
    fill: var(--text-0);
    font-family: var(--mono);
    font-weight: 600;
  }
</style>
