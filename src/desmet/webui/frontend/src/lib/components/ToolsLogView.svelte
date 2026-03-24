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
