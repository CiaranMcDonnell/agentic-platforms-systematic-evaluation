# Containerized Per-Platform Evaluation Design

## Overview

Move adapter execution from in-process to per-platform Docker containers. Each platform gets its own image with only its SDK dependencies, eliminating opentelemetry and pydantic version conflicts between crewai, agent-framework, and google-adk. The harness and webui remain on the host; they communicate with the container via JSON over stdin/stdout and progress over stderr.

## Motivation

Three platform SDKs have mutually exclusive opentelemetry pins:
- crewai: `~=1.34.0`
- google-adk: `>=1.36.0, <1.39.0`
- agent-framework-core: `>=1.39.0`

The current workaround (`override-dependencies`) forces a compromise version that none of the frameworks officially support, degrading OTEL instrumentation. With per-platform containers, each adapter gets its intended otel version and tracing works at full fidelity.

This also strengthens the project's extensibility story: a user adding a new framework writes one adapter file, one Dockerfile, and one platforms.yaml entry — no dependency conflicts with existing platforms.

## Architecture

```
Host (webui + harness + runner)
  |
  |-- docker exec desmet-eval-crewai python -m desmet.harness.entrypoint context.json
  |     |-- stderr: progress lines (real-time)
  |     +-- stdout: StageResult JSON (on completion)
  |
  +-- Workspace bind-mounted at /workspace (tools read/write files directly)
```

### Docker Image Structure

**Base image** (`infrastructure/Dockerfile.base`):
Extends the existing `Dockerfile.eval`. Ubuntu 24.04, Python 3.11, uv, bun, git, Mermaid CLI. Installs the desmet package with core dependencies only (no platform extras).

Image tag: `desmet-eval-base:1.0`

**Per-platform images** (`infrastructure/Dockerfile.{platform}`):
Each extends the base and installs one platform extra.

```dockerfile
FROM desmet-eval-base:1.0
RUN uv sync --extra langgraph
```

Five images: `desmet-eval-langgraph`, `desmet-eval-crewai`, `desmet-eval-openai-agents`, `desmet-eval-agent-framework`, `desmet-eval-google-adk`.

**Build trigger**: The webui builds images lazily on first evaluation run for a platform. If the image already exists, the build is skipped. Progress shown in the UI.

### Serialization Contract

**Input (host to container)**: `StageContext` serialized to JSON, written to a temp file in the bind-mounted workspace. Fields:
- `story` — dict (dataclass fields, datetime as ISO string)
- `workspace` — always `/workspace` inside container
- `platform_id`, `model`, `temperature`, `max_iterations`, `time_budget_seconds`, `allowed_tools`, `metadata` — pass through
- `artifacts` — prior stage results as dicts, using the existing runner serialization logic (dataclasses.asdict + datetime conversion)
- `progress_callback` — not sent. The entrypoint writes progress to stderr.

**Output (container to host)**: `StageResult` (with nested `AgentTrace`) serialized to JSON, printed to stdout. Uses the same `dataclasses.asdict()` + datetime-to-isoformat conversion already in `runner.py` lines 636-718.

**Progress (container to host)**: `ProgressReporter` callback inside the container writes lines to stderr. The host reads stderr line-by-line in real time and feeds each line into the existing `_broadcast_log` -> WebSocket pipeline.

### Container Runner

New module: `src/desmet/harness/container_runner.py`

Primary function:
```python
async def run_stage_in_container(
    platform_id: str,
    stage_name: str,
    context: StageContext,
    progress_callback: Callable[[str], None] | None,
) -> StageResult
```

Steps:
1. Ensure platform image exists (lazy build if missing)
2. Start container with workspace bind-mounted at `/workspace` (reuse across stages for same platform+story, same lifecycle as current eval containers)
3. Write serialized StageContext JSON to `<workspace>/.desmet-context.json`
4. Run `docker exec <container> python -m desmet.harness.entrypoint .desmet-context.json`
5. Stream stderr line-by-line to `progress_callback`
6. Collect stdout, parse JSON into typed `StageResult` subclass
7. Clean up context file
8. Return result

Image management functions:
- `has_image(platform_id) -> bool` — check if Docker image exists
- `build_image(platform_id, progress_callback) -> bool` — build from Dockerfile
- `ensure_image(platform_id, progress_callback)` — build if missing

Container lifecycle functions (extend existing `_tools.py` patterns):
- `start_platform_container(platform_id, story_id, workspace) -> str` — start container, return name
- `stop_platform_container(platform_id, story_id)` — stop and remove

### Adapter Entrypoint

New module: `src/desmet/harness/entrypoint.py`

Runs inside the container. Invoked as `python -m desmet.harness.entrypoint <context_file>`.

Steps:
1. Read context JSON from file path argument
2. Deserialize into `StageContext` with `workspace=Path("/workspace")`
3. Set `progress_callback` to `lambda msg: print(msg, file=sys.stderr, flush=True)`
4. Import adapter via `get_adapter(platform_id)`, call `initialize()`
5. Call the stage method (`generate_requirements`, `generate_code`, etc.)
6. Serialize `StageResult` to JSON, print to stdout
7. Call `shutdown()` on adapter

Error handling: exceptions are caught, serialized as a failed `StageResult` with the error message, and printed to stdout. Non-zero exit code signals the host that something went wrong.

### Runner Integration

The existing `EvaluationRunner` gets a minimal change. Before calling the adapter in-process, check if a container image exists:

```python
if container_runner.has_image(platform_id):
    stage_result = await container_runner.run_stage_in_container(
        platform_id, stage_name, stage_ctx, progress_callback,
    )
else:
    stage_method = getattr(adapter, method_name)
    stage_result = await stage_method(stage_ctx)
```

The in-process fallback remains for development and testing (no Docker needed to run tests).

### WebUI Integration

**Image building**: The webui's infrastructure management page (already manages Docker Compose for visual platforms) gains a "Build Platform Images" action. This calls `container_runner.build_image()` for each platform, streaming build logs to the UI.

**Evaluation runs**: No change to the webui evaluation flow. The runner decides whether to use containers or in-process. Progress continues flowing via the same WebSocket channel.

## Files Changed

- `infrastructure/Dockerfile.base` — rename/extend existing `Dockerfile.eval`
- `infrastructure/Dockerfile.langgraph` — new (3 lines)
- `infrastructure/Dockerfile.crewai` — new (3 lines)
- `infrastructure/Dockerfile.openai-agents` — new (3 lines)
- `infrastructure/Dockerfile.agent-framework` — new (3 lines)
- `infrastructure/Dockerfile.google-adk` — new (3 lines)
- `src/desmet/harness/container_runner.py` — new (container orchestration)
- `src/desmet/harness/entrypoint.py` — new (runs inside container)
- `src/desmet/harness/runner.py` — modify stage execution to check for container
- `src/desmet/harness/context.py` — add `to_dict()` / `from_dict()` serialization
- `src/desmet/harness/results.py` — add `from_dict()` deserialization
- `src/desmet/harness/trace.py` — add `from_dict()` deserialization
- `src/desmet/harness/story.py` — add `to_dict()` serialization (if not sufficient)
- `src/desmet/webui/api.py` — add image build endpoint
