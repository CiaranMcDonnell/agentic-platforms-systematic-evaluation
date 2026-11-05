<script lang="ts">
  import { onMount } from 'svelte';
  import EChart from '../EChart.svelte';
  import { fetchResultRuns } from '../../api';
  import type { ResultRun } from '../../api';

  let { runId = null }: { runId?: string | null } = $props();

  const METRIC_LABELS: Record<string, string> = {
    tokens_total: 'Tokens',
    cost_usd: 'Cost (USD)',
    wall_clock_seconds: 'Wall clock (s)',
    llm_calls: 'LLM calls',
    prompt_tokens_per_call: 'Prompt tokens / LLM call',
  };

  let metric = $state('tokens_total');
  let log = $state(false);
  let runs = $state<ResultRun[]>([]);
  // Extra runs to compare against the selected one (one series per model).
  let compare = $state<string[]>([]);

  onMount(async () => {
    try {
      runs = (await fetchResultRuns()).runs;
    } catch {
      runs = [];
    }
  });

  let baseRun = $derived(runId ?? runs[0]?.run_id ?? null);

  let endpoint = $derived.by(() => {
    const params = new URLSearchParams({ metric, log: String(log) });
    const ids = [baseRun, ...compare.filter((r) => r !== baseRun)].filter(Boolean) as string[];
    if (ids.length) params.set('run_ids', ids.join(','));
    return `/api/dashboard/charts/spread?${params.toString()}`;
  });

  function toggle(id: string) {
    compare = compare.includes(id) ? compare.filter((r) => r !== id) : [...compare, id];
  }

  function runLabel(r: ResultRun): string {
    const d = r.started_at ? new Date(r.started_at).toLocaleDateString() : '';
    return `${d} · ${r.model ?? 'unknown model'}${r.note ? ` — ${r.note}` : ''}`;
  }
</script>

<div>
  <div class="spread-head">
    <h2 style="font-size: 14px; font-weight: 600;">Repeats and models</h2>
    <div class="controls">
      <label>
        <span class="text-muted">Metric:</span>
        <select class="input" bind:value={metric}>
          {#each Object.keys(METRIC_LABELS) as key}
            <option value={key}>{METRIC_LABELS[key]}</option>
          {/each}
        </select>
      </label>
      <label>
        <input type="checkbox" bind:checked={log} />
        <span class="text-muted">Log scale</span>
      </label>
      {#if runs.length > 1}
        <details class="compare">
          <summary class="input">Compare runs{compare.length ? ` (${compare.length})` : ''}</summary>
          <div class="compare-list">
            {#each runs.filter((r) => r.run_id !== baseRun) as r}
              <label>
                <input type="checkbox" checked={compare.includes(r.run_id)} onchange={() => toggle(r.run_id)} />
                {runLabel(r)}
              </label>
            {/each}
          </div>
        </details>
      {/if}
    </div>
  </div>
  <p class="text-muted hint">
    Median (large marker), range (line) and each repeat (hollow) per platform.
    Add runs on other models to compare platform × model.
  </p>
  {#key endpoint}
    <EChart {endpoint} height={400} />
  {/key}
</div>

<style>
  .spread-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 6px;
  }
  .controls {
    display: flex;
    align-items: center;
    gap: 14px;
    font-size: 12px;
    flex-wrap: wrap;
  }
  .controls label {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .controls select,
  .compare summary {
    padding: 4px 8px;
    font-size: 12px;
  }
  .compare {
    position: relative;
  }
  .compare summary {
    cursor: pointer;
    list-style: none;
  }
  .compare-list {
    position: absolute;
    right: 0;
    z-index: 10;
    margin-top: 4px;
    max-height: 280px;
    overflow-y: auto;
    min-width: 320px;
    padding: 8px;
    background: var(--bg-2);
    border: 1px solid var(--border);
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .hint {
    font-size: 11px;
    margin-bottom: 10px;
  }
</style>
