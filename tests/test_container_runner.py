"""Tests for the container runner (image management + stage execution)."""
from __future__ import annotations

import pytest

from desmet.harness.container_runner import (
    image_name,
    dockerfile_path,
    PLATFORM_EXTRA_MAP,
)


class TestImageNaming:
    def test_image_name_langgraph(self):
        assert image_name("langgraph") == "desmet-eval-langgraph:1.0"

    def test_image_name_crewai(self):
        assert image_name("crewai") == "desmet-eval-crewai:1.0"

    def test_image_name_google_adk(self):
        assert image_name("google_adk") == "desmet-eval-google-adk:1.0"

    def test_image_name_openai_agents(self):
        assert image_name("openai_agents_sdk") == "desmet-eval-openai-agents:1.0"

    def test_image_name_agent_framework(self):
        assert image_name("microsoft_agent_framework") == "desmet-eval-agent-framework:1.0"


class TestDockerfilePath:
    def test_path_for_langgraph(self):
        path = dockerfile_path("langgraph")
        assert path.name == "Dockerfile.langgraph"

    def test_path_for_crewai(self):
        path = dockerfile_path("crewai")
        assert path.name == "Dockerfile.crewai"

    def test_path_for_google_adk(self):
        path = dockerfile_path("google_adk")
        assert path.name == "Dockerfile.google-adk"


class TestPlatformExtraMap:
    def test_all_sdk_platforms_have_extras(self):
        expected = {"langgraph", "crewai", "openai_agents_sdk", "microsoft_agent_framework", "google_adk"}
        assert expected == set(PLATFORM_EXTRA_MAP.keys())

    def test_extra_names_match_pyproject(self):
        assert PLATFORM_EXTRA_MAP["langgraph"] == "langgraph"
        assert PLATFORM_EXTRA_MAP["crewai"] == "crewai"
        assert PLATFORM_EXTRA_MAP["openai_agents_sdk"] == "openai-agents"
        assert PLATFORM_EXTRA_MAP["microsoft_agent_framework"] == "agent-framework"
        assert PLATFORM_EXTRA_MAP["google_adk"] == "google-adk"
