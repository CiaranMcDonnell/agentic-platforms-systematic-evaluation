<script lang="ts">
  import { fetchFrameworkMetrics } from '../../api';
  import type { FrameworkMetricsPlatform } from '../../api';

  let { runId = null }: { runId?: string | null } = $props();

  let platforms = $state<FrameworkMetricsPlatform[]>([]);

  $effect(() => {
    fetchFrameworkMetrics(runId)
      .then((fm) => (platforms = fm.platforms))
      .catch(() => (platforms = []));
  });

  const FM_KEYS = [
    'tokens_per_stage',
    'iteration_ratio',
    'first_action_latency_ms',
    'redundant_tool_call_rate',
    'tool_failure_rate',
    'framework_overhead_ms',
    'cost_usd',
    'total_tokens',
  ] as const;

  const FM_LABELS: Record<string, string> = {
    tokens_per_stage: 'Tokens / Stage',
    iteration_ratio: 'Iteration Ratio',
    first_action_latency_ms: 'First-Action Latency',
    redundant_tool_call_rate: 'Redundant Calls',
    tool_failure_rate: 'Tool Failure Rate',
    framework_overhead_ms: 'Framework Overhead',
    cost_usd: 'Cost (USD)',
    total_tokens: 'Total Tokens',
  };

  function fmFormat(key: string, val: number | null | undefined): string {
    if (val === null || val === undefined) return 'N/A';
    if (key === 'tokens_per_stage' || key === 'total_tokens') {
      return val.toLocaleString();
    }
    if (
      key === 'iteration_ratio' ||
      key === 'redundant_tool_call_rate' ||
      key === 'tool_failure_rate'
    ) {
      return (val * 100).toFixed(1) + '%';
    }
    if (key === 'first_action_latency_ms' || key === 'framework_overhead_ms') {
      return val.toLocaleString() + ' ms';
    }
    if (key === 'cost_usd') {
      return '$' + val.toFixed(4);
    }
    return String(val);
  }
</script>

{#if platforms.length > 0}
  <div class="card">
    <h2 style="font-size: 14px; font-weight: 600; margin-bottom: 16px;">
      Framework Metrics (per-stage averages)
    </h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            {#each platforms as p}
              <th style="text-align: right;">{p.platform_name}</th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each FM_KEYS as key}
            <tr>
              <td style="font-size: 12px; font-weight: 500;">{FM_LABELS[key]}</td>
              {#each platforms as p}
                <td class="mono" style="text-align: right; font-size: 12px;">
                  {fmFormat(key, p.metrics[key])}
                </td>
              {/each}
            </tr>
          {/each}
          <tr style="border-top: 1px solid var(--border);">
            <td style="font-size: 11px; color: var(--text-2);">Stories</td>
            {#each platforms as p}
              <td class="mono text-muted" style="text-align: right; font-size: 11px;">
                {p.story_count}
              </td>
            {/each}
          </tr>
        </tbody>
      </table>
    </div>
  </div>
{/if}
