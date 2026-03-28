# Docker + WebUI Integration Improvements

**Date:** 2026-03-28
**Status:** Approved

## Problem

The Docker container setup has several UX and operational gaps:

1. **No shutdown lifecycle** — Docker Compose services and eval containers persist after the webui stops, leaving orphaned processes that consume resources and will fail anyway since infrastructure deps (Postgres, Redis) are down.
2. **Large images** — Base image is 3.48GB; platform images reach 5GB. Build-time tools (compilers, dev headers) are included in the runtime image unnecessarily.
3. **No build progress** — Image builds take minutes with only a spinner. No indication of what's happening or which step is running.
4. **Basic platform cards** — No image metadata (size, build date), no rebuild/delete actions, no build log visibility.

## Design

### 1. Shutdown Lifecycle

**Location:** `src/desmet/webui/api.py` — FastAPI `lifespan` shutdown hook.

On webui shutdown:
1. Call `compose_down("all")` to stop all Docker Compose profiles (visual platforms + infrastructure + Langfuse).
2. Find and remove all eval containers matching `desmet-run-*` via `docker ps -aq --filter name=desmet-run- | xargs docker rm -f`.
3. Log each action to structlog.

On startup: no change — current behaviour reports what's already running without auto-starting.

**Error handling:** Shutdown cleanup is best-effort. If Docker is unreachable or a container is already gone, log a warning and continue. Never block shutdown on cleanup failures.

### 2. Multi-Stage Base Image

**Location:** `infrastructure/Dockerfile.base`

**Stage 1 — builder:**
- Ubuntu 24.04 with `build-essential`, Python 3.11 dev headers, `software-properties-common`
- Install uv, bun, Mermaid CLI + Puppeteer/Chromium
- `COPY` project files and run `uv sync --no-dev`
- All compilation happens here

**Stage 2 — runtime:**
- Fresh Ubuntu 24.04 with runtime-only libs:
  - `libatomic1`, `libasound2t64`, `libatk-bridge2.0-0`, `libatk1.0-0`, `libcups2`, `libdbus-1-3`, `libdrm2`, `libgbm1`, `libgtk-3-0t64`, `libnspr4`, `libnss3`, `libpango-1.0-0`, `libx11-xcb1`, `libxcomposite1`, `libxdamage1`, `libxfixes3`, `libxrandr2`, `libxshmfence1`, `fonts-liberation`, `xdg-utils`
  - `curl`, `wget`, `git`, `jq`, `sqlite3`, `rsync`, `ca-certificates`, `locales`
  - Python 3.11 runtime (no `-dev`)
- Copy from builder:
  - `/bin/uv`, `/bin/uvx`
  - `/home/agent/.bun/` (bun runtime)
  - `/home/agent/.local/bin/node` symlink
  - `/home/agent/.cache/puppeteer/` (Chromium binary)
  - `/home/agent/.config/puppeteer.json`
  - `/home/agent/.bun/install/global/` (mermaid-cli)
  - `/app/` (project + venv)
- No `build-essential`, no `*-dev` packages, no `software-properties-common`, no apt lists

**Expected savings:** ~800MB–1.2GB off the base image. Platform images inherit savings automatically since they `FROM desmet-eval-base:1.0`.

**Smoke test:** Unchanged — `uv run python -c "from desmet.harness.entrypoint import run_entrypoint"` plus tool version checks.

### 3. WebSocket Build Streaming

**Backend — new endpoint:** `ws /ws/images/build`

Protocol:
1. Client connects and sends: `{"platforms": ["langgraph"]}` (specific platforms) or `{}` (all SDK platforms)
2. Server streams JSON messages per line of Docker build output:
   ```json
   {"platform": "langgraph", "phase": "base", "line": "Step 3/8: RUN apt-get update..."}
   {"platform": "langgraph", "phase": "platform", "line": "Step 2/4: RUN uv sync --extra langgraph..."}
   {"platform": "langgraph", "status": "built"}
   {"platform": "crewai", "phase": "platform", "line": "..."}
   {"platform": "crewai", "status": "failed", "error": "uv sync returned exit code 1"}
   ```
3. When all requested platforms are processed, server sends: `{"done": true, "summary": {"built": 3, "exists": 1, "failed": 1}}`
4. Server closes the WebSocket.

**Implementation:**
- `build_image()` in `container_runner.py` gains a new variant `build_image_streaming()` that yields lines instead of collecting them. Uses `subprocess.Popen` with `stdout=PIPE, stderr=STDOUT` and iterates lines.
- The WebSocket handler runs the build in a thread (via `asyncio.to_thread`) and forwards lines to the WS client as they arrive.
- The existing `POST /api/images/build` endpoint stays unchanged for CLI/programmatic use.

**Frontend:**
- New function in `api.ts`: `connectImageBuild(platforms, onMessage)` — returns a WebSocket, caller provides message handler.
- PlatformCard and Platforms page use this during builds instead of the HTTP endpoint.

### 4. Expandable PlatformCard

**Collapsed state (default):**
- Name, category badge, status badge (unchanged)
- Adapter badge + infra type (unchanged)
- New: one-line image summary when image exists: `"3.5 GB  ·  built 2h ago"` in muted text
- New: expand chevron icon on the right

**Expanded state (click card or chevron):**
- **Image details section:** Full image tag, exact size, build timestamp
- **Actions row:**
  - SDK platforms: "Rebuild Image" (rebuild even if exists), "Delete Image" (docker rmi)
  - Docker platforms: "Start" / "Stop" (existing behaviour)
- **Build log panel:** Collapsible `<pre>` block.
  - During active build: live-streams output from the WebSocket
  - After build: shows last build output (stored in component state, not persisted)
- **Last evaluation:** Timestamp and story ID of most recent run for this platform (read from result store via new endpoint)

**Backend support — new endpoints:**
- `GET /api/images/detail` — returns `{platform_id: {exists, size_bytes, created_at, tag}}` for all SDK platforms. Uses `docker image inspect` to get size and creation date.
- `DELETE /api/images/{platform_id}` — runs `docker rmi <tag>`, returns `{success, message}`.
- `POST /api/images/{platform_id}/rebuild` — removes existing image then builds fresh, returns `{status}`.

**Frontend — updated `api.ts`:**
- `fetchImageDetails()` — calls `GET /api/images/detail`
- `deleteImage(platformId)` — calls `DELETE /api/images/{platform_id}`
- `rebuildImage(platformId)` — calls `POST /api/images/{platform_id}/rebuild`

**Data store:**
- `store.imageDetails` — `Record<string, {exists, size_bytes, created_at, tag}>`, refreshed alongside platform statuses.

## Files to Change

| File | Change |
|------|--------|
| `src/desmet/webui/api.py` | Shutdown hook, new image detail/delete/rebuild endpoints, WS build endpoint |
| `src/desmet/infra.py` | `cleanup_all_docker()` function for shutdown |
| `src/desmet/harness/container_runner.py` | `build_image_streaming()` generator, `delete_image()`, `get_image_details()` |
| `infrastructure/Dockerfile.base` | Multi-stage rewrite |
| `src/desmet/webui/frontend/src/lib/api.ts` | New API functions + WS build connector |
| `src/desmet/webui/frontend/src/lib/data.svelte.ts` | `store.imageDetails`, refresh function |
| `src/desmet/webui/frontend/src/lib/components/PlatformCard.svelte` | Expandable card with details, actions, build log |
| `src/desmet/webui/frontend/src/lib/components/StatusBadge.svelte` | No changes needed |
| `src/desmet/webui/frontend/src/lib/pages/Platforms.svelte` | Wire up new callbacks, remove "Build All" HTTP call in favour of WS |

## Out of Scope

- Auto-starting services on webui startup
- Persisting build logs to disk
- Remote Docker host support
- Image registry push/pull
