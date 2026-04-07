# Deploy stage: Dockerfile + port mapping

**Date:** 2026-04-07
**Status:** Approved (pending user review)

## Problem

The deploy stage prompt currently requires only `docker-compose.yaml` and the validator only checks that file's existence. Two consequences:

1. **No Dockerfile required.** An agent can write a compose file referencing a published image (`image: python:3.11`) and pass validation without ever packaging the baseline application. The whole point of the deploy stage — verifying the agent can containerize the *baseline* app — gets bypassed.

2. **Silent port mismatch.** The harness writes a `.env` file at deploy time containing `PORT=<platform.deploy_port>` from `config/platforms.yaml` (8001 for langgraph, 8002 for crewai, …, 8009 for n8n) and curls `http://localhost:<deploy_port>/health` for the health check. But the prompt never tells the agent about this convention. If the agent hardcodes `"8000:8000"` in the compose `ports:` block, the host-side port is wrong and `health_check` curls a port that nothing is listening on. Validation passes (compose file exists), but the deploy is functionally broken in a way the eval pipeline can't see.

## Goal

Make every successful deploy stage produce:
- A `Dockerfile` that builds the baseline app, and
- A `docker-compose.yaml` that maps host port `${PORT}` (injected by the harness) to the application's container-internal port.

Make the validator enforce both, so a model that skips either fails the stage and gets an actionable retry hint.

## Non-goals

- Per-story port configuration. All current basic/intermediate stories use FastAPI/uvicorn on container port `8000`. We pin that as the convention. If a future story needs a different internal port, revisit then (YAGNI).
- Story-level health endpoint configuration. The harness defaults to `/health` which matches the baseline.
- Validator-side compose schema parsing. We do a literal substring lint, not a YAML parse. If the agent writes valid-but-weird compose, we accept it.
- Other compose conventions (`${PORT:-8000}` default-fallback syntax, `$PORT` shell-style). The worked example in the prompt shows `${PORT}` and the validator matches that exact form. The agent will copy what it sees.

## Design

### 1. Prompt change — `config/prompts.yaml`

Replace the `deploy.tasks` list. New ordering:

```yaml
deploy:
  preamble: "Build, deploy, and verify the project on the remote server."
  tasks_preamble: "## Steps"
  tasks:
    - "Install dependencies: uv sync"
    - "Run the test suite: uv run pytest"
    - "Build the package: uv build"
    - >-
      Write a `Dockerfile` in the workspace root that builds and runs
      the application. Use a Python 3.11 base image, copy the project,
      run `uv sync --no-dev`, and start the service with
      `uvicorn app.main:app --host 0.0.0.0 --port 8000`. The container
      MUST listen on port 8000.
    - >-
      Write a `docker-compose.yaml` in the workspace root that builds
      from the Dockerfile (`build: .`) and maps host port `${PORT}` to
      container port 8000. The harness injects the `PORT` environment
      variable via a `.env` file at deploy time, so the compose MUST
      use `${PORT}` literally on the host side — do NOT hardcode a
      host port.

      Minimal example:
        services:
          app:
            build: .
            ports:
              - "${PORT}:8000"
    - 'Push to remote server: deploy_remote(action="push")'
    - 'Start/restart the service: deploy_remote(action="restart")'
    - 'Verify the deployment: deploy_remote(action="health_check")'
    - >-
      Report success or failure, then STOP. A separate reviewer will
      validate the workspace automatically.
```

The two new artifact-creation steps slot in **after** `uv build` and **before** `deploy_remote(push)` so that everything in the workspace is final before the agent pushes.

### 2. Validator change — `src/desmet/adapters/_validation.py`

Replace the deploy branch of `validate_workspace`:

```python
if stage == "deploy":
    compose = ws / "docker-compose.yaml"
    dockerfile = ws / "Dockerfile"
    if not compose.exists() or not dockerfile.exists():
        return False
    # Lint: compose must use the harness-injected ${PORT} variable on
    # the host side, otherwise health_check will curl the wrong port.
    try:
        return "${PORT}" in compose.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
```

Properties:
- **Both files required.** Closes the "image: python:3.11" loophole.
- **Literal `${PORT}` lint.** Catches the silent port-mismatch failure. Strict literal match because the prompt shows that exact form.
- **Fail-closed on read errors.** `OSError` (e.g. permission denied, encoding catastrophe) → `False` → retry. Same semantics as the existence checks for other stages.
- **`errors="ignore"` on read.** Defensive against weird Windows host encodings (BOM, utf-16). Better than crashing the validator.

### 3. Hint message change — `src/desmet/adapters/_tools.py`

Update the deploy hint in `_check_completion` so the post-Bug-B retry feedback names the specific failure mode:

```python
"deploy": (
    "Ensure both `Dockerfile` and `docker-compose.yaml` exist in the "
    "workspace root, and that docker-compose.yaml uses `${PORT}` "
    "literally on the host side of the port mapping (e.g. "
    '`"${PORT}:8000"`). The harness injects PORT via .env at deploy time.'
),
```

This hint is what the langgraph/openai_agents adapters now thread back into the executor's system prompt on retry (the Bug B fix from the prior conversation). It tells the model exactly which of the three failure modes (missing Dockerfile / missing compose / hardcoded port) to fix without making the agent re-derive the contract.

### 4. Tests — `tests/test_validation.py`

Four new cases covering each failure mode plus the happy path:

| Case | Setup | Expected |
|---|---|---|
| `test_deploy_passes_when_both_files_present_with_port_var` | write Dockerfile + compose containing `${PORT}:8000` | `True` |
| `test_deploy_fails_when_dockerfile_missing` | only compose, no Dockerfile | `False` |
| `test_deploy_fails_when_compose_missing` | only Dockerfile | `False` |
| `test_deploy_fails_when_compose_hardcodes_port` | both files, compose has `8001:8000` (no `${PORT}`) | `False` |

Notes on what we deliberately do **not** test:
- `${PORT:-8000}` default-fallback syntax — strict matcher rejects this; documented as a known limitation. If we observe agents drifting to that form in real runs, broaden the matcher to a regex and add a test then.
- YAML schema validity — out of scope for a substring lint.

## Alternatives considered

- **Make the validator parse YAML and walk `services.*.ports`.** Catches more failure modes (e.g. `${PORT}` in a comment) but adds a YAML dependency and parsing surface area for negligible practical gain. Substring lint is sufficient for the failure mode we observed.
- **Surface `platform_id` and `deploy_port` in the prompt and have the agent hardcode the right number.** Couples the agent to platform identity, requires plumbing through context, and breaks the property that the same generated artifact works on every platform. Rejected in Q1 of brainstorming.
- **Add a story-level `internal_port` field to user story YAML.** Premature configurability; every current story uses 8000. Revisit if a future story actually needs Flask/5000 or similar.
- **Extract a "stage artifact spec" data class shared by validator and prompt builder.** YAGNI for a one-stage change. The duplication between prompt YAML and validator code is small and intentional (one is the contract, the other is the enforcement).

## Risks and mitigations

- **Risk:** Agent uses `$PORT` (no braces) instead of `${PORT}`. Both are valid in compose v2, but the strict matcher rejects `$PORT`. **Mitigation:** the worked example in the prompt shows `${PORT}` and agents reliably copy worked examples. If we see drift, broaden the matcher with a regex.
- **Risk:** Agent writes `${PORT}` in a comment but hardcodes the actual port. **Mitigation:** the substring is in the file → lint passes → deploy still fails at health check. The validator can't catch every form of malice, only common honest mistakes. The retry hint will guide the model to the right fix when health check fails.
- **Risk:** Existing benchmark runs that previously "passed" the deploy stage with a hardcoded port now fail. **Mitigation:** intentional. Those runs were silently broken (curling the wrong port). Surfacing the failure is the point.

## Out of scope for this change

- Updating any existing baseline `Dockerfile` or `docker-compose.yaml` (none exist — agent generates from scratch every time).
- The Bug B retry-feedback plumbing (already done in the prior conversation; this change just provides a better hint string for that mechanism to use).
- Multi-service compose files (e.g. app + database). Current stories are single-service; revisit if needed.
- Per-platform Dockerfile templates. Every platform's deploy stage runs the same prompt and produces the same artifact shape — only the host-side port differs, and that's handled via `${PORT}`.
