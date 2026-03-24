<script lang="ts">
  import { onMount } from 'svelte';
  import { fetchStories } from '../api';
  import type { Story } from '../api';

  let stories = $state<Story[]>([]);
  let diffFilter = $state('all');
  let search = $state('');
  let tagFilter = $state<string | null>(null);
  let expandedId = $state<string | null>(null);

  // All unique tags across stories
  let allTags = $derived(
    [...new Set(stories.flatMap(s => s.tags || []))].sort()
  );

  // Filtered stories
  let filtered = $derived(
    stories.filter(s => {
      if (diffFilter !== 'all' && s.difficulty !== diffFilter) return false;
      if (tagFilter && !(s.tags || []).includes(tagFilter)) return false;
      if (search) {
        const q = search.toLowerCase();
        return (
          s.id.toLowerCase().includes(q) ||
          s.title.toLowerCase().includes(q) ||
          s.description.toLowerCase().includes(q)
        );
      }
      return true;
    })
  );

  // Stats
  let stats = $derived({
    total: stories.length,
    basic: stories.filter(s => s.difficulty === 'basic').length,
    intermediate: stories.filter(s => s.difficulty === 'intermediate').length,
    advanced: stories.filter(s => s.difficulty === 'advanced').length,
  });

  const diffColors: Record<string, string> = {
    basic: '#4ade80', intermediate: '#facc15', advanced: '#f87171'
  };

  function toggleExpand(id: string) {
    expandedId = expandedId === id ? null : id;
  }

  function formatTime(seconds: number): string {
    if (seconds >= 3600) return `${(seconds / 3600).toFixed(1)}h`;
    if (seconds >= 60) return `${Math.round(seconds / 60)}m`;
    return `${seconds}s`;
  }

  onMount(async () => {
    const res = await fetchStories();
    stories = (res as any).stories || [];
  });
</script>

<div>
  <h1 style="margin-bottom: 24px;">User Stories</h1>

  <!-- Stats bar -->
  <div class="stats-row">
    <div class="stat-chip">
      <span class="stat-chip-num">{stats.total}</span>
      <span class="stat-chip-label">Total</span>
    </div>
    <div class="stat-chip">
      <span class="stat-chip-num" style="color: {diffColors.basic};">{stats.basic}</span>
      <span class="stat-chip-label">Basic</span>
    </div>
    <div class="stat-chip">
      <span class="stat-chip-num" style="color: {diffColors.intermediate};">{stats.intermediate}</span>
      <span class="stat-chip-label">Intermediate</span>
    </div>
    <div class="stat-chip">
      <span class="stat-chip-num" style="color: {diffColors.advanced};">{stats.advanced}</span>
      <span class="stat-chip-label">Advanced</span>
    </div>
  </div>

  <!-- Search + filters -->
  <div class="filter-bar">
    <input
      type="text"
      class="input search-input"
      placeholder="Search stories..."
      bind:value={search}
    />
    <div class="filter-group">
      {#each ['all', 'basic', 'intermediate', 'advanced'] as d}
        <button
          class="btn btn-sm {diffFilter === d ? 'btn-primary' : 'btn-outline'}"
          style="text-transform: capitalize;"
          onclick={() => diffFilter = d}
        >{d}</button>
      {/each}
    </div>
  </div>

  <!-- Tag pills -->
  {#if allTags.length > 0}
    <div class="tag-bar">
      <span class="tag-bar-label">Tags:</span>
      {#each allTags as tag}
        <button
          class="tag-pill"
          class:active={tagFilter === tag}
          onclick={() => tagFilter = tagFilter === tag ? null : tag}
        >{tag}</button>
      {/each}
      {#if tagFilter}
        <button class="tag-clear" onclick={() => tagFilter = null}>Clear</button>
      {/if}
    </div>
  {/if}

  <!-- Results count -->
  <div class="results-count">
    {filtered.length} {filtered.length === 1 ? 'story' : 'stories'}
    {#if diffFilter !== 'all' || search || tagFilter}
      <span class="text-muted"> (filtered)</span>
    {/if}
  </div>

  <!-- Story cards -->
  {#if filtered.length === 0}
    <div class="card" style="text-align: center; padding: 48px; color: var(--text-2);">
      No stories match your filters.
    </div>
  {:else}
    <div class="story-list">
      {#each filtered as s (s.id)}
        <button class="story-card" class:expanded={expandedId === s.id} onclick={() => toggleExpand(s.id)}>
          <div class="story-header">
            <div class="story-id mono">{s.id}</div>
            <span class="diff-dot" style="background: {diffColors[s.difficulty] || '#666'};"></span>
            <span class="diff-label" style="color: {diffColors[s.difficulty] || '#666'};">{s.difficulty}</span>
            <div class="story-title">{s.title}</div>
            <div class="story-meta">
              <span class="meta-item" title="Acceptance criteria">{s.acceptance_criteria_count} AC</span>
              <span class="meta-sep"></span>
              <span class="meta-item" title="Time budget">{formatTime(s.time_budget_seconds)}</span>
              <span class="meta-sep"></span>
              <span class="meta-item" title="Max iterations">{s.max_iterations} iter</span>
            </div>
            <svg class="chevron" class:rotated={expandedId === s.id} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </div>

          {#if expandedId === s.id}
            <!-- svelte-ignore a11y_click_events_have_key_events -->
            <div class="story-detail" onclick={(e) => e.stopPropagation()}>
              <p class="story-desc">{s.description}</p>

              <div class="detail-grid">
                <div class="detail-item">
                  <span class="detail-label">Category</span>
                  <span class="detail-value">{s.category || '—'}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">Difficulty</span>
                  <span class="detail-value" style="color: {diffColors[s.difficulty]};">{s.difficulty}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">Time Budget</span>
                  <span class="detail-value mono">{formatTime(s.time_budget_seconds)}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">Max Iterations</span>
                  <span class="detail-value mono">{s.max_iterations}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">Acceptance Criteria</span>
                  <span class="detail-value mono">{s.acceptance_criteria_count}</span>
                </div>
              </div>

              {#if (s.tags || []).length > 0}
                <div class="detail-tags">
                  {#each s.tags as tag}
                    <span class="badge badge-blue" style="font-size: 11px;">{tag}</span>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  /* Stats */
  .stats-row {
    display: flex; gap: 12px; margin-bottom: 20px;
  }
  .stat-chip {
    flex: 1;
    display: flex; flex-direction: column; align-items: center;
    padding: 12px; border-radius: 8px;
    border: 1px solid var(--border); background: var(--bg-1);
  }
  .stat-chip-num { font-family: var(--mono); font-size: 22px; font-weight: 700; color: var(--text-0); }
  .stat-chip-label { font-size: 11px; color: var(--text-2); margin-top: 2px; }

  /* Filters */
  .filter-bar {
    display: flex; gap: 12px; align-items: center; margin-bottom: 12px;
  }
  .search-input {
    flex: 1; max-width: 320px;
  }
  .filter-group { display: flex; gap: 6px; }

  .tag-bar {
    display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-bottom: 12px;
  }
  .tag-bar-label { font-size: 11px; color: var(--text-2); margin-right: 2px; }
  .tag-pill {
    padding: 2px 10px; border-radius: 12px; font-size: 11px;
    border: 1px solid var(--border); background: var(--bg-1);
    color: var(--text-1); cursor: pointer; transition: all 0.15s;
  }
  .tag-pill:hover { border-color: var(--border-hover); }
  .tag-pill.active { background: var(--text-0); color: var(--bg-0); border-color: var(--text-0); }
  .tag-clear {
    font-size: 11px; color: var(--text-2); cursor: pointer;
    background: none; border: none; text-decoration: underline;
  }

  .results-count { font-size: 12px; color: var(--text-2); margin-bottom: 16px; }

  /* Story cards */
  .story-list { display: flex; flex-direction: column; gap: 8px; }
  .story-card {
    display: block; width: 100%; text-align: left;
    padding: 14px 16px; border-radius: 8px;
    border: 1px solid var(--border); background: var(--bg-1);
    cursor: pointer; transition: all 0.15s;
  }
  .story-card:hover { border-color: var(--border-hover); }
  .story-card.expanded { border-color: var(--text-2); }

  .story-header {
    display: flex; align-items: center; gap: 10px;
  }
  .story-id { font-size: 11px; color: var(--text-2); min-width: 60px; }
  .diff-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .diff-label { font-size: 11px; min-width: 80px; }
  .story-title { flex: 1; font-size: 13px; font-weight: 500; color: var(--text-0); }
  .story-meta { display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--text-2); flex-shrink: 0; }
  .meta-sep { width: 1px; height: 12px; background: var(--border); }
  .chevron {
    width: 16px; height: 16px; color: var(--text-2); flex-shrink: 0;
    transition: transform 0.2s;
  }
  .chevron.rotated { transform: rotate(180deg); }

  /* Expanded detail */
  .story-detail {
    margin-top: 14px; padding-top: 14px;
    border-top: 1px solid var(--border);
  }
  .story-desc {
    font-size: 13px; color: var(--text-1); line-height: 1.5;
    margin: 0 0 16px 0;
  }
  .detail-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 12px; margin-bottom: 12px;
  }
  .detail-item { display: flex; flex-direction: column; gap: 2px; }
  .detail-label { font-size: 10px; color: var(--text-2); text-transform: uppercase; letter-spacing: 0.5px; }
  .detail-value { font-size: 13px; color: var(--text-0); }
  .detail-tags { display: flex; gap: 6px; flex-wrap: wrap; }
</style>
