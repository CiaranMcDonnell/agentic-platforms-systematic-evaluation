<script lang="ts">
  /**
   * Platform × story picker for the Scoring page.
   *
   * Every cell is one platform/story pair, marked with how the run went and
   * whether it has been scored, so the grid doubles as the scoring to-do
   * list. Once a pair is picked the grid folds into a one-line summary with
   * previous/next-unscored navigation.
   */
  import type { Platform, Story, StoryAvailability } from '../api';
  import { formatCost, formatDuration, formatTokens } from '../execution';

  let {
    platforms,
    stories,
    availability,
    selectedPlatform,
    selectedStory,
    onselect,
  }: {
    platforms: Platform[];
    stories: Story[];
    /** platform → story → run summary; null while loading or if it failed. */
    availability: Record<string, Record<string, StoryAvailability>> | null;
    selectedPlatform: string;
    selectedStory: string;
    onselect: (platformId: string, storyId: string) => void;
  } = $props();

  type Status = 'passed' | 'partial' | 'failed' | 'trace' | 'none' | 'unknown';
  type Cell = { pid: string; sid: string; a: StoryAvailability | null; status: Status; scored: 'all' | 'some' | 'none' };

  let expanded = $state(true);

  // Fold away once something is picked; reopen when the selection clears.
  $effect(() => {
    expanded = !(selectedPlatform && selectedStory);
  });

  let rows = $derived(
    platforms.filter((p) => p.implemented || Object.keys(availability?.[p.id] ?? {}).length > 0),
  );

  function cellOf(pid: string, sid: string): Cell {
    if (!availability) return { pid, sid, a: null, status: 'unknown', scored: 'none' };
    const a = availability[pid]?.[sid] ?? null;
    let status: Status = 'none';
    if (a && !a.repeats) status = 'trace';
    else if (a) status = a.passed === a.repeats ? 'passed' : a.passed ? 'partial' : 'failed';
    const scored = a && a.repeats ? (a.scored >= a.repeats ? 'all' : a.scored ? 'some' : 'none') : 'none';
    return { pid, sid, a, status, scored };
  }

  let grid = $derived(rows.map((p) => ({ p, cells: stories.map((s) => cellOf(p.id, s.id)) })));

  // Row-major: finish one platform before moving to the next.
  let order = $derived(grid.flatMap((r) => r.cells));
  let unscored = $derived(order.filter((c) => c.a && c.a.repeats > 0 && c.scored !== 'all'));
  let currentIndex = $derived(order.findIndex((c) => c.pid === selectedPlatform && c.sid === selectedStory));

  function neighbour(dir: 1 | -1): Cell | null {
    const n = order.length;
    if (!n) return null;
    const start = currentIndex === -1 ? (dir === 1 ? -1 : 0) : currentIndex;
    for (let k = 1; k <= n; k++) {
      const c = order[(((start + dir * k) % n) + n) % n];
      if (c.a && c.a.repeats > 0 && c.scored !== 'all' && c !== order[currentIndex]) return c;
    }
    return null;
  }

  let prevUnscored = $derived(neighbour(-1));
  let nextUnscored = $derived(neighbour(1));

  let current = $derived(selectedPlatform && selectedStory ? cellOf(selectedPlatform, selectedStory) : null);

  function rowProgress(pid: string): { run: number; scored: number } {
    const rowsA = Object.values(availability?.[pid] ?? {}).filter((a) => a.repeats > 0);
    return { run: rowsA.length, scored: rowsA.filter((a) => a.scored >= a.repeats).length };
  }

  function pick(c: Cell) {
    if (c.status === 'none') return;
    expanded = false;
    onselect(c.pid, c.sid);
  }

  const MARK: Record<Status, string> = { passed: '✓', partial: '◐', failed: '✗', trace: '○', none: '·', unknown: '?' };

  function statusText(c: Cell): string {
    const a = c.a;
    if (c.status === 'unknown') return 'status unknown';
    if (!a) return 'not run';
    if (!a.repeats) return 'trace from another run';
    if (c.status === 'passed') return a.repeats > 1 ? `passed ${a.repeats}/${a.repeats}` : 'passed';
    if (c.status === 'partial') return `${a.passed}/${a.repeats} passed`;
    return a.repeats > 1 ? `failed 0/${a.repeats}` : 'failed';
  }

  function scoredText(c: Cell): string {
    const a = c.a;
    if (!a || !a.repeats) return '';
    if (c.scored === 'all') return a.repeats > 1 ? `scored ${a.scored}/${a.repeats}` : 'scored';
    return c.scored === 'some' ? `scored ${a.scored}/${a.repeats}` : 'not scored';
  }

  function usageText(a: StoryAvailability | null): string {
    if (!a || !a.repeats) return '';
    const parts = [
      `${a.repeats > 1 ? 'avg ' : ''}${formatDuration((a.wall_clock_seconds ?? 0) * 1000)}`,
      `${formatTokens(Math.round(a.tokens ?? 0))} tok`,
    ];
    if (a.cost_usd !== null) parts.push(formatCost(a.cost_usd));
    if (!a.has_trace) parts.push('no trace on disk');
    return parts.join(' · ');
  }

  function cellTitle(p: Platform, s: Story, c: Cell): string {
    const bits = [statusText(c), scoredText(c), usageText(c.a)].filter(Boolean);
    return `${p.name} — ${s.id} ${s.title}\n${bits.join(' · ')}`;
  }

  function platformName(id: string): string {
    return platforms.find((p) => p.id === id)?.name ?? id;
  }

  function storyTitle(id: string): string {
    return stories.find((s) => s.id === id)?.title ?? id;
  }
</script>

{#if expanded || !current}
  <div class="picker">
    <div class="picker-head">
      <span class="picker-title">Choose a run to score</span>
      {#if availability}
        <span class="picker-meta">{unscored.length} left to score</span>
      {/if}
      {#if current}
        <button class="link" onclick={() => (expanded = false)}>Collapse</button>
      {/if}
    </div>
    <div class="grid-scroll">
      <table class="grid">
        <thead>
          <tr>
            <th class="corner"></th>
            {#each stories as s (s.id)}
              <th class="story-col" title="{s.id} — {s.title} ({s.difficulty})">{s.id}</th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each grid as { p, cells } (p.id)}
            {@const prog = rowProgress(p.id)}
            <tr>
              <th class="platform-row">
                <span class="pname">{p.name}</span>
                {#if availability}
                  <span class="pmeta">{prog.scored}/{prog.run}</span>
                {/if}
              </th>
              {#each cells as c, i (c.sid)}
                <td>
                  <button
                    class="cell {c.status}"
                    class:selected={c.pid === selectedPlatform && c.sid === selectedStory}
                    disabled={c.status === 'none'}
                    title={cellTitle(p, stories[i], c)}
                    aria-label={cellTitle(p, stories[i], c)}
                    onclick={() => pick(c)}
                  >
                    <span class="mark">{MARK[c.status]}</span>
                    {#if c.a?.repeats}
                      <span class="scored-dot {c.scored}"></span>
                    {/if}
                  </button>
                </td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <div class="legend">
      <span><span class="lm passed">✓</span> passed</span>
      <span><span class="lm partial">◐</span> some repeats passed</span>
      <span><span class="lm failed">✗</span> failed</span>
      <span><span class="lm trace">○</span> trace from another run</span>
      <span><span class="lm">·</span> not run</span>
      <span class="sep"></span>
      <span><span class="scored-dot all inline"></span> scored</span>
      <span><span class="scored-dot some inline"></span> partly scored</span>
      <span><span class="scored-dot none inline"></span> not scored</span>
      <span class="sep"></span>
      <span class="dim">Row count = scored / run</span>
    </div>
  </div>
{:else}
  <div class="bar">
    <span class="bar-mark {current.status}">{MARK[current.status]}</span>
    <span class="crumb">
      <strong>{platformName(current.pid)}</strong>
      <span class="dim">›</span>
      <strong>{current.sid}</strong>
      <span class="title">{storyTitle(current.sid)}</span>
    </span>
    <span class="facts">
      <span class={current.status}>{statusText(current)}</span>
      {#if scoredText(current)}
        <span class:ok={current.scored === 'all'} class:warn={current.scored !== 'all'}>· {scoredText(current)}</span>
      {/if}
      {#if usageText(current.a)}<span class="dim">· {usageText(current.a)}</span>{/if}
    </span>
    <span class="bar-actions">
      <button
        class="nav"
        disabled={!prevUnscored}
        title={prevUnscored ? `${platformName(prevUnscored.pid)} › ${prevUnscored.sid}` : 'Nothing else to score'}
        onclick={() => prevUnscored && pick(prevUnscored)}>‹ Prev unscored</button
      >
      <button
        class="nav"
        disabled={!nextUnscored}
        title={nextUnscored ? `${platformName(nextUnscored.pid)} › ${nextUnscored.sid}` : 'Nothing else to score'}
        onclick={() => nextUnscored && pick(nextUnscored)}>Next unscored ›</button
      >
      <span class="dim left">{unscored.length} left</span>
      <button class="nav primary" onclick={() => (expanded = true)}>Change</button>
    </span>
  </div>
{/if}

<style>
  .picker {
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 28px;
  }
  .picker-head {
    display: flex;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 10px;
  }
  .picker-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-0);
  }
  .picker-meta {
    font-size: 11px;
    color: var(--text-2);
    font-family: var(--mono);
  }
  .link {
    margin-left: auto;
    background: none;
    border: none;
    color: var(--text-2);
    font: inherit;
    font-size: 12px;
    cursor: pointer;
  }
  .link:hover {
    color: var(--text-0);
  }

  .grid-scroll {
    overflow-x: auto;
  }
  .grid {
    border-collapse: separate;
    border-spacing: 3px;
  }
  .grid th {
    font-weight: 500;
    font-size: 11px;
    color: var(--text-2);
    white-space: nowrap;
  }
  .story-col {
    font-family: var(--mono);
    padding: 0 0 4px;
    text-align: center;
    min-width: 46px;
  }
  .platform-row {
    text-align: left;
    padding-right: 10px;
  }
  .pname {
    color: var(--text-0);
    font-size: 12px;
  }
  .pmeta {
    margin-left: 8px;
    font-family: var(--mono);
    font-size: 10px;
    color: var(--text-3);
  }
  .grid td {
    padding: 0;
  }

  .cell {
    position: relative;
    width: 46px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid transparent;
    border-radius: 5px;
    background: var(--bg-2);
    color: var(--text-3);
    font: inherit;
    font-size: 13px;
    cursor: pointer;
    transition: border-color 0.12s, transform 0.12s;
  }
  .cell:hover:not(:disabled) {
    border-color: var(--border-hover);
  }
  .cell:disabled {
    background: transparent;
    cursor: default;
  }
  .cell.passed {
    background: color-mix(in srgb, var(--green) 16%, var(--bg-2));
    color: var(--green);
  }
  .cell.partial {
    background: color-mix(in srgb, var(--yellow) 16%, var(--bg-2));
    color: var(--yellow);
  }
  .cell.failed {
    background: color-mix(in srgb, var(--red) 16%, var(--bg-2));
    color: var(--red);
  }
  .cell.trace {
    border: 1px dashed var(--border-hover);
    color: var(--text-2);
  }
  .cell.unknown {
    color: var(--text-2);
  }
  .cell.selected {
    border-color: var(--text-0);
    box-shadow: 0 0 0 1px var(--text-0);
  }
  .mark {
    line-height: 1;
  }

  .scored-dot {
    position: absolute;
    right: 4px;
    bottom: 4px;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    box-sizing: border-box;
  }
  .scored-dot.all {
    background: var(--blue);
  }
  .scored-dot.some {
    border: 1.5px solid var(--blue);
    background: linear-gradient(90deg, var(--blue) 50%, transparent 50%);
  }
  .scored-dot.none {
    border: 1.5px solid var(--text-3);
  }
  .scored-dot.inline {
    position: static;
    display: inline-block;
    vertical-align: middle;
    margin-right: 2px;
  }

  .legend {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
    margin-top: 10px;
    font-size: 11px;
    color: var(--text-2);
  }
  .legend .sep {
    width: 1px;
    height: 12px;
    background: var(--border);
  }
  .lm {
    display: inline-block;
    width: 14px;
    text-align: center;
    color: var(--text-3);
  }
  .lm.passed {
    color: var(--green);
  }
  .lm.partial {
    color: var(--yellow);
  }
  .lm.failed {
    color: var(--red);
  }
  .lm.trace {
    color: var(--text-2);
  }

  .bar {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    padding: 8px 12px;
    margin-bottom: 28px;
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: 12px;
  }
  .bar-mark {
    font-size: 14px;
    width: 18px;
    text-align: center;
    color: var(--text-2);
  }
  .bar-mark.passed,
  .facts .passed {
    color: var(--green);
  }
  .bar-mark.partial,
  .facts .partial {
    color: var(--yellow);
  }
  .bar-mark.failed,
  .facts .failed {
    color: var(--red);
  }
  .crumb {
    display: flex;
    align-items: baseline;
    gap: 6px;
    color: var(--text-0);
    min-width: 0;
  }
  .crumb .title {
    color: var(--text-1);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 320px;
  }
  .facts {
    display: flex;
    gap: 5px;
    font-family: var(--mono);
    font-size: 11px;
    color: var(--text-1);
  }
  .facts .ok {
    color: var(--blue);
  }
  .facts .warn {
    color: var(--yellow);
  }
  .bar-actions {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .nav {
    background: none;
    border: 1px solid var(--border);
    border-radius: 5px;
    color: var(--text-1);
    font: inherit;
    font-size: 12px;
    padding: 4px 10px;
    cursor: pointer;
  }
  .nav:hover:not(:disabled) {
    color: var(--text-0);
    border-color: var(--border-hover);
  }
  .nav:disabled {
    color: var(--text-3);
    cursor: default;
  }
  .nav.primary {
    background: var(--bg-3);
    color: var(--text-0);
  }
  .left {
    font-family: var(--mono);
    font-size: 11px;
  }
  .dim {
    color: var(--text-2);
  }
</style>
