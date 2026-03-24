# LangSmith Integration + LangGraph Upgrade — Design Spec

**Date:** 2026-03-24
**Status:** Approved for implementation
**Scope:** LangGraph adapter rewrite (StateGraph) + LangSmith tracing client + DESMET webUI trace tab

---

## 1. Background & Motivation

The current LangGraph adapter uses the legacy `langchain.agents.create_agent` API and declares
`trace_format: "LangSmith"` in its metadata, but never actually integrates LangSmith. Langfuse
is used for all platforms uniformly.

This spec covers two improvements made together because they are mutually reinforcing:

1. **Graph upgrade** — rewrite the adapter to use an explicit `StateGraph`
   (planner → executor → validator) so that LangGraph runs are evaluated on the framework's
   actual architectural differentiator (conditional routing, persistent state), not a generic
   ReAct loop that any framework could replicate.

2. **LangSmith integration** — add a LangSmith client, proxy API endpoints, and a webUI trace
   tab so that the richer graph-node traces produced by the upgraded adapter are surfaced inline
   in the DESMET scoring page.

### Why both together

The graph upgrade is what makes LangSmith traces meaningful. An upgraded adapter running against
the legacy `create_agent` API produces flat LangSmith runs with no node topology. The two changes
only deliver full value when shipped together.

### Comparative fairness

Langfuse remains the consistent tracing backend for **all 9 platforms**. LangSmith is additive
and LangGraph-only. Programmatic DESMET metrics (tokens, cost, duration, iterations) continue to
be extracted from the Langfuse trace and the local `AgentTrace`, so cross-platform comparison is
unaffected.

---

## 2. LangGraph Adapter Rewrite

### 2.1 Graph topology

Each SDLC stage runs the same graph structure internally:

```
START
  └─▶ planner_node       LLM call — reads task prompt, emits structured plan into state
        └─▶ executor_node  LLM call + tools — executes one step of the plan
              └─▶ tool_node  (LangGraph ToolNode) — runs any tool_calls from executor
                    └─▶ validator_node  structured check — inspects workspace
                          ├─▶ executor_node  (if check fails and retry_count < MAX_RETRIES)
                          └─▶ END            (if check passes OR retry_count >= MAX_RETRIES)
```

`MAX_RETRIES` defaults to 3. The graph's iteration limit guard is separate from DESMET's
`max_iterations` (which caps total LLM calls, not validator loops).

### 2.2 State schema

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]  # LangGraph built-in reducer
    plan: str                    # planner output, carried into executor system prompt
    stage: str                   # "requirements" | "codegen" | "testing" | "deploy"
    retry_count: int             # validator loop count
    workspace: str               # absolute path, for validator file checks
    validator_passed: bool       # set by validator, read by conditional edge
```

### 2.3 Node responsibilities

**`planner_node`**
- Receives the DESMET stage prompt (requirements / codegen / testing / deploy)
- Emits a concise numbered plan into `state["plan"]`
- Single LLM call, no tools
- LangSmith run type: `"chain"` → child `"llm"`

**`executor_node`**
- Reads `state["plan"]` and `state["messages"]` history
- Calls LLM with tools bound
- If LLM returns tool_calls, routes to `tool_node` automatically (LangGraph built-in)
- If LLM returns final text, routes to `validator_node`
- LangSmith run type: `"chain"` → child `"llm"` → grandchild `"tool"` (per tool call)

**`tool_node`**
- Standard `langgraph.prebuilt.ToolNode` wrapping the DESMET tool set
- No LLM call; deterministic execution
- Returns tool results into `messages`, routes back to `executor_node`
- LangSmith run type: `"tool"`

**`validator_node`**
- Deterministic; no LLM call
- Checks workspace state (see §2.4)
- Sets `state["validator_passed"]` and increments `state["retry_count"]`
- LangSmith run type: `"chain"` (fast, no model)

### 2.4 Validator checks per stage

| Stage | Check | Pass condition |
|---|---|---|
| `requirements` | File existence + content | Any `.md` or `.txt` in workspace AND file contains ≥ 3 of: `functional`, `non-functional`, `acceptance`, `constraint` (case-insensitive) |
| `codegen` | File existence + syntax | At least one `.py` file written AND `py_compile.compile()` returns without error |
| `testing` | Test file + test functions | At least one `test_*.py` or `*_test.py` AND file contains `def test_` |
| `deploy` | Deployment artefact | `docker-compose.yaml` exists in workspace |

Validator reads the workspace path from `state["workspace"]`. All checks are pure filesystem
operations — no LLM call, no token cost.

### 2.5 Conditional routing

```python
from langgraph.graph import StateGraph, END

def route_after_validator(state: AgentState) -> str:
    if state["validator_passed"]:
        return END
    if state["retry_count"] >= MAX_RETRIES:
        return END   # give up gracefully, stage marked hit_limit=True
    return "executor_node"

# Graph construction (required before calling astream):
builder = StateGraph(AgentState)
builder.add_node("planner_node", planner_node)
builder.add_node("executor_node", executor_node)
builder.add_node("tool_node", ToolNode(tools))
builder.add_node("validator_node", validator_node)
builder.set_entry_point("planner_node")
builder.add_edge("planner_node", "executor_node")
# executor_node → tool_node routing is handled automatically by ToolNode
builder.add_conditional_edges("validator_node", route_after_validator)
graph = builder.compile()  # compile() returns a CompiledStateGraph (a LangChain Runnable)
```

### 2.6 LangSmith tracing (automatic)

No code changes required for LangSmith tracing itself. When the following env vars are set,
LangGraph automatically traces every node execution to LangSmith:

```
LANGSMITH_API_KEY=lsv2_pt_...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=desmet-evaluation   # optional but recommended
```

The adapter captures the LangSmith run ID after graph execution via the LangChain run manager
and stores it in the stage result for webUI retrieval.

### 2.7 LangSmith run ID capture

The adapter pre-generates a `run_id` UUID before each stage's graph invocation and passes it
through the LangGraph `RunnableConfig`. `RunnableConfig` has an explicit `run_id` field
(`Optional[uuid.UUID]`); when `LANGCHAIN_TRACING_V2=true`, LangSmith reads this field and
uses it as the top-level trace run ID, making retrieval deterministic.

```python
import uuid
from langchain_core.runnables import RunnableConfig

# Per stage — call once per stage invocation:
run_id = uuid.uuid4()
config: RunnableConfig = {
    "run_id": run_id,
    "callbacks": [langfuse_callback],      # existing Langfuse callback unchanged
    "run_name": f"desmet-langgraph-{stage_name}",
}

async for chunk in graph.astream(initial_state, config=config):
    ...

# After astream() completes — run_id is already known, no inspection needed:
langsmith_run_id = str(run_id) if langsmith_tracing_enabled else None
stage_result.langsmith_run_id = langsmith_run_id
```

`langsmith_tracing_enabled` is `True` when both `LANGCHAIN_TRACING_V2=true` and
`LANGSMITH_API_KEY` are present in the environment. If either is absent, `langsmith_run_id`
stays `None` and no LangSmith features are activated.

This field is stored in `StageResult` (new optional field `langsmith_run_id: str | None = None`).
The runner persistence layer serialises it per-stage (see §4.4 for details).

---

## 3. LangSmith Client

### 3.1 New file: `src/desmet/webui/langsmith_client.py`

Mirrors the structure of `langfuse_client.py`. Uses `httpx.AsyncClient` against the LangSmith
REST API (`https://api.smith.langchain.com`).

**Authentication:** `X-API-Key: {LANGSMITH_API_KEY}` header (personal access token).

**Functions:**

```python
async def check_status() -> dict[str, Any]:
    """Returns {"available": bool, "project": str | None}"""

async def fetch_run_tree(run_id: str) -> dict[str, Any] | None:
    """
    Fetches a LangSmith run and its full child-run tree.
    Normalises to the same shape as langfuse_client.fetch_trace() observations:
    {
        "run": {id, name, run_type, start_time, end_time, latency_ms,
                total_tokens, error, tags},
        "children": [
            {
                "id", "name", "run_type",          # "chain"|"llm"|"tool"
                "start_time", "end_time", "latency_ms",
                "model": str | None,
                "tokens": {"input": int, "output": int, "total": int},
                "error": str | None,
                "inputs": str | None,              # truncated to 500 chars
                "outputs": str | None,             # truncated to 500 chars
                "children": [...]                  # recursive
            }
        ]
    }
    """
```

**LangSmith API endpoints used:**
- `GET /runs/{run_id}` — fetch single run metadata
- `GET /runs?parent_run_id={run_id}&limit=100` — fetch child runs

The query parameter name for child-run filtering is `parent_run_id` (consistent with the
LangSmith Python SDK's `Client.list_runs(parent_run_id=...)` method). Implementers should
verify against the live API reference at `https://api.smith.langchain.com/docs` if the SDK
version changes. If raw HTTP calls return empty children, switch to the `langsmith` Python SDK's
`Client.list_runs()` instead of direct HTTP.

Tree is assembled client-side from flat child list.

### 3.2 Environment variables

| Variable | Required | Default |
|---|---|---|
| `LANGSMITH_API_KEY` | Yes (for LangSmith features) | — |
| `LANGCHAIN_TRACING_V2` | Yes (for automatic tracing) | — |
| `LANGCHAIN_PROJECT` | No | `"default"` |
| `LANGSMITH_BASE_URL` | No | `https://api.smith.langchain.com` |

If `LANGSMITH_API_KEY` is not set, all LangSmith features degrade gracefully: `check_status()`
returns `{"available": false}`, `fetch_run_tree()` returns `None`, the webUI tab is hidden.

---

## 4. Backend API Changes

### 4.1 New endpoints in `src/desmet/webui/api.py`

```
GET /api/langsmith/status
    → {"available": bool, "project": str | None}

GET /api/langsmith/runs/{run_id}
    → run tree (same shape as langsmith_client.fetch_run_tree output)
    → {"error": "..."} if not found or LangSmith unavailable
```

### 4.2 Updated: `GET /api/config`

Adds `langsmith_available: bool` so the frontend knows whether to show the LangSmith tab.

**Python backend** (`api.py`, `get_config()`):

```python
from desmet.webui.langsmith_client import check_status as langsmith_check_status

@router.get("/api/config")
async def get_config():
    langsmith_status = await langsmith_check_status()
    return {
        # ... existing fields ...
        "langsmith_available": langsmith_status["available"],
    }
```

**TypeScript frontend** (`api.ts`, `AppConfig` interface):

```typescript
interface AppConfig {
  // ... existing fields ...
  langsmith_available?: boolean;
}
```

The frontend checks `config.langsmith_available` to conditionally render the LangSmith tab.
If the field is absent or `false`, the tab is hidden and the existing single-tab behaviour is
preserved.

### 4.3 Updated: `GET /api/dashboard/scoring/{platform_id}/{story_id}`

Adds `langsmith_run_id: str | None` to the response (read from persisted stage trace JSON).

### 4.4 `StageResult` model update and persistence

New optional field appended to `StageResult` in `src/desmet/harness/results.py` (after
`raw_output`):

```python
langsmith_run_id: str | None = None
```

**Runner serialisation** (`src/desmet/harness/runner.py`, `_save_stage_trace`):

The existing `stage_entry` dict built per-stage must include this field:

```python
stage_entry: dict[str, Any] = {
    # ... existing fields ...
    "langsmith_run_id": sr.langsmith_run_id,   # add this line
}
```

This writes `langsmith_run_id` into `stages_data[stage_key]` alongside the other per-stage
fields, producing JSON of the form:

```json
{
  "execution_id": "...",
  "langfuse_trace_id": "...",
  "stages": {
    "requirements": { "langsmith_run_id": "uuid-str-or-null", ... },
    "codegen": { "langsmith_run_id": "uuid-str-or-null", ... }
  }
}
```

**Scoring endpoint** (`GET /api/dashboard/scoring/{platform_id}/{story_id}`):

Reads the first non-`None` `langsmith_run_id` across stages (requirements → codegen → testing →
deploy):

```python
stages = raw_trace.get("stages", {})
langsmith_run_id = next(
    (s.get("langsmith_run_id") for s in stages.values() if s.get("langsmith_run_id")),
    None,
)
```

No separate `StoryMetrics` dataclass is involved.

---

## 5. Frontend Changes

### 5.1 Scoring page (`Scoring.svelte`) — LangGraph only

When `platform_id === "langgraph"` and `langsmith_run_id` is present, the trace section shows
two tabs:

```
┌─────────────────────────────────────────────┐
│  [ Langfuse Trace ]  [ LangSmith Graph ]    │
└─────────────────────────────────────────────┘
```

- **Langfuse Trace tab** — existing `TraceViewer` component, unchanged
- **LangSmith Graph tab** — new `LangSmithTraceViewer` component (see §5.2)

If `langsmith_run_id` is absent (LangSmith not configured or old run), no tabs are shown —
existing behaviour is preserved.

`platform_id` and `story_id` are already available in `Scoring.svelte` as props passed from
the parent routing component (line 63–64 of `NewRun.svelte` confirms they are passed as
`platform_id: selectedPlatform, story_id: selectedStory`). No additional prop threading is
required.

### 5.2 New component: `LangSmithTraceViewer.svelte`

Fetches `GET /api/langsmith/runs/{run_id}` and renders the run tree.

Reuses `SpanNode.svelte` by normalising each `LangSmithRun` into a `LangfuseObservation`
before passing it to the component. The mapping is:

| LangSmith field | `LangfuseObservation` field | Notes |
|---|---|---|
| `run_type === "llm"` | `type: "generation"` | renders ✨ icon (SpanNode checks `type === 'generation'`) |
| `run_type === "tool"` | `type: "span"` | renders 📂 icon (SpanNode has no separate tool icon) |
| `run_type === "chain"` | `type: "span"` | renders 📂 icon, shows node name |
| `inputs` | `input` | field renamed |
| `outputs` | `output` | field renamed |
| `tokens` | `tokens` | identical shape |
| `model` | `model` | identical |
| `latency_ms` | `latency_ms` | identical |
| `error` | `status_message` | non-null error maps to `status_message`; `level` → `"ERROR"` |
| — (no error) | `level: "DEFAULT"` | constant; `SpanNode.svelte` reads `level` for error styling |
| — | `cost: 0` | LangSmith does not expose cost; zero prevents render errors |
| — | `children` | mapped recursively |

**`rootLatency` prop:** `SpanNode.svelte` requires `rootLatency: number` (no default).
`LangSmithTraceViewer.svelte` must pass the top-level run's `latency_ms` (from
`LangSmithRunTree.run.latency_ms`) as `rootLatency` when rendering each root-level child,
and propagate it unchanged through recursive `<svelte:self>` calls.

The normalisation function is a pure TypeScript helper inside `LangSmithTraceViewer.svelte`
and is not exported. Node names (`planner_node`, `executor_node`, `tool_node`,
`validator_node`) are preserved in the `name` field, giving the evaluator a clear view of
graph execution.

### 5.3 API types (`api.ts`)

New types:

```typescript
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
```

The existing `StoryScoreData` interface gains `langsmith_run_id`:

```typescript
export interface StoryScoreData {
  // ... existing fields ...
  langsmith_run_id?: string | null;
}
```

New API function:

```typescript
export const fetchLangSmithRun = (runId: string) =>
  request<LangSmithRunTree>('/api/langsmith/runs/' + runId);
```

---

## 6. Data Flow

```
LangGraph StateGraph execution (per DESMET stage)
  │
  ├─▶ Langfuse CallbackHandler (existing)
  │     └─▶ Langfuse: generic span tree (as before)
  │
  ├─▶ LangSmith automatic tracing (new, env-var driven)
  │     └─▶ LangSmith: planner_node / executor_node / tool_node / validator_node spans
  │
  └─▶ Local AgentTrace (existing)
        └─▶ messages, tool_calls, tokens, timing

After streaming:
  adapter uses pre-generated run_id UUID (set before astream())
  stores str(run_id) in StageResult.langsmith_run_id
  persisted to {results_dir}/{platform}/{story}/{exec_id}_stages.json

Dashboard API:
  /api/dashboard/scoring/langgraph/{story_id}
    returns langsmith_run_id alongside langfuse_trace_id

Frontend:
  Scoring page (LangGraph) → two tabs
  LangSmith tab → GET /api/langsmith/runs/{run_id}
               → LangSmithTraceViewer renders node tree
```

---

## 7. Files Changed / Created

| File | Change |
|---|---|
| `src/desmet/adapters/langgraph.py` | Full rewrite — StateGraph, planner/executor/validator nodes |
| `src/desmet/harness/results.py` | Add `langsmith_run_id: str | None = None` to `StageResult` |
| `src/desmet/harness/runner.py` | Add `langsmith_run_id` to `stage_entry` dict in `_save_stage_trace` |
| `src/desmet/webui/langsmith_client.py` | New — LangSmith REST API client |
| `src/desmet/webui/api.py` | Add `/api/langsmith/status`, `/api/langsmith/runs/{id}`, update `/api/config` and scoring endpoint |
| `src/desmet/webui/frontend/src/lib/api.ts` | Add `LangSmithRun`, `LangSmithRunTree` types; update `StoryScoreData` and `AppConfig`; add `fetchLangSmithRun` |
| `src/desmet/webui/frontend/src/lib/components/LangSmithTraceViewer.svelte` | New component |
| `src/desmet/webui/frontend/src/lib/pages/Scoring.svelte` | Add two-tab trace section for LangGraph |
| `.env.example` | Add `LANGSMITH_API_KEY`, `LANGCHAIN_TRACING_V2`, `LANGCHAIN_PROJECT` |

---

## 8. Out of Scope

- LangSmith for any platform other than LangGraph
- Replacing Langfuse with LangSmith as the primary tracing backend
- LangSmith dataset / evaluation features (only trace viewing is in scope)
- Upgrading any other adapter's graph implementation
- LangSmith organisation / service key setup (personal access token only)
