"""Canonical execution model — one shape for every platform's run.

Each framework emits a different span tree (LangGraph chains, CrewAI
``<Role>._execute_core`` agents, ADK ``invoke_agent`` spans, Agent Framework
``executor.process`` spans, OpenAI ``agent-*`` spans) and a different local
message trace. The web UI should never see those differences. This module
maps either source onto the same grammar:

    ExecutionModel
      └── Stage (requirements → codegen → testing → deploy)
            └── AgentTurn (role: manager | planner | executor | reviewer | other)
                  └── Step (kind: llm | tool)

plus ``Transition`` edges that say where control moved: turn to turn inside
a stage (``sequence``), backwards loops (``retry``) and stage boundaries
(``stage``). Framework plumbing (routers, runnables, edge groups, message
sends, pipeline/loop wrappers) is dropped; the raw names survive on each
turn and step so a drawer can still show what the framework called them.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

__all__ = [
    "STAGE_ORDER",
    "ROLE_ORDER",
    "Step",
    "AgentTurn",
    "Stage",
    "Transition",
    "ExecutionModel",
    "normalise_agent_name",
    "build_from_langfuse",
    "build_from_stage_file",
]

STAGE_ORDER: tuple[str, ...] = ("requirements", "codegen", "testing", "deploy")
ROLE_ORDER: tuple[str, ...] = ("manager", "planner", "executor", "reviewer", "other")

# Roles between which a backwards move is a retry loop (reviewer sends the
# executor back, executor re-plans). Manager loops are orchestration, not
# retries, so the manager is excluded.
_RETRY_ROLES: tuple[str, ...] = ("planner", "executor", "reviewer")

_EXCERPT_LEN = 1500


# ── Data model ──────────────────────────────────────────────────────────


@dataclass
class Step:
    """One LLM call or tool call inside an agent turn."""

    id: str
    kind: str  # "llm" | "tool"
    name: str
    raw_name: str
    raw_type: str
    start_time: str | None = None
    end_time: str | None = None
    duration_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    model: str | None = None
    cost_usd: float = 0.0
    success: bool | None = None
    error: str | None = None
    input: str | None = None
    output: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "raw_name": self.raw_name,
            "raw_type": self.raw_type,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "model": self.model,
            "cost_usd": self.cost_usd,
            "success": self.success,
            "error": self.error,
            "input": self.input,
            "output": self.output,
        }


@dataclass
class AgentTurn:
    """A contiguous run of work by one agent role."""

    id: str
    role: str
    raw_name: str
    stage_key: str
    start_time: str | None = None
    end_time: str | None = None
    duration_ms: float = 0.0
    is_retry: bool = False
    error: str | None = None
    steps: list[Step] = field(default_factory=list)

    @property
    def llm_calls(self) -> int:
        return sum(1 for s in self.steps if s.kind == "llm")

    @property
    def tool_calls(self) -> int:
        return sum(1 for s in self.steps if s.kind == "tool")

    @property
    def tool_failures(self) -> int:
        return sum(1 for s in self.steps if s.kind == "tool" and s.success is False)

    @property
    def tokens_in(self) -> int:
        return sum(s.tokens_in for s in self.steps if s.kind == "llm")

    @property
    def tokens_out(self) -> int:
        return sum(s.tokens_out for s in self.steps if s.kind == "llm")

    @property
    def tokens(self) -> int:
        return self.tokens_in + self.tokens_out

    @property
    def cost_usd(self) -> float:
        return sum(s.cost_usd for s in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "raw_name": self.raw_name,
            "stage_key": self.stage_key,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "is_retry": self.is_retry,
            "error": self.error,
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "tool_failures": self.tool_failures,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "tokens": self.tokens,
            "cost_usd": self.cost_usd,
            "steps": [s.to_dict() for s in self.steps],
        }


@dataclass
class Stage:
    key: str
    turns: list[AgentTurn] = field(default_factory=list)
    start_time: str | None = None
    end_time: str | None = None
    duration_ms: float = 0.0
    success: bool | None = None
    error: str | None = None
    # Stage-level usage reported by the harness (local stage files carry
    # totals but no per-message usage). Used when the turns have none.
    reported_tokens: int = 0
    # Stage cost from the harness. Langfuse cannot price most OpenRouter
    # models, so per-step cost is usually zero and this is the real figure.
    reported_cost_usd: float = 0.0

    @property
    def tokens(self) -> int:
        from_turns = sum(t.tokens for t in self.turns)
        return from_turns if from_turns > 0 else self.reported_tokens

    @property
    def cost_usd(self) -> float:
        from_turns = sum(t.cost_usd for t in self.turns)
        return from_turns if from_turns > 0 else self.reported_cost_usd

    @property
    def summary(self) -> dict[str, dict[str, Any]]:
        """Per-role aggregates for this stage (only roles that appear)."""
        out: dict[str, dict[str, Any]] = {}
        for turn in self.turns:
            agg = out.setdefault(
                turn.role,
                {
                    "turns": 0,
                    "retries": 0,
                    "llm_calls": 0,
                    "tool_calls": 0,
                    "tool_failures": 0,
                    "tokens": 0,
                    "duration_ms": 0.0,
                },
            )
            agg["turns"] += 1
            agg["retries"] += 1 if turn.is_retry else 0
            agg["llm_calls"] += turn.llm_calls
            agg["tool_calls"] += turn.tool_calls
            agg["tool_failures"] += turn.tool_failures
            agg["tokens"] += turn.tokens
            agg["duration_ms"] += turn.duration_ms
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error": self.error,
            "tokens": self.tokens,
            "cost_usd": self.cost_usd,
            "summary": self.summary,
            "turns": [t.to_dict() for t in self.turns],
        }


@dataclass
class Transition:
    source: str
    target: str
    kind: str  # "sequence" | "retry" | "stage"

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "target": self.target, "kind": self.kind}


@dataclass
class ExecutionModel:
    platform_id: str
    story_id: str
    source: str  # "langfuse" | "local"
    attempts: int = 1
    stages: list[Stage] = field(default_factory=list)
    transitions: list[Transition] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, Any]:
        turns = [t for s in self.stages for t in s.turns]
        by_role: dict[str, dict[str, Any]] = {}
        for stage in self.stages:
            for role, agg in stage.summary.items():
                tgt = by_role.setdefault(role, {k: 0 for k in agg})
                for k, v in agg.items():
                    tgt[k] += v
        return {
            "turns": len(turns),
            "retries": sum(1 for t in turns if t.is_retry),
            "llm_calls": sum(t.llm_calls for t in turns),
            "tool_calls": sum(t.tool_calls for t in turns),
            "tool_failures": sum(t.tool_failures for t in turns),
            "tokens": sum(s.tokens for s in self.stages),
            "cost_usd": sum(s.cost_usd for s in self.stages),
            "duration_ms": sum(s.duration_ms for s in self.stages),
            "roles": [r for r in ROLE_ORDER if r in by_role],
            "by_role": by_role,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform_id": self.platform_id,
            "story_id": self.story_id,
            "source": self.source,
            "attempts": self.attempts,
            "stage_order": list(STAGE_ORDER),
            "role_order": list(ROLE_ORDER),
            "summary": self.summary,
            "stages": [s.to_dict() for s in self.stages],
            "transitions": [t.to_dict() for t in self.transitions],
            "notes": list(self.notes),
        }


# ── Name normalisation ──────────────────────────────────────────────────

_STAGE_RE = re.compile(r"(requirements|codegen|testing|deploy)")

# Framework wrappers around an agent name. Order matters: strip the longer
# prefixes first.
_AGENT_PREFIXES = (
    "invoke_agent ",
    "executor.process ",
    "agent-",
    "agent_",
    "desmet-",
    "desmet_",
)
_AGENT_SUFFIXES = ("._execute_core", ".kickoff")

# CrewAI persona names (config/prompts.yaml) → canonical role.
_PERSONA_ROLES: dict[str, str] = {
    "technical lead": "planner",
    "code reviewer": "reviewer",
    "requirements analyst": "executor",
    "software developer": "executor",
    "qa engineer": "executor",
    "devops engineer": "executor",
}

_ROLE_TOKENS: tuple[tuple[str, str], ...] = (
    ("orchestrator", "manager"),
    ("manager", "manager"),
    ("planner", "planner"),
    ("executor", "executor"),
    ("reviewer", "reviewer"),
    ("review", "reviewer"),
)

# Names that are never agents even though they can carry a stage token.
_NON_AGENT_RE = re.compile(
    r"^(stage-|story-|desmet-single-|workflow\.|edge_group|message\.send|route|"
    r"runnable|langgraph$|tool_node|plan$|review$|llm-|chat |call_llm|"
    r"crew_|.*(_pipeline|_loop)$)",
    re.IGNORECASE,
)


def normalise_agent_name(raw: str | None) -> tuple[str, str, bool] | None:
    """Map a framework-native agent name onto ``(role, clean_name, is_retry)``.

    Returns ``None`` when the name does not describe an agent at all
    (plumbing, stage wrappers, LLM or tool spans).
    """
    if not raw:
        return None
    name = raw.strip()
    if _NON_AGENT_RE.match(name):
        return None

    for prefix in _AGENT_PREFIXES:
        if name.lower().startswith(prefix):
            name = name[len(prefix) :]
            break
    for suffix in _AGENT_SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)]

    # LangGraph tags sub-nodes as "executor/write" — keep the agent part.
    name = name.split("/")[0].strip()

    is_retry = False
    if name.lower().endswith("_fallback"):
        name = name[: -len("_fallback")]
        is_retry = True

    # Drop a leading stage token: "codegen_executor" → "executor".
    stripped = _STAGE_RE.sub("", name.lower()).strip("_- ")
    clean = name if stripped == "" else name[len(name) - len(stripped) :] if name.lower().endswith(stripped) else name

    lowered = stripped or name.lower()
    if lowered in _PERSONA_ROLES:
        return _PERSONA_ROLES[lowered], name, is_retry
    for token, role in _ROLE_TOKENS:
        if token in lowered:
            return role, clean, is_retry
    return None


def _stage_from_name(name: str | None) -> str | None:
    if not name:
        return None
    m = _STAGE_RE.search(name.lower())
    return m.group(1) if m else None


# ── Time helpers ────────────────────────────────────────────────────────


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _duration_ms(start: str | None, end: str | None) -> float:
    s, e = _parse_ts(start), _parse_ts(end)
    if s is None or e is None:
        return 0.0
    return max(0.0, (e - s).total_seconds() * 1000)


def _min_ts(values: Iterable[str | None]) -> str | None:
    parsed = [(v, _parse_ts(v)) for v in values if v]
    parsed = [(v, p) for v, p in parsed if p is not None]
    return min(parsed, key=lambda x: x[1])[0] if parsed else None


def _max_ts(values: Iterable[str | None]) -> str | None:
    parsed = [(v, _parse_ts(v)) for v in values if v]
    parsed = [(v, p) for v, p in parsed if p is not None]
    return max(parsed, key=lambda x: x[1])[0] if parsed else None


def _excerpt(value: Any) -> str | None:
    if value is None:
        return None
    s = value if isinstance(value, str) else str(value)
    return s if len(s) <= _EXCERPT_LEN else s[:_EXCERPT_LEN] + "…"


# ── Langfuse builder ────────────────────────────────────────────────────

_TOOL_PREFIX = "tool-"
_TOOL_SUFFIX = ".run"
_LLM_NAME_RE = re.compile(r"^(llm-|chat )(.+)$")


def _walk(obs: dict[str, Any]) -> Iterable[dict[str, Any]]:
    yield obs
    for child in obs.get("children") or []:
        yield from _walk(child)


def _sorted_children(obs: dict[str, Any]) -> list[dict[str, Any]]:
    kids = list(obs.get("children") or [])
    kids.sort(key=lambda c: (_parse_ts(c.get("start_time")) or datetime.max.replace(tzinfo=timezone.utc)))
    return kids


def _is_harness_summary(obs: dict[str, Any]) -> bool:
    """``agent-<name>`` generations recorded by adapters as turn summaries."""
    return (
        obs.get("type") == "generation"
        and str(obs.get("name", "")).startswith("agent-")
        and not obs.get("children")
    )


def _step_from_observation(obs: dict[str, Any], step_id: str) -> Step | None:
    otype = str(obs.get("type") or "span").lower()
    name = str(obs.get("name") or "")
    if _is_harness_summary(obs):
        return None

    kind: str | None = None
    clean = name
    model = obs.get("model")
    if otype == "generation":
        kind = "llm"
        m = _LLM_NAME_RE.match(name)
        if m and not model:
            model = m.group(2)
    elif otype == "tool" or name.startswith(_TOOL_PREFIX):
        kind = "tool"
        if clean.startswith(_TOOL_PREFIX):
            clean = clean[len(_TOOL_PREFIX) :]
        if clean.endswith(_TOOL_SUFFIX):
            clean = clean[: -len(_TOOL_SUFFIX)]
    if kind is None:
        return None

    tokens = obs.get("tokens") or {}
    is_error = str(obs.get("level") or "DEFAULT").upper() == "ERROR"
    return Step(
        id=step_id,
        kind=kind,
        name=clean,
        raw_name=name,
        raw_type=otype,
        start_time=obs.get("start_time"),
        end_time=obs.get("end_time"),
        duration_ms=float(obs.get("latency_ms") or _duration_ms(obs.get("start_time"), obs.get("end_time"))),
        tokens_in=int(tokens.get("input") or 0),
        tokens_out=int(tokens.get("output") or 0),
        model=model,
        cost_usd=float(obs.get("cost") or 0),
        success=(not is_error) if kind == "tool" else None,
        error=obs.get("status_message") if is_error else None,
        input=_excerpt(obs.get("input")),
        output=_excerpt(obs.get("output")),
    )


class _LangfuseWalker:
    """Collects agent turns from a span tree, stage by stage."""

    def __init__(self) -> None:
        self.turns: list[AgentTurn] = []
        self._counter = 0

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter}"

    def visit(self, obs: dict[str, Any], stage_key: str | None, turn: AgentTurn | None) -> None:
        name = str(obs.get("name") or "")
        if name.startswith("stage-"):
            stage_key = name[len("stage-") :]
        elif stage_key is None:
            stage_key = _stage_from_name(name)

        agent = normalise_agent_name(name) if not _is_harness_summary(obs) else None
        if agent is not None:
            role, clean, is_retry = agent
            if turn is not None and turn.role == role:
                # Same agent nested inside itself (Agent Framework wraps
                # executor.process X around invoke_agent X): keep one turn.
                turn.is_retry = turn.is_retry or is_retry
                if str(obs.get("level") or "").upper() == "ERROR" and not turn.error:
                    turn.error = obs.get("status_message") or "error"
            else:
                turn = AgentTurn(
                    id=self._next_id("turn"),
                    role=role,
                    raw_name=clean,
                    stage_key=stage_key or _stage_from_name(name) or "unknown",
                    start_time=obs.get("start_time"),
                    end_time=obs.get("end_time"),
                    duration_ms=float(obs.get("latency_ms") or _duration_ms(obs.get("start_time"), obs.get("end_time"))),
                    is_retry=is_retry,
                    error=obs.get("status_message") if str(obs.get("level") or "").upper() == "ERROR" else None,
                )
                self.turns.append(turn)
                for child in _sorted_children(obs):
                    self.visit(child, stage_key, turn)
                return

        step = _step_from_observation(obs, self._next_id("step")) if turn is not None else None
        if step is not None:
            turn.steps.append(step)  # type: ignore[union-attr]
            if step.kind == "llm" and turn.stage_key == "unknown" and stage_key:
                turn.stage_key = stage_key  # type: ignore[union-attr]

        for child in _sorted_children(obs):
            self.visit(child, stage_key, turn)


def _select_attempt(roots: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, dict[str, Any] | None]:
    """Pick the subtree of the latest ``story-*`` span plus orphans in its window."""
    story_spans = [o for r in roots for o in _walk(r) if str(o.get("name", "")).startswith("story-")]
    if not story_spans:
        return roots, 1, None
    story_spans.sort(key=lambda o: _parse_ts(o.get("start_time")) or datetime.min.replace(tzinfo=timezone.utc))
    latest = story_spans[-1]
    start, end = _parse_ts(latest.get("start_time")), _parse_ts(latest.get("end_time"))

    story_ids = {id(o) for o in _walk(latest)}
    selected: list[dict[str, Any]] = [latest]
    for root in roots:
        if any(id(o) in story_ids for o in _walk(root)):
            # The root contains (or is) the chosen story; its other children
            # belong to other attempts or are the trace wrapper itself.
            continue
        ts = _parse_ts(root.get("start_time"))
        if start is None or end is None or ts is None or (start <= ts <= end):
            selected.append(root)
    return selected, len(story_spans), latest


def _stage_spans(selected: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for root in selected:
        for o in _walk(root):
            name = str(o.get("name") or "")
            if name.startswith("stage-"):
                out[name[len("stage-") :]] = o
    return out


def build_from_langfuse(
    trace_detail: dict[str, Any],
    *,
    platform_id: str,
    story_id: str,
) -> ExecutionModel:
    """Build the canonical model from ``langfuse_client.fetch_trace`` output."""
    roots = list(trace_detail.get("observations") or [])
    selected, attempts, _story = _select_attempt(roots)

    walker = _LangfuseWalker()
    for root in sorted(selected, key=lambda o: _parse_ts(o.get("start_time")) or datetime.max.replace(tzinfo=timezone.utc)):
        walker.visit(root, None, None)

    turns = [t for t in walker.turns if t.steps]
    stage_info = {
        key: {
            "start_time": span.get("start_time"),
            "end_time": span.get("end_time"),
            "duration_ms": float(span.get("latency_ms") or 0),
            "error": span.get("status_message") if str(span.get("level") or "").upper() == "ERROR" else None,
        }
        for key, span in _stage_spans(selected).items()
    }
    model = ExecutionModel(platform_id=platform_id, story_id=story_id, source="langfuse", attempts=attempts)
    _assemble(model, turns, stage_info)
    return model


def _assemble(
    model: ExecutionModel,
    turns: list[AgentTurn],
    stage_info: dict[str, dict[str, Any]],
) -> None:
    """Group turns into ordered stages, derive timings and transitions."""
    by_stage: dict[str, list[AgentTurn]] = {}
    for t in turns:
        by_stage.setdefault(t.stage_key, []).append(t)

    keys = [k for k in STAGE_ORDER if k in by_stage or k in stage_info]
    keys += sorted(k for k in by_stage if k not in STAGE_ORDER)

    for key in keys:
        stage_turns = sorted(
            by_stage.get(key, []),
            key=lambda t: _parse_ts(t.start_time) or datetime.max.replace(tzinfo=timezone.utc),
        )
        for i, t in enumerate(stage_turns, start=1):
            t.id = f"{key}-{i}"
            for j, s in enumerate(t.steps, start=1):
                s.id = f"{t.id}-s{j}"
        info = stage_info.get(key) or {}
        start = info.get("start_time") or _min_ts(t.start_time for t in stage_turns)
        end = info.get("end_time") or _max_ts(t.end_time for t in stage_turns)
        model.stages.append(
            Stage(
                key=key,
                turns=stage_turns,
                start_time=start,
                end_time=end,
                duration_ms=float(info.get("duration_ms") or _duration_ms(start, end)),
                success=info.get("success"),
                error=info.get("error"),
                reported_tokens=int(info.get("tokens") or 0),
                reported_cost_usd=float(info.get("cost_usd") or 0),
            )
        )

    model.transitions = _derive_transitions(model.stages)


def _derive_transitions(stages: list[Stage]) -> list[Transition]:
    out: list[Transition] = []
    prev_last: AgentTurn | None = None
    for stage in stages:
        if not stage.turns:
            continue
        if prev_last is not None:
            out.append(Transition(prev_last.id, stage.turns[0].id, "stage"))
        last_worker: AgentTurn | None = None  # last non-manager turn seen
        for a, b in zip(stage.turns, stage.turns[1:]):
            if a.role != "manager":
                last_worker = a
            kind = "sequence"
            if b.is_retry:
                kind = "retry"
            elif (
                # Control moved back (or stayed) in the planner→executor→
                # reviewer chain. A manager in between (MagenticOne) does
                # not change that: reviewer → manager → executor is a loop.
                last_worker is not None
                and last_worker.role in _RETRY_ROLES
                and b.role in _RETRY_ROLES
                and _RETRY_ROLES.index(b.role) <= _RETRY_ROLES.index(last_worker.role)
            ):
                kind = "retry"
                b.is_retry = True
            out.append(Transition(a.id, b.id, kind))
        prev_last = stage.turns[-1]
    return out


# ── Local stage-file builder ────────────────────────────────────────────


def _agent_tag(metadata: dict[str, Any]) -> str | None:
    for key in ("agent", "node", "agent_role"):
        val = metadata.get(key)
        if val:
            return str(val)
    return None


def build_from_stage_file(data: dict[str, Any]) -> ExecutionModel:
    """Build the canonical model from a ``*_stages.json`` trace file."""
    platform_id = str(data.get("platform_id") or "")
    story_id = str(data.get("story_id") or "")
    model = ExecutionModel(platform_id=platform_id, story_id=story_id, source="local")

    stages_raw: dict[str, Any] = data.get("stages") or {}
    all_turns: list[AgentTurn] = []
    stage_info: dict[str, dict[str, Any]] = {}

    for key, stage in stages_raw.items():
        stage_info[key] = {
            "start_time": stage.get("start_time"),
            "end_time": stage.get("end_time"),
            "duration_ms": float(stage.get("wall_clock_seconds") or 0) * 1000,
            "success": stage.get("success"),
            "error": stage.get("error_message") or None,
            "tokens": int(stage.get("tokens_input") or 0) + int(stage.get("tokens_output") or 0),
            "cost_usd": float(stage.get("cost_usd") or 0),
        }
        all_turns.extend(_turns_from_stage(key, stage))

    if not any(_agent_tag(m.get("metadata") or {}) for st in stages_raw.values() for m in st.get("messages", [])):
        model.notes.append("Local trace carries no agent identity; one turn per stage.")

    _assemble(model, all_turns, stage_info)
    return model


def _turns_from_stage(key: str, stage: dict[str, Any]) -> list[AgentTurn]:
    messages: list[dict[str, Any]] = stage.get("messages") or []
    tool_calls: list[dict[str, Any]] = stage.get("tool_calls") or []

    turns: list[AgentTurn] = []
    current: AgentTurn | None = None
    tool_msg_owner: list[AgentTurn] = []  # turn owning the k-th tool-role message
    step_n = 0

    def new_turn(role: str, raw: str, is_retry: bool, ts: str | None) -> AgentTurn:
        t = AgentTurn(id=f"{key}-{len(turns) + 1}", role=role, raw_name=raw, stage_key=key, start_time=ts, is_retry=is_retry)
        turns.append(t)
        return t

    for msg in messages:
        role_msg = str(msg.get("role") or "")
        meta = msg.get("metadata") or {}
        tag = _agent_tag(meta)
        ts = msg.get("timestamp")

        if tag:
            agent = normalise_agent_name(tag) or ("other", tag.split("/")[0], False)
            role, clean, is_retry = agent
            if current is None or current.role != role or current.raw_name != clean:
                current = new_turn(role, clean, is_retry, ts)
        elif role_msg == "user":
            continue
        elif current is None:
            current = new_turn("other", "agent", False, ts)

        if role_msg in ("assistant", "ai"):
            step_n += 1
            current.steps.append(
                Step(
                    id=f"{key}-s{step_n}",
                    kind="llm",
                    name=meta.get("model") or "llm",
                    raw_name=tag or role_msg,
                    raw_type="message",
                    start_time=ts,
                    end_time=ts,
                    tokens_in=int(meta.get("tokens_in") or 0),
                    tokens_out=int(meta.get("tokens_out") or 0),
                    model=meta.get("model"),
                    output=_excerpt(msg.get("content")),
                )
            )
        elif role_msg == "tool":
            tool_msg_owner.append(current)
        current.end_time = ts or current.end_time

    if not turns and tool_calls:
        turns.append(AgentTurn(id=f"{key}-1", role="other", raw_name="agent", stage_key=key))

    # Attribute tool calls: by matching tool-role messages when the trace has
    # them, otherwise everything goes to the executor (or the only turn).
    owners: list[AgentTurn]
    if len(tool_msg_owner) >= len(tool_calls) and tool_calls:
        owners = tool_msg_owner[: len(tool_calls)]
    else:
        fallback = next((t for t in turns if t.role == "executor"), turns[0] if turns else None)
        owners = [fallback] * len(tool_calls) if fallback else []

    for i, (tc, owner) in enumerate(zip(tool_calls, owners), start=1):
        success = tc.get("success")
        owner.steps.append(
            Step(
                id=f"{key}-t{i}",
                kind="tool",
                name=str(tc.get("tool_name") or "tool"),
                raw_name=str(tc.get("tool_name") or "tool"),
                raw_type="tool_call",
                start_time=tc.get("timestamp"),
                end_time=tc.get("timestamp"),
                duration_ms=float(tc.get("duration_ms") or 0),
                success=bool(success) if success is not None else None,
                error=tc.get("error"),
                input=_excerpt(tc.get("arguments")),
                output=_excerpt(tc.get("result")),
            )
        )

    for t in turns:
        t.duration_ms = _duration_ms(t.start_time, t.end_time)
    return [t for t in turns if t.steps]
