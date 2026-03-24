"""Platform metadata models and enumerations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PlatformCategory(Enum):
    """Categories of agentic platforms."""

    MULTI_AGENT_FRAMEWORK = "multi_agent_framework"
    AGENT_SDK_RUNTIME = "agent_sdk_runtime"
    VISUAL_WORKFLOW_PLATFORM = "visual_workflow_platform"


class PlatformRuntime(Enum):
    """Runtime environment for the platform."""

    PYTHON = "python"
    NODEJS = "nodejs"
    DOCKER = "docker"


@dataclass
class PlatformInfo:
    """Metadata about a platform."""

    name: str
    id: str
    category: PlatformCategory
    runtime: PlatformRuntime
    version: str
    vendor: str
    description: str
    documentation_url: str
    repository_url: str
