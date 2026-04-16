"""Tests for Stage 1: Story loading and StageContext preparation."""

import pytest

from desmet.harness.context import StageContext
from desmet.harness.story import DifficultyLevel, UserStory
from desmet.harness.story_loader import prepare_stage_context


@pytest.fixture
def sample_story():
    return UserStory(
        id="US-001",
        title="Add Email Validation",
        description="Add a validate_email function",
        difficulty=DifficultyLevel.BASIC,
        category="code_generation",
        prompt="Implement a validate_email function that checks format",
        target_files=["utils/validation.py"],
        time_budget_seconds=300,
        max_iterations=25,
    )


class TestPrepareStageContext:
    def test_creates_stage_context(self, sample_story, tmp_path):
        ctx = prepare_stage_context(sample_story, workspace=tmp_path)
        assert isinstance(ctx, StageContext)
        assert ctx.story is sample_story
        assert ctx.workspace == tmp_path

    def test_inherits_story_constraints(self, sample_story, tmp_path):
        ctx = prepare_stage_context(sample_story, workspace=tmp_path)
        assert ctx.time_budget_seconds == 300
        assert ctx.max_iterations == 25

    def test_overrides_constraints(self, sample_story, tmp_path):
        ctx = prepare_stage_context(
            sample_story,
            workspace=tmp_path,
            time_budget_seconds=600,
            timeout_multiplier=1.5,
        )
        assert ctx.time_budget_seconds == 900  # 600 * 1.5

    def test_artifacts_start_empty(self, sample_story, tmp_path):
        ctx = prepare_stage_context(sample_story, workspace=tmp_path)
        assert ctx.artifacts == {}

    def test_custom_model(self, sample_story, tmp_path):
        ctx = prepare_stage_context(sample_story, workspace=tmp_path, model="claude-sonnet-4-6")
        assert ctx.model == "claude-sonnet-4-6"


def test_prepare_stage_context_accepts_platform_id(sample_story, tmp_path):
    ctx = prepare_stage_context(sample_story, workspace=tmp_path, platform_id="crewai")
    assert ctx.platform_id == "crewai"


def test_prepare_stage_context_platform_id_defaults_to_empty(sample_story, tmp_path):
    ctx = prepare_stage_context(sample_story, workspace=tmp_path)
    assert ctx.platform_id == ""
