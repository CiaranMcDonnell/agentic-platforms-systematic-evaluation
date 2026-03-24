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
    assert 9000 <= port <= 9999


def test_deploy_port_differs_across_platforms():
    p1 = _deploy_port("crewai", "US-001")
    p2 = _deploy_port("langgraph", "US-001")
    assert p1 != p2


def test_deploy_remote_in_available_tools():
    assert "deploy_remote" in AVAILABLE_TOOLS


def test_deploy_remote_push_calls_subprocess(tmp_path):
    env = {
        "DEPLOY_HOST": "1.2.3.4",
        "DEPLOY_USER": "deploy",
        "DEPLOY_KEY_PATH": "/tmp/fake_key",
        "DEPLOY_BASE_PATH": "/opt/desmet",
    }
    with patch.dict(os.environ, env), \
         patch("desmet.adapters._tools.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="sent ok", stderr="", returncode=0)
        result = _deploy_remote(
            workspace=tmp_path,
            platform_id="crewai",
            story_id="US-001",
            action="push",
        )
        assert mock_run.called
        assert "sent ok" in result


def test_deploy_remote_restart_calls_subprocess(tmp_path):
    env = {
        "DEPLOY_HOST": "1.2.3.4",
        "DEPLOY_USER": "deploy",
        "DEPLOY_KEY_PATH": "/tmp/fake_key",
        "DEPLOY_BASE_PATH": "/opt/desmet",
    }
    with patch.dict(os.environ, env), \
         patch("desmet.adapters._tools.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="started", stderr="", returncode=0)
        result = _deploy_remote(
            workspace=tmp_path,
            platform_id="crewai",
            story_id="US-001",
            action="restart",
        )
        cmd = mock_run.call_args[0][0]
        assert "docker compose up -d --build" in cmd
        assert "started" in result


def test_deploy_remote_health_check_uses_port(tmp_path):
    env = {
        "DEPLOY_HOST": "1.2.3.4",
        "DEPLOY_USER": "deploy",
        "DEPLOY_KEY_PATH": "/tmp/fake_key",
    }
    with patch.dict(os.environ, env), \
         patch("desmet.adapters._tools.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout='{"status":"ok"}', stderr="", returncode=0)
        result = _deploy_remote(
            workspace=tmp_path,
            platform_id="crewai",
            story_id="US-001",
            action="health_check",
        )
        cmd = mock_run.call_args[0][0]
        port = _deploy_port("crewai", "US-001")
        assert str(port) in cmd
        assert "curl" in cmd


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
    env = {
        "DEPLOY_HOST": "1.2.3.4",
        "DEPLOY_USER": "deploy",
        "DEPLOY_KEY_PATH": "/tmp/fake_key",
    }
    with patch.dict(os.environ, env):
        result = _deploy_remote(
            workspace=tmp_path,
            platform_id="crewai",
            story_id="US-001",
            action="destroy",
        )
    assert "Error" in result
    assert "unknown action" in result
