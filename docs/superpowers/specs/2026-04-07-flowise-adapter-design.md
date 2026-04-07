# Flowise Platform Adapter — Design Spec

**Date:** 2026-04-07
**Status:** Approved

## Summary

Implement the Flowise adapter as the second visual/workflow platform adapter. This also extracts a shared `VisualAgentAdapter` base class from the n8n implementation, capturing the retry loop, trace management, and SDLC stage methods that both adapters (and future LangFlow/Dify) share.

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Agent approach | Flowise native Agent node | Same as n8n — evaluate the platform's real capabilities |
| LLM credentials | Container env var (`OPENAI_API_KEY`) | Flowise auto-detects; no API provisioning needed |
| Stage mapping | 4 separate chatflows | Same as n8n — matches `_execute_stage` pattern |
| Agent pattern | Single agent node per stage | Same as n8n |
| Retry handling | Shared adapter-side retry loop | Extracted into `VisualAgentAdapter` base |
| Shared base | Extract `VisualAgentAdapter` now | Two implementations make the abstraction concrete, not premature |

## Architecture

```
VisualPlatformAdapter (harness/adapter.py)
    └── VisualAgentAdapter (adapters/_visual_base.py)  ← NEW shared base
            ├── N8nAdapter (adapters/n8n.py)           ← refactored
            └── FlowiseAdapter (adapters/flowise.py)   ← new
```

### VisualAgentAdapter (shared base)

Provides:
- `_execute_visual_stage(stage_name, prompt_fn, result_cls, context)` — retry loop: build prompt → call `_run_workflow` → validate workspace → retry or return result
- `_translate_workspace(host_path)` — host path → `/desmet-results/...` container path
- Trace lifecycle (start_trace, record_message, build_stage_result, finish_trace)
- 4 SDLC stage methods delegating to `_execute_visual_stage`

Subclasses implement:
- `_run_workflow(stage_name, prompt, system_msg, workspace) -> dict` — create, execute, clean up a workflow. Returns raw execution data.
- `_collect_execution_metrics(trace, exec_data)` — platform-specific metric extraction
- `initialize()` / `shutdown()` / `health_check()` — platform-specific lifecycle

### FlowiseClient

Thin async HTTP wrapper using `httpx.AsyncClient`:

```python
class FlowiseClient:
    def __init__(self, base_url: str, api_key: str | None = None): ...

    # Chatflows
    async def create_chatflow(self, definition: dict) -> str
    async def delete_chatflow(self, chatflow_id: str) -> None

    # Execution (synchronous — returns result directly)
    async def predict(self, chatflow_id: str, question: str) -> dict

    # Health
    async def health_check(self) -> bool
    async def close(self) -> None
```

**Auth:** `Authorization: Bearer <apikey>` header. Optional — read from `FLOWISE_API_KEY` env var or `config["api_key"]`.

**No credential provisioning** — LLM API keys are passed as container env vars.

**No execution polling** — `POST /api/v1/prediction/{chatflowId}` returns results synchronously.

### Chatflow Templates

Python dicts in `src/desmet/adapters/flowise_templates.py`, one per SDLC stage.

Each chatflow contains:
- **Agent node** — Flowise agent node with system message and tool connections
- **LLM node** — ChatOpenAI node, model name configured, credential resolved from env
- **Tool nodes** — Custom Tool nodes with JS code for execute_shell, read_file, write_file (same sandbox logic as n8n, adapted for Flowise node schema)

`build_chatflow()` function deep-copies a template and injects prompt, system message, workspace path, and model name.

### FlowiseAdapter

```python
class FlowiseAdapter(VisualAgentAdapter):
    def __init__(self, config: dict | None = None): ...

    # Lifecycle
    async def initialize(self) -> None
    async def shutdown(self) -> None
    async def health_check(self) -> bool

    # VisualPlatformAdapter contract
    async def create_workflow(self, definition) -> str
    async def execute_workflow(self, workflow_id, inputs) -> dict
    async def delete_workflow(self, workflow_id) -> None

    # VisualAgentAdapter abstract methods
    async def _run_workflow(self, stage_name, prompt, system_msg, workspace) -> dict
    def _collect_execution_metrics(self, trace, exec_data) -> None
```

`_run_workflow`: creates chatflow from template, calls `predict()`, deletes chatflow, returns result dict.

`_collect_execution_metrics`: extracts timing from response metadata. Flowise returns token usage in the prediction response when available.

## Infrastructure Changes

**`docker-compose.yaml`** — additions to flowise service:

```yaml
environment:
  # existing vars...
  - OPENAI_API_KEY=${OPENAI_API_KEY:-}
  - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
  - FLOWISE_SECRETKEY_OVERWRITE=${FLOWISE_API_KEY:-}
volumes:
  - flowise_data:/root/.flowise
  - ${DESMET_RESULTS_DIR:-../results}:/desmet-results
```

**`registry.py`** — add `"flowise"` to `_IMPLEMENTED_PLATFORMS`.

## N8nAdapter Refactor

Refactor `N8nAdapter` to inherit from `VisualAgentAdapter`:
- Move retry loop, trace management, SDLC methods, `_translate_workspace` into `VisualAgentAdapter`
- N8nAdapter implements `_run_workflow` (create n8n workflow, execute, poll, delete, return exec data)
- N8nAdapter implements `_collect_execution_metrics` (existing logic, unchanged)
- N8nAdapter keeps `initialize`/`shutdown` (credential provisioning stays)
- All existing n8n tests must continue to pass

## File Inventory

| File | Action |
|---|---|
| `src/desmet/adapters/_visual_base.py` | **New** — `VisualAgentAdapter` shared base |
| `src/desmet/adapters/flowise.py` | Replace stub with `FlowiseAdapter` + `FlowiseClient` |
| `src/desmet/adapters/flowise_templates.py` | **New** — chatflow templates for 4 stages |
| `src/desmet/adapters/n8n.py` | Refactor to inherit from `VisualAgentAdapter` |
| `infrastructure/docker-compose.yaml` | Add env vars + workspace volume to flowise service |
| `src/desmet/adapters/registry.py` | Add `"flowise"` to `_IMPLEMENTED_PLATFORMS` |
| `tests/test_flowise_adapter.py` | **New** — unit tests |
| `tests/test_n8n_adapter.py` | Verify no regressions after refactor |
| `tests/test_visual_base.py` | **New** — unit tests for shared base |

## Testing

- **`test_visual_base.py`**: Test `_execute_visual_stage` retry loop with mock subclass, `_translate_workspace` path mapping
- **`test_flowise_adapter.py`**: FlowiseClient init/auth, chatflow template structure/parameterization, adapter structure/metadata, stage execution with mocked client
- **`test_n8n_adapter.py`**: All 19 existing tests must pass after refactor
