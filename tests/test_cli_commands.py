"""Tests for CLI command registration."""

from unittest.mock import patch

from typer.testing import CliRunner

from desmet.cli import app

runner = CliRunner()


class TestWebuiCommand:
    def test_help_shows_webui(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "webui" in result.output

    @patch("desmet.cli.uvicorn")
    def test_webui_default_options(self, mock_uvicorn):
        """Verify webui passes correct defaults to uvicorn."""
        # We patch uvicorn at the module level where it's lazily imported
        with patch("uvicorn.run") as mock_run:
            runner.invoke(app, ["webui"])
            mock_run.assert_called_once_with(
                "desmet.webui.api:app",
                host="127.0.0.1",
                port=8042,
                reload=False,
                log_level="info",
            )
