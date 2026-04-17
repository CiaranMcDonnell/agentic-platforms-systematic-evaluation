"""
Infrastructure management for DESMET evaluation.

Handles Docker Compose interaction and platform readiness checks.
"""

from __future__ import annotations

import importlib
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from desmet.platforms_config import get_platforms_config

COMPOSE_FILE = (
    Path(__file__).resolve().parent.parent.parent / "infrastructure" / "docker-compose.yaml"
)

PROFILE_TARGETS: dict[str, list[str]] = {
    "flowise": ["flowise"],
    "langflow": ["langflow"],
    "dify": ["dify"],
    "n8n": ["n8n"],
    "langfuse": ["langfuse"],
    "infrastructure": ["infrastructure"],
    "all": ["flowise", "langflow", "dify", "n8n", "langfuse"],
}

# ── Evaluation platforms (derived from config/platforms.yaml) ───────────
_platforms = get_platforms_config()

PLATFORM_PACKAGES: dict[str, str | None] = {
    pid: data.get("python_package") for pid, data in _platforms.items()
}

PLATFORM_CONTAINERS: dict[str, str | None] = {
    pid: data.get("container_name") for pid, data in _platforms.items()
}

PLATFORM_NAMES: dict[str, str] = {pid: data["name"] for pid, data in _platforms.items()}

# ── Infrastructure services (not evaluation targets) ───────────────────
INFRA_SERVICES: dict[str, dict] = {
    "langfuse": {
        "name": "Langfuse",
        "description": "Observability & tracing (auto-managed)",
        "containers": ["desmet-langfuse-web"],
        "profile": "langfuse",
        "managed": True,
    },
    "infrastructure": {
        "name": "Postgres + Redis",
        "description": "Shared database & cache",
        "containers": ["desmet-postgres", "desmet-redis"],
        "profile": "infrastructure",
    },
}

_API_KEY_VARS: dict[str, str] = {
    "OPENAI_API_KEY": "openai",
    "ANTHROPIC_API_KEY": "anthropic",
    "GOOGLE_API_KEY": "google",
    "OPENROUTER_API_KEY": "openrouter",
}


@dataclass
class PlatformStatus:
    platform_id: str
    name: str
    infra_type: str
    status: str


@dataclass
class ConfigStatus:
    model: str
    api_keys_set: list[str] = field(default_factory=list)
    langfuse_status: str = "not configured"
    deploy_status: str = "not configured"


def is_package_importable(package_name: str) -> bool:
    try:
        importlib.import_module(package_name)
        return True
    except ImportError:
        return False


def get_container_status(container_name: str) -> str:
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return "not started"
        return result.stdout.strip()
    except FileNotFoundError:
        return "docker not found"
    except subprocess.TimeoutExpired:
        return "not started"


def get_platform_statuses() -> list[PlatformStatus]:
    from desmet.harness.container_runner import has_image

    statuses = []
    for pid in PLATFORM_PACKAGES:
        name = PLATFORM_NAMES[pid]
        package = PLATFORM_PACKAGES[pid]
        container = PLATFORM_CONTAINERS[pid]

        if package is not None:
            # SDK platform: check for container image first, then local install
            if has_image(pid):
                statuses.append(
                    PlatformStatus(
                        platform_id=pid,
                        name=name,
                        infra_type="Docker (isolated)",
                        status="ready",
                    )
                )
            else:
                installed = is_package_importable(package)
                statuses.append(
                    PlatformStatus(
                        platform_id=pid,
                        name=name,
                        infra_type="Docker (isolated)" if not installed else "Python SDK",
                        status="ready" if installed else "not built",
                    )
                )
        else:
            container_status = get_container_status(container) if container else "not started"
            # A running visual-platform container is "ready" for a benchmark run,
            # matching the SDK-platform "ready" terminology surfaced in the UI.
            if container_status == "running":
                container_status = "ready"
            statuses.append(
                PlatformStatus(
                    platform_id=pid,
                    name=name,
                    infra_type="Docker",
                    status=container_status,
                )
            )

    return statuses


def get_docker_platform_statuses() -> dict[str, str]:
    """Return container/image status for all docker-based platforms.

    For visual platforms (Flowise, etc.) returns live container status.
    For SDK platforms (LangGraph, etc.) returns 'ready' if the Docker
    image is built, otherwise 'not built'.
    """
    from desmet.harness.container_runner import has_image

    result: dict[str, str] = {}
    for pid, container in PLATFORM_CONTAINERS.items():
        if container is not None:
            # Visual platform — check running container. A running container is
            # "ready" for a benchmark run, matching SDK-platform terminology.
            status = get_container_status(container)
            result[pid] = "ready" if status == "running" else status
        elif PLATFORM_PACKAGES.get(pid) is not None:
            # SDK platform — check Docker image existence
            result[pid] = "ready" if has_image(pid) else "not built"
    return result


def get_infra_statuses() -> list[dict]:
    """Return status of infrastructure services (Langfuse, Postgres+Redis).

    A service can be backed by multiple containers (e.g. the "Postgres +
    Redis" card represents both ``desmet-postgres`` and ``desmet-redis``).
    Aggregated status:

    * ``running``     — all containers in the group are running
    * ``partial``     — some containers running, others not
    * ``not started`` — no containers running

    The ``containers`` list in the response exposes per-container state
    so the UI can show which ones specifically are up.
    """
    results = []
    for sid, info in INFRA_SERVICES.items():
        container_names: list[str] = info.get("containers", [])
        # Back-compat: accept a single "container" field for older entries
        if not container_names and "container" in info:
            container_names = [info["container"]]

        per_container = [
            {"name": name, "status": get_container_status(name)} for name in container_names
        ]
        running = sum(1 for c in per_container if c["status"] == "running")
        total = len(per_container)

        if total == 0:
            status = "not started"
        elif running == total:
            status = "running"
        elif running == 0:
            status = "not started"
        else:
            status = "partial"

        results.append(
            {
                "id": sid,
                "name": info["name"],
                "description": info["description"],
                "status": status,
                "managed": info.get("managed", False),
                "containers": per_container,
                "running_count": running,
                "total_count": total,
            }
        )
    return results


def get_config_status() -> ConfigStatus:
    from desmet.llm_config import get_config

    model = get_config().model

    api_keys_set = [provider for var, provider in _API_KEY_VARS.items() if os.getenv(var)]

    langfuse_pub = os.getenv("LANGFUSE_PUBLIC_KEY")
    langfuse_sec = os.getenv("LANGFUSE_SECRET_KEY")
    if langfuse_pub and langfuse_sec:
        langfuse_status = "configured"
    elif is_package_importable("langfuse"):
        langfuse_status = "installed, not configured"
    else:
        langfuse_status = "not installed"

    # Deploy target status
    deploy_host = os.getenv("DEPLOY_HOST")
    deploy_repo = os.getenv("DEPLOY_REPO")
    deploy_key = os.getenv("DEPLOY_KEY_PATH")
    if deploy_host and deploy_repo and deploy_key:
        deploy_status = "configured"
    elif deploy_host or deploy_repo:
        deploy_status = "partially configured"
    else:
        deploy_status = "not configured"

    return ConfigStatus(
        model=model,
        api_keys_set=api_keys_set,
        langfuse_status=langfuse_status,
        deploy_status=deploy_status,
    )


def compose_up(target: str) -> subprocess.CompletedProcess:
    if target not in PROFILE_TARGETS:
        raise ValueError(
            f"Unknown target '{target}'. Available: {', '.join(sorted(PROFILE_TARGETS))}"
        )

    profiles = PROFILE_TARGETS[target]
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE)]
    for p in profiles:
        cmd.extend(["--profile", p])
    cmd.extend(["up", "-d", "--wait"])

    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def compose_down(target: str | None = None) -> subprocess.CompletedProcess:
    if target and target not in PROFILE_TARGETS:
        raise ValueError(
            f"Unknown target '{target}'. Available: {', '.join(sorted(PROFILE_TARGETS))}"
        )

    profiles = (
        PROFILE_TARGETS.get(target, PROFILE_TARGETS["all"]) if target else PROFILE_TARGETS["all"]
    )

    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE)]
    for p in profiles:
        cmd.extend(["--profile", p])
    cmd.append("down")

    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def cleanup_all_docker() -> None:
    """Best-effort cleanup of all DESMET Docker resources.

    Called on webui shutdown. Stops Compose services and removes
    any lingering evaluation containers.
    """
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
            capture_output=True,
            text=True,
            timeout=10,
        )
        container_ids = ps.stdout.strip()
        if container_ids:
            subprocess.run(
                ["docker", "rm", "-f"] + container_ids.split(),
                capture_output=True,
                text=True,
                timeout=30,
            )
            _log.info("Removed eval containers: %s", container_ids.replace("\n", ", "))
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        _log.warning("Could not clean eval containers: %s", e)
