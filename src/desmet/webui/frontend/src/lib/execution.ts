/**
 * Shared presentation helpers for the canonical execution model.
 *
 * The role palette is the single source of truth for agent colours across
 * the lane view, the drawer and the summary table, so every platform's run
 * is read with the same visual grammar.
 */
import type { ExecutionModel, ExecutionRole, ExecutionStage, ExecutionStep, ExecutionTurn } from './api';

export const ROLE_COLORS: Record<ExecutionRole, string> = {
  manager: 'var(--purple)',
  planner: 'var(--green)',
  executor: 'var(--blue)',
  reviewer: 'var(--yellow)',
  other: 'var(--text-2)',
};

export const ROLE_LABELS: Record<ExecutionRole, string> = {
  manager: 'Manager',
  planner: 'Planner',
  executor: 'Executor',
  reviewer: 'Reviewer',
  other: 'Agent',
};

export const STAGE_LABELS: Record<string, string> = {
  requirements: 'Requirements',
  codegen: 'Code Generation',
  testing: 'Testing',
  deploy: 'Deploy',
  unknown: 'Unassigned',
};

// CrewAI persona names (config/prompts.yaml) → canonical role. Mirrors the
// backend table in desmet.harness.execution_model.
const PERSONA_ROLES: Record<string, ExecutionRole> = {
  'technical lead': 'planner',
  'code reviewer': 'reviewer',
  'requirements analyst': 'executor',
  'software developer': 'executor',
  'qa engineer': 'executor',
  'devops engineer': 'executor',
};

const ROLE_TOKENS: Array<[string, ExecutionRole]> = [
  ['orchestrator', 'manager'],
  ['manager', 'manager'],
  ['planner', 'planner'],
  ['executor', 'executor'],
  ['reviewer', 'reviewer'],
];

/**
 * Map a framework-native agent name ("invoke_agent desmet_codegen_executor",
 * "Code Reviewer._execute_core", "executor/write") onto a canonical role.
 */
export function normaliseRole(raw: string | null | undefined): ExecutionRole {
  if (!raw) return 'other';
  let name = raw.trim();
  for (const prefix of ['invoke_agent ', 'executor.process ', 'agent-', 'agent_', 'desmet-', 'desmet_']) {
    if (name.toLowerCase().startsWith(prefix)) {
      name = name.slice(prefix.length);
      break;
    }
  }
  name = name.split('/')[0].replace(/\._execute_core$/, '').replace(/_fallback$/, '');
  const lowered = name.toLowerCase().replace(/(requirements|codegen|testing|deploy)[_-]?/g, '').trim();
  if (PERSONA_ROLES[lowered]) return PERSONA_ROLES[lowered];
  for (const [token, role] of ROLE_TOKENS) {
    if (lowered.includes(token)) return role;
  }
  return 'other';
}

export function roleColor(role: string): string {
  return ROLE_COLORS[role as ExecutionRole] ?? ROLE_COLORS.other;
}

export function roleLabel(role: string): string {
  return ROLE_LABELS[role as ExecutionRole] ?? role;
}

export function stageLabel(key: string): string {
  return STAGE_LABELS[key] ?? key;
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms)) return '—';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const m = Math.floor(ms / 60_000);
  const s = Math.round((ms % 60_000) / 1000);
  return `${m}m ${s.toString().padStart(2, '0')}s`;
}

export function formatTokens(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 10_000) return `${Math.round(n / 1000)}k`;
  if (n >= 1_000) return `${(n / 1000).toFixed(1)}k`;
  return n.toLocaleString();
}

export function formatCost(usd: number | null | undefined): string {
  if (usd === null || usd === undefined || !Number.isFinite(usd)) return '—';
  if (usd === 0) return '$0';
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  if (usd < 1) return `$${usd.toFixed(3)}`;
  return `$${usd.toFixed(2)}`;
}

// ── Time and cumulative-usage helpers for the lane views ──────────────

export type UsageMetric = 'tokens' | 'cost';

export function formatMetric(metric: UsageMetric, v: number): string {
  return metric === 'cost' ? formatCost(v) : formatTokens(Math.round(v));
}

/** Epoch ms. Naive timestamps are UTC, matching the backend's parser. */
export function parseTs(ts: string | null | undefined): number | null {
  if (!ts) return null;
  const zoned = /(Z|[+-]\d\d:?\d\d)$/.test(ts) ? ts : `${ts}Z`;
  const v = Date.parse(zoned);
  return Number.isFinite(v) ? v : null;
}

export type TimeWindow = { t0: number; t1: number };

function windowOf(times: Array<string | null | undefined>): TimeWindow | null {
  const ms = times.map(parseTs).filter((v): v is number => v !== null);
  if (!ms.length) return null;
  return { t0: Math.min(...ms), t1: Math.max(...ms) };
}

export function turnWindow(turn: ExecutionTurn): TimeWindow | null {
  return (
    windowOf([turn.start_time, turn.end_time]) ??
    windowOf(turn.steps.flatMap((s) => [s.start_time, s.end_time]))
  );
}

export function stageWindow(stage: ExecutionStage): TimeWindow | null {
  return windowOf([stage.start_time, stage.end_time, ...stage.turns.flatMap((t) => [t.start_time, t.end_time])]);
}

export function runWindow(model: ExecutionModel): TimeWindow | null {
  const ws = model.stages.map(stageWindow).filter((w): w is TimeWindow => w !== null);
  if (!ws.length) return null;
  return { t0: Math.min(...ws.map((w) => w.t0)), t1: Math.max(...ws.map((w) => w.t1)) };
}

/** Steps in time order; local traces append tool calls after the messages. */
export function orderedSteps(turn: ExecutionTurn): ExecutionStep[] {
  return turn.steps
    .map((step, i) => ({ step, i, t: parseTs(step.start_time) ?? parseTs(step.end_time) }))
    .sort((a, b) => (a.t !== null && b.t !== null && a.t !== b.t ? a.t - b.t : a.i - b.i))
    .map((x) => x.step);
}

export function metricTotal(model: ExecutionModel, metric: UsageMetric): number {
  return metric === 'cost' ? model.summary.cost_usd ?? 0 : model.summary.tokens;
}

export type UsageEvent = {
  stageKey: string;
  turn: ExecutionTurn | null;
  step: ExecutionStep | null;
  delta: number;
};

/**
 * Per-LLM-call usage increments, stage by stage.
 *
 * When a stage's calls carry no usage of their own (local traces have no
 * per-message tokens; Langfuse cannot price OpenRouter models) the
 * harness-reported stage total is spread over its LLM calls — by token
 * share for cost, evenly otherwise — and the series is flagged as estimated.
 */
export function usageEvents(model: ExecutionModel, metric: UsageMetric): { events: UsageEvent[]; estimated: boolean } {
  const own = (s: ExecutionStep) => (metric === 'cost' ? s.cost_usd ?? 0 : s.tokens_in + s.tokens_out);
  const events: UsageEvent[] = [];
  let estimated = false;
  for (const stage of model.stages) {
    const calls = stage.turns.flatMap((turn) =>
      orderedSteps(turn)
        .filter((s) => s.kind === 'llm')
        .map((step) => ({ turn, step })),
    );
    const ownSum = calls.reduce((a, c) => a + own(c.step), 0);
    const total = metric === 'cost' ? stage.cost_usd ?? 0 : stage.tokens;
    if (ownSum > 0) {
      for (const c of calls) {
        const delta = own(c.step);
        if (delta > 0) events.push({ stageKey: stage.key, ...c, delta });
      }
    } else if (total > 0) {
      estimated = true;
      if (calls.length) {
        const tok = (s: ExecutionStep) => s.tokens_in + s.tokens_out;
        const tokSum = metric === 'cost' ? calls.reduce((a, c) => a + tok(c.step), 0) : 0;
        for (const c of calls) {
          const w = tokSum > 0 ? tok(c.step) / tokSum : 1 / calls.length;
          if (w > 0) events.push({ stageKey: stage.key, ...c, delta: total * w });
        }
      } else {
        events.push({ stageKey: stage.key, turn: null, step: null, delta: total });
      }
    }
  }
  return { events, estimated };
}

const TICK_STEPS_MS = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600].map((s) => s * 1000);

/** Smallest round tick interval that keeps labels at least ``minPx`` apart. */
export function tickInterval(pxPerMs: number, minPx = 110): number {
  for (const step of TICK_STEPS_MS) if (step * pxPerMs >= minPx) return step;
  return TICK_STEPS_MS[TICK_STEPS_MS.length - 1];
}
