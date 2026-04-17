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
    "langgraph":          ("desmet.adapters.multiagent.langgraph",        "LangGraphAdapter"),
    "crewai":             ("desmet.adapters.multiagent.crewai",           "CrewAIAdapter"),
    "microsoft_agent_framework": ("desmet.adapters.multiagent.agent_framework", "AgentFrameworkAdapter"),
    "openai_agents_sdk":  ("desmet.adapters.sdk.openai_agents", "OpenAIAgentsAdapter"),
    "google_adk":         ("desmet.adapters.sdk.google_adk",   "GoogleADKAdapter"),
    "flowise":            ("desmet.adapters.flowise",          "FlowiseAdapter"),
    "langflow":           ("desmet.adapters.langflow",         "LangFlowAdapter"),
    "dify":               ("desmet.adapters.dify",             "DifyAdapter"),
    "n8n":                ("desmet.adapters.n8n",              "N8nAdapter"),
}


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


# Re-export from lightweight module (avoids circular import through adapters.__init__)
from desmet.platforms_config import (  # noqa: E402, F401
    _load_platforms_yaml,
    get_platform_field,
    get_platforms_config,
)


def load_platform_info(platform_id: str) -> PlatformInfo:
    """Load PlatformInfo from config/platforms.yaml.

    Returns a PlatformInfo with ``version="config"``; adapters should
    override the version with the runtime SDK version.

    Raises KeyError if *platform_id* is not found in the YAML.
    """
    platforms = _load_platforms_yaml()
    if platform_id not in platforms:
        raise KeyError(f"Platform '{platform_id}' not found in config/platforms.yaml")
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


import functools


@functools.lru_cache(maxsize=None)
def _is_implemented(platform_id: str) -> bool:
    """Check whether an adapter is a real implementation (not a stub).

    An adapter is considered implemented when its registered class exists
    and is not a stub (no ``_is_desmet_stub`` marker from
    :mod:`desmet.adapters._shared.stub`).

    **Missing SDK dependencies don't count as "not implemented"** — the
    adapter code still exists, it just can't run in this particular
    Python env.  Coded adapters (LangGraph, CrewAI, etc.) usually run
    inside their Docker container (which has the SDK), so the webui's
    base env doesn't need every SDK installed.  When an import fails
    because an *external* SDK module (not a ``desmet.*`` module) is
    missing, we assume the adapter is implemented and runnable via its
    container image.

    Result is cached per-process — adapter availability does not change
    at runtime.
    """
    if platform_id not in ADAPTER_REGISTRY:
        return False
    module_path, class_name = ADAPTER_REGISTRY[platform_id]
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as e:
        # Distinguish "missing SDK" from "broken adapter code":
        #   - missing ext. SDK (e.g. "langchain_core")  → implemented (containerised)
        #   - missing desmet module (e.g. "desmet.foo") → broken, not implemented
        missing = e.name or ""
        if missing and not missing.startswith("desmet"):
            return True
        return False
    except Exception:
        return False
    adapter_cls = getattr(module, class_name, None)
    if adapter_cls is None:
        return False
    return not getattr(adapter_cls, "_is_desmet_stub", False)


def list_available_platforms() -> list[str]:
    """Return platform IDs whose adapters are fully implemented.

    Uses :func:`_is_implemented` to detect implementation status by
    inspecting the adapter class — stubs and unimportable adapters
    are excluded automatically.  No hand-maintained list to keep in
    sync: adding a new adapter only requires registering it in
    :data:`ADAPTER_REGISTRY`.
    """
    return sorted(pid for pid in ADAPTER_REGISTRY if _is_implemented(pid))


def list_all_platforms() -> list[str]:
    """Return all registered platform IDs (implemented + stubs)."""
    return sorted(ADAPTER_REGISTRY)
