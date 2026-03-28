"""Tests for the container adapter entrypoint."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from desmet.harness.context import StageContext
from desmet.harness.story import UserStory, DifficultyLevel


def _make_context(tmp_path: Path) -> StageContext:
    story = UserStory(
        id="test_story", title="Test", description="Test",
        difficulty=DifficultyLevel.BASIC, category="test",
        prompt="Build something",
    )
    return StageContext(
        story=story, workspace=tmp_path, platform_id="crewai",
        max_iterations=5,
    )


class TestEntrypointModule:
    def test_module_is_importable(self):
        import desmet.harness.entrypoint
        assert hasattr(desmet.harness.entrypoint, "run_entrypoint")

    def test_run_entrypoint_signature(self):
        import inspect
        from desmet.harness.entrypoint import run_entrypoint
        sig = inspect.signature(run_entrypoint)
        params = list(sig.parameters.keys())
        assert "context_path" in params

    def test_writes_context_and_reads_back(self, tmp_path):
        """Test that a context file can be written and parsed."""
        ctx = _make_context(tmp_path)
        context_path = tmp_path / ".desmet-context.json"
        with open(context_path, "w") as f:
            json.dump(ctx.to_dict(), f)

        loaded = json.loads(context_path.read_text())
        assert loaded["platform_id"] == "crewai"
        assert loaded["story"]["id"] == "test_story"
