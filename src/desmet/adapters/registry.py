"""
Adapter Registry

Maps platform IDs to adapter classes with lazy importing to avoid pulling in
heavy SDK dependencies at module load time.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import yaml

from desmet.harness.adapter import BasePlatformAdapter
from desmet.harness.models import PlatformCategory, PlatformInfo, PlatformRuntime


class AdapterNotImplementedError(NotImplementedError):
    """Raised when requesting an adapter that is still a stub."""

    def __init__(self, platform_id: str):
        super().__init__(
            f"Adapter for '{platform_id}' is not yet implemented. "
            f"Only platforms with completed adapters can be evaluated."
        )
        self.platform_id = platform_id


# (module_path, class_name)
ADAPTER_REGISTRY: dict[str, tuple[str, str]] = {
    "langgraph":          ("desmet.adapters.langgraph",        "LangGraphAdapter"),
    "crewai":             ("desmet.adapters.crewai",           "CrewAIAdapter"),
    "microsoft_agent_framework": ("desmet.adapters.agent_framework", "AgentFrameworkAdapter"),
    "openai_agents_sdk":  ("desmet.adapters.openai_agents",    "OpenAIAgentsAdapter"),
    "google_adk":         ("desmet.adapters.google_adk",       "GoogleADKAdapter"),
    "flowise":            ("desmet.adapters.flowise",          "FlowiseAdapter"),
    "langflow":           ("desmet.adapters.langflow",         "LangFlowAdapter"),
    "dify":               ("desmet.adapters.dify",             "DifyAdapter"),
    "n8n":                ("desmet.adapters.n8n",              "N8nAdapter"),
}


_PLATFORMS_YAML = Path(__file__).resolve().parents[3] / "config" / "platforms.yaml"
_platforms_cache: dict[str, dict] | None = None

_CATEGORY_MAP = {
    "multi_agent_framework": PlatformCategory.MULTI_AGENT_FRAMEWORK,
    "agent_sdk_runtime": PlatformCategory.AGENT_SDK_RUNTIME,
    "visual_workflow_platform": PlatformCategory.VISUAL_WORKFLOW_PLATFORM,
}

_RUNTIME_MAP = {
    "python": PlatformRuntime.PYTHON,
    "nodejs": PlatformRuntime.NODEJS,
    "docker": PlatformRuntime.DOCKER,
}


def _load_platforms_yaml() -> dict[str, dict]:
    global _platforms_cache
    if _platforms_cache is not None:
        return _platforms_cache
    with open(_PLATFORMS_YAML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    _platforms_cache = {p["id"]: p for p in data["platforms"]}
    return _platforms_cache


def load_platform_info(platform_id: str) -> PlatformInfo:
    """Load PlatformInfo from config/platforms.yaml.

    Returns a PlatformInfo with ``version="config"``; adapters should
    override the version with the runtime SDK version.

    Raises KeyError if *platform_id* is not found in the YAML.
    """
    platforms = _load_platforms_yaml()
    if platform_id not in platforms:
        raise KeyError(f"Platform '{platform_id}' not found in {_PLATFORMS_YAML}")
    p = platforms[platform_id]
    return PlatformInfo(
        name=p["name"],
        id=p["id"],
        category=_CATEGORY_MAP[p["category"]],
        runtime=_RUNTIME_MAP[p["runtime"].lower()],
        version="config",
        vendor=p.get("vendor", "Unknown"),
        description=p.get("description", ""),
        documentation_url=p.get("documentation_url", ""),
        repository_url=p.get("repository_url", ""),
    )


def get_adapter(
    platform_id: str,
    config: dict[str, Any] | None = None,
) -> BasePlatformAdapter:
    """Lazily import and instantiate an adapter by platform ID.

    Raises
    ------
    KeyError
        If *platform_id* is not in the registry.
    """
    if platform_id not in ADAPTER_REGISTRY:
        raise KeyError(
            f"Unknown platform '{platform_id}'. "
            f"Known platforms: {', '.join(sorted(ADAPTER_REGISTRY))}"
        )

    module_path, class_name = ADAPTER_REGISTRY[platform_id]

    module = importlib.import_module(module_path)
    adapter_cls = getattr(module, class_name)
    return adapter_cls(config=config)


# Platforms whose adapters are fully implemented (i.e. do not raise
# NotImplementedError on their stage methods).  Update this set as more
# adapters are completed.
_IMPLEMENTED_PLATFORMS: frozenset[str] = frozenset({"langgraph", "crewai", "openai_agents_sdk"})


def list_available_platforms() -> list[str]:
    """Return platform IDs whose adapters are fully implemented.

    Only platforms in ``_IMPLEMENTED_PLATFORMS`` are returned; stub adapters
    that raise ``NotImplementedError`` are excluded.  Update
    ``_IMPLEMENTED_PLATFORMS`` above as more adapters are completed.
    """
    return sorted(ADAPTER_REGISTRY.keys() & _IMPLEMENTED_PLATFORMS)


def list_all_platforms() -> list[str]:
    """Return all registered platform IDs (implemented + stubs)."""
    return sorted(ADAPTER_REGISTRY)
