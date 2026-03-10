"""Tests for CLI command registration."""

from typer.testing import CliRunner

from desmet.cli import app

runner = CliRunner()


class TestUpCommand:
    def test_no_args_shows_targets(self):
        result = runner.invoke(app, ["up"])
        assert result.exit_code == 0
        assert "flowise" in result.output
        assert "langfuse" in result.output

    def test_invalid_target(self):
        result = runner.invoke(app, ["up", "nonexistent"])
        assert result.exit_code == 1
        assert "Unknown target" in result.output


class TestDownCommand:
    def test_invalid_target(self):
        result = runner.invoke(app, ["down", "nonexistent"])
        assert result.exit_code == 1
        assert "Unknown target" in result.output


class TestStatusCommand:
    def test_status_runs(self):
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
