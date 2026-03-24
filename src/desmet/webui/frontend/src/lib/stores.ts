import { writable } from 'svelte/store';

export type Page =
  | 'dashboard'
  | 'platforms'
  | 'stories'
  | 'new-run'
  | 'run-history'
  | 'run-detail'
  | 'results-overview'
  | 'scoring'
  | 'comparison'
  | 'story-detail';

export const currentPage = writable<Page>('dashboard');
export const selectedRunId = writable<string | null>(null);
