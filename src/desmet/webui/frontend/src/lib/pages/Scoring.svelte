<script lang="ts">
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { scoringTarget } from '../stores';
  import {
    fetchRubric, fetchStoryScore, submitScore,
    fetchLangSmithStatus,
  } from '../api';
  import type { ScoringRubric, StoryScoreData } from '../api';
  import { store } from '../data.svelte';
  import TraceViewer from '../components/TraceViewer.svelte';
  import LangSmithTraceViewer from '../components/LangSmithTraceViewer.svelte';

  let rubric = $state<ScoringRubric | null>(null);

  let selectedPlatform = $state('');
  let selectedStory = $state('');
  let scoreData = $state<StoryScoreData | null>(null);
  let scores = $state<Record<string, number>>({});
  let notes = $state<Record<string, string>>({});
  let saving = $state(false);
  let saveMsg = $state('');
  let loadingScore = $state(false);
  let activeTab = $state<'langfuse' | 'langsmith'>('langfuse');
  let langsmithAvailable = $state<boolean | null>(null);

  onMount(async () => {
    const rub = await fetchRubric();
    rubric = rub;
    // init scores
    if (rubric) {
      for (const dim of rubric.dimensions) {
        scores[dim] = 0;
        notes[dim] = '';
      }
    }
    // Pre-select from navigation hint (e.g. "Score this" from Story Detail)
    const target = get(scoringTarget);   // get() reads store value imperatively
    if (target) {
      selectedPlatform = target.platform_id;
      selectedStory = target.story_id;
      scoringTarget.set(null);
      await loadScore();
    }
  });

  async function loadScore() {
    if (!selectedPlatform || !selectedStory) return;
    saveMsg = '';
    loadingScore = true;
    scoreData = null;
    scoreData = await fetchStoryScore(selectedPlatform, selectedStory);
    loadingScore = false;
    // Lazy-check LangSmith only when relevant (langgraph + has run ID)
    if (selectedPlatform === 'langgraph' && scoreData?.langsmith_run_id && langsmithAvailable === null) {
      fetchLangSmithStatus().then(s => langsmithAvailable = s.available).catch(() => langsmithAvailable = false);
    }
    if (scoreData?.scored && scoreData.scores) {
      scores = { ...scoreData.scores };
      notes = { ...(scoreData.notes || {}) };
    } else if (rubric) {
      for (const dim of rubric.dimensions) {
        scores[dim] = 0;
        notes[dim] = '';
      }
    }
  }

  async function handleSave() {
    saving = true;
    saveMsg = '';
    try {
      await submitScore({
        platform_id: selectedPlatform,
        story_id: selectedStory,
        scores,
        notes,
      });
      saveMsg = 'Saved';
    } catch {
      saveMsg = 'Error saving';
    }
    saving = false;
  }

  const dimLabels: Record<string, string> = {
    pipeline_completeness: 'Pipeline Completeness',
    tool_integration: 'Tool Integration',
    error_recovery: 'Error Recovery',
    time_efficiency: 'Time Efficiency',
    autonomy: 'Autonomy',
    trace_quality: 'Trace Quality',
  };
</script>

<div>
  <h1 style="margin-bottom: 28px;">Scoring</h1>

  <!-- Selectors -->
  <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 28px;">
    <div>
      <label class="label" for="score-platform">Platform</label>
      <select id="score-platform" class="input" bind:value={selectedPlatform} onchange={loadScore}>
        <option value="">Select platform…</option>
        {#each store.platforms as p}
          <option value={p.id}>{p.name}</option>
        {/each}
      </select>
    </div>
    <div>
      <label class="label" for="score-story">Story</label>
      <select id="score-story" class="input" bind:value={selectedStory} onchange={loadScore}>
        <option value="">Select story…</option>
        {#each store.stories as s}
          <option value={s.id}>{s.title}</option>
        {/each}
      </select>
    </div>
  </div>

  {#if scoreData && rubric}
    <!-- Execution Evidence -->
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 28px;">
      <div class="card">
        <div class="stat-label">Wall Clock</div>
        <div class="stat-number">{scoreData.wall_clock_seconds?.toFixed(1) ?? '—'}s</div>
      </div>
      <div class="card">
        <div class="stat-label">Iterations</div>
        <div class="stat-number">{scoreData.iterations ?? '—'}</div>
      </div>
      <div class="card">
        <div class="stat-label">Tool Calls</div>
        <div class="stat-number">{scoreData.tool_calls ?? '—'}</div>
      </div>
      <div class="card">
        <div class="stat-label">Success</div>
        <div class="stat-number">
          {#if scoreData.success === true}
            <span style="color: var(--green);">Yes</span>
          {:else if scoreData.success === false}
            <span style="color: var(--red);">No</span>
          {:else}
            —
          {/if}
        </div>
      </div>
    </div>

    <!-- Rubric form -->
    <div class="card" style="margin-bottom: 28px;">
      <h2 style="font-size: 14px; font-weight: 600; margin-bottom: 20px;">DESMET Rubric (0–3)</h2>
      {#each rubric.dimensions as dim}
        <div style="margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <span style="font-size: 13px; font-weight: 500;">{dimLabels[dim] || dim}</span>
            <span class="mono" style="font-size: 14px; font-weight: 600; color: var(--text-0);">{scores[dim]}</span>
          </div>

          <!-- Level descriptions -->
          <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; margin-bottom: 8px;">
            {#each [0, 1, 2, 3] as lvl}
              <button
                class="score-level"
                class:active={scores[dim] === lvl}
                onclick={() => scores[dim] = lvl}
              >
                <span class="score-level-num">{lvl}</span>
                <span class="score-level-desc">{rubric.rubric[dim]?.[String(lvl)] || ''}</span>
              </button>
            {/each}
          </div>

          <input
            type="text"
            class="input"
            placeholder="Notes (optional)…"
            bind:value={notes[dim]}
            style="font-size: 12px;"
          />
        </div>
      {/each}

      <div style="display: flex; align-items: center; gap: 12px; margin-top: 16px;">
        <button class="btn btn-primary" onclick={handleSave} disabled={saving}>
          {saving ? 'Saving…' : 'Save Scores'}
        </button>
        {#if saveMsg}
          <span style="font-size: 12px; color: {saveMsg === 'Saved' ? 'var(--green)' : 'var(--red)'};">{saveMsg}</span>
        {/if}
      </div>
    </div>

    <!-- Trace -->
    {#if scoreData.langfuse_trace_id || scoreData.trace?.messages?.length}
      {@const showLangSmithTab =
        selectedPlatform === 'langgraph' &&
        !!scoreData.langsmith_run_id &&
        langsmithAvailable === true}
      <div>
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
          <h2 style="font-size: 14px; font-weight: 600;">Execution Trace</h2>
          {#if showLangSmithTab}
            <div class="trace-tabs">
              <button
                class="trace-tab"
                class:active={activeTab === 'langfuse'}
                onclick={() => activeTab = 'langfuse'}
              >Langfuse Trace</button>
              <button
                class="trace-tab"
                class:active={activeTab === 'langsmith'}
                onclick={() => activeTab = 'langsmith'}
              >LangSmith Graph</button>
            </div>
          {/if}
        </div>

        {#if showLangSmithTab && activeTab === 'langsmith'}
          <LangSmithTraceViewer runId={scoreData.langsmith_run_id!} />
        {:else if scoreData.langfuse_trace_id}
          <TraceViewer langfuseTraceId={scoreData.langfuse_trace_id} />
        {:else if scoreData.trace?.messages?.length}
          <TraceViewer messages={scoreData.trace.messages} />
        {/if}
      </div>
    {/if}
  {:else if loadingScore}
    <div class="card" style="padding: 48px; color: var(--text-2); text-align: center;">Loading score data…</div>
  {:else if selectedPlatform && selectedStory && scoreData && !scoreData.found}
    <div class="card" style="padding: 48px; color: var(--text-2); text-align: center;">
      No execution data found for this platform/story combination.
    </div>
  {:else if !selectedPlatform || !selectedStory}
    <div class="card" style="padding: 48px; color: var(--text-2); text-align: center;">
      Select a platform and story above to begin scoring.
    </div>
  {/if}
</div>

<style>
  .score-level {
    display: flex; flex-direction: column; gap: 2px;
    padding: 8px; border-radius: 4px; cursor: pointer;
    border: 1px solid var(--border); background: var(--bg-1);
    text-align: left; transition: all 0.15s;
  }
  .score-level:hover { border-color: var(--border-hover); }
  .score-level.active { border-color: var(--text-0); background: var(--bg-2); }
  .score-level-num { font-family: var(--mono); font-size: 12px; font-weight: 700; color: var(--text-0); }
  .score-level-desc { font-size: 10px; color: var(--text-2); line-height: 1.3; }
  .trace-tabs {
    display: flex;
    gap: 4px;
    background: var(--bg-2);
    border-radius: 6px;
    padding: 3px;
  }
  .trace-tab {
    padding: 5px 14px;
    font-size: 12px;
    font-family: var(--sans);
    font-weight: 500;
    border: none;
    border-radius: 4px;
    background: transparent;
    color: var(--text-2);
    cursor: pointer;
    transition: background 0.1s, color 0.1s;
  }
  .trace-tab.active {
    background: var(--bg-0, #fff);
    color: var(--text-0);
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }
</style>
