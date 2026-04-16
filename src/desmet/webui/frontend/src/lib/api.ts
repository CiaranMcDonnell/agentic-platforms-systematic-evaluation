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
  deploy_status: string;
  temperature: number;
  available_models: Record<string, string[]>;
  valid_stages: string[];
  difficulty_levels: string[];
  langsmith_available?: boolean;
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
  deploy_mode?: string;
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
  dim_scores?: Record<string, number | null>;
}

export interface OverviewData {
  has_data: boolean;
  platforms?: OverviewPlatform[];
  category_colours?: Record<string, Record<string, string>>;
}

export interface ScoringMatrixPlatform {
  platform_id: string;
  platform_name: string;
  colour: string;
  scores: Record<string, number | null>;
  scored_count: number;
}

export interface ScoringMatrixData {
  platforms: ScoringMatrixPlatform[];
  dimensions: string[];
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
  langsmith_run_id?: string | null;
  framework_metrics?: Record<string, number | null>;
}

export interface ToolCallSummary {
  name: string;
  count: number;
  success_rate: number;
}

export interface GraphNode {
  id: string;
  role: string;
  tokens_in: number;
  tokens_out: number;
  tool_calls: ToolCallSummary[];
  iterations: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  message_count: number;
  token_volume: number;
  sequence: number[];
}

export interface TimelineEvent {
  index: number;
  type: 'llm' | 'tool' | 'agent' | 'routing';
  raw_type: string;
  agent_id: string;
  role: string;
  content: string;
  timestamp: string;
  duration_ms: number | null;
  tokens_in: number | null;
  tokens_out: number | null;
  model: string | null;
  tool_name: string | null;
  tool_success: boolean | null;
  target_agent_id: string | null;
}

export interface CommunicationGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  topology: string;
  platform: string;
  story_id: string;
  timeline: TimelineEvent[];
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
  type: 'span' | 'generation' | 'tool';
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

// ── LangSmith trace types ────────────────

export interface LangSmithRun {
  id: string;
  name: string;
  run_type: 'llm' | 'tool' | 'chain';
  start_time: string | null;
  end_time: string | null;
  latency_ms: number;
  model: string | null;
  tokens: { input: number; output: number; total: number };
  error: string | null;
  inputs: string | null;
  outputs: string | null;
  children: LangSmithRun[];
}

export interface LangSmithRunTree {
  run: {
    id: string;
    name: string;
    run_type: string;
    start_time: string | null;
    end_time: string | null;
    latency_ms: number;
    total_tokens: number;
    error: string | null;
    tags: string[];
  };
  children: LangSmithRun[];
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

export class ApiError extends Error {
  constructor(public status: number, public statusText: string, public body: unknown) {
    super(`API ${status}: ${statusText}`);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const { headers: extraHeaders, ...restOpts } = opts;
  const headers: Record<string, string> = {
    ...(restOpts.body ? { 'Content-Type': 'application/json' } : {}),
    ...(extraHeaders instanceof Headers
      ? Object.fromEntries(extraHeaders.entries())
      : Array.isArray(extraHeaders)
        ? Object.fromEntries(extraHeaders)
        : (extraHeaders as Record<string, string> | undefined) ?? {}),
  };
  const res = await fetch(path, {
    ...restOpts,
    headers,
  });
  if (!res.ok) {
    let body: unknown;
    try { body = await res.json(); } catch { body = await res.text().catch(() => null); }
    throw new ApiError(res.status, res.statusText, body);
  }
  return res.json() as Promise<T>;
}

// ── Management ──────────────────────────

export const fetchPlatforms = () =>
  request<{ platforms: Platform[] }>('/api/platforms');

export const fetchPlatformStatuses = () =>
  request<{ statuses: Record<string, string> }>('/api/platforms/status');

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

// ── Image build ───────────────────

export interface ImageDetail {
  exists: boolean;
  tag: string | null;
  size_bytes: number;
  created_at: string;
}

export interface ImageBuildMessage {
  platform?: string;
  phase?: string;
  line?: string;
  status?: string;
  error?: string;
  done?: boolean;
  summary?: { built: number; exists: number; failed: number };
}

export const buildImages = (platforms?: string[]) =>
  request<{ images: Record<string, { status: string; reason?: string }> }>('/api/images/build', {
    method: 'POST',
    body: JSON.stringify(platforms ? { platforms } : {}),
  });

export const fetchImageStatus = () =>
  request<Record<string, { exists: boolean }>>('/api/images/status');

export const fetchImageDetails = () =>
  request<Record<string, ImageDetail>>('/api/images/detail');

export const deleteImage = (platformId: string) =>
  request<{ success: boolean; message: string }>(`/api/images/${platformId}`, { method: 'DELETE' });

export const rebuildImage = (platformId: string) =>
  request<{ status: string; reason?: string }>(`/api/images/${platformId}/rebuild`, { method: 'POST' });

// ── Infrastructure ─────────────────

export interface InfraContainer {
  name: string;
  status: string;
}

export interface InfraService {
  id: string;
  name: string;
  description: string;
  status: string;          // "running" | "partial" | "not started"
  managed?: boolean;
  containers?: InfraContainer[];
  running_count?: number;
  total_count?: number;
}

export const fetchInfrastructure = () =>
  request<{ services: InfraService[] }>('/api/infrastructure');

// ── Dashboard / Results ─────────────────

export interface ResultRun {
  run_id: string;
  started_at: string | null;
  finished_at: string | null;
  model: string | null;
  platforms_filter: string[] | null;
  note: string | null;
}

export const fetchResultRuns = () =>
  request<{ runs: ResultRun[] }>('/api/result-runs');

export const fetchOverview = (runId?: string | null) => {
  const qs = runId ? `?run_id=${runId}` : '';
  return request<OverviewData>(`/api/dashboard/overview${qs}`);
};

export const fetchChartJSON = (endpoint: string) =>
  request<{ chart: Record<string, unknown> | null }>(endpoint);

export const fetchRubric = () =>
  request<ScoringRubric>('/api/dashboard/scoring/rubric');

export const fetchScoringMatrix = (runId?: string | null) => {
  const qs = runId ? `?run_id=${runId}` : '';
  return request<ScoringMatrixData>(`/api/dashboard/scoring/matrix${qs}`);
};

export const fetchStoryScore = (pid: string, sid: string) =>
  request<StoryScoreData>(`/api/dashboard/scoring/${pid}/${sid}`);

export const fetchAgentGraph = (pid: string, sid: string) =>
  request<CommunicationGraph>(`/api/dashboard/graph/${pid}/${sid}`);

export const submitScore = (data: { platform_id: string; story_id: string; scores: Record<string, number>; notes: Record<string, string> }) =>
  request<{ success: boolean }>('/api/dashboard/scoring/submit', { method: 'POST', body: JSON.stringify(data) });

export const fetchStoryDetail = (sid: string) =>
  request<StoryDetailData>(`/api/dashboard/story/${sid}`);

export interface FrameworkMetricsPlatform {
  platform_id: string;
  platform_name: string;
  story_count: number;
  metrics: Record<string, number | null>;
}

export const fetchFrameworkMetrics = (runId?: string | null) => {
  const qs = runId ? `?run_id=${runId}` : '';
  return request<{ platforms: FrameworkMetricsPlatform[] }>(
    `/api/dashboard/framework-metrics${qs}`
  );
};

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

// ── LangSmith ────────────────────────────

export const fetchLangSmithStatus = () =>
  request<{ available: boolean; project: string | null }>('/api/langsmith/status');

export const fetchLangSmithRun = (runId: string) =>
  request<LangSmithRunTree>('/api/langsmith/runs/' + runId);

// ── WebSocket ───────────────────────────

export function connectRunLogs(runId: string, onMessage: (line: string) => void): WebSocket {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${proto}//${location.host}/ws/runs/${runId}`);
  ws.onmessage = (e) => onMessage(e.data);
  ws.onerror = (e) => console.warn('[DESMET] WebSocket error for run', runId, e);
  return ws;
}

export function connectImageBuild(
  platforms: string[] | undefined,
  onMessage: (msg: ImageBuildMessage) => void,
): WebSocket {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${proto}//${location.host}/ws/images/build`);
  ws.onopen = () => {
    ws.send(JSON.stringify(platforms ? { platforms } : {}));
  };
  ws.onmessage = (e) => {
    try {
      onMessage(JSON.parse(e.data));
    } catch {
      console.warn('[DESMET] Failed to parse image build message', e.data);
    }
  };
  ws.onerror = (e) => console.warn('[DESMET] Image build WS error', e);
  return ws;
}
