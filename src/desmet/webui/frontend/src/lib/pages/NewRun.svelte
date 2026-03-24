<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchRuns, startRun } from '../api';
  import type { Run } from '../api';
  import { store } from '../data.svelte';
  import { currentPage, selectedRunId } from '../stores';
  import StatusBadge from '../components/StatusBadge.svelte';

  let recentRuns = $state<Run[]>([]);

  let selectedPlatforms = $state<string[]>([]);
  let selectedStories = $state<string[]>([]);
  let selectedDifficulties = $state<string[]>([]);
  let selectedStages = $state<string[]>([]);
  let model = $state('');
  let customModel = $state('');
  let dryRun = $state(false);
  let submitting = $state(false);
  let startError = $state<string | null>(null);

  let impl = $derived(store.platforms.filter(p => p.implemented));
  let notImpl = $derived(store.platforms.filter(p => !p.implemented));

  // Filter visible stories based on selected difficulties
  let filteredStories = $derived(
    selectedDifficulties.length
      ? store.stories.filter(s => selectedDifficulties.includes(s.difficulty))
      : store.stories
  );

  // Difficulty colour map
  const diffColour: Record<string, string> = {
    basic: 'var(--green)',
    intermediate: 'var(--yellow)',
    advanced: 'var(--red)',
  };

  onMount(async () => {
    const runsRes = await fetchRuns();
    const allRuns = (runsRes as any).runs || [];
    recentRuns = allRuns.slice(-5).reverse();
  });

  function togglePlatform(id: string) {
    // Only allow toggling implemented platforms
    if (!impl.find(p => p.id === id)) return;
    selectedPlatforms = selectedPlatforms.includes(id)
      ? selectedPlatforms.filter(x => x !== id)
      : [...selectedPlatforms, id];
  }

  function toggleItem(arr: string[], id: string): string[] {
    return arr.includes(id) ? arr.filter(x => x !== id) : [...arr, id];
  }

  // Clear story selections that no longer match when difficulty changes
  $effect(() => {
    if (selectedDifficulties.length) {
      const validIds = new Set(filteredStories.map(s => s.id));
      const pruned = selectedStories.filter(id => validIds.has(id));
      if (pruned.length !== selectedStories.length) {
        selectedStories = pruned;
      }
    }
  });

  function viewRun(id: string) {
    selectedRunId.set(id);
    currentPage.set('run-detail');
  }

  async function submit() {
    if (!selectedPlatforms.length) return;
    submitting = true;
    startError = null;
    try {
      const res = await startRun({
        platforms: selectedPlatforms,
        stories: selectedStories,
        difficulties: selectedDifficulties,
        stages: selectedStages,
        model: (model === '__custom__' ? customModel : model) || null,
        dry_run: dryRun,
      });
      if (res.run_id) {
        selectedRunId.set(res.run_id);
        currentPage.set('run-detail');
      } else if (res.error) {
        startError = res.error;
        if (res.active_run_id) {
          selectedRunId.set(res.active_run_id);
          currentPage.set('run-detail');
        }
      }
    } finally {
      submitting = false;
    }
  }
</script>

<div class="newrun">
  <h1 style="margin-bottom: 20px;">New Benchmark Run</h1>

  <!-- ── Row 1: Filter bar ──────────────────────────────────── -->
  <div class="filter-row">
    <div class="filter-group">
      <span class="filter-label">Difficulty</span>
      <div class="filter-pills">
        {#each store.config?.difficulty_levels || [] as d}
          <button
            class="toggle-pill {selectedDifficulties.includes(d) ? 'toggle-active' : ''}"
            onclick={() => selectedDifficulties = toggleItem(selectedDifficulties, d)}
          >
            <span class="toggle-dot {d}"></span>
            {d}
          </button>
        {/each}
      </div>
    </div>

    <div class="filter-divider"></div>

    <div class="filter-group">
      <span class="filter-label">Stages</span>
      <div class="filter-pills">
        {#each (store.config?.valid_stages || []).filter(s => s !== 'all') as s}
          <button
            class="toggle-pill {selectedStages.includes(s) ? 'toggle-active' : ''}"
            onclick={() => selectedStages = toggleItem(selectedStages, s)}
          >
            {s}
          </button>
        {/each}
      </div>
    </div>

    <div class="filter-divider"></div>

    <div class="filter-group" style="flex: 1; min-width: 200px;">
      <span class="filter-label">Model</span>
      <select class="input" style="max-width: 320px;" bind:value={model}>
        <option value="">Default ({store.config?.model})</option>
        {#each store.config?.available_models || [] as m}<option value={m}>{m}</option>{/each}
        <option value="__custom__">Custom model</option>
      </select>
    </div>
  </div>

  {#if model === '__custom__'}
    <div class="card" style="padding: 14px 20px;">
      <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
        <input
          id="custom-model"
          class="input"
          type="text"
          style="max-width: 360px;"
          placeholder="e.g. claude-opus-4-6 or openai/gpt-5.4"
          bind:value={customModel}
        />
        <div style="font-size: 12.5px; color: var(--text-2); line-height: 1.5;">
          Native: <code style="font-size: 12px;">claude-opus-4-6</code>, <code style="font-size: 12px;">gpt-5.4-2026-03-05</code>
          · OpenRouter: <code style="font-size: 12px;">vendor/model</code> — <a href="https://openrouter.ai/models" target="_blank" rel="noopener" style="color: var(--accent);">browse models</a>
        </div>
      </div>
    </div>
  {/if}

  <!-- ── Row 2: 3-column layout ─────────────────────────────── -->
  <div class="main-grid">
    <!-- Col 1: Platforms (all, with unavailable greyed) -->
    <div class="card main-col">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
        <h3 class="text-secondary" style="font-weight: 500;">
          Platforms
          <span class="count-badge">{selectedPlatforms.length}/{impl.length} ready</span>
        </h3>
        <div style="display: flex; gap: 6px;">
          <button class="btn btn-outline btn-sm" onclick={() => selectedPlatforms = impl.map(p => p.id)}>All</button>
          <button class="btn btn-outline btn-sm" onclick={() => selectedPlatforms = []}>None</button>
        </div>
      </div>

      <div style="display: flex; flex-direction: column; gap: 5px;">
        {#each impl as p}
          <div
            class="checkbox-card {selectedPlatforms.includes(p.id) ? 'selected' : ''}"
            onclick={() => togglePlatform(p.id)}
            onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') togglePlatform(p.id); }}
            role="button"
            tabindex="0"
          >
            <input type="checkbox" checked={selectedPlatforms.includes(p.id)} />
            <div style="flex: 1; min-width: 0;">
              <div style="font-weight: 500; font-size: 13px;">{p.name}</div>
              <div style="font-size: 11px; color: var(--text-2);">{p.category}</div>
            </div>
            <StatusBadge status={p.status} />
          </div>
        {/each}

        {#if notImpl.length}
          <div style="font-size: 10px; color: var(--text-2); text-transform: uppercase; letter-spacing: 0.06em; margin-top: 10px; padding-left: 2px;">
            Not available
          </div>
          {#each notImpl as p}
            <div class="checkbox-card disabled-card">
              <input type="checkbox" disabled checked={false} />
              <div style="flex: 1; min-width: 0;">
                <div style="font-weight: 500; font-size: 13px; color: var(--text-2);">{p.name}</div>
                <div style="font-size: 11px; color: var(--text-2); opacity: 0.6;">{p.category}</div>
              </div>
              <StatusBadge status={p.status} />
            </div>
          {/each}
        {/if}
      </div>
    </div>

    <!-- Col 2: Stories (richer cards) -->
    <div class="card main-col">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
        <h3 class="text-secondary" style="font-weight: 500;">
          Stories
          <span class="count-badge">
            {selectedStories.length ? `${selectedStories.length}/${filteredStories.length}` : `${filteredStories.length} total`}
          </span>
        </h3>
        {#if selectedStories.length}
          <button class="btn btn-outline btn-sm" onclick={() => selectedStories = []}>Clear</button>
        {:else}
          <span style="font-size: 11px; color: var(--text-2);">all included</span>
        {/if}
      </div>

      <div class="story-list">
        {#each filteredStories as s}
          <button
            class="story-card {selectedStories.includes(s.id) ? 'story-active' : ''}"
            onclick={() => selectedStories = toggleItem(selectedStories, s.id)}
          >
            <div class="story-header">
              <span class="story-id">{s.id}</span>
              <span class="story-diff-dot" style="background: {diffColour[s.difficulty] || 'var(--text-2)'}"></span>
              <span class="story-diff-label">{s.difficulty}</span>
            </div>
            <div class="story-title">{s.title}</div>
            {#if s.description}
              <div class="story-desc">{s.description}</div>
            {/if}
            <div class="story-meta">
              <span>{s.acceptance_criteria_count} criteria</span>
              <span>{Math.round(s.time_budget_seconds / 60)}m budget</span>
              {#if s.tags?.length}
                <span>{s.tags.length} tags</span>
              {/if}
            </div>
          </button>
        {/each}
        {#if !filteredStories.length}
          <div style="font-size: 13px; color: var(--text-2); padding: 20px 0; text-align: center;">
            No stories match the selected difficulty filter.
          </div>
        {/if}
      </div>
    </div>

    <!-- Col 3: Status + Recent Runs -->
    <div style="display: flex; flex-direction: column; gap: 16px;">
      <!-- API Key Status -->
      <div class="card">
        <h3 class="text-secondary" style="font-weight: 500; margin-bottom: 12px;">Provider Status</h3>
        <div style="display: flex; flex-direction: column; gap: 8px;">
          {#each ['openrouter', 'openai', 'anthropic', 'google'] as provider}
            <div class="status-row">
              <span class="status-dot {store.config?.api_keys_set?.includes(provider) ? 'dot-green' : 'dot-dim'}"></span>
              <span style="font-size: 13px; text-transform: capitalize;{store.config?.api_keys_set?.includes(provider) ? '' : ' color: var(--text-2);'}">{provider}</span>
              <span style="font-size: 11px; color: var(--text-2); margin-left: auto;">
                {store.config?.api_keys_set?.includes(provider) ? 'configured' : 'no key'}
              </span>
            </div>
          {/each}
          <div class="status-row" style="margin-top: 2px; padding-top: 8px; border-top: 1px solid var(--border);">
            <span class="status-dot {store.config?.langfuse_status === 'configured' ? 'dot-green' : 'dot-dim'}"></span>
            <span style="font-size: 13px;{store.config?.langfuse_status === 'configured' ? '' : ' color: var(--text-2);'}">Langfuse</span>
            <span style="font-size: 11px; color: var(--text-2); margin-left: auto;">{store.config?.langfuse_status || 'not set'}</span>
          </div>
          <div class="status-row">
            <span class="status-dot {store.config?.deploy_status === 'configured' ? 'dot-green' : store.config?.deploy_status === 'partially configured' ? 'dot-yellow' : 'dot-dim'}"></span>
            <span style="font-size: 13px;{store.config?.deploy_status === 'configured' ? '' : ' color: var(--text-2);'}">Deploy Target</span>
            <span style="font-size: 11px; color: var(--text-2); margin-left: auto;">{store.config?.deploy_status || 'not set'}</span>
          </div>
        </div>
      </div>

      <!-- Recent Runs -->
      <div class="card" style="flex: 1;">
        <h3 class="text-secondary" style="font-weight: 500; margin-bottom: 12px;">Recent Runs</h3>
        {#if recentRuns.length}
          <div style="display: flex; flex-direction: column; gap: 6px;">
            {#each recentRuns as r}
              <button
                class="run-row"
                onclick={() => viewRun(r.run_id)}
              >
                <span class="run-id mono">{r.run_id}</span>
                <span class="run-status badge badge-{r.status === 'completed' ? 'green' : r.status === 'failed' ? 'red' : r.status === 'running' ? 'yellow' : 'gray'}">
                  {r.status}
                </span>
                <span class="run-time">
                  {r.started_at ? new Date(r.started_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
                </span>
              </button>
            {/each}
          </div>
        {:else}
          <div style="font-size: 13px; color: var(--text-2); padding: 16px 0; text-align: center;">
            No runs yet
          </div>
        {/if}
      </div>
    </div>
  </div>

  <!-- ── Row 3: Submit bar ──────────────────────────────────── -->
  <div class="submit-bar">
    <div class="checkbox-card" style="flex-shrink: 0;" onclick={() => dryRun = !dryRun} onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') dryRun = !dryRun; }} role="button" tabindex="0">
      <input type="checkbox" checked={dryRun} />
      <div>
        <div style="font-weight: 500; font-size: 13px;">Dry Run</div>
      </div>
    </div>

    <div class="submit-summary">
      {selectedPlatforms.length} platform{selectedPlatforms.length !== 1 ? 's' : ''}
      · {selectedStories.length || 'all'} stor{selectedStories.length === 1 ? 'y' : 'ies'}
      · {selectedDifficulties.length ? selectedDifficulties.join(', ') : 'all difficulties'}
      · {selectedStages.length ? selectedStages.join(', ') : 'all stages'}
    </div>

    <button
      class="btn btn-primary"
      style="padding: 10px 28px; font-size: 14px; border-radius: 8px; flex-shrink: 0;"
      disabled={!selectedPlatforms.length || submitting}
      onclick={submit}
    >
      {submitting ? 'Starting...' : 'Start Benchmark Run'}
    </button>
  </div>

  {#if startError}
    <div class="start-error">{startError}</div>
  {/if}
</div>

<style>
  .newrun {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  /* ── Filter row ─────────────────────── */
  .filter-row {
    display: flex;
    align-items: center;
    gap: 20px;
    flex-wrap: wrap;
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 20px;
  }
  .filter-group {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .filter-label {
    font-size: 11px;
    color: var(--text-2);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 500;
    white-space: nowrap;
  }
  .filter-pills {
    display: flex;
    gap: 6px;
  }
  .filter-divider {
    width: 1px;
    height: 28px;
    background: var(--border);
    flex-shrink: 0;
  }

  /* ── Main 3-col grid ────────────────── */
  .main-grid {
    display: grid;
    grid-template-columns: 1fr 1.4fr 280px;
    gap: 16px;
    align-items: start;
  }
  .main-col {
    max-height: calc(100vh - 260px);
    overflow-y: auto;
  }
  @media (max-width: 1100px) {
    .main-grid {
      grid-template-columns: 1fr 1fr;
    }
    .main-grid > :nth-child(3) {
      grid-column: 1 / -1;
    }
  }
  @media (max-width: 750px) {
    .main-grid {
      grid-template-columns: 1fr;
    }
  }

  /* ── Disabled platform cards ────────── */
  .disabled-card {
    opacity: 0.45;
    cursor: default;
    pointer-events: none;
  }

  /* ── Story cards ────────────────────── */
  .story-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .story-card {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 10px 14px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: transparent;
    cursor: pointer;
    transition: all 0.12s ease;
    text-align: left;
    font-family: inherit;
    color: var(--text-1);
  }
  .story-card:hover {
    border-color: var(--border-hover);
    color: var(--text-0);
  }
  .story-card.story-active {
    border-color: var(--accent, #d4a853);
    background: rgba(212, 168, 83, 0.1);
    color: var(--text-0);
    box-shadow: 0 0 0 1px rgba(212, 168, 83, 0.25);
  }
  .story-header {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .story-id {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--text-2);
  }
  .story-active .story-id {
    color: var(--text-1);
  }
  .story-diff-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .story-diff-label {
    font-size: 11px;
    color: var(--text-2);
    text-transform: capitalize;
  }
  .story-title {
    font-size: 13px;
    font-weight: 500;
    line-height: 1.3;
  }
  .story-desc {
    font-size: 12px;
    color: var(--text-2);
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .story-meta {
    display: flex;
    gap: 10px;
    font-size: 11px;
    color: var(--text-2);
    margin-top: 2px;
  }

  /* ── Provider status rows ───────────── */
  .status-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .dot-green { background: var(--green); }
  .dot-yellow { background: var(--yellow, #f59e0b); }
  .dot-dim { background: var(--text-2); opacity: 0.4; }

  /* ── Recent run rows ────────────────── */
  .run-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: transparent;
    cursor: pointer;
    transition: border-color 0.12s ease;
    font-family: inherit;
    color: var(--text-0);
    text-align: left;
  }
  .run-row:hover {
    border-color: var(--border-hover);
  }
  .run-id {
    font-size: 12px;
    color: var(--text-1);
  }
  .run-time {
    font-size: 11px;
    color: var(--text-2);
    margin-left: auto;
  }

  /* ── Submit bar ─────────────────────── */
  .submit-bar {
    display: flex;
    align-items: center;
    gap: 16px;
    background: var(--bg-1);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 20px;
  }
  .submit-summary {
    flex: 1;
    font-size: 12.5px;
    color: var(--text-2);
    min-width: 0;
  }

  .start-error {
    margin-top: 8px;
    padding: 10px 16px;
    background: color-mix(in srgb, var(--error, #e53e3e) 10%, transparent);
    border: 1px solid var(--error, #e53e3e);
    border-radius: 6px;
    color: var(--error, #e53e3e);
    font-size: 13px;
  }

  /* ── Shared ─────────────────────────── */
  .count-badge {
    font-size: 11px;
    font-weight: 400;
    color: var(--text-2);
    margin-left: 6px;
  }

  /* ── Toggle pills ───────────────────── */
  .toggle-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-1);
    font-size: 13px;
    font-family: inherit;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.12s ease;
    text-transform: capitalize;
    white-space: nowrap;
  }
  .toggle-pill:hover {
    border-color: var(--border-hover);
    color: var(--text-0);
  }
  .toggle-pill.toggle-active {
    border-color: var(--accent, #d4a853);
    background: rgba(212, 168, 83, 0.15);
    color: var(--text-0);
    box-shadow: 0 0 0 1px rgba(212, 168, 83, 0.3);
  }
  .toggle-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .toggle-dot.basic { background: var(--green); }
  .toggle-dot.intermediate { background: var(--yellow); }
  .toggle-dot.advanced { background: var(--red); }
</style>
