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
    flatten(traceData.observations, origin)
      .filter(s => s.duration_ms >= 10)  // hide sub-10ms wrapper noise
      .sort((a, b) => a.start_rel_ms - b.start_rel_ms)
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

  <!-- Timeline body (grid + rows) -->
  <div class="tl-body">
    <div class="tl-grid">
      <div class="grid-line" style="left:0%"></div>
      <div class="grid-line" style="left:25%"></div>
      <div class="grid-line" style="left:50%"></div>
      <div class="grid-line" style="left:75%"></div>
      <div class="grid-line" style="left:100%"></div>
    </div>

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
  .tl-body { position: relative; }

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
    position: absolute;
    top: 0;
    left: 140px;
    right: 100px;
    bottom: 0;
    pointer-events: none;
  }

  .grid-line {
    position: absolute;
    top: 0;
    bottom: 0;
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
