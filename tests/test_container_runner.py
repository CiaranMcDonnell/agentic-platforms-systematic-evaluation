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
    """All coded platforms currently use the shared Dockerfile.platform
    template.  If a platform-specific Dockerfile.<extra> file is added
    later (escape hatch), dockerfile_path prefers it over the template.
    """

    def test_falls_back_to_template_for_langgraph(self):
        path = dockerfile_path("langgraph")
        assert path.name == "Dockerfile.platform"
        assert path.exists()

    def test_falls_back_to_template_for_crewai(self):
        path = dockerfile_path("crewai")
        assert path.name == "Dockerfile.platform"
        assert path.exists()

    def test_falls_back_to_template_for_google_adk(self):
        path = dockerfile_path("google_adk")
        assert path.name == "Dockerfile.platform"
        assert path.exists()

    def test_prefers_platform_specific_dockerfile_when_present(self, tmp_path, monkeypatch):
        """If Dockerfile.<extra> exists, dockerfile_path returns it instead of the template."""
        import desmet.harness.container_runner as cr

        # Point the infra dir at a temp directory with a fake specific dockerfile
        fake_infra = tmp_path
        (fake_infra / "Dockerfile.platform").write_text("FROM base")
        (fake_infra / "Dockerfile.langgraph").write_text("FROM custom")

        monkeypatch.setattr(cr, "_INFRA_DIR", fake_infra)
        result = dockerfile_path("langgraph")
        assert result.name == "Dockerfile.langgraph"

    def test_returns_template_when_no_specific_dockerfile(self, tmp_path, monkeypatch):
        import desmet.harness.container_runner as cr

        fake_infra = tmp_path
        (fake_infra / "Dockerfile.platform").write_text("FROM base")
        monkeypatch.setattr(cr, "_INFRA_DIR", fake_infra)
        result = dockerfile_path("langgraph")
        assert result.name == "Dockerfile.platform"


class TestPlatformBuildArgs:
    def test_passes_platform_extra(self):
        from desmet.harness.container_runner import _platform_build_args

        args = _platform_build_args("langgraph")
        assert "--build-arg" in args
        assert "PLATFORM_EXTRA=langgraph" in args

    def test_uses_pip_extra_not_platform_id(self):
        """openai_agents_sdk has pip_extra=openai-agents (hyphenated)."""
        from desmet.harness.container_runner import _platform_build_args

        args = _platform_build_args("openai_agents_sdk")
        assert "PLATFORM_EXTRA=openai-agents" in args


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
