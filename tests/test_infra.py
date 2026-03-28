"""Tests for infrastructure management module."""

from unittest.mock import MagicMock, patch

from desmet.infra import (
    COMPOSE_FILE,
    PLATFORM_CONTAINERS,
    PLATFORM_PACKAGES,
    PROFILE_TARGETS,
    cleanup_all_docker,
    get_config_status,
    get_container_status,
    get_docker_platform_statuses,
    get_platform_statuses,
    is_package_importable,
)


class TestConstants:
    def test_profile_targets_has_all_visual_platforms(self):
        assert "flowise" in PROFILE_TARGETS
        assert "langflow" in PROFILE_TARGETS
        assert "dify" in PROFILE_TARGETS
        assert "n8n" in PROFILE_TARGETS
        assert "langfuse" in PROFILE_TARGETS

    def test_profile_targets_all_includes_everything(self):
        all_profiles = PROFILE_TARGETS["all"]
        for target in ("flowise", "langflow", "dify", "n8n", "langfuse"):
            assert target in all_profiles

    def test_platform_packages_covers_all_python_platforms(self):
        assert PLATFORM_PACKAGES["langgraph"] == "langgraph"
        assert PLATFORM_PACKAGES["crewai"] == "crewai"

    def test_platform_packages_none_for_docker_platforms(self):
        assert PLATFORM_PACKAGES["flowise"] is None
        assert PLATFORM_PACKAGES["dify"] is None
        assert PLATFORM_PACKAGES["n8n"] is None

    def test_platform_containers_none_for_python_platforms(self):
        assert PLATFORM_CONTAINERS["langgraph"] is None
        assert PLATFORM_CONTAINERS["crewai"] is None

    def test_platform_containers_set_for_docker_platforms(self):
        assert PLATFORM_CONTAINERS["flowise"] == "desmet-flowise"
        assert PLATFORM_CONTAINERS["n8n"] == "desmet-n8n"
        assert PLATFORM_CONTAINERS["dify"] == "desmet-dify-api"

    def test_compose_file_points_to_infrastructure(self):
        assert COMPOSE_FILE.name == "docker-compose.yaml"
        assert "infrastructure" in str(COMPOSE_FILE)


class TestIsPackageImportable:
    def test_importable_stdlib(self):
        assert is_package_importable("json") is True

    def test_not_importable(self):
        assert is_package_importable("nonexistent_package_xyz_123") is False


class TestGetContainerStatus:
    @patch("desmet.infra.subprocess.run")
    def test_running_container(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="running\n"
        )
        assert get_container_status("desmet-flowise") == "running"

    @patch("desmet.infra.subprocess.run")
    def test_not_running_container(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="exited\n"
        )
        assert get_container_status("desmet-flowise") == "exited"

    @patch("desmet.infra.subprocess.run")
    def test_container_not_found(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout=""
        )
        assert get_container_status("desmet-flowise") == "not started"

    @patch("desmet.infra.subprocess.run")
    def test_docker_not_available(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        assert get_container_status("desmet-flowise") == "docker not found"


class TestGetPlatformStatuses:
    @patch("desmet.harness.container_runner.has_image", return_value=False)
    @patch("desmet.infra.get_container_status")
    @patch("desmet.infra.is_package_importable")
    def test_sdk_platform_with_local_install(self, mock_import, mock_container, mock_has_image):
        mock_import.return_value = True
        mock_container.return_value = "not started"
        statuses = get_platform_statuses()
        lg = next(s for s in statuses if s.platform_id == "langgraph")
        assert lg.infra_type == "Python SDK"
        assert lg.status == "ready"

    @patch("desmet.harness.container_runner.has_image", return_value=False)
    @patch("desmet.infra.get_container_status")
    @patch("desmet.infra.is_package_importable")
    def test_sdk_platform_not_built(self, mock_import, mock_container, mock_has_image):
        mock_import.return_value = False
        mock_container.return_value = "not started"
        statuses = get_platform_statuses()
        lg = next(s for s in statuses if s.platform_id == "langgraph")
        assert lg.status == "not built"
        assert lg.infra_type == "Docker (isolated)"

    @patch("desmet.harness.container_runner.has_image", return_value=True)
    @patch("desmet.infra.get_container_status")
    @patch("desmet.infra.is_package_importable")
    def test_sdk_platform_with_docker_image(self, mock_import, mock_container, mock_has_image):
        mock_import.return_value = False
        mock_container.return_value = "not started"
        statuses = get_platform_statuses()
        lg = next(s for s in statuses if s.platform_id == "langgraph")
        assert lg.status == "ready"
        assert lg.infra_type == "Docker (isolated)"

    @patch("desmet.harness.container_runner.has_image", return_value=False)
    @patch("desmet.infra.get_container_status")
    @patch("desmet.infra.is_package_importable")
    def test_docker_platform_running(self, mock_import, mock_container, mock_has_image):
        mock_import.return_value = False
        mock_container.return_value = "running"
        statuses = get_platform_statuses()
        fw = next(s for s in statuses if s.platform_id == "flowise")
        assert fw.infra_type == "Docker"
        assert fw.status == "running"

    @patch("desmet.harness.container_runner.has_image", return_value=False)
    @patch("desmet.infra.get_container_status")
    @patch("desmet.infra.is_package_importable")
    def test_docker_platform_not_started(self, mock_import, mock_container, mock_has_image):
        mock_import.return_value = False
        mock_container.return_value = "not started"
        statuses = get_platform_statuses()
        fw = next(s for s in statuses if s.platform_id == "flowise")
        assert fw.status == "not started"


class TestGetDockerPlatformStatuses:
    @patch("desmet.harness.container_runner.has_image")
    @patch("desmet.infra.get_container_status")
    def test_includes_visual_platforms(self, mock_container, mock_has_image):
        mock_container.return_value = "running"
        mock_has_image.return_value = False
        result = get_docker_platform_statuses()
        assert result["flowise"] == "running"
        assert result["n8n"] == "running"

    @patch("desmet.harness.container_runner.has_image")
    @patch("desmet.infra.get_container_status")
    def test_includes_sdk_image_status(self, mock_container, mock_has_image):
        mock_container.return_value = "not started"
        mock_has_image.return_value = True
        result = get_docker_platform_statuses()
        assert result["langgraph"] == "ready"

    @patch("desmet.harness.container_runner.has_image")
    @patch("desmet.infra.get_container_status")
    def test_sdk_not_built(self, mock_container, mock_has_image):
        mock_container.return_value = "not started"
        mock_has_image.return_value = False
        result = get_docker_platform_statuses()
        assert result["langgraph"] == "not built"


class TestGetConfigStatus:
    @patch.dict("os.environ", {"DESMET_MODEL": "gpt-4o", "OPENAI_API_KEY": "sk-test"}, clear=False)
    def test_model_and_key_detected(self):
        status = get_config_status()
        assert status.model == "gpt-4o"
        assert "OPENAI_API_KEY" in status.api_keys_set

    @patch.dict("os.environ", {
        "DESMET_MODEL": "",
        "DEFAULT_MODEL": "",
        "OPENAI_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
        "GOOGLE_API_KEY": "",
        "OPENROUTER_API_KEY": "",
        "LANGFUSE_PUBLIC_KEY": "",
        "LANGFUSE_SECRET_KEY": "",
    }, clear=False)
    @patch("desmet.infra.is_package_importable", return_value=False)
    def test_defaults_when_no_env(self, _mock_import):
        status = get_config_status()
        assert status.model == "gpt-5.4-2026-03-05"
        assert status.api_keys_set == []
        assert status.langfuse_status == "not installed"


class TestCleanupAllDocker:
    @patch("desmet.infra.compose_down")
    @patch("desmet.infra.subprocess.run")
    def test_calls_compose_down_all(self, mock_run, mock_compose):
        mock_compose.return_value = MagicMock(returncode=0)
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        cleanup_all_docker()
        mock_compose.assert_called_once_with("all")

    @patch("desmet.infra.compose_down")
    @patch("desmet.infra.subprocess.run")
    def test_removes_eval_containers(self, mock_run, mock_compose):
        mock_compose.return_value = MagicMock(returncode=0)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="abc123\ndef456\n"),
            MagicMock(returncode=0),
        ]
        cleanup_all_docker()
        ps_call = mock_run.call_args_list[0]
        assert "--filter" in ps_call.args[0]
        assert "name=desmet-run-" in ps_call.args[0]

    @patch("desmet.infra.compose_down")
    @patch("desmet.infra.subprocess.run")
    def test_survives_docker_not_found(self, mock_run, mock_compose):
        mock_compose.side_effect = FileNotFoundError()
        mock_run.side_effect = FileNotFoundError()
        cleanup_all_docker()

    @patch("desmet.infra.compose_down")
    @patch("desmet.infra.subprocess.run")
    def test_survives_compose_failure(self, mock_run, mock_compose):
        mock_compose.return_value = MagicMock(returncode=1, stderr="error")
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        cleanup_all_docker()
