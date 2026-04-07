"""Tests for CLI command registration."""

from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from desmet.cli import app

runner = CliRunner()


class TestWebuiCommand:
    def test_help_shows_options(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--host" in result.output
        assert "--port" in result.output
        assert "--reload" in result.output
        assert "clean-on-exit" in result.output  # new flag

    def test_default_invocation(self):
        """Verify default invocation passes correct defaults to uvicorn."""
        mock_run = MagicMock()
        mock_atexit = MagicMock()
        with patch("uvicorn.run", mock_run), \
             patch("atexit.register", mock_atexit):
            runner.invoke(app, [])
            mock_run.assert_called_once_with(
                "desmet.webui.api:app",
                host="127.0.0.1",
                port=8042,
                reload=False,
                log_level="info",
            )
            # clean_on_exit defaults to True → atexit handler registered
            assert mock_atexit.called

    def test_no_clean_on_exit_skips_atexit(self):
        """When --no-clean-on-exit is passed, no cleanup handler registers."""
        mock_run = MagicMock()
        mock_atexit = MagicMock()
        with patch("uvicorn.run", mock_run), \
             patch("atexit.register", mock_atexit):
            runner.invoke(app, ["--no-clean-on-exit"])
            mock_run.assert_called_once()
            assert not mock_atexit.called
