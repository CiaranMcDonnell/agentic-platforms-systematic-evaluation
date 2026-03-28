"""Tests for the container runner (image management + stage execution)."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from desmet.harness.container_runner import (
    image_name,
    dockerfile_path,
    PLATFORM_EXTRA_MAP,
    delete_image,
    get_image_details,
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


class TestDeleteImage:
    @patch("desmet.harness.container_runner.subprocess.run")
    def test_delete_existing_image(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert delete_image("langgraph") is True
        mock_run.assert_called_once()
        args = mock_run.call_args.args[0]
        assert "rmi" in args
        assert "desmet-eval-langgraph:1.0" in args

    @patch("desmet.harness.container_runner.subprocess.run")
    def test_delete_missing_image(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="No such image")
        assert delete_image("langgraph") is False

    @patch("desmet.harness.container_runner.subprocess.run")
    def test_delete_docker_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        assert delete_image("langgraph") is False


class TestGetImageDetails:
    @patch("desmet.harness.container_runner.subprocess.run")
    def test_returns_details_for_existing_image(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[{"Size": 3500000000, "Created": "2026-03-28T12:00:00Z"}]',
        )
        details = get_image_details("langgraph")
        assert details is not None
        assert details["size_bytes"] == 3500000000
        assert details["created_at"] == "2026-03-28T12:00:00Z"
        assert details["tag"] == "desmet-eval-langgraph:1.0"
        assert details["exists"] is True

    @patch("desmet.harness.container_runner.subprocess.run")
    def test_returns_none_for_missing_image(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        details = get_image_details("langgraph")
        assert details is None

    @patch("desmet.harness.container_runner.subprocess.run")
    def test_returns_none_on_docker_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        details = get_image_details("langgraph")
        assert details is None
