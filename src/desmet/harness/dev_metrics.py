"""Static developer experience metrics for platform adapters."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_ADAPTERS_DIR = Path(__file__).resolve().parents[1] / "adapters"
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PYPROJECT = _PROJECT_ROOT / "pyproject.toml"

_SHARED_MODULES = [
    "_shared/base.py",
    "_shared/tools.py",
    "_shared/prompts.py",
    "_shared/tracing.py",
    "_shared/validation.py",
    "_shared/planning.py",
    "_shared/observation.py",
    "_shared/retry.py",
]

_PLATFORM_ADAPTER_FILE: dict[str, str] = {
    "microsoft_agent_framework": "agent_framework.py",
    "openai_agents_sdk": "openai_agents.py",
}


@dataclass
class DevMetrics:
    platform_id: str
    adapter_loc: int = 0
    adapter_sloc: int = 0
    dependency_count: int = 0
    dependency_names: list[str] = field(default_factory=list)
    install_size_mb: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform_id": self.platform_id,
            "adapter_loc": self.adapter_loc,
            "adapter_sloc": self.adapter_sloc,
            "dependency_count": self.dependency_count,
            "dependency_names": self.dependency_names,
            "install_size_mb": self.install_size_mb,
        }


def count_loc(source: str) -> int:
    """Count non-blank, non-comment-only lines."""
    count = 0
    for line in source.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count


def count_sloc(source: str) -> int:
    """Count logical statement lines (excludes imports, docstrings, blanks, comments)."""
    lines = source.splitlines()
    count = 0
    in_docstring = False
    docstring_delim = None

    for line in lines:
        stripped = line.strip()

        if in_docstring:
            if docstring_delim in stripped:
                in_docstring = False
            continue

        if not stripped or stripped.startswith("#"):
            continue

        # Detect docstring start
        if stripped.startswith('"""') or stripped.startswith("'''"):
            delim = stripped[:3]
            if stripped.count(delim) >= 2:
                continue  # Single-line docstring
            in_docstring = True
            docstring_delim = delim
            continue

        if stripped.startswith("import ") or stripped.startswith("from "):
            continue

        count += 1
    return count


def _parse_optional_deps() -> dict[str, list[str]]:
    """Parse [project.optional-dependencies] from pyproject.toml."""
    if not _PYPROJECT.exists():
        return {}

    text = _PYPROJECT.read_text(encoding="utf-8")
    extras: dict[str, list[str]] = {}
    current_extra: str | None = None
    in_section = False

    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "[project.optional-dependencies]":
            in_section = True
            continue
        if in_section and stripped.startswith("["):
            break
        if not in_section:
            continue

        m = re.match(r"^(\w[\w-]*)\s*=\s*\[", stripped)
        if m:
            current_extra = m.group(1)
            extras[current_extra] = []
            continue

        if current_extra is not None:
            if stripped == "]":
                current_extra = None
                continue
            req_match = re.match(r'"([^"]+)"', stripped)
            if req_match:
                req = req_match.group(1)
                pkg_name = re.split(r"[>=<!\[;]", req)[0].strip()
                if pkg_name:
                    extras[current_extra].append(pkg_name)

    return extras


def _get_platform_extra(platform_id: str) -> str | None:
    from desmet.platforms_config import get_platform_field

    return get_platform_field(platform_id, "pip_extra", None)


def compute_dev_metrics(platform_id: str) -> DevMetrics:
    dm = DevMetrics(platform_id=platform_id)

    # Adapter LOC — consult explicit mapping first, then fall back to
    # convention (platform_id.py, then underscored).
    override = _PLATFORM_ADAPTER_FILE.get(platform_id)
    if override is not None:
        adapter_file = _ADAPTERS_DIR / override
    else:
        adapter_file = _ADAPTERS_DIR / f"{platform_id}.py"
        if not adapter_file.exists():
            alt_name = platform_id.replace("-", "_")
            adapter_file = _ADAPTERS_DIR / f"{alt_name}.py"

    if adapter_file.exists():
        source = adapter_file.read_text(encoding="utf-8")
        dm.adapter_loc = count_loc(source)
        dm.adapter_sloc = count_sloc(source)

    # Dependencies from pyproject.toml
    extras = _parse_optional_deps()
    pip_extra = _get_platform_extra(platform_id)
    if pip_extra and pip_extra in extras:
        dm.dependency_names = extras[pip_extra]
        dm.dependency_count = len(dm.dependency_names)

    # Install size from Docker image (if built)
    try:
        import json as _json
        import subprocess

        from desmet.harness.container_runner import _BASE_IMAGE, get_image_details

        platform_details = get_image_details(platform_id)
        if platform_details:
            platform_size = platform_details["size_bytes"]
            base_probe = subprocess.run(
                ["docker", "image", "inspect", _BASE_IMAGE],
                capture_output=True,
                text=True,
                timeout=10,
            )
            base_size = 0
            if base_probe.returncode == 0:
                data = _json.loads(base_probe.stdout)
                if data:
                    base_size = data[0].get("Size", 0)
            delta = max(0, platform_size - base_size)
            dm.install_size_mb = round(delta / (1024 * 1024), 1)
    except Exception:
        pass

    return dm


def compute_all_dev_metrics() -> dict[str, DevMetrics]:
    from desmet.platforms_config import get_platforms_config

    results: dict[str, DevMetrics] = {}
    for pid in get_platforms_config():
        dm = compute_dev_metrics(pid)
        if dm.adapter_loc > 0 or dm.dependency_count > 0:
            results[pid] = dm
    return results


def get_shared_loc() -> int:
    total = 0
    for filename in _SHARED_MODULES:
        path = _ADAPTERS_DIR / filename
        if path.exists():
            total += count_loc(path.read_text(encoding="utf-8"))
    return total
