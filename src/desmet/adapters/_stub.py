"""Stub adapter factory for unimplemented platforms.

Generates adapter classes from ``config/platforms.yaml`` metadata so that
stub files are reduced to a single line each.  Two factories are provided:

- ``create_stub_adapter(platform_id)`` — for :class:`BasePlatformAdapter`
  stubs (Microsoft Agent Framework, OpenAI Agents, Google ADK).
- ``create_visual_stub_adapter(platform_id, default_url)`` — for
  :class:`VisualPlatformAdapter` stubs (Flowise, LangFlow, Dify, n8n).

Both return a **class** (not an instance) that:
  * Returns :class:`PlatformInfo` loaded from YAML via the registry.
  * Raises ``NotImplementedError`` on all stage / lifecycle methods.
  * Returns ``False`` on ``health_check()``.
"""

from __future__ import annotations

from typing import Any

from desmet.adapters.registry import load_platform_info
from desmet.harness.adapter import BasePlatformAdapter, VisualPlatformAdapter
from desmet.harness.context import StageContext
from desmet.harness.models import PlatformInfo
from desmet.harness.results import (
    CodeResult,
    DeployResult,
    RequirementsResult,
    TestResult,
)


def create_stub_adapter(platform_id: str) -> type[BasePlatformAdapter]:
    """Create a stub adapter class backed by YAML metadata.

    The returned class is a concrete subclass of :class:`BasePlatformAdapter`
    whose stage methods all raise ``NotImplementedError``.
    """
    _info = load_platform_info(platform_id)
    _msg = f"{_info.name} adapter not yet implemented"

    class _StubAdapter(BasePlatformAdapter):
        __doc__ = f"Stub adapter for {_info.name}."

        @property
        def platform_info(self) -> PlatformInfo:
            return _info

        async def initialize(self) -> None:
            raise NotImplementedError(_msg)

        async def shutdown(self) -> None:
            pass

        async def health_check(self) -> bool:
            return False

        async def generate_requirements(self, context: StageContext) -> RequirementsResult:
            raise NotImplementedError(_msg)

        async def generate_code(self, context: StageContext) -> CodeResult:
            raise NotImplementedError(_msg)

        async def generate_tests(self, context: StageContext) -> TestResult:
            raise NotImplementedError(_msg)

        async def build_and_deploy(self, context: StageContext) -> DeployResult:
            raise NotImplementedError(_msg)

    _StubAdapter.__name__ = f"{_info.name.replace(' ', '')}Adapter"
    _StubAdapter.__qualname__ = _StubAdapter.__name__
    return _StubAdapter


def create_visual_stub_adapter(
    platform_id: str,
    default_url: str = "http://localhost:3000",
) -> type[VisualPlatformAdapter]:
    """Create a stub adapter class for visual/workflow platforms.

    The returned class is a concrete subclass of
    :class:`VisualPlatformAdapter` whose stage and workflow methods all
    raise ``NotImplementedError``.
    """
    _info = load_platform_info(platform_id)
    _msg = f"{_info.name} adapter not yet implemented"

    class _VisualStubAdapter(VisualPlatformAdapter):
        __doc__ = f"Stub adapter for {_info.name}."

        def __init__(self, config: dict[str, Any] | None = None):
            super().__init__(
                base_url=config.get("base_url", default_url) if config else default_url,
                api_key=config.get("api_key") if config else None,
                config=config,
            )

        @property
        def platform_info(self) -> PlatformInfo:
            return _info

        async def initialize(self) -> None:
            raise NotImplementedError(_msg)

        async def shutdown(self) -> None:
            pass

        async def health_check(self) -> bool:
            return False

        async def create_workflow(self, workflow_definition: dict) -> str:
            raise NotImplementedError(_msg)

        async def execute_workflow(self, workflow_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
            raise NotImplementedError(_msg)

        async def delete_workflow(self, workflow_id: str) -> None:
            raise NotImplementedError(_msg)

        async def generate_requirements(self, context: StageContext) -> RequirementsResult:
            raise NotImplementedError(_msg)

        async def generate_code(self, context: StageContext) -> CodeResult:
            raise NotImplementedError(_msg)

        async def generate_tests(self, context: StageContext) -> TestResult:
            raise NotImplementedError(_msg)

        async def build_and_deploy(self, context: StageContext) -> DeployResult:
            raise NotImplementedError(_msg)

    _VisualStubAdapter.__name__ = f"{_info.name.replace(' ', '')}Adapter"
    _VisualStubAdapter.__qualname__ = _VisualStubAdapter.__name__
    return _VisualStubAdapter
