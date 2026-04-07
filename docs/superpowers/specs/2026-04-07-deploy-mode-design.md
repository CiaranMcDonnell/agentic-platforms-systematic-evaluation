# Deploy Mode Selection — Design Spec

**Date:** 2026-04-07
**Status:** Approved

## Summary

Add a deploy mode selector to the NewRun page so users can choose between local Docker deployment and remote server deployment. The `deploy_remote` tool routes internally based on mode — the agent doesn't need to know which mode is active.

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Local deploy action | Docker Compose locally | Tests containerization without SSH overhead |
| UI placement | Per-run toggle on NewRun | Flexibility to mix local/remote across runs |
| Tool interface | Same tool, mode-aware routing | Agent-transparent; same prompts for both modes |

## Data Flow

```
NewRun UI (deploy_mode selector)
    → RunConfig.deploy_mode ("local" | "remote")
    → RunRequest → runner
    → StageContext.metadata["deploy_mode"]
    → runner sets DESMET_DEPLOY_MODE env var
    → _deploy_remote reads mode and routes:
        "local"  → docker compose in workspace
        "remote" → SSH to server (existing logic)
```

## Changes

### Frontend — NewRun.svelte

Segmented control near the Dry Run toggle:
- **Local (Docker)** — default, always available
- **Remote Server** — disabled with tooltip if `deploy_status !== "configured"`

### Frontend — api.ts

Add `deploy_mode?: string` to `RunConfig` interface (default `"local"`).

### Backend — api.py

Add `deploy_mode: str = "local"` to `RunRequest` Pydantic model. Pass through to runner config.

### Runner — runner.py

Before executing the deploy stage, set `os.environ["DESMET_DEPLOY_MODE"]` from `context.metadata["deploy_mode"]`. Clean up in finally block.

### Tool — _tools.py

`_deploy_remote` reads `os.environ.get("DESMET_DEPLOY_MODE", "local")` at the top. If `"local"`:

- **push** → no-op, return "Local mode — workspace is already available"
- **restart** → run `docker compose up -d --build` directly in the workspace directory (subprocess, no SSH). Write `.env` with `COMPOSE_PROJECT_NAME` and `PORT` first.
- **health_check** → run `curl -sf http://localhost:{port}{url}` directly (subprocess, no SSH)

If `"remote"` → existing SSH logic, unchanged.

### Tests

Add tests for local mode: push no-op, restart calls docker compose locally, health_check curls localhost.

## File Inventory

| File | Change |
|---|---|
| `src/desmet/webui/frontend/src/lib/api.ts` | Add `deploy_mode` to `RunConfig` |
| `src/desmet/webui/frontend/src/lib/pages/NewRun.svelte` | Add deploy target selector |
| `src/desmet/webui/api.py` | Add `deploy_mode` to `RunRequest` |
| `src/desmet/harness/runner.py` | Pass `deploy_mode` into context, set env var |
| `src/desmet/adapters/_tools.py` | Add local mode routing in `_deploy_remote` |
| `tests/test_deploy_remote.py` | Add tests for local mode |
