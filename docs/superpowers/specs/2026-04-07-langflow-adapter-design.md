# LangFlow Platform Adapter — Design Spec

**Date:** 2026-04-07
**Status:** Approved

## Summary

Implement the LangFlow adapter as the third visual/workflow platform adapter, inheriting from the shared `VisualAgentAdapter` base class. Follows the same pattern as Flowise: synchronous execution, env-var credentials, flow templates.

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Agent approach | LangFlow native Agent node | Same as n8n/Flowise — evaluate native capabilities |
| LLM credentials | Container env var | Same as Flowise — LangFlow auto-detects |
| Stage mapping | 4 separate flows | Established pattern |
| Execution model | Synchronous (`POST /api/v1/run/{id}`) | Same as Flowise — no polling |
| Base class | `VisualAgentAdapter` | Already extracted, provides retry/trace/SDLC methods |

## Components

### LangFlowClient

Async httpx wrapper for LangFlow REST API:
- `create_flow(definition) -> str` — `POST /api/v1/flows`
- `delete_flow(flow_id)` — `DELETE /api/v1/flows/{id}`
- `run_flow(flow_id, input_value) -> dict` — `POST /api/v1/run/{id}` (synchronous)
- `health_check() -> bool` — `GET /api/v1/flows?limit=1`
- Auth: `Authorization: Bearer <key>` (optional, from `LANGFLOW_API_KEY`)

### Flow Templates

Python dicts in `langflow_templates.py` with LangFlow node types:
- Agent node, ChatOpenAI node, 3 Custom Tool nodes (execute_shell, read_file, write_file)
- `build_flow(stage_name, prompt, system_msg, workspace, model_name)` parameterizes at runtime

### LangFlowAdapter

Extends `VisualAgentAdapter`:
- `_run_workflow`: create flow → run → cleanup → return result
- `_collect_execution_metrics`: extract token usage from run response
- `initialize/shutdown/health_check`: client lifecycle
- No credential provisioning — env vars on container

## Infrastructure Changes

Docker compose langflow service additions:
```yaml
environment:
  - OPENAI_API_KEY=${OPENAI_API_KEY:-}
  - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
volumes:
  - langflow_data:/app/langflow
  - ${DESMET_RESULTS_DIR:-../results}:/desmet-results
```

## File Inventory

| File | Action |
|---|---|
| `src/desmet/adapters/langflow.py` | Replace stub with LangFlowClient + LangFlowAdapter |
| `src/desmet/adapters/langflow_templates.py` | New — flow templates for 4 stages |
| `infrastructure/docker-compose.yaml` | Add env vars + workspace volume to langflow service |
| `src/desmet/adapters/registry.py` | Add `"langflow"` to `_IMPLEMENTED_PLATFORMS` |
| `tests/test_langflow_adapter.py` | New — unit tests |
