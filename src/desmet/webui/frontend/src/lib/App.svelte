<script lang="ts">
  import { currentPage, selectedRunId } from './stores';
  import type { Page } from './stores';

  import Dashboard from './pages/Dashboard.svelte';
  import Platforms from './pages/Platforms.svelte';
  import Stories from './pages/Stories.svelte';
  import NewRun from './pages/NewRun.svelte';
  import RunHistory from './pages/RunHistory.svelte';
  import RunDetail from './pages/RunDetail.svelte';
  import ResultsOverview from './pages/ResultsOverview.svelte';
  import Scoring from './pages/Scoring.svelte';
  import Comparison from './pages/Comparison.svelte';
  import StoryDetail from './pages/StoryDetail.svelte';

  let page = $state<Page>('dashboard');
  let runId = $state<string | null>(null);

  currentPage.subscribe((v) => (page = v));
  selectedRunId.subscribe((v) => (runId = v));

  function nav(p: Page) {
    currentPage.set(p);
  }

  function viewRun(id: string) {
    selectedRunId.set(id);
    currentPage.set('run-detail');
  }

  const manageLinks: { page: Page; label: string }[] = [
    { page: 'dashboard', label: 'Dashboard' },
    { page: 'platforms', label: 'Platforms' },
    { page: 'stories', label: 'Stories' },
    { page: 'new-run', label: 'New Run' },
    { page: 'run-history', label: 'Run History' },
  ];

  const resultsLinks: { page: Page; label: string }[] = [
    { page: 'results-overview', label: 'Overview' },
    { page: 'scoring', label: 'Scoring' },
    { page: 'comparison', label: 'Comparison' },
    { page: 'story-detail', label: 'Story Detail' },
  ];
</script>

<div class="shell">
  <!-- Sidebar -->
  <aside class="sidebar">
    <div class="sidebar-brand">
      <span style="font-size: 15px; font-weight: 700; letter-spacing: -0.02em;">DESMET</span>
      <span style="font-size: 10px; color: var(--text-2); text-transform: uppercase; letter-spacing: 0.08em;">Console</span>
    </div>

    <nav class="sidebar-nav">
      <div class="nav-section">
        <div class="nav-section-label">Manage</div>
        {#each manageLinks as link}
          <button
            class="nav-item"
            class:active={page === link.page}
            onclick={() => nav(link.page)}
          >
            {link.label}
          </button>
        {/each}
      </div>

      <div class="nav-section">
        <div class="nav-section-label">Results</div>
        {#each resultsLinks as link}
          <button
            class="nav-item"
            class:active={page === link.page}
            onclick={() => nav(link.page)}
          >
            {link.label}
          </button>
        {/each}
      </div>
    </nav>
  </aside>

  <!-- Main content -->
  <main class="main-content">
    {#if page === 'dashboard'}
      <Dashboard />
    {:else if page === 'platforms'}
      <Platforms />
    {:else if page === 'stories'}
      <Stories />
    {:else if page === 'new-run'}
      <NewRun />
    {:else if page === 'run-history'}
      <RunHistory onViewRun={viewRun} />
    {:else if page === 'run-detail' && runId}
      <RunDetail runId={runId} onBack={() => nav('run-history')} />
    {:else if page === 'results-overview'}
      <ResultsOverview />
    {:else if page === 'scoring'}
      <Scoring />
    {:else if page === 'comparison'}
      <Comparison />
    {:else if page === 'story-detail'}
      <StoryDetail />
    {/if}
  </main>
</div>

<style>
  .shell {
    display: flex;
    min-height: 100vh;
  }

  .sidebar {
    width: 200px;
    flex-shrink: 0;
    background: var(--bg-0);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    overflow-y: auto;
  }

  .sidebar-brand {
    padding: 20px 16px 16px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    border-bottom: 1px solid var(--border);
  }

  .sidebar-nav {
    padding: 12px 0;
    flex: 1;
  }

  .nav-section {
    margin-bottom: 8px;
  }

  .nav-section-label {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-2);
    padding: 8px 16px 4px;
  }

  .nav-item {
    display: block;
    width: 100%;
    text-align: left;
    padding: 7px 16px;
    font-size: 13px;
    color: var(--text-1);
    background: none;
    border: none;
    cursor: pointer;
    transition: all 0.12s;
    border-left: 2px solid transparent;
  }

  .nav-item:hover {
    color: var(--text-0);
    background: var(--bg-1);
  }

  .nav-item.active {
    color: var(--text-0);
    background: var(--bg-1);
    border-left-color: var(--text-0);
  }

  .main-content {
    flex: 1;
    margin-left: 200px;
    padding: 32px 40px;
    min-height: 100vh;
  }
</style>
