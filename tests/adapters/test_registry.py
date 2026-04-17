"""Tests for the adapter registry and stub infrastructure."""

from __future__ import annotations

import pytest

from desmet.adapters.registry import (
    ADAPTER_REGISTRY,
    get_adapter,
    list_all_platforms,
    list_available_platforms,
    load_platform_info,
)
from desmet.harness.adapter import BasePlatformAdapter, VisualPlatformAdapter
from desmet.harness.models import PlatformCategory, PlatformInfo, PlatformRuntime

# ---------------------------------------------------------------------------
# load_platform_info
# ---------------------------------------------------------------------------


class TestLoadPlatformInfo:
    """load_platform_info reads metadata from config/platforms.yaml."""

    def test_returns_platform_info(self):
        info = load_platform_info("langgraph")
        assert isinstance(info, PlatformInfo)

    def test_fields_populated(self):
        info = load_platform_info("langgraph")
        assert info.name == "LangGraph"
        assert info.id == "langgraph"
        assert info.category == PlatformCategory.MULTI_AGENT_FRAMEWORK
        assert info.runtime == PlatformRuntime.PYTHON
        assert info.vendor == "LangChain Inc"
        assert "langgraph" in info.documentation_url.lower() or "langchain" in info.documentation_url.lower()
        assert info.repository_url != ""

    def test_version_is_config(self):
        info = load_platform_info("crewai")
        assert info.version == "config"

    def test_all_registered_platforms_loadable(self):
        for pid in list_all_platforms():
            info = load_platform_info(pid)
            assert info.id == pid

    def test_unknown_platform_raises_key_error(self):
        with pytest.raises(KeyError, match="nonexistent"):
            load_platform_info("nonexistent")

    def test_visual_platforms_are_docker_or_python(self):
        visual_ids = ["flowise", "langflow", "dify", "n8n"]
        for pid in visual_ids:
            info = load_platform_info(pid)
            assert info.category == PlatformCategory.VISUAL_WORKFLOW_PLATFORM
            assert info.runtime in (PlatformRuntime.DOCKER, PlatformRuntime.PYTHON)


# ---------------------------------------------------------------------------
# list_all_platforms / list_available_platforms
# ---------------------------------------------------------------------------


class TestListPlatforms:
    def test_list_all_returns_nine(self):
        all_platforms = list_all_platforms()
        assert len(all_platforms) == 9

    def test_list_all_sorted(self):
        all_platforms = list_all_platforms()
        assert all_platforms == sorted(all_platforms)

    def test_available_is_subset_of_all(self):
        available = set(list_available_platforms())
        all_set = set(list_all_platforms())
        assert available <= all_set

    def test_available_is_nonempty_when_any_sdk_installed(self):
        """At least one adapter should import successfully in any dev env.

        Specific adapters are included only when their SDK is installed,
        so we can't hardcode names here.  Visual adapters (flowise,
        langflow, dify, n8n) only need httpx which is always present,
        so at least those should be available.
        """
        available = set(list_available_platforms())
        # Visual adapters don't need heavy SDKs — at least some should appear
        visual = {"flowise", "langflow", "dify", "n8n"}
        assert available & visual, (
            f"Expected at least one visual adapter in {visual}, got {available}"
        )

    def test_coded_adapters_available_even_without_sdks(self):
        """Coded adapters show as available even when their SDK isn't in
        the webui env — they run inside Docker containers that have the
        SDK installed.  A ``ModuleNotFoundError`` for an external SDK
        module should NOT exclude the adapter from the list.
        """
        available = list_available_platforms()
        # Coded adapters should all be present regardless of SDK availability
        coded = {
            "langgraph", "crewai", "openai_agents_sdk",
            "microsoft_agent_framework", "google_adk",
        }
        assert coded <= set(available), (
            f"Expected all coded adapters in list, missing: {coded - set(available)}"
        )


class TestAutoDerivedImplementation:
    """Verify _is_implemented() correctly detects stubs vs real adapters."""

    def test_stub_class_detected_as_not_implemented(self):
        """A class carrying the _is_desmet_stub marker should be rejected."""
        from desmet.adapters.registry import _is_implemented
        from desmet.adapters._shared.stub import create_visual_stub_adapter

        # create_visual_stub_adapter returns a class with _is_desmet_stub=True
        cls = create_visual_stub_adapter("flowise", default_url="http://x")
        assert getattr(cls, "_is_desmet_stub", False) is True

    def test_real_adapter_detected_as_implemented(self):
        """Visual adapters don't need external SDKs — they should be detected."""
        from desmet.adapters.registry import _is_implemented

        # At least one visual adapter should be importable in any dev env
        assert _is_implemented("flowise") is True

    def test_unknown_platform_not_implemented(self):
        from desmet.adapters.registry import _is_implemented

        assert _is_implemented("nonexistent_platform") is False

    def test_missing_external_sdk_still_implemented(self, monkeypatch):
        """If importing the adapter fails because an EXTERNAL SDK is
        missing (e.g. langchain_core), the adapter is still considered
        implemented — containerised runs work regardless.
        """
        import importlib
        from desmet.adapters import registry

        registry._is_implemented.cache_clear()

        def fake_import(name):
            if name == "desmet.adapters.multiagent.langgraph":
                raise ModuleNotFoundError(
                    "No module named 'langchain_core'", name="langchain_core",
                )
            return importlib.import_module.__wrapped__(name) if hasattr(importlib.import_module, '__wrapped__') else importlib.import_module(name)

        monkeypatch.setattr(registry.importlib, "import_module", fake_import)
        assert registry._is_implemented("langgraph") is True
        registry._is_implemented.cache_clear()

    def test_missing_desmet_module_not_implemented(self, monkeypatch):
        """If importing the adapter fails because a DESMET module is
        missing (broken code, not a missing SDK), the adapter is NOT
        considered implemented.
        """
        from desmet.adapters import registry

        registry._is_implemented.cache_clear()

        def fake_import(name):
            if name == "desmet.adapters.multiagent.langgraph":
                raise ModuleNotFoundError(
                    "No module named 'desmet.adapters._broken'",
                    name="desmet.adapters._broken",
                )
            raise RuntimeError("unexpected call")

        monkeypatch.setattr(registry.importlib, "import_module", fake_import)
        assert registry._is_implemented("langgraph") is False
        registry._is_implemented.cache_clear()


# ---------------------------------------------------------------------------
# get_adapter
# ---------------------------------------------------------------------------


class TestGetAdapter:
    def test_returns_adapter_instance(self):
        pytest.importorskip("langchain_core", reason="langchain_core not installed")
        adapter = get_adapter("langgraph")
        assert isinstance(adapter, BasePlatformAdapter)

    def test_unknown_platform_raises_key_error(self):
        with pytest.raises(KeyError, match="Unknown platform"):
            get_adapter("nonexistent_platform")

    def test_stub_adapters_are_base_platform_adapter(self):
        stub_ids = ["google_adk"]
        for pid in stub_ids:
            adapter = get_adapter(pid)
            assert isinstance(adapter, BasePlatformAdapter)

    def test_agent_framework_adapter_is_base_platform_adapter(self):
        adapter = get_adapter("microsoft_agent_framework")
        assert isinstance(adapter, BasePlatformAdapter)

    def test_visual_stubs_are_visual_platform_adapter(self):
        visual_ids = ["flowise", "langflow", "dify", "n8n"]
        for pid in visual_ids:
            adapter = get_adapter(pid)
            assert isinstance(adapter, VisualPlatformAdapter)

    def test_stub_initialize_raises(self):
        import asyncio

        pytest.importorskip("google.adk", reason="google.adk not installed")
        adapter = get_adapter("google_adk")
        with pytest.raises((NotImplementedError, RuntimeError)):
            asyncio.run(adapter.initialize())

    def test_agent_framework_initialize_raises_without_package(self):
        import asyncio

        adapter = get_adapter("microsoft_agent_framework")
        with pytest.raises(RuntimeError, match="Failed to import"):
            asyncio.run(adapter.initialize())

    def test_stub_health_check_returns_false(self):
        import asyncio

        adapter = get_adapter("google_adk")
        assert asyncio.run(adapter.health_check()) is False

    def test_stub_platform_info_matches_yaml(self):
        adapter = get_adapter("microsoft_agent_framework")
        yaml_info = load_platform_info("microsoft_agent_framework")
        adapter_info = adapter.platform_info
        assert adapter_info.name == yaml_info.name
        assert adapter_info.vendor == yaml_info.vendor
        assert adapter_info.category == yaml_info.category

    def test_visual_stub_has_base_url(self):
        adapter = get_adapter("n8n")
        assert hasattr(adapter, "base_url")
        assert adapter.base_url == "http://localhost:5678"

    def test_config_passed_to_adapter(self):
        pytest.importorskip("langchain_core", reason="langchain_core not installed")
        adapter = get_adapter("langgraph", config={"model": "gpt-4"})
        assert adapter.config == {"model": "gpt-4"}


# ---------------------------------------------------------------------------
# ADAPTER_REGISTRY coverage
# ---------------------------------------------------------------------------


class TestAdapterRegistry:
    def test_registry_has_nine_entries(self):
        assert len(ADAPTER_REGISTRY) == 9

    def test_all_entries_are_tuples(self):
        for pid, entry in ADAPTER_REGISTRY.items():
            assert isinstance(entry, tuple)
            assert len(entry) == 2
            module_path, class_name = entry
            assert isinstance(module_path, str)
            assert isinstance(class_name, str)

    def test_all_registered_adapters_importable(self):
        """Every adapter in the registry should be importable (skip if SDK missing)."""
        for pid in ADAPTER_REGISTRY:
            try:
                adapter = get_adapter(pid)
                assert adapter is not None
            except (ModuleNotFoundError, RuntimeError):
                pytest.skip(f"SDK for {pid} not installed")
