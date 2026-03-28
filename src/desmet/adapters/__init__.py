"""
Platform Adapters

Each module implements BasePlatformAdapter for a specific agentic platform.
"""

from desmet.harness.adapter import BasePlatformAdapter, VisualPlatformAdapter

from ._base import ToolAgentAdapter
from .registry import (
    AdapterNotImplementedError,
    get_adapter,
    list_all_platforms,
    list_available_platforms,
)

__all__ = [
    "BasePlatformAdapter",
    "ToolAgentAdapter",
    "VisualPlatformAdapter",
    "AdapterNotImplementedError",
    "get_adapter",
    "list_all_platforms",
    "list_available_platforms",
]
