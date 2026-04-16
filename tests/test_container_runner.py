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


class TestDeleteAllEvalImages:
    @patch("desmet.harness.container_runner.subprocess.run")
    def test_removes_all_coded_platforms_plus_base(self, mock_run):
        from desmet.harness.container_runner import (
            delete_all_eval_images,
            PLATFORM_EXTRA_MAP,
        )

        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
        results = delete_all_eval_images(include_base=True)

        # One entry per coded platform + the base image
        assert len(results) == len(PLATFORM_EXTRA_MAP) + 1
        assert "desmet-eval-base:1.0" in results
        assert all(ok is True for ok in results.values())

        # Each call should be 'docker rmi <tag>'
        for call in mock_run.call_args_list:
            cmd = call.args[0]
            assert cmd[0] == "docker"
            assert cmd[1] == "rmi"

    @patch("desmet.harness.container_runner.subprocess.run")
    def test_skips_base_when_include_base_false(self, mock_run):
        from desmet.harness.container_runner import (
            delete_all_eval_images,
            PLATFORM_EXTRA_MAP,
        )

        mock_run.return_value = MagicMock(returncode=0)
        results = delete_all_eval_images(include_base=False)

        assert len(results) == len(PLATFORM_EXTRA_MAP)
        assert "desmet-eval-base:1.0" not in results

    @patch("desmet.harness.container_runner.subprocess.run")
    def test_progress_callback_called_per_image(self, mock_run):
        from desmet.harness.container_runner import (
            delete_all_eval_images,
            PLATFORM_EXTRA_MAP,
        )

        mock_run.return_value = MagicMock(returncode=0)
        messages: list[str] = []
        delete_all_eval_images(
            include_base=True, progress_callback=messages.append,
        )
        # One message per platform + one for the base
        assert len(messages) == len(PLATFORM_EXTRA_MAP) + 1
        assert any("base" in m for m in messages)

    @patch("desmet.harness.container_runner.subprocess.run")
    def test_handles_missing_images_gracefully(self, mock_run):
        from desmet.harness.container_runner import delete_all_eval_images

        # Simulate 'No such image' errors
        mock_run.return_value = MagicMock(returncode=1, stderr="No such image")
        results = delete_all_eval_images(include_base=True)

        # Function returns without raising; all results are False
        assert all(ok is False for ok in results.values())


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


class TestEnsureContainerDeployWiring:
    """The deploy stage runs INSIDE the per-platform container, but the
    DEPLOY_* env vars and the SSH key file live on the HOST.  These
    tests pin the bridge between them: env passthrough + key bind-mount
    + DEPLOY_KEY_PATH rewrite to the in-container path.

    Regression target: a benchmark with deploy stage that ran fine on
    the in-process adapter path returned an instant
    "Error: DEPLOY_HOST..." once the new container architecture
    landed, because none of the DEPLOY_* env vars were forwarded.
    """

    @patch("desmet.harness.container_runner.subprocess.run")
    def test_deploy_env_vars_passed_through(self, mock_run, tmp_path, monkeypatch):
        """When DEPLOY_HOST/USER/PORT/REPO/BASE_PATH/MODE are set on the
        host, _ensure_container must add ``-e VAR=val`` flags for each.
        """
        import desmet.harness.container_runner as cr

        # Stub docker probes: container not running, no stale, run succeeds
        def fake_run(cmd, *args, **kwargs):
            joined = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "inspect" in joined and "{{.State.Running}}" in joined:
                return MagicMock(returncode=1, stdout="")  # not running
            if "rm" in joined and "-f" in joined:
                return MagicMock(returncode=0)  # stale removal
            if "network" in joined and "inspect" in joined:
                return MagicMock(returncode=1)  # no desmet-network
            return MagicMock(returncode=0, stdout="container-id\n", stderr="")

        mock_run.side_effect = fake_run

        for var in (
            "DEPLOY_HOST", "DEPLOY_PORT", "DEPLOY_USER",
            "DEPLOY_REPO", "DEPLOY_BASE_PATH", "DESMET_DEPLOY_MODE",
        ):
            monkeypatch.setenv(var, f"value-{var}")
        # No key file → mount path is skipped
        monkeypatch.delenv("DEPLOY_KEY_PATH", raising=False)

        cr._ensure_container("langgraph", "US-001", tmp_path)

        # Find the docker run invocation
        run_call = next(
            c for c in mock_run.call_args_list
            if isinstance(c.args[0], list) and "run" in c.args[0] and "-d" in c.args[0]
        )
        argv = run_call.args[0]
        joined_argv = " ".join(argv)

        for var in (
            "DEPLOY_HOST", "DEPLOY_PORT", "DEPLOY_USER",
            "DEPLOY_REPO", "DEPLOY_BASE_PATH", "DESMET_DEPLOY_MODE",
        ):
            assert f"{var}=value-{var}" in joined_argv, (
                f"missing {var} in docker run argv: {joined_argv}"
            )

    @patch("desmet.harness.container_runner.subprocess.run")
    def test_deploy_key_file_bind_mounted_when_present(
        self, mock_run, tmp_path, monkeypatch,
    ):
        """When DEPLOY_KEY_PATH points at a real file, _ensure_container
        bind-mounts it read-only at /run/secrets/deploy_key and rewrites
        DEPLOY_KEY_PATH inside the container to that fixed path.
        """
        import desmet.harness.container_runner as cr

        def fake_run(cmd, *args, **kwargs):
            joined = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "inspect" in joined and "{{.State.Running}}" in joined:
                return MagicMock(returncode=1, stdout="")
            if "rm" in joined and "-f" in joined:
                return MagicMock(returncode=0)
            if "network" in joined and "inspect" in joined:
                return MagicMock(returncode=1)
            return MagicMock(returncode=0, stdout="container-id\n", stderr="")

        mock_run.side_effect = fake_run

        # Real key file on disk so the os.path.isfile check passes
        key_file = tmp_path / "fake_deploy_key"
        key_file.write_text("not-a-real-key")
        monkeypatch.setenv("DEPLOY_KEY_PATH", str(key_file))
        monkeypatch.setenv("DESMET_DEPLOY_MODE", "remote")

        cr._ensure_container("langgraph", "US-001", tmp_path)

        run_call = next(
            c for c in mock_run.call_args_list
            if isinstance(c.args[0], list) and "run" in c.args[0] and "-d" in c.args[0]
        )
        argv = run_call.args[0]
        joined = " ".join(argv)

        # Bind-mount present (read-only) at the fixed in-container path
        assert "/run/secrets/deploy_key:ro" in joined, (
            f"key bind-mount missing from argv: {joined}"
        )
        # Inside-container env var rewritten to the mount target
        assert "DEPLOY_KEY_PATH=/run/secrets/deploy_key" in joined
        # The host filesystem path must NOT be exposed as the env var value
        assert f"DEPLOY_KEY_PATH={key_file}" not in joined

    @patch("desmet.harness.container_runner.subprocess.run")
    def test_deploy_key_skipped_when_local_mode(
        self, mock_run, tmp_path, monkeypatch,
    ):
        """Local deploy mode never needs the SSH key, so no mount or
        env var rewrite should happen even if DEPLOY_KEY_PATH is set."""
        import desmet.harness.container_runner as cr

        def fake_run(cmd, *args, **kwargs):
            joined = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "inspect" in joined and "{{.State.Running}}" in joined:
                return MagicMock(returncode=1, stdout="")
            if "rm" in joined and "-f" in joined:
                return MagicMock(returncode=0)
            if "network" in joined and "inspect" in joined:
                return MagicMock(returncode=1)
            return MagicMock(returncode=0, stdout="container-id\n", stderr="")

        mock_run.side_effect = fake_run

        key_file = tmp_path / "fake_deploy_key"
        key_file.write_text("not-a-real-key")
        monkeypatch.setenv("DEPLOY_KEY_PATH", str(key_file))
        monkeypatch.setenv("DESMET_DEPLOY_MODE", "local")

        cr._ensure_container("langgraph", "US-001", tmp_path)

        run_call = next(
            c for c in mock_run.call_args_list
            if isinstance(c.args[0], list) and "run" in c.args[0] and "-d" in c.args[0]
        )
        joined = " ".join(run_call.args[0])
        assert "/run/secrets/deploy_key" not in joined, (
            f"local mode should not bind-mount the deploy key: {joined}"
        )

    @patch("desmet.harness.container_runner.subprocess.run")
    def test_deploy_key_skipped_when_file_missing(
        self, mock_run, tmp_path, monkeypatch,
    ):
        """If DEPLOY_KEY_PATH points at a path that doesn't exist on the
        host, the mount is skipped (and a warning is logged) rather than
        passing a broken bind-mount to docker.
        """
        import desmet.harness.container_runner as cr

        def fake_run(cmd, *args, **kwargs):
            joined = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "inspect" in joined and "{{.State.Running}}" in joined:
                return MagicMock(returncode=1, stdout="")
            if "rm" in joined and "-f" in joined:
                return MagicMock(returncode=0)
            if "network" in joined and "inspect" in joined:
                return MagicMock(returncode=1)
            return MagicMock(returncode=0, stdout="container-id\n", stderr="")

        mock_run.side_effect = fake_run

        monkeypatch.setenv("DEPLOY_KEY_PATH", str(tmp_path / "does-not-exist"))
        monkeypatch.setenv("DESMET_DEPLOY_MODE", "remote")

        cr._ensure_container("langgraph", "US-001", tmp_path)

        run_call = next(
            c for c in mock_run.call_args_list
            if isinstance(c.args[0], list) and "run" in c.args[0] and "-d" in c.args[0]
        )
        joined = " ".join(run_call.args[0])
        assert "/run/secrets/deploy_key" not in joined
