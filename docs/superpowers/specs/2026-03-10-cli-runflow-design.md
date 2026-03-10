# CLI Run Flow Improvements Design

**Date**: 2026-03-10
**Status**: Approved
**Goal**: Add `up`/`down`/`status` commands to the CLI so Docker infrastructure and platform readiness are managed from `desmet-eval` instead of manual `docker compose` commands.

## Problem

Running visual platforms (Flowise, Dify, n8n, LangFlow) and Langfuse requires manually running `docker compose --profile <name> up -d` from the `infrastructure/` directory. There is no way to check what's running or whether platforms are ready before starting an evaluation.

## New Commands

### `desmet-eval up <target>`

Starts Docker infrastructure for the given target by running `docker compose --profile <target> up -d` from the `infrastructure/` directory.

Targets map directly to existing docker-compose profiles:

| Target | Profile | Services started |
|--------|---------|-----------------|
| `flowise` | `flowise` | Flowise, postgres |
| `langflow` | `langflow` | LangFlow, postgres, redis |
| `dify` | `dify` | Dify API + web + worker, postgres, redis |
| `n8n` | `n8n` | n8n, postgres |
| `langfuse` | `langfuse` | Langfuse web + worker, postgres, clickhouse, minio, redis |
| `all` | all of the above | All visual platforms + langfuse |

After starting, the command uses `docker compose up -d --wait` which waits for healthchecks and reports which services are healthy. Subprocess timeout is 120s to allow time for multi-service targets.

`desmet-eval up` with no argument prints the available targets.

### `desmet-eval down [target]`

Stops Docker services. With a target, stops only that profile's services. Without a target, stops all DESMET services (`docker compose down`).

### `desmet-eval status`

Displays a Rich table showing:

1. **Platform readiness** — for each of the 10 platforms:
   - Python SDK platforms: checks if the package is importable (e.g. `import crewai`)
   - Docker platforms: checks if the container is running via `docker compose ps`
   - Shows: platform name, infrastructure type ("none needed" / "Docker"), status ("ready" / "not installed" / "running" / "not started")

2. **Configuration** — below the table:
   - Active model (from `DESMET_MODEL` / `DEFAULT_MODEL` / default)
   - API key status (which provider keys are set, without showing values)
   - Langfuse status (connected / not configured / not installed)

## Implementation

### New module: `src/desmet/infra.py`

Encapsulates Docker Compose interaction so the CLI stays thin.

```python
COMPOSE_FILE = Path(__file__).resolve().parent.parent.parent / "infrastructure" / "docker-compose.yaml"

PROFILE_TARGETS: dict[str, list[str]] = {
    "flowise": ["flowise"],
    "langflow": ["langflow"],
    "dify": ["dify"],
    "n8n": ["n8n"],
    "langfuse": ["langfuse"],
    "all": ["flowise", "langflow", "dify", "n8n", "langfuse"],
}

# Maps platform IDs to their importable Python package name (None = Docker-only)
PLATFORM_PACKAGES: dict[str, str | None] = {
    "langgraph": "langgraph",
    "crewai": "crewai",
    "microsoft_autogen": "autogen",
    "openai_agents_sdk": "agents",
    "google_adk": "google.adk",
    "semantic_kernel": "semantic_kernel",
    "flowise": None,
    "langflow": None,
    "dify": None,
    "n8n": None,
}

# Maps platform IDs to their Docker container name (None = no Docker needed)
PLATFORM_CONTAINERS: dict[str, str | None] = {
    "langgraph": None,
    "crewai": None,
    "microsoft_autogen": None,
    "openai_agents_sdk": None,
    "google_adk": None,
    "semantic_kernel": None,
    "flowise": "desmet-flowise",
    "langflow": "desmet-langflow",
    "dify": "desmet-dify-api",
    "n8n": "desmet-n8n",
}

def compose_up(target: str) -> subprocess.CompletedProcess
def compose_down(target: str | None) -> subprocess.CompletedProcess
def get_container_status(container_name: str) -> str  # "running" | "exited" | "not started" | "docker not found"
def is_package_importable(package_name: str) -> bool
def get_platform_status() -> list[PlatformStatus]  # dataclass with name, infra_type, status
def get_config_status() -> ConfigStatus  # dataclass with model, provider, api_key_set, langfuse_status
```

### CLI additions in `src/desmet/cli.py`

Three new `@app.command()` functions: `up`, `down`, `status`. Each delegates to `infra.py` and uses Rich for output.

### No changes to

- `runner.py` — the runner doesn't need to know about Docker
- `docker-compose.yaml` — existing profiles are already correct
- Existing `run`, `list-platforms`, `list-stories` commands

## File Impact

| File | Action |
|------|--------|
| `src/desmet/infra.py` | New — ~100 lines |
| `src/desmet/cli.py` | Add 3 commands — ~80 lines |
| `tests/test_infra.py` | New — ~60 lines (unit tests for status checks) |
