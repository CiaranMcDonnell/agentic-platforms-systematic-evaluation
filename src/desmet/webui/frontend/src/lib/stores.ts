import { writable } from 'svelte/store';

export type Page = 'dashboard' | 'platforms' | 'stories' | 'new-run' |
                  'run-history' | 'run-detail' | 'results-overview' |
                  'scoring' | 'comparison' | 'story-detail'

export const currentPage = writable<Page>('dashboard')
export const selectedRunId = writable<string | null>(null)

// Pre-select platform+story when navigating from Story Detail to Scoring
export const scoringTarget = writable<{ platform_id: string; story_id: string } | null>(null)

/** Selected run for Results section — null = latest */
export const selectedResultsRunId = writable<string | null>(null)
