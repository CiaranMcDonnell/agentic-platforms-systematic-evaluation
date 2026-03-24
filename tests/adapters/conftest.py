"""Shared fixtures for adapter tests."""


import pytest

from desmet.harness.context import StageContext
from desmet.harness.story import DifficultyLevel, UserStory


@pytest.fixture
def sample_story() -> UserStory:
    """A minimal UserStory for adapter tests."""
    return UserStory(
        id="US-TEST-001",
        title="Test Story",
        description="A test story for adapter tests",
        difficulty=DifficultyLevel.BASIC,
        category="code_generation",
        prompt="Implement a hello world function",
    )


@pytest.fixture
def sample_context(sample_story, tmp_path) -> StageContext:
    """A StageContext wired to a temporary workspace."""
    return StageContext(
        story=sample_story,
        workspace=tmp_path,
        time_budget_seconds=60,
        max_iterations=5,
    )
