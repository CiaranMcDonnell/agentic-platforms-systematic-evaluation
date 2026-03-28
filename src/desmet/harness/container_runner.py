"""Container runner for per-platform isolated evaluation.

Manages Docker images (build/check) and runs adapter stages inside
per-platform containers.  The host serializes StageContext to JSON,
the container runs the entrypoint, and the result comes back as
StageResult JSON on stdout with progress on stderr.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

from desmet.platforms_config import get_platform_field, get_platforms_config
from desmet.harness.context import StageContext
from desmet.harness.results import StageResult

_log = logging.getLogger(__name__)

_INFRA_DIR = Path(__file__).resolve().parents[3] / "infrastructure"
_IMAGE_TAG = "1.0"
_BASE_IMAGE = f"desmet-eval-base:{_IMAGE_TAG}"

_STAGE_NAMES = {"requirements", "codegen", "testing", "deploy"}

# Built from config/platforms.yaml — maps SDK platform IDs to their pip extra.
# Visual platforms (no pip_extra) are excluded.
PLATFORM_EXTRA_MAP: dict[str, str] = {
    pid: data["pip_extra"]
    for pid, data in get_platforms_config().items()
    if data.get("pip_extra")
}


def image_name(platform_id: str) -> str:
    """Return the Docker image tag for a platform."""
    suffix = get_platform_field(platform_id, "pip_extra", platform_id)
    return f"desmet-eval-{suffix}:{_IMAGE_TAG}"


def dockerfile_path(platform_id: str) -> Path:
    """Return the Dockerfile path for a platform."""
    suffix = get_platform_field(platform_id, "pip_extra", platform_id)
    return _INFRA_DIR / f"Dockerfile.{suffix}"


def has_image(platform_id: str) -> bool:
    """Check if the Docker image for a platform exists."""
    tag = image_name(platform_id)
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", tag],
            capture_output=True, timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def build_image(
    platform_id: str,
    progress_callback: Callable[[str], None] | None = None,
) -> bool:
    """Build the Docker image for a platform.

    Builds the base image first if it doesn't exist.
    Returns True on success.
    """
    project_root = Path(__file__).resolve().parents[3]

    # Ensure base image exists
    try:
        probe = subprocess.run(
            ["docker", "image", "inspect", _BASE_IMAGE],
            capture_output=True, timeout=10,
        )
        if probe.returncode != 0:
            if progress_callback:
                progress_callback(f"Building base image {_BASE_IMAGE}...")
            base_result = subprocess.run(
                [
                    "docker", "build",
                    "-f", str(_INFRA_DIR / "Dockerfile.base"),
                    "-t", _BASE_IMAGE,
                    str(project_root),
                ],
                capture_output=True, text=True, timeout=600,
            )
            if base_result.returncode != 0:
                _log.error("Base image build failed: %s", base_result.stderr)
                if progress_callback:
                    progress_callback(f"Base image build FAILED: {base_result.stderr[:200]}")
                return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

    # Build platform image
    tag = image_name(platform_id)
    df = dockerfile_path(platform_id)
    if progress_callback:
        progress_callback(f"Building {tag}...")

    try:
        result = subprocess.run(
            [
                "docker", "build",
                "-f", str(df),
                "-t", tag,
                str(project_root),
            ],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            _log.error("Image build failed for %s: %s", platform_id, result.stderr)
            if progress_callback:
                progress_callback(f"Build FAILED for {tag}: {result.stderr[:200]}")
            return False
        if progress_callback:
            progress_callback(f"Built {tag}")
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        _log.error("Image build error: %s", e)
        return False


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


def _container_name(platform_id: str, story_id: str) -> str:
    """Deterministic container name for a platform+story run."""
    suffix = get_platform_field(platform_id, "pip_extra", platform_id)
    return f"desmet-run-{suffix}-{story_id}"


def _ensure_container(
    platform_id: str,
    story_id: str,
    workspace: Path,
) -> str:
    """Start a persistent container for the platform+story.

    Returns the container name. Reuses existing container if running.
    """
    name = _container_name(platform_id, story_id)

    # Check if already running
    try:
        probe = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", name],
            capture_output=True, text=True, timeout=10,
        )
        if probe.returncode == 0 and "true" in probe.stdout.lower():
            return name
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Remove stale container if exists
    subprocess.run(
        ["docker", "rm", "-f", name],
        capture_output=True, timeout=10,
    )

    # Start container
    workspace_abs = str(workspace.resolve()).replace("\\", "/")
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    tag = image_name(platform_id)

    result = subprocess.run(
        [
            "docker", "run", "-d",
            "--name", name,
            "-v", f"{workspace_abs}:/workspace",
            "-w", "/workspace",
            tag,
            "bash", "-c", "sleep infinity",
        ],
        capture_output=True, text=True, timeout=60, env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to start container {name}: {result.stderr}")
    return name


def stop_container(platform_id: str, story_id: str) -> None:
    """Stop and remove the container for a platform+story."""
    name = _container_name(platform_id, story_id)
    try:
        subprocess.run(
            ["docker", "rm", "-f", name],
            capture_output=True, timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


async def run_stage_in_container(
    platform_id: str,
    stage_name: str,
    context: StageContext,
    progress_callback: Callable[[str], None] | None = None,
) -> StageResult:
    """Run an adapter stage inside a per-platform Docker container.

    Writes StageContext JSON to the workspace, runs the entrypoint via
    docker exec, streams stderr for progress, and parses stdout as
    StageResult JSON.
    """
    if stage_name not in _STAGE_NAMES:
        raise ValueError(f"Unknown stage: {stage_name}")

    # Ensure image and container
    if not has_image(platform_id):
        build_image(platform_id, progress_callback)

    story_id = context.story.id
    container = _ensure_container(platform_id, story_id, context.workspace)

    # Write context JSON to workspace
    ctx_data = context.to_dict()
    ctx_data.setdefault("metadata", {})["stage_name"] = stage_name
    ctx_file = context.workspace / ".desmet-context.json"
    with open(ctx_file, "w") as f:
        json.dump(ctx_data, f)

    # Run entrypoint via docker exec, streaming stderr
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    proc = await asyncio.create_subprocess_exec(
        "docker", "exec", "-w", "/app", container,
        "uv", "run", "python", "-m", "desmet.harness.entrypoint", "/workspace/.desmet-context.json",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    # Stream stderr (progress) line by line
    async def _stream_stderr():
        while True:
            line = await proc.stderr.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip()
            if text and progress_callback:
                progress_callback(text)

    stderr_task = asyncio.create_task(_stream_stderr())
    stdout_data = await proc.stdout.read()
    await stderr_task
    await proc.wait()

    # Clean up context file
    try:
        ctx_file.unlink(missing_ok=True)
    except OSError:
        pass

    # Parse result
    if not stdout_data.strip():
        return StageResult(
            platform_id=platform_id,
            stage_name=stage_name,
            success=False,
            error_message="Container produced no output",
        )

    try:
        result_data = json.loads(stdout_data)
        return StageResult.from_dict(result_data)
    except (json.JSONDecodeError, Exception) as e:
        return StageResult(
            platform_id=platform_id,
            stage_name=stage_name,
            success=False,
            error_message=f"Failed to parse container output: {e}",
        )
