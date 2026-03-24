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

    def test_langgraph_and_crewai_available(self):
        available = list_available_platforms()
        assert "langgraph" in available
        assert "crewai" in available


# ---------------------------------------------------------------------------
# get_adapter
# ---------------------------------------------------------------------------


class TestGetAdapter:
    def test_returns_adapter_instance(self):
        adapter = get_adapter("langgraph")
        assert isinstance(adapter, BasePlatformAdapter)

    def test_unknown_platform_raises_key_error(self):
        with pytest.raises(KeyError, match="Unknown platform"):
            get_adapter("nonexistent_platform")

    def test_stub_adapters_are_base_platform_adapter(self):
        stub_ids = ["microsoft_agent_framework", "openai_agents_sdk", "google_adk"]
        for pid in stub_ids:
            adapter = get_adapter(pid)
            assert isinstance(adapter, BasePlatformAdapter)

    def test_visual_stubs_are_visual_platform_adapter(self):
        visual_ids = ["flowise", "langflow", "dify", "n8n"]
        for pid in visual_ids:
            adapter = get_adapter(pid)
            assert isinstance(adapter, VisualPlatformAdapter)

    def test_stub_initialize_raises(self):
        import asyncio

        adapter = get_adapter("microsoft_agent_framework")
        with pytest.raises(NotImplementedError, match="not yet implemented"):
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
        """Every adapter in the registry should be importable."""
        for pid in ADAPTER_REGISTRY:
            adapter = get_adapter(pid)
            assert adapter is not None
