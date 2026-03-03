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


# (module_path, class_name)
ADAPTER_REGISTRY: dict[str, tuple[str, str]] = {
    "langgraph":          ("desmet.adapters.langgraph",        "LangGraphAdapter"),
    "crewai":             ("desmet.adapters.crewai",           "CrewAIAdapter"),
    "microsoft_autogen":  ("desmet.adapters.autogen",          "AutoGenAdapter"),
    "openai_agents_sdk":  ("desmet.adapters.openai_agents",    "OpenAIAgentsAdapter"),
    "google_adk":         ("desmet.adapters.google_adk",       "GoogleADKAdapter"),
    "semantic_kernel":    ("desmet.adapters.semantic_kernel",   "SemanticKernelAdapter"),
    "flowise":            ("desmet.adapters.flowise",          "FlowiseAdapter"),
    "langflow":           ("desmet.adapters.langflow",         "LangFlowAdapter"),
    "dify":               ("desmet.adapters.dify",             "DifyAdapter"),
    "n8n":                ("desmet.adapters.n8n",              "N8nAdapter"),
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


def list_available_platforms() -> list[str]:
    """Return all platform IDs with registered adapter classes.

    All adapters now have concrete classes (though stub adapters raise
    ``NotImplementedError`` on most methods).
    """
    return sorted(ADAPTER_REGISTRY)


def list_all_platforms() -> list[str]:
    """Return all registered platform IDs (implemented + stubs)."""
    return sorted(ADAPTER_REGISTRY)
