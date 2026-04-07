"""Tests for the deploy_remote tool."""
import os
from unittest.mock import patch, MagicMock

from desmet.adapters._tools import _deploy_port, _deploy_remote, AVAILABLE_TOOLS


def test_deploy_port_is_deterministic():
    port1 = _deploy_port("crewai", "US-001")
    port2 = _deploy_port("crewai", "US-001")
    assert port1 == port2


def test_deploy_port_in_range():
    port = _deploy_port("crewai", "US-001")
    assert 8000 <= port <= 8999


def test_deploy_port_differs_across_platforms():
    p1 = _deploy_port("crewai", "US-001")
    p2 = _deploy_port("langgraph", "US-001")
    assert p1 != p2


def test_deploy_remote_in_available_tools():
    assert "deploy_remote" in AVAILABLE_TOOLS


# _deploy_remote requires DEPLOY_HOST, DEPLOY_USER, DEPLOY_KEY_PATH, DEPLOY_REPO

_DEPLOY_ENV = {
    "DEPLOY_HOST": "1.2.3.4",
    "DEPLOY_USER": "deploy",
    "DEPLOY_KEY_PATH": "/tmp/fake_key",
    "DEPLOY_BASE_PATH": "/opt/desmet",
    "DEPLOY_REPO": "https://github.com/test/repo.git",
}


def test_deploy_remote_push_calls_git(tmp_path):
    """Push action uses git add/commit/push."""
    with patch.dict(os.environ, _DEPLOY_ENV), \
         patch("desmet.adapters._tools.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="pushed", stderr="", returncode=0)
        result = _deploy_remote(
            workspace=tmp_path,
            platform_id="crewai",
            story_id="US-001",
            action="push",
        )
        assert mock_run.called
        # git add, possibly git diff, possibly git commit, then git push
        calls = [str(c) for c in mock_run.call_args_list]
        assert any("git" in c for c in calls)


def test_deploy_remote_restart_calls_ssh(tmp_path):
    """Restart action SSHes to server and runs docker compose."""
    with patch.dict(os.environ, _DEPLOY_ENV), \
         patch("desmet.adapters._tools.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="started", stderr="", returncode=0)
        result = _deploy_remote(
            workspace=tmp_path,
            platform_id="crewai",
            story_id="US-001",
            action="restart",
        )
        assert mock_run.called
        calls_str = " ".join(str(c) for c in mock_run.call_args_list)
        assert "ssh" in calls_str or "docker" in calls_str


def test_deploy_remote_health_check_uses_port(tmp_path):
    """Health check curls the deploy port via SSH."""
    with patch.dict(os.environ, _DEPLOY_ENV), \
         patch("desmet.adapters._tools.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout='{"status":"ok"}', stderr="", returncode=0)
        result = _deploy_remote(
            workspace=tmp_path,
            platform_id="crewai",
            story_id="US-001",
            action="health_check",
        )
        assert mock_run.called
        port = _deploy_port("crewai", "US-001")
        calls_str = " ".join(str(c) for c in mock_run.call_args_list)
        assert str(port) in calls_str


def test_deploy_remote_missing_env_returns_error(tmp_path):
    with patch.dict(os.environ, {}, clear=True):
        result = _deploy_remote(
            workspace=tmp_path,
            platform_id="crewai",
            story_id="US-001",
            action="push",
        )
        assert "Error" in result


def test_deploy_remote_invalid_action(tmp_path):
    with patch.dict(os.environ, _DEPLOY_ENV):
        result = _deploy_remote(
            workspace=tmp_path,
            platform_id="crewai",
            story_id="US-001",
            action="destroy",
        )
    assert "Error" in result
