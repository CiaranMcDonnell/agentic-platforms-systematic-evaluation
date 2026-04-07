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

    def test_default_invocation(self):
        """Verify default invocation passes correct defaults to uvicorn."""
        mock_run = MagicMock()
        with patch("uvicorn.run", mock_run):
            runner.invoke(app, [])
            mock_run.assert_called_once_with(
                "desmet.webui.api:app",
                host="127.0.0.1",
                port=8042,
                reload=False,
                log_level="info",
            )
