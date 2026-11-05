<script lang="ts">
  import type { ExecutionTurn, ExecutionStep } from '../api';
  import { formatContent } from '../format';
  import { roleColor, roleLabel, stageLabel, formatDuration, formatTokens } from '../execution';

  let { turn, onclose }: { turn: ExecutionTurn | null; onclose: () => void } = $props();

  let openStepId = $state<string | null>(null);

  $effect(() => {
    // Collapse any open step when the selected turn changes.
    if (turn) openStepId = null;
  });

  function stepStat(step: ExecutionStep): string {
    if (step.kind === 'llm') {
      return step.tokens_in || step.tokens_out
        ? `${formatTokens(step.tokens_in)}↑ ${formatTokens(step.tokens_out)}↓`
        : formatDuration(step.duration_ms);
    }
    return formatDuration(step.duration_ms);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (turn && e.key === 'Escape') onclose();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if turn}
  <div class="drawer" role="complementary">
    <div class="drawer-header" style="--role-color: {roleColor(turn.role)}">
      <div>
        <div class="drawer-title">
          <span class="role-dot"></span>
          <span>{roleLabel(turn.role)}</span>
          {#if turn.is_retry}<span class="tag warn">retry</span>{/if}
          {#if turn.error}<span class="tag bad">error</span>{/if}
        </div>
        <div class="drawer-sub">
          {stageLabel(turn.stage_key)} · <span class="mono">{turn.raw_name}</span>
        </div>
      </div>
      <button class="close" onclick={onclose} aria-label="Close">&times;</button>
    </div>

    <div class="drawer-stats">
      <div><span class="k">LLM</span><span class="v">{turn.llm_calls}</span></div>
      <div><span class="k">Tools</span><span class="v" class:bad={turn.tool_failures > 0}>{turn.tool_calls}{turn.tool_failures ? ` / ${turn.tool_failures} fail` : ''}</span></div>
      <div><span class="k">Tokens</span><span class="v">{formatTokens(turn.tokens_in)}↑ {formatTokens(turn.tokens_out)}↓</span></div>
      <div><span class="k">Time</span><span class="v">{formatDuration(turn.duration_ms)}</span></div>
    </div>

    {#if turn.error}
      <div class="error-box">{turn.error}</div>
    {/if}

    <div class="steps">
      {#each turn.steps as step, i (step.id)}
        {@const open = openStepId === step.id}
        <div class="step" class:open class:failed={step.success === false}>
          <button type="button" class="step-row" onclick={() => (openStepId = open ? null : step.id)}>
            <span class="step-idx">{i + 1}</span>
            <span class="kind" class:llm={step.kind === 'llm'} class:tool={step.kind === 'tool'}>{step.kind === 'llm' ? 'LLM' : 'TOOL'}</span>
            <span class="step-name" title={step.raw_name}>{step.kind === 'llm' ? (step.model ?? step.name) : step.name}</span>
            {#if step.success === false}<span class="tag bad">fail</span>{/if}
            <span class="step-stat">{stepStat(step)}</span>
          </button>
          {#if open}
            <div class="step-body">
              {#if step.error}<div class="error-box">{step.error}</div>{/if}
              {#if step.input}
                <div class="io-label">Input</div>
                <pre class="io">{formatContent(step.input)}</pre>
              {/if}
              {#if step.output}
                <div class="io-label">Output</div>
                <pre class="io">{formatContent(step.output)}</pre>
              {/if}
              {#if !step.input && !step.output}
                <div class="dim">No payload captured for this step.</div>
              {/if}
              <div class="raw">raw: <span class="mono">{step.raw_type}:{step.raw_name}</span></div>
            </div>
          {/if}
        </div>
      {/each}
      {#if turn.steps.length === 0}
        <div class="dim" style="padding: 12px;">No steps recorded.</div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .drawer {
    width: 360px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    max-height: 640px;
  }
  .drawer-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 12px 14px;
    border-bottom: 1px solid var(--border);
  }
  .drawer-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-0);
  }
  .drawer-sub {
    margin-top: 4px;
    font-size: 11px;
    color: var(--text-2);
  }
  .role-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: var(--role-color);
  }
  .close {
    background: none;
    border: none;
    color: var(--text-2);
    font-size: 18px;
    cursor: pointer;
    line-height: 1;
  }
  .close:hover {
    color: var(--text-0);
  }
  .drawer-stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 6px;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
  }
  .drawer-stats .k {
    display: block;
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    color: var(--text-2);
  }
  .drawer-stats .v {
    font-size: 11px;
    font-family: var(--mono);
    color: var(--text-0);
  }
  .steps {
    overflow-y: auto;
    flex: 1;
  }
  .step {
    border-bottom: 1px solid var(--border);
  }
  .step.failed .step-row {
    background: color-mix(in srgb, var(--red) 6%, transparent);
  }
  .step-row {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: none;
    border: none;
    color: var(--text-0);
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  .step-row:hover {
    background: rgba(255, 255, 255, 0.04);
  }
  .step-idx {
    font-size: 9px;
    color: var(--text-3);
    width: 16px;
    text-align: right;
    font-family: var(--mono);
  }
  .kind {
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 0.5px;
    padding: 1px 5px;
    border-radius: 3px;
    background: color-mix(in srgb, var(--text-2) 20%, transparent);
    color: var(--text-2);
  }
  .kind.llm {
    background: color-mix(in srgb, var(--blue) 20%, transparent);
    color: var(--blue);
  }
  .kind.tool {
    background: color-mix(in srgb, var(--green) 20%, transparent);
    color: var(--green);
  }
  .step-name {
    flex: 1;
    font-size: 11px;
    font-family: var(--mono);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .step-stat {
    font-size: 10px;
    color: var(--text-2);
    font-family: var(--mono);
    white-space: nowrap;
  }
  .step-body {
    padding: 6px 12px 12px 36px;
  }
  .io-label {
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    color: var(--text-2);
    margin: 6px 0 4px;
  }
  .io {
    margin: 0;
    padding: 8px;
    background: var(--bg-0);
    border-radius: 4px;
    font-size: 10.5px;
    line-height: 1.45;
    color: var(--text-1);
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 220px;
    overflow: auto;
  }
  .raw {
    margin-top: 8px;
    font-size: 9px;
    color: var(--text-3);
  }
  .tag {
    font-size: 9px;
    padding: 1px 5px;
    border-radius: 3px;
    font-weight: 600;
  }
  .tag.warn {
    background: color-mix(in srgb, var(--yellow) 20%, transparent);
    color: var(--yellow);
  }
  .tag.bad {
    background: color-mix(in srgb, var(--red) 20%, transparent);
    color: var(--red);
  }
  .error-box {
    margin: 8px 14px;
    padding: 8px;
    border-radius: 4px;
    background: color-mix(in srgb, var(--red) 10%, transparent);
    color: var(--red);
    font-size: 11px;
    white-space: pre-wrap;
  }
  .bad {
    color: var(--red);
  }
  .dim {
    color: var(--text-2);
    font-size: 11px;
  }
  .mono {
    font-family: var(--mono);
  }
</style>
