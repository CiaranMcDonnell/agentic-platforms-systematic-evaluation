"""Lightweight platform config loader.

Reads config/platforms.yaml without importing any adapter or harness modules.
Safe to import from anywhere without triggering heavy dependency chains.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_PLATFORMS_YAML = Path(__file__).resolve().parents[2] / "config" / "platforms.yaml"
_platforms_cache: dict[str, dict] | None = None


def _load_platforms_yaml() -> dict[str, dict]:
    global _platforms_cache
    if _platforms_cache is not None:
        return _platforms_cache
    with open(_PLATFORMS_YAML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    _platforms_cache = {p["id"]: p for p in data["platforms"]}
    return _platforms_cache


def get_platforms_config() -> dict[str, dict]:
    """Return the full ``{id: {...}}`` mapping from ``config/platforms.yaml``.

    Each value is the raw YAML dict for that platform, including fields
    like ``pip_extra``, ``python_package``, ``container_name``, ``colour``.

    The result is cached — safe to call repeatedly.
    """
    return _load_platforms_yaml()


def get_platform_field(platform_id: str, field: str, default: Any = None) -> Any:
    """Look up a single field for *platform_id* from ``platforms.yaml``."""
    platforms = _load_platforms_yaml()
    return platforms.get(platform_id, {}).get(field, default)
