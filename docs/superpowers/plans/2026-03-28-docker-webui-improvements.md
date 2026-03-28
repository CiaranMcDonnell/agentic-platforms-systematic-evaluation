# Docker + WebUI Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean shutdown of Docker on webui exit, smaller images via multi-stage builds, WebSocket streaming for image builds, and expandable platform cards with image metadata and actions.

**Architecture:** Four independent changes: (1) shutdown hook in FastAPI lifespan, (2) multi-stage Dockerfile.base, (3) new WS endpoint + streaming build function in container_runner, (4) expanded PlatformCard with detail/action/log panels. The frontend talks to existing and new API endpoints.

**Tech Stack:** Python/FastAPI (backend), Svelte 5 (frontend), Docker CLI (subprocess), WebSocket (FastAPI + browser)

---

### Task 1: Shutdown Lifecycle — Backend

**Files:**
- Modify: `src/desmet/infra.py`
- Modify: `src/desmet/webui/api.py:113-152` (lifespan function)
- Test: `tests/test_infra.py`

- [ ] **Step 1: Write failing tests for `cleanup_all_docker()`**

Add to `tests/test_infra.py`:

```python
from desmet.infra import cleanup_all_docker


class TestCleanupAllDocker:
    @patch("desmet.infra.compose_down")
    @patch("desmet.infra.subprocess.run")
    def test_calls_compose_down_all(self, mock_run, mock_compose):
        mock_compose.return_value = MagicMock(returncode=0)
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        cleanup_all_docker()
        mock_compose.assert_called_once_with("all")

    @patch("desmet.infra.compose_down")
    @patch("desmet.infra.subprocess.run")
    def test_removes_eval_containers(self, mock_run, mock_compose):
        mock_compose.return_value = MagicMock(returncode=0)
        # First call: docker ps to list eval containers
        # Second call: docker rm -f to remove them
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="abc123\ndef456\n"),
            MagicMock(returncode=0),
        ]
        cleanup_all_docker()
        ps_call = mock_run.call_args_list[0]
        assert "--filter" in ps_call.args[0]
        assert "name=desmet-run-" in ps_call.args[0]

    @patch("desmet.infra.compose_down")
    @patch("desmet.infra.subprocess.run")
    def test_survives_docker_not_found(self, mock_run, mock_compose):
        mock_compose.side_effect = FileNotFoundError()
        mock_run.side_effect = FileNotFoundError()
        # Should not raise
        cleanup_all_docker()

    @patch("desmet.infra.compose_down")
    @patch("desmet.infra.subprocess.run")
    def test_survives_compose_failure(self, mock_run, mock_compose):
        mock_compose.return_value = MagicMock(returncode=1, stderr="error")
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        # Should not raise
        cleanup_all_docker()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_infra.py::TestCleanupAllDocker -v`
Expected: ImportError — `cleanup_all_docker` not defined

- [ ] **Step 3: Implement `cleanup_all_docker()` in `infra.py`**

Add at the end of `src/desmet/infra.py` (after `compose_down`):

```python
def cleanup_all_docker() -> None:
    """Best-effort cleanup of all DESMET Docker resources.

    Called on webui shutdown. Stops Compose services and removes
    any lingering evaluation containers.
    """
    import logging
    _log = logging.getLogger("desmet.infra")

    # 1. Stop all Compose services
    try:
        result = compose_down("all")
        if result.returncode == 0:
            _log.info("Stopped all Docker Compose services")
        else:
            _log.warning("compose down returned %d: %s", result.returncode, result.stderr)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        _log.warning("Could not stop Compose services: %s", e)

    # 2. Remove eval containers (desmet-run-*)
    try:
        ps = subprocess.run(
            ["docker", "ps", "-aq", "--filter", "name=desmet-run-"],
            capture_output=True, text=True, timeout=10,
        )
        container_ids = ps.stdout.strip()
        if container_ids:
            subprocess.run(
                ["docker", "rm", "-f"] + container_ids.split(),
                capture_output=True, timeout=30,
            )
            _log.info("Removed eval containers: %s", container_ids.replace("\n", ", "))
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        _log.warning("Could not clean eval containers: %s", e)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_infra.py::TestCleanupAllDocker -v`
Expected: All 4 PASS

- [ ] **Step 5: Wire into the lifespan shutdown hook**

In `src/desmet/webui/api.py`, replace the shutdown section of the `lifespan` function (lines 150-151):

```python
    # ── Shutdown ─────────────────────────────────────────────────────────
    logger.info("DESMET Management Console shutting down")
```

with:

```python
    # ── Shutdown ─────────────────────────────────────────────────────────
    logger.info("DESMET Management Console shutting down — cleaning up Docker resources")
    from desmet.infra import cleanup_all_docker
    cleanup_all_docker()
    logger.info("Shutdown complete")
```

Also add `cleanup_all_docker` to the existing import block at the top of `api.py` (line 68-79) — add it alongside the other infra imports:

```python
from desmet.infra import (
    ...
    cleanup_all_docker,
)
```

Then remove the inline import from the shutdown block since it's now at the top.

- [ ] **Step 6: Commit**

```bash
git add src/desmet/infra.py src/desmet/webui/api.py tests/test_infra.py
git commit -m "feat: shutdown Docker services when webui stops"
```

---

### Task 2: Multi-Stage Dockerfile.base

**Files:**
- Modify: `infrastructure/Dockerfile.base`

- [ ] **Step 1: Rewrite `Dockerfile.base` as a multi-stage build**

Replace the entire file with:

```dockerfile
# =============================================================================
# DESMET Agent Evaluation Environment — Multi-stage build
# =============================================================================
# Stage 1 (builder): compiles everything with build tools
# Stage 2 (runtime): copies only what agents need at runtime
#
# Build:
#   docker build -f infrastructure/Dockerfile.base -t desmet-eval-base:1.0 .
# =============================================================================

# ── Stage 1: Builder ─────────────────────────────────────────────────────
FROM ubuntu:24.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System packages (build + runtime deps together — we'll only copy runtime later)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget git jq unzip zip \
    build-essential make rsync ca-certificates gnupg \
    software-properties-common \
    locales sqlite3 \
    # Puppeteer/Chromium runtime deps
    libasound2t64 libatk-bridge2.0-0 libatk1.0-0 libcups2 \
    libdbus-1-3 libdrm2 libgbm1 libgtk-3-0t64 libnspr4 libnss3 \
    libpango-1.0-0 libx11-xcb1 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libxshmfence1 \
    fonts-liberation xdg-utils \
    && rm -rf /var/lib/apt/lists/* \
    && locale-gen en_US.UTF-8

ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8

# Python 3.11
RUN add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       python3.11 python3.11-venv python3.11-dev \
    && rm -rf /var/lib/apt/lists/* \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python  python  /usr/bin/python3.11 1

# uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Non-root user
RUN useradd -m -s /bin/bash agent \
    && mkdir -p /workspace \
    && chown agent:agent /workspace

RUN git config --system user.name "desmet-agent" \
    && git config --system user.email "agent@desmet.local"

USER agent
ENV HOME=/home/agent \
    PATH="/home/agent/.bun/bin:/home/agent/.local/bin:$PATH"

# Bun
RUN curl -fsSL https://bun.sh/install | bash

# Node symlink
RUN mkdir -p /home/agent/.local/bin \
    && ln -s /home/agent/.bun/bin/bun /home/agent/.local/bin/node

# Mermaid CLI + Puppeteer
ENV PUPPETEER_CACHE_DIR=/home/agent/.cache/puppeteer
RUN bun install --global @mermaid-js/mermaid-cli

RUN mkdir -p /home/agent/.config \
    && echo '{"args":["--no-sandbox","--disable-setuid-sandbox"]}' \
       > /home/agent/.config/puppeteer.json

# Install DESMET package
COPY --chown=agent:agent pyproject.toml uv.lock README.md /app/
COPY --chown=agent:agent src/ /app/src/
WORKDIR /app
RUN uv sync --no-dev


# ── Stage 2: Runtime ─────────────────────────────────────────────────────
FROM ubuntu:24.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Runtime-only packages (no build-essential, no *-dev)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget git jq sqlite3 rsync ca-certificates gnupg \
    locales \
    # Python 3.11 runtime
    software-properties-common \
    # Puppeteer/Chromium runtime deps
    libasound2t64 libatk-bridge2.0-0 libatk1.0-0 libcups2 \
    libdbus-1-3 libdrm2 libgbm1 libgtk-3-0t64 libnspr4 libnss3 \
    libpango-1.0-0 libx11-xcb1 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libxshmfence1 \
    fonts-liberation xdg-utils \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends python3.11 python3.11-venv \
    && rm -rf /var/lib/apt/lists/* \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python  python  /usr/bin/python3.11 1 \
    && locale-gen en_US.UTF-8

ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8

# Create same user
RUN useradd -m -s /bin/bash agent \
    && mkdir -p /workspace \
    && chown agent:agent /workspace

RUN git config --system user.name "desmet-agent" \
    && git config --system user.email "agent@desmet.local"

# Copy tools from builder
COPY --from=builder /bin/uv /bin/uvx /bin/
COPY --from=builder --chown=agent:agent /home/agent/.bun /home/agent/.bun
COPY --from=builder --chown=agent:agent /home/agent/.local /home/agent/.local
COPY --from=builder --chown=agent:agent /home/agent/.cache/puppeteer /home/agent/.cache/puppeteer
COPY --from=builder --chown=agent:agent /home/agent/.config/puppeteer.json /home/agent/.config/puppeteer.json
COPY --from=builder --chown=agent:agent /app /app

USER agent
ENV HOME=/home/agent \
    PATH="/home/agent/.bun/bin:/home/agent/.local/bin:$PATH" \
    PUPPETEER_CACHE_DIR=/home/agent/.cache/puppeteer

# Smoke test from /app where the venv lives
WORKDIR /app
RUN echo "=== Smoke test ===" \
    && python --version \
    && uv --version \
    && bun --version \
    && git --version \
    && uv run python -c "from desmet.harness.entrypoint import run_entrypoint" \
    && echo "All tools verified"

WORKDIR /workspace
CMD ["bash"]
```

- [ ] **Step 2: Remove old images and rebuild**

```bash
docker rmi desmet-eval-base:1.0 || true
docker build -f infrastructure/Dockerfile.base -t desmet-eval-base:1.0 .
```

Expected: Successful build. Verify size reduction:
```bash
docker images desmet-eval-base:1.0 --format "{{.Size}}"
```
Should be noticeably smaller than 3.48GB (target: ~2.2-2.6GB).

- [ ] **Step 3: Rebuild one platform image to verify inheritance**

```bash
docker rmi desmet-eval-langgraph:1.0 || true
docker build -f infrastructure/Dockerfile.langgraph -t desmet-eval-langgraph:1.0 .
```

Expected: Successful build, `uv sync --extra langgraph` completes.

- [ ] **Step 4: Run smoke test inside the container**

```bash
docker run --rm desmet-eval-langgraph:1.0 bash -c "uv run python -c 'import langgraph; print(langgraph.__version__)' && mmdc --version && bun --version && git --version"
```

Expected: All commands succeed — langgraph importable, mmdc available, bun works.

- [ ] **Step 5: Commit**

```bash
git add infrastructure/Dockerfile.base
git commit -m "perf: multi-stage Dockerfile.base to reduce image size"
```

---

### Task 3: Streaming Image Build — Backend

**Files:**
- Modify: `src/desmet/harness/container_runner.py`
- Test: `tests/test_container_runner.py`

- [ ] **Step 1: Write failing tests for new functions**

Add to `tests/test_container_runner.py`:

```python
from unittest.mock import MagicMock, patch

from desmet.harness.container_runner import (
    delete_image,
    get_image_details,
    image_name,
    PLATFORM_EXTRA_MAP,
)


class TestDeleteImage:
    @patch("desmet.harness.container_runner.subprocess.run")
    def test_delete_existing_image(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert delete_image("langgraph") is True
        mock_run.assert_called_once()
        args = mock_run.call_args.args[0]
        assert "rmi" in args
        assert "desmet-eval-langgraph:1.0" in args

    @patch("desmet.harness.container_runner.subprocess.run")
    def test_delete_missing_image(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="No such image")
        assert delete_image("langgraph") is False

    @patch("desmet.harness.container_runner.subprocess.run")
    def test_delete_docker_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        assert delete_image("langgraph") is False


class TestGetImageDetails:
    @patch("desmet.harness.container_runner.subprocess.run")
    def test_returns_details_for_existing_image(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[{"Size": 3500000000, "Created": "2026-03-28T12:00:00Z"}]',
        )
        details = get_image_details("langgraph")
        assert details is not None
        assert details["size_bytes"] == 3500000000
        assert details["created_at"] == "2026-03-28T12:00:00Z"
        assert details["tag"] == "desmet-eval-langgraph:1.0"
        assert details["exists"] is True

    @patch("desmet.harness.container_runner.subprocess.run")
    def test_returns_none_for_missing_image(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        details = get_image_details("langgraph")
        assert details is None

    @patch("desmet.harness.container_runner.subprocess.run")
    def test_returns_none_on_docker_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        details = get_image_details("langgraph")
        assert details is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_container_runner.py::TestDeleteImage tests/test_container_runner.py::TestGetImageDetails -v`
Expected: ImportError — `delete_image`, `get_image_details` not defined

- [ ] **Step 3: Implement `delete_image()` and `get_image_details()`**

Add to `src/desmet/harness/container_runner.py` after the `build_image()` function (after line 135):

```python
def delete_image(platform_id: str) -> bool:
    """Remove the Docker image for a platform. Returns True on success."""
    tag = image_name(platform_id)
    try:
        result = subprocess.run(
            ["docker", "rmi", tag],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_image_details(platform_id: str) -> dict[str, Any] | None:
    """Return image metadata (size, creation date) or None if not found."""
    tag = image_name(platform_id)
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", tag],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        if not data:
            return None
        return {
            "exists": True,
            "tag": tag,
            "size_bytes": data[0].get("Size", 0),
            "created_at": data[0].get("Created", ""),
        }
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_container_runner.py::TestDeleteImage tests/test_container_runner.py::TestGetImageDetails -v`
Expected: All 6 PASS

- [ ] **Step 5: Implement `build_image_streaming()` generator**

Add to `src/desmet/harness/container_runner.py` after `build_image()`:

```python
from collections.abc import Generator


def build_image_streaming(
    platform_id: str,
) -> Generator[dict[str, str], None, bool]:
    """Build a platform image, yielding progress dicts line-by-line.

    Yields dicts like:
        {"platform": "langgraph", "phase": "base", "line": "Step 3/8 ..."}
        {"platform": "langgraph", "status": "built"}

    Returns True on success (accessible via generator .value after StopIteration).
    """
    project_root = Path(__file__).resolve().parents[3]

    # Check base image
    try:
        probe = subprocess.run(
            ["docker", "image", "inspect", _BASE_IMAGE],
            capture_output=True, timeout=10,
        )
        need_base = probe.returncode != 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        yield {"platform": platform_id, "status": "failed", "error": "Docker not available"}
        return False

    if need_base:
        yield {"platform": platform_id, "phase": "base", "line": f"Building {_BASE_IMAGE}..."}
        proc = subprocess.Popen(
            [
                "docker", "build",
                "-f", str(_INFRA_DIR / "Dockerfile.base"),
                "-t", _BASE_IMAGE,
                str(project_root),
            ],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        for line in proc.stdout:
            yield {"platform": platform_id, "phase": "base", "line": line.rstrip()}
        proc.wait()
        if proc.returncode != 0:
            yield {"platform": platform_id, "status": "failed", "error": "Base image build failed"}
            return False

    # Build platform image
    tag = image_name(platform_id)
    df = dockerfile_path(platform_id)
    yield {"platform": platform_id, "phase": "platform", "line": f"Building {tag}..."}

    proc = subprocess.Popen(
        [
            "docker", "build",
            "-f", str(df),
            "-t", tag,
            str(project_root),
        ],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    for line in proc.stdout:
        yield {"platform": platform_id, "phase": "platform", "line": line.rstrip()}
    proc.wait()

    if proc.returncode != 0:
        yield {"platform": platform_id, "status": "failed", "error": f"Build failed for {tag}"}
        return False

    yield {"platform": platform_id, "status": "built"}
    return True
```

Note: also add `Generator` to the imports at the top of the file — change `from collections.abc import Callable` to `from collections.abc import Callable, Generator`.

- [ ] **Step 6: Commit**

```bash
git add src/desmet/harness/container_runner.py tests/test_container_runner.py
git commit -m "feat: add image delete, details, and streaming build to container_runner"
```

---

### Task 4: WebSocket Build Endpoint + Image Management APIs

**Files:**
- Modify: `src/desmet/webui/api.py`

- [ ] **Step 1: Add image detail, delete, and rebuild endpoints**

Add after the existing `image_status` endpoint in `src/desmet/webui/api.py`:

```python
@app.get("/api/images/detail")
async def image_details():
    """Return image metadata for all SDK platforms."""
    from desmet.harness.container_runner import PLATFORM_EXTRA_MAP, get_image_details

    result = {}
    for pid in PLATFORM_EXTRA_MAP:
        details = get_image_details(pid)
        if details:
            result[pid] = details
        else:
            result[pid] = {"exists": False, "tag": None, "size_bytes": 0, "created_at": ""}
    return result


@app.delete("/api/images/{platform_id}")
async def delete_platform_image(platform_id: str):
    """Delete a platform's Docker image."""
    from desmet.harness.container_runner import PLATFORM_EXTRA_MAP, delete_image

    if platform_id not in PLATFORM_EXTRA_MAP:
        raise HTTPException(status_code=404, detail="Not an SDK platform")
    success = delete_image(platform_id)
    return {"success": success, "message": "Deleted" if success else "Failed to delete image"}


@app.post("/api/images/{platform_id}/rebuild")
async def rebuild_platform_image(platform_id: str):
    """Delete and rebuild a platform's Docker image."""
    from desmet.harness.container_runner import (
        PLATFORM_EXTRA_MAP,
        build_image,
        delete_image,
    )

    if platform_id not in PLATFORM_EXTRA_MAP:
        raise HTTPException(status_code=404, detail="Not an SDK platform")

    delete_image(platform_id)

    log_lines: list[str] = []
    success = await asyncio.get_event_loop().run_in_executor(
        None, lambda: build_image(platform_id, progress_callback=log_lines.append),
    )
    if success:
        return {"status": "built"}
    return {"status": "failed", "reason": log_lines[-1] if log_lines else "unknown error"}
```

- [ ] **Step 2: Add WebSocket build streaming endpoint**

Add after the new endpoints above, near the existing `/ws/runs/{run_id}` WebSocket:

```python
# ── WebSocket for image build streaming ────────────────────────────────


@app.websocket("/ws/images/build")
async def ws_image_build(websocket: WebSocket):
    """Stream Docker image build output over WebSocket.

    Client sends: {"platforms": ["langgraph"]} or {} for all.
    Server streams: {"platform": "...", "phase": "...", "line": "..."}
    Ends with:      {"done": true, "summary": {...}}
    """
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        request = json.loads(raw) if raw else {}
    except (WebSocketDisconnect, json.JSONDecodeError):
        return

    from desmet.harness.container_runner import (
        PLATFORM_EXTRA_MAP,
        build_image_streaming,
        has_image,
    )

    platforms = request.get("platforms", list(PLATFORM_EXTRA_MAP.keys()))
    summary: dict[str, int] = {"built": 0, "exists": 0, "failed": 0}

    for pid in platforms:
        if pid not in PLATFORM_EXTRA_MAP:
            continue
        if has_image(pid):
            summary["exists"] += 1
            await websocket.send_json({"platform": pid, "status": "exists"})
            continue

        # Run the blocking generator in a thread, forwarding lines
        import queue
        q: queue.Queue[dict | None] = queue.Queue()

        def _run_build():
            gen = build_image_streaming(pid)
            for msg in gen:
                q.put(msg)
            q.put(None)  # sentinel

        loop = asyncio.get_event_loop()
        fut = loop.run_in_executor(None, _run_build)

        # Drain queue and forward to WebSocket
        build_success = False
        while True:
            # Poll queue with short timeout to stay async-friendly
            try:
                msg = await asyncio.to_thread(q.get, timeout=0.5)
            except Exception:
                if fut.done():
                    break
                continue
            if msg is None:
                break
            await websocket.send_json(msg)
            if msg.get("status") == "built":
                build_success = True
            elif msg.get("status") == "failed":
                build_success = False

        await fut
        summary["built" if build_success else "failed"] += 1

    await websocket.send_json({"done": True, "summary": summary})
    await websocket.close()
```

Also add `import json` and `import queue` to the top of `api.py` if not already present. (`json` is already imported via other usage; `queue` is not — add it to the stdlib imports block.)

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/api.py
git commit -m "feat: add image management endpoints and WS build streaming"
```

---

### Task 5: Frontend — API Functions and Data Store

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/api.ts`
- Modify: `src/desmet/webui/frontend/src/lib/data.svelte.ts`

- [ ] **Step 1: Add new API types and functions to `api.ts`**

Add after the existing `fetchImageStatus` function in `api.ts`:

```typescript
// ── Image detail types ────────────

export interface ImageDetail {
  exists: boolean;
  tag: string | null;
  size_bytes: number;
  created_at: string;
}

export interface ImageBuildMessage {
  platform?: string;
  phase?: string;
  line?: string;
  status?: string;
  error?: string;
  done?: boolean;
  summary?: { built: number; exists: number; failed: number };
}
```

Replace the existing `buildImages` and `fetchImageStatus` functions (the ones we added earlier) with:

```typescript
export const buildImages = (platforms?: string[]) =>
  request<{ images: Record<string, { status: string; reason?: string }> }>('/api/images/build', {
    method: 'POST',
    body: JSON.stringify(platforms ? { platforms } : {}),
  });

export const fetchImageStatus = () =>
  request<Record<string, { exists: boolean }>>('/api/images/status');

export const fetchImageDetails = () =>
  request<Record<string, ImageDetail>>('/api/images/detail');

export const deleteImage = (platformId: string) =>
  request<{ success: boolean; message: string }>(`/api/images/${platformId}`, { method: 'DELETE' });

export const rebuildImage = (platformId: string) =>
  request<{ status: string; reason?: string }>(`/api/images/${platformId}/rebuild`, { method: 'POST' });
```

Add WebSocket connector for build streaming (after the existing `connectRunLogs` function):

```typescript
export function connectImageBuild(
  platforms: string[] | undefined,
  onMessage: (msg: ImageBuildMessage) => void,
): WebSocket {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${proto}//${location.host}/ws/images/build`);
  ws.onopen = () => {
    ws.send(JSON.stringify(platforms ? { platforms } : {}));
  };
  ws.onmessage = (e) => {
    try {
      onMessage(JSON.parse(e.data));
    } catch {
      console.warn('[DESMET] Failed to parse image build message', e.data);
    }
  };
  ws.onerror = (e) => console.warn('[DESMET] Image build WS error', e);
  return ws;
}
```

- [ ] **Step 2: Update the data store with image details**

In `src/desmet/webui/frontend/src/lib/data.svelte.ts`, add the import:

```typescript
import {
  fetchPlatforms, fetchStories, fetchConfig,
  fetchPlatformStatuses, fetchInfrastructure,
  fetchImageDetails,
} from './api';
import type { Platform, Story, AppConfig, InfraService, ImageDetail } from './api';
```

Add `imageDetails` to the store object:

```typescript
export const store = $state({
  // Static (fetched once on app init)
  platforms: [] as Platform[],
  stories: [] as Story[],
  config: null as AppConfig | null,

  // Slow-live (fetched lazily, updated in background)
  platformStatuses: {} as Record<string, string>,
  infraServices: [] as InfraService[],
  imageDetails: {} as Record<string, ImageDetail>,

  // Loading flags
  initialized: false,
  initError: null as string | null,
});
```

Add a refresh function and call it from `initData`:

```typescript
export async function refreshImageDetails(): Promise<void> {
  const res = await fetchImageDetails();
  store.imageDetails = res;
}
```

Update `initData` to also fire image details in the background:

```typescript
    // Fire-and-forget: slow checks resolve in background
    refreshPlatformStatuses().catch(() => {});
    refreshInfra().catch(() => {});
    refreshImageDetails().catch(() => {});
```

- [ ] **Step 3: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/api.ts src/desmet/webui/frontend/src/lib/data.svelte.ts
git commit -m "feat: add image detail/build APIs and data store"
```

---

### Task 6: Frontend — Expandable PlatformCard

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/components/PlatformCard.svelte`
- Modify: `src/desmet/webui/frontend/src/lib/pages/Platforms.svelte`

- [ ] **Step 1: Rewrite PlatformCard with expandable design**

Replace the entire `src/desmet/webui/frontend/src/lib/components/PlatformCard.svelte` with:

```svelte
<script lang="ts">
  import StatusBadge from './StatusBadge.svelte';
  import type { Platform, ImageDetail, ImageBuildMessage } from '../api';
  import { deleteImage, connectImageBuild } from '../api';
  import { refreshPlatformStatuses, refreshImageDetails } from '../data.svelte';

  let { platform, imageDetail, onDockerAction, onBuildImage }: {
    platform: Platform;
    imageDetail: ImageDetail | undefined;
    onDockerAction: (action: string, target: string) => Promise<{ success: boolean; message?: string }>;
    onBuildImage: (platformId: string) => Promise<{ success: boolean; message?: string }>;
  } = $props();

  let isDocker = $derived(platform.infra_type === 'Docker');
  let isSDK = $derived(platform.infra_type === 'Docker (isolated)' || platform.infra_type === 'Python SDK');
  let isUp = $derived(platform.status === 'running');
  let needsBuild = $derived(platform.status === 'not built');

  let expanded = $state(false);
  let actionState = $state<'idle' | 'starting' | 'stopping' | 'building' | 'deleting' | 'success' | 'error'>('idle');
  let errorMsg = $state('');
  let buildLogs = $state<string[]>([]);
  let buildWs: WebSocket | null = $state(null);

  function formatSize(bytes: number): string {
    if (bytes === 0) return '';
    const gb = bytes / 1e9;
    return gb >= 1 ? `${gb.toFixed(1)} GB` : `${(bytes / 1e6).toFixed(0)} MB`;
  }

  function formatAge(iso: string): string {
    if (!iso) return '';
    const diff = Date.now() - new Date(iso).getTime();
    const hours = Math.floor(diff / 3600000);
    if (hours < 1) return 'just now';
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }

  let sizeText = $derived(imageDetail?.exists ? formatSize(imageDetail.size_bytes) : '');
  let ageText = $derived(imageDetail?.exists ? formatAge(imageDetail.created_at) : '');
  let summaryText = $derived(
    sizeText && ageText ? `${sizeText}  ·  built ${ageText}` :
    sizeText ? sizeText :
    ageText ? `built ${ageText}` : ''
  );

  async function handleDockerAction(action: string) {
    actionState = action === 'up' ? 'starting' : 'stopping';
    errorMsg = '';
    try {
      const res = await onDockerAction(action, platform.id);
      if (res && !res.success) {
        actionState = 'error';
        errorMsg = res.message || `Failed to ${action === 'up' ? 'start' : 'stop'}`;
      } else {
        actionState = 'success';
        setTimeout(() => { if (actionState === 'success') actionState = 'idle'; }, 3000);
      }
    } catch (err: any) {
      actionState = 'error';
      errorMsg = err?.message || 'Unexpected error';
    }
  }

  function handleBuildStreaming() {
    actionState = 'building';
    errorMsg = '';
    buildLogs = [];

    buildWs = connectImageBuild([platform.id], (msg: ImageBuildMessage) => {
      if (msg.line) {
        buildLogs = [...buildLogs, msg.line];
      }
      if (msg.status === 'built') {
        actionState = 'success';
        setTimeout(() => { if (actionState === 'success') actionState = 'idle'; }, 3000);
        refreshPlatformStatuses();
        refreshImageDetails();
      } else if (msg.status === 'failed') {
        actionState = 'error';
        errorMsg = msg.error || 'Build failed';
        refreshPlatformStatuses();
      }
      if (msg.done) {
        buildWs?.close();
        buildWs = null;
      }
    });
  }

  async function handleDelete() {
    if (!confirm(`Delete Docker image for ${platform.name}?`)) return;
    actionState = 'deleting';
    errorMsg = '';
    try {
      const res = await deleteImage(platform.id);
      if (res.success) {
        actionState = 'success';
        setTimeout(() => { if (actionState === 'success') actionState = 'idle'; }, 3000);
        await Promise.all([refreshPlatformStatuses(), refreshImageDetails()]);
      } else {
        actionState = 'error';
        errorMsg = res.message || 'Delete failed';
      }
    } catch (err: any) {
      actionState = 'error';
      errorMsg = err?.message || 'Delete failed';
    }
  }

  async function handleRebuild() {
    // Delete first, then stream build
    actionState = 'deleting';
    try {
      await deleteImage(platform.id);
    } catch { /* continue anyway */ }
    handleBuildStreaming();
  }

  let busy = $derived(['starting', 'stopping', 'building', 'deleting'].includes(actionState));
</script>

<div class="card" class:expanded>
  <!-- Collapsed header — always visible -->
  <div class="card-header" onclick={() => expanded = !expanded} role="button" tabindex="0" onkeydown={(e) => { if (e.key === 'Enter') expanded = !expanded; }}>
    <div style="flex: 1; min-width: 0;">
      <div style="display: flex; justify-content: space-between; align-items: flex-start;">
        <div>
          <h3 style="margin: 0; font-weight: 500; font-size: 14px;">{platform.name}</h3>
          <p style="margin: 4px 0 0; font-size: 12px; color: var(--text-2);">{platform.category}</p>
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          <StatusBadge status={platform.status} />
          <span class="chevron" class:open={expanded}>&#9662;</span>
        </div>
      </div>

      <div style="margin-top: 10px; display: flex; gap: 8px; align-items: center;">
        {#if platform.implemented}
          <span class="badge badge-green">Adapter Ready</span>
        {:else}
          <span class="badge badge-gray">Stub</span>
        {/if}
        <span style="font-size: 11px; color: var(--text-2);">{platform.infra_type}</span>
        {#if summaryText}
          <span style="font-size: 11px; color: var(--text-2);">·  {summaryText}</span>
        {/if}
      </div>
    </div>
  </div>

  <!-- Expanded content -->
  {#if expanded}
    <div class="card-body">
      <!-- Image details -->
      {#if isSDK && imageDetail?.exists}
        <div class="detail-row">
          <span class="detail-label">Image</span>
          <span class="detail-value mono">{imageDetail.tag}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Size</span>
          <span class="detail-value">{formatSize(imageDetail.size_bytes)}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Built</span>
          <span class="detail-value">{new Date(imageDetail.created_at).toLocaleString()}</span>
        </div>
      {/if}

      <!-- Actions -->
      <div style="margin-top: 12px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
        {#if isDocker}
          {#if actionState === 'starting'}
            <button class="btn btn-outline btn-sm" disabled><span class="spinner"></span> Starting…</button>
          {:else if actionState === 'stopping'}
            <button class="btn btn-danger btn-sm" disabled><span class="spinner"></span> Stopping…</button>
          {:else if !isUp}
            <button class="btn btn-outline btn-sm" onclick={() => handleDockerAction('up')}>Start</button>
          {:else}
            <button class="btn btn-danger btn-sm" onclick={() => handleDockerAction('down')}>Stop</button>
          {/if}
        {:else if isSDK}
          {#if actionState === 'building'}
            <button class="btn btn-outline btn-sm" disabled><span class="spinner"></span> Building…</button>
          {:else if actionState === 'deleting'}
            <button class="btn btn-outline btn-sm" disabled><span class="spinner"></span> Deleting…</button>
          {:else if needsBuild}
            <button class="btn btn-outline btn-sm" onclick={handleBuildStreaming}>Build Image</button>
          {:else}
            <button class="btn btn-outline btn-sm" onclick={handleRebuild}>Rebuild Image</button>
            <button class="btn btn-danger btn-sm" onclick={handleDelete}>Delete Image</button>
          {/if}
        {/if}

        {#if actionState === 'success'}
          <span style="font-size: 12px; color: var(--green);">&#10003; Done</span>
        {/if}
      </div>

      <!-- Error -->
      {#if actionState === 'error'}
        <div class="error-box">
          {errorMsg}
          <button class="error-dismiss" onclick={() => { actionState = 'idle'; errorMsg = ''; }}>dismiss</button>
        </div>
      {/if}

      <!-- Build logs -->
      {#if buildLogs.length > 0}
        <div class="build-log">
          <div class="build-log-header" onclick={() => buildLogs = []}>
            <span>Build Log ({buildLogs.length} lines)</span>
            <span style="font-size: 11px; cursor: pointer; color: var(--text-2);">clear</span>
          </div>
          <div class="build-log-body">
            {#each buildLogs as line}
              <div class="log-line">{line}</div>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .card { cursor: default; }
  .card-header { cursor: pointer; }
  .card-body {
    border-top: 1px solid var(--border);
    padding-top: 14px;
    margin-top: 14px;
  }
  .chevron {
    font-size: 12px;
    color: var(--text-2);
    transition: transform 0.2s;
    display: inline-block;
  }
  .chevron.open { transform: rotate(180deg); }

  .detail-row {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    padding: 3px 0;
  }
  .detail-label { color: var(--text-2); }
  .detail-value { color: var(--text-1); }

  .error-box {
    margin-top: 8px;
    padding: 8px 10px;
    border-radius: 6px;
    background: rgba(239,68,68,0.08);
    border: 1px solid rgba(239,68,68,0.25);
    font-size: 12px;
    color: #ef4444;
  }
  .error-dismiss {
    background: none;
    border: none;
    color: #ef4444;
    text-decoration: underline;
    cursor: pointer;
    font-size: 12px;
    padding: 0;
    margin-left: 8px;
  }

  .build-log {
    margin-top: 12px;
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
  }
  .build-log-header {
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--bg-1);
    font-size: 11px;
    font-weight: 500;
    color: var(--text-1);
  }
  .build-log-body {
    background: var(--bg-0);
    padding: 8px 12px;
    font-family: var(--mono);
    font-size: 11px;
    line-height: 1.6;
    max-height: 300px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
  }
  .log-line { color: var(--text-2); padding: 1px 0; }

  .spinner {
    display: inline-block;
    width: 12px;
    height: 12px;
    border: 2px solid currentColor;
    border-right-color: transparent;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
    vertical-align: middle;
    margin-right: 4px;
  }
</style>
```

- [ ] **Step 2: Update Platforms.svelte to pass `imageDetail` and use WS for Build All**

Replace the entire `src/desmet/webui/frontend/src/lib/pages/Platforms.svelte` with:

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { dockerUp, dockerDown, connectImageBuild } from '../api';
  import type { ImageBuildMessage } from '../api';
  import { store, refreshPlatformStatuses, refreshImageDetails } from '../data.svelte';
  import PlatformCard from '../components/PlatformCard.svelte';

  async function onDockerAction(action: string, target: string): Promise<{ success: boolean; message?: string }> {
    try {
      const res: any = action === 'up' ? await dockerUp(target) : await dockerDown(target);
      await refreshPlatformStatuses();
      return res || { success: true };
    } catch (err: any) {
      await refreshPlatformStatuses();
      return { success: false, message: err?.message || `Failed to ${action === 'up' ? 'start' : 'stop'} ${target}` };
    }
  }

  async function onBuildImage(platformId: string): Promise<{ success: boolean; message?: string }> {
    // Stub — individual card builds now use WS directly via PlatformCard
    return { success: true };
  }

  let buildingAll = $state(false);
  let buildAllResult = $state<string | null>(null);

  function onBuildAll() {
    buildingAll = true;
    buildAllResult = null;

    const ws = connectImageBuild(undefined, (msg: ImageBuildMessage) => {
      if (msg.done && msg.summary) {
        const s = msg.summary;
        const parts: string[] = [];
        if (s.built) parts.push(`${s.built} built`);
        if (s.exists) parts.push(`${s.exists} already exist`);
        if (s.failed) parts.push(`${s.failed} failed`);
        buildAllResult = parts.join(', ') || 'No SDK platforms found';
        buildingAll = false;
        ws.close();
        refreshPlatformStatuses();
        refreshImageDetails();
      }
    });
  }

  let loading = $state(true);
  let categories = $derived([...new Set(store.platforms.map(p => p.category))]);
  let hasUnbuilt = $derived(store.platforms.some(p =>
    (p.infra_type === 'Docker (isolated)' || p.infra_type === 'Python SDK') &&
    (store.platformStatuses[p.id] === 'not built' || p.status === 'not built')
  ));

  onMount(() => { loading = false; });
</script>

<div>
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 28px;">
    <h1>Platforms</h1>
    <div style="display: flex; gap: 8px; align-items: center;">
      {#if hasUnbuilt}
        <button class="btn btn-outline" onclick={onBuildAll} disabled={buildingAll}>
          {#if buildingAll}
            <span style="display: inline-block; width: 12px; height: 12px; border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%; animation: spin 0.6s linear infinite; vertical-align: middle; margin-right: 4px;"></span>
            Building All…
          {:else}
            Build All Images
          {/if}
        </button>
      {/if}
      {#if buildAllResult}
        <span style="font-size: 12px; color: var(--text-2);">{buildAllResult}</span>
      {/if}
      <button class="btn btn-outline" onclick={refreshPlatformStatuses}>Refresh</button>
    </div>
  </div>

  {#if loading}
    <div class="card" style="text-align: center; padding: 48px; color: var(--text-2);">Loading platforms…</div>
  {:else if store.platforms.length === 0}
    <div class="card" style="text-align: center; padding: 48px; color: var(--text-2);">No platforms configured.</div>
  {:else}
    {#each categories as cat}
      <div style="margin-bottom: 28px;">
        <h2 style="margin-bottom: 12px;">{cat}</h2>
        <div class="grid-3">
          {#each store.platforms.filter(p => p.category === cat) as platform}
            <PlatformCard
              platform={{ ...platform, status: store.platformStatuses[platform.id] || platform.status }}
              imageDetail={store.imageDetails[platform.id]}
              {onDockerAction}
              {onBuildImage}
            />
          {/each}
        </div>
      </div>
    {/each}
  {/if}
</div>
```

- [ ] **Step 3: Build and verify**

```bash
cd src/desmet/webui/frontend && bun run build
```

Expected: Clean build (no errors).

- [ ] **Step 4: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/components/PlatformCard.svelte src/desmet/webui/frontend/src/lib/pages/Platforms.svelte
git commit -m "feat: expandable platform cards with image details, actions, and build logs"
```

---

### Task 7: Update Existing Tests

**Files:**
- Modify: `tests/test_infra.py`

The existing `TestGetPlatformStatuses` tests need updating because:
1. `get_platform_statuses()` now imports `has_image` which must be mocked.
2. Status `"not installed"` changed to `"not built"` for SDK platforms without images.
3. `infra_type` changed from `"none needed"` to `"Docker (isolated)"` / `"Python SDK"`.

- [ ] **Step 1: Update the existing platform status tests**

Replace the `TestGetPlatformStatuses` class in `tests/test_infra.py`:

```python
class TestGetPlatformStatuses:
    @patch("desmet.harness.container_runner.has_image", return_value=False)
    @patch("desmet.infra.get_container_status")
    @patch("desmet.infra.is_package_importable")
    def test_sdk_platform_with_local_install(self, mock_import, mock_container, mock_has_image):
        mock_import.return_value = True
        mock_container.return_value = "not started"
        statuses = get_platform_statuses()
        lg = next(s for s in statuses if s.platform_id == "langgraph")
        assert lg.infra_type == "Python SDK"
        assert lg.status == "ready"

    @patch("desmet.harness.container_runner.has_image", return_value=False)
    @patch("desmet.infra.get_container_status")
    @patch("desmet.infra.is_package_importable")
    def test_sdk_platform_not_built(self, mock_import, mock_container, mock_has_image):
        mock_import.return_value = False
        mock_container.return_value = "not started"
        statuses = get_platform_statuses()
        lg = next(s for s in statuses if s.platform_id == "langgraph")
        assert lg.status == "not built"
        assert lg.infra_type == "Docker (isolated)"

    @patch("desmet.harness.container_runner.has_image", return_value=True)
    @patch("desmet.infra.get_container_status")
    @patch("desmet.infra.is_package_importable")
    def test_sdk_platform_with_docker_image(self, mock_import, mock_container, mock_has_image):
        mock_import.return_value = False
        mock_container.return_value = "not started"
        statuses = get_platform_statuses()
        lg = next(s for s in statuses if s.platform_id == "langgraph")
        assert lg.status == "ready"
        assert lg.infra_type == "Docker (isolated)"

    @patch("desmet.harness.container_runner.has_image", return_value=False)
    @patch("desmet.infra.get_container_status")
    @patch("desmet.infra.is_package_importable")
    def test_docker_platform_running(self, mock_import, mock_container, mock_has_image):
        mock_import.return_value = False
        mock_container.return_value = "running"
        statuses = get_platform_statuses()
        fw = next(s for s in statuses if s.platform_id == "flowise")
        assert fw.infra_type == "Docker"
        assert fw.status == "running"

    @patch("desmet.harness.container_runner.has_image", return_value=False)
    @patch("desmet.infra.get_container_status")
    @patch("desmet.infra.is_package_importable")
    def test_docker_platform_not_started(self, mock_import, mock_container, mock_has_image):
        mock_import.return_value = False
        mock_container.return_value = "not started"
        statuses = get_platform_statuses()
        fw = next(s for s in statuses if s.platform_id == "flowise")
        assert fw.status == "not started"
```

Also update the imports at the top of the file to include the new function and add the `has_image` mock target:

```python
from desmet.infra import (
    COMPOSE_FILE,
    PLATFORM_CONTAINERS,
    PLATFORM_PACKAGES,
    PROFILE_TARGETS,
    cleanup_all_docker,
    get_config_status,
    get_container_status,
    get_docker_platform_statuses,
    get_platform_statuses,
    is_package_importable,
)
```

- [ ] **Step 2: Add tests for `get_docker_platform_statuses`**

Add a new test class:

```python
class TestGetDockerPlatformStatuses:
    @patch("desmet.harness.container_runner.has_image")
    @patch("desmet.infra.get_container_status")
    def test_includes_visual_platforms(self, mock_container, mock_has_image):
        mock_container.return_value = "running"
        mock_has_image.return_value = False
        result = get_docker_platform_statuses()
        assert result["flowise"] == "running"
        assert result["n8n"] == "running"

    @patch("desmet.harness.container_runner.has_image")
    @patch("desmet.infra.get_container_status")
    def test_includes_sdk_image_status(self, mock_container, mock_has_image):
        mock_container.return_value = "not started"
        mock_has_image.return_value = True
        result = get_docker_platform_statuses()
        assert result["langgraph"] == "ready"

    @patch("desmet.harness.container_runner.has_image")
    @patch("desmet.infra.get_container_status")
    def test_sdk_not_built(self, mock_container, mock_has_image):
        mock_container.return_value = "not started"
        mock_has_image.return_value = False
        result = get_docker_platform_statuses()
        assert result["langgraph"] == "not built"
```

- [ ] **Step 3: Run all infra tests**

Run: `python -m pytest tests/test_infra.py -v`
Expected: All PASS

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/test_infra.py tests/test_container_runner.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_infra.py
git commit -m "test: update infra tests for docker shutdown, image status changes"
```

---

### Task 8: Final Verification

- [ ] **Step 1: Build frontend**

```bash
cd src/desmet/webui/frontend && bun run build
```

Expected: Clean build.

- [ ] **Step 2: Run all project tests**

```bash
python -m pytest tests/ -v --tb=short
```

Expected: All tests pass (excluding pre-existing collection errors from missing deps like `duckdb`).

- [ ] **Step 3: Verify Docker image rebuild with new multi-stage Dockerfile**

```bash
docker rmi desmet-eval-base:1.0 desmet-eval-langgraph:1.0 2>/dev/null; \
docker build -f infrastructure/Dockerfile.base -t desmet-eval-base:1.0 . && \
docker build -f infrastructure/Dockerfile.langgraph -t desmet-eval-langgraph:1.0 . && \
docker images desmet-eval-base:1.0 --format "Base: {{.Size}}" && \
docker images desmet-eval-langgraph:1.0 --format "LangGraph: {{.Size}}"
```

Expected: Both build successfully. Base should be smaller than 3.48GB.

- [ ] **Step 4: Commit any remaining changes**

```bash
git status
# If any unstaged changes, add and commit with appropriate message
```
