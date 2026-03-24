/**
 * Typed API client for the DESMET FastAPI backend.
 */

// ── Types ───────────────────────────────

export interface Platform {
  id: string;
  name: string;
  infra_type: string;
  status: string;
  implemented: boolean;
  category: string;
}

export interface Story {
  id: string;
  title: string;
  description: string;
  difficulty: string;
  category: string;
  acceptance_criteria_count: number;
  time_budget_seconds: number;
  max_iterations: number;
  tags: string[];
}

export interface AppConfig {
  model: string;
  provider: string;
  api_keys_set: string[];
  langfuse_status: string;
  temperature: number;
  available_models: string[];
  allow_custom_model?: boolean;
  valid_stages: string[];
  difficulty_levels: string[];
}

export interface Run {
  run_id: string;
  status: string;
  config: RunConfig;
  started_at: string | null;
  finished_at: string | null;
  log_count?: number;
  logs?: string[];
  error: string | null;
  summary: Record<string, unknown> | null;
}

export interface RunConfig {
  platforms: string[];
  stories: string[];
  difficulties: string[];
  stages: string[];
  dry_run: boolean;
  model?: string | null;
}

export interface DashboardStats {
  has_data: boolean;
  platforms_evaluated: string[];
  platforms_count: number;
  total_story_runs: number;
  stories_completed: number;
  stories_failed: number;
  unique_stories: number;
}

export interface OverviewPlatform {
  platform_id: string;
  platform_name: string;
  category: string;
  overall_score: number;
  stories_total: number;
  stories_completed: number;
  completion_rate: number;
  scored: number;
  total_to_score: number;
  colour: string;
}

export interface OverviewData {
  has_data: boolean;
  platforms?: OverviewPlatform[];
  category_colours?: Record<string, Record<string, string>>;
}

export interface ScoringRubric {
  dimensions: string[];
  rubric: Record<string, Record<string, string>>;
}

export interface StoryScoreData {
  found: boolean;
  scored?: boolean;
  scores?: Record<string, number>;
  notes?: Record<string, string>;
  wall_clock_seconds?: number;
  iterations?: number;
  tool_calls?: number;
  success?: boolean;
  trace?: TraceData | null;
  langfuse_trace_id?: string | null;
}

export interface TraceData {
  messages?: TraceMessage[];
  [key: string]: unknown;
}

export interface TraceMessage {
  role?: string;
  content?: string;
}

export interface StoryDetailData {
  story_id: string;
  platforms: StoryPlatformRow[];
  traces: Record<string, TraceData>;
  langfuse_trace_ids?: Record<string, string>;
}

// ── Langfuse trace types ────────────────

export interface LangfuseObservation {
  id: string;
  name: string;
  type: 'span' | 'generation';
  start_time: string | null;
  end_time: string | null;
  latency_ms: number;
  model: string | null;
  tokens: { input: number; output: number; total: number };
  cost: number;
  level: string;
  status_message: string | null;
  input?: string | null;
  output?: string | null;
  metadata?: Record<string, unknown>;
  children: LangfuseObservation[];
}

export interface LangfuseTraceDetail {
  trace: {
    id: string;
    name: string;
    timestamp: string;
    total_tokens: number;
    latency_ms: number;
    cost: number;
    tags: string[];
    metadata: Record<string, unknown>;
  };
  observations: LangfuseObservation[];
}

export interface LangfuseTraceSummary {
  id: string;
  name: string;
  timestamp: string;
  latency_ms: number;
  total_tokens: number;
  tags: string[];
}

export interface StoryPlatformRow {
  platform_id: string;
  platform_name: string;
  success: boolean;
  wall_clock_seconds: number;
  iterations: number;
  tool_calls: number;
  colour: string;
  [key: string]: unknown;
}

// ── Request helper ──────────────────────

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  return res.json() as Promise<T>;
}

// ── Management ──────────────────────────

export const fetchPlatforms = () =>
  request<{ platforms: Platform[] }>('/api/platforms');

export const fetchConfig = () =>
  request<AppConfig>('/api/config');

export const fetchStories = (difficulty?: string) =>
  request<{ stories: Story[] }>(`/api/stories${difficulty ? `?difficulty=${difficulty}` : ''}`);

export const fetchRuns = () =>
  request<{ runs: Run[] }>('/api/runs');

export const fetchDashboardStats = () =>
  request<DashboardStats>('/api/dashboard/stats');

export const fetchRun = (id: string) =>
  request<Run>('/api/runs/' + id);

export const startRun = (cfg: RunConfig) =>
  request<{ run_id?: string; status?: string; error?: string; active_run_id?: string }>('/api/runs/start', { method: 'POST', body: JSON.stringify(cfg) });

export const cancelRun = (id: string) =>
  request<{ status: string }>(`/api/runs/${id}/cancel`, { method: 'POST' });

export const dockerUp = (target: string) =>
  request<{ success: boolean; message: string }>('/api/docker/up', { method: 'POST', body: JSON.stringify({ target }) });

export const dockerDown = (target: string) =>
  request<{ success: boolean; message: string }>('/api/docker/down', { method: 'POST', body: JSON.stringify({ target }) });

// ── Infrastructure ─────────────────

export interface InfraService {
  id: string;
  name: string;
  description: string;
  status: string;
}

export const fetchInfrastructure = () =>
  request<{ services: InfraService[] }>('/api/infrastructure');

// ── Dashboard / Results ─────────────────

export const fetchOverview = () =>
  request<OverviewData>('/api/dashboard/overview');

export const fetchChartJSON = (endpoint: string) =>
  request<{ chart: Record<string, unknown> | null }>(endpoint);

export const fetchRubric = () =>
  request<ScoringRubric>('/api/dashboard/scoring/rubric');

export const fetchStoryScore = (pid: string, sid: string) =>
  request<StoryScoreData>(`/api/dashboard/scoring/${pid}/${sid}`);

export const submitScore = (data: { platform_id: string; story_id: string; scores: Record<string, number>; notes: Record<string, string> }) =>
  request<{ success: boolean }>('/api/dashboard/scoring/submit', { method: 'POST', body: JSON.stringify(data) });

export const fetchStoryDetail = (sid: string) =>
  request<StoryDetailData>(`/api/dashboard/story/${sid}`);

// ── Langfuse ────────────────────────────

export const fetchLangfuseStatus = () =>
  request<{ available: boolean; host: string | null }>('/api/langfuse/status');

export const fetchLangfuseTraces = (params?: { session_id?: string; tag?: string; limit?: number }) => {
  const qs = new URLSearchParams();
  if (params?.session_id) qs.set('session_id', params.session_id);
  if (params?.tag) qs.set('tag', params.tag);
  if (params?.limit) qs.set('limit', String(params.limit));
  const q = qs.toString();
  return request<{ traces: LangfuseTraceSummary[]; langfuse_available: boolean }>(
    `/api/langfuse/traces${q ? '?' + q : ''}`
  );
};

export const fetchLangfuseTrace = (traceId: string) =>
  request<LangfuseTraceDetail>(`/api/langfuse/traces/${traceId}`);

// ── WebSocket ───────────────────────────

export function connectRunLogs(runId: string, onMessage: (line: string) => void): WebSocket {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${proto}//${location.host}/ws/runs/${runId}`);
  ws.onmessage = (e) => onMessage(e.data);
  ws.onerror = () => {};
  return ws;
}
