<script lang="ts">
  import type { ExecutionModel, ExecutionRoleSummary } from '../api';
  import { roleColor, roleLabel, stageLabel, formatDuration, formatTokens } from '../execution';

  let { model, roles = null }: { model: ExecutionModel; roles?: string[] | null } = $props();

  let rowRoles = $derived(model.role_order.filter((r) => (roles ?? model.summary.roles).includes(r)));

  function cell(stageKey: string, role: string): ExecutionRoleSummary | null {
    const stage = model.stages.find((s) => s.key === stageKey);
    return stage?.summary[role] ?? null;
  }
</script>

<table class="summary">
  <thead>
    <tr>
      <th class="role-col">Role</th>
      {#each model.stages as stage}
        <th>
          {stageLabel(stage.key)}
          <span class="th-meta">{#if stage.tokens}{formatTokens(stage.tokens)} tok ·&nbsp;{/if}{formatDuration(stage.duration_ms)}</span>
        </th>
      {/each}
      <th class="total-col">Total</th>
    </tr>
  </thead>
  <tbody>
    {#each rowRoles as role}
      {@const total = model.summary.by_role[role]}
      <tr>
        <td class="role-col" style="--role-color: {roleColor(role)}">
          <span class="role-dot"></span>{roleLabel(role)}
        </td>
        {#each model.stages as stage}
          {@const c = cell(stage.key, role)}
          <td>
            {#if c}
              <div class="line">
                {c.turns} turn{c.turns === 1 ? '' : 's'} · {c.llm_calls} LLM · {c.tool_calls} tool{c.tool_calls === 1 ? '' : 's'}
                {#if c.tool_failures}<span class="bad"> · {c.tool_failures} fail</span>{/if}
                {#if c.retries}<span class="warn"> · {c.retries} retry</span>{/if}
              </div>
              <div class="line dim">{c.tokens ? formatTokens(c.tokens) : '—'} tok · {formatDuration(c.duration_ms)}</div>
            {:else}
              <span class="dim">—</span>
            {/if}
          </td>
        {/each}
        <td class="total-col">
          {#if total}
            <div class="line">{total.turns} turns · {total.llm_calls} LLM · {total.tool_calls} tools</div>
            <div class="line dim">{total.tokens ? formatTokens(total.tokens) : '—'} tok · {formatDuration(total.duration_ms)}</div>
          {/if}
        </td>
      </tr>
    {/each}
  </tbody>
</table>

<style>
  .summary {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
  }
  th,
  td {
    text-align: left;
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }
  th {
    font-weight: 600;
    color: var(--text-1);
    text-transform: uppercase;
    letter-spacing: 0.4px;
    font-size: 10px;
    white-space: nowrap;
  }
  .th-meta {
    margin-left: 6px;
    font-family: var(--mono);
    text-transform: none;
    letter-spacing: 0;
    color: var(--text-2);
  }
  .role-col {
    font-weight: 600;
    color: var(--text-0);
    white-space: nowrap;
  }
  .total-col {
    border-left: 1px solid var(--border);
  }
  .role-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--role-color);
    margin-right: 8px;
    vertical-align: middle;
  }
  .line {
    white-space: nowrap;
    font-family: var(--mono);
    color: var(--text-0);
  }
  .dim {
    color: var(--text-2);
  }
  .bad {
    color: var(--red);
  }
  .warn {
    color: var(--yellow);
  }
</style>
