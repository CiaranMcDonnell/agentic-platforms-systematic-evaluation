"""
Adapter Registry

Maps platform IDs to adapter classes with lazy importing to avoid pulling in
heavy SDK dependencies at module load time.
"""

from __future__ import annotations

import importlib
from typing import Any

from desmet.harness.base import BasePlatformAdapter


class AdapterNotImplementedError(NotImplementedError):
    """Raised when requesting an adapter that is still a stub."""

    def __init__(self, platform_id: str):
        super().__init__(
            f"Adapter for '{platform_id}' is not yet implemented. "
            f"Only platforms with completed adapters can be evaluated."
        )
        self.platform_id = platform_id


# (module_path, class_name | None)
# class_name=None means the adapter file exists but has no implementation yet.
ADAPTER_REGISTRY: dict[str, tuple[str, str | None]] = {
    "langgraph":          ("desmet.adapters.langgraph",        "LangGraphAdapter"),
    "crewai":             ("desmet.adapters.crewai",           "CrewAIAdapter"),
    "microsoft_autogen":  ("desmet.adapters.autogen",          None),
    "openai_agents_sdk":  ("desmet.adapters.openai_agents",    None),
    "google_adk":         ("desmet.adapters.google_adk",       None),
    "semantic_kernel":    ("desmet.adapters.semantic_kernel",   None),
    "flowise":            ("desmet.adapters.flowise",          None),
    "langflow":           ("desmet.adapters.langflow",         None),
    "dify":               ("desmet.adapters.dify",             None),
    "n8n":                ("desmet.adapters.n8n",              None),
}


def get_adapter(
    platform_id: str,
    config: dict[str, Any] | None = None,
) -> BasePlatformAdapter:
    """Lazily import and instantiate an adapter by platform ID.

    Raises
    ------
    KeyError
        If *platform_id* is not in the registry.
    AdapterNotImplementedError
        If the adapter is still a stub (class_name is None).
    """
    if platform_id not in ADAPTER_REGISTRY:
        raise KeyError(
            f"Unknown platform '{platform_id}'. "
            f"Known platforms: {', '.join(sorted(ADAPTER_REGISTRY))}"
        )

    module_path, class_name = ADAPTER_REGISTRY[platform_id]

    if class_name is None:
        raise AdapterNotImplementedError(platform_id)

    module = importlib.import_module(module_path)
    adapter_cls = getattr(module, class_name)
    return adapter_cls(config=config)


def list_available_platforms() -> list[str]:
    """Return platform IDs that have a real (non-stub) adapter class."""
    return sorted(
        pid for pid, (_, cls_name) in ADAPTER_REGISTRY.items()
        if cls_name is not None
    )


def list_all_platforms() -> list[str]:
    """Return all registered platform IDs (implemented + stubs)."""
    return sorted(ADAPTER_REGISTRY)
