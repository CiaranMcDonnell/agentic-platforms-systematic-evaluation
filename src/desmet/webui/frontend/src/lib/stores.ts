import { writable } from 'svelte/store';

export type Page = 'dashboard' | 'platforms' | 'stories' | 'new-run' |
                  'run-history' | 'run-detail' | 'results-overview' |
                  'scoring' | 'comparison' | 'story-detail'

export const currentPage = writable<Page>('dashboard')
export const selectedRunId = writable<string | null>(null)

// Pre-select platform+story when navigating from Story Detail to Scoring
export const scoringTarget = writable<{ platform_id: string; story_id: string } | null>(null)

/** Selected run for the Results section — null means "latest".
 *
 * Backed by the ``?run=...`` query string so it survives page refreshes,
 * is bookmarkable/shareable, and participates in browser back/forward.
 * Reading the initial value from the URL also lets deep-links like
 * ``/?run=abc123`` work out of the box.
 */
function readRunFromUrl(): string | null {
  if (typeof window === 'undefined') return null;
  return new URL(window.location.href).searchParams.get('run');
}

export const selectedResultsRunId = writable<string | null>(readRunFromUrl());

if (typeof window !== 'undefined') {
  selectedResultsRunId.subscribe((v) => {
    const url = new URL(window.location.href);
    const current = url.searchParams.get('run');
    const next = v ?? null;
    if ((current ?? null) === next) return;
    if (next) url.searchParams.set('run', next);
    else url.searchParams.delete('run');
    // Use replaceState so the dropdown doesn't spam browser history.
    window.history.replaceState(window.history.state, '', url.toString());
  });

  window.addEventListener('popstate', () => {
    const run = readRunFromUrl();
    selectedResultsRunId.update((prev) => (prev === run ? prev : run));
  });
}
