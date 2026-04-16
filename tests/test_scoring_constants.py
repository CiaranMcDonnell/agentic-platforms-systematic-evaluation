"""Tests that scoring constants in dashboard.data are the same objects as
those defined in harness.story (i.e. imported, not duplicated)."""

from desmet.harness.story import SCORING_DIMENSIONS as STORY_DIMS
from desmet.harness.story import SCORING_RUBRIC as STORY_RUBRIC
from desmet.dashboard.data import SCORING_DIMENSIONS as DASHBOARD_DIMS
from desmet.dashboard.data import SCORING_RUBRIC as DASHBOARD_RUBRIC


def test_scoring_dimensions_same_object():
    """SCORING_DIMENSIONS in dashboard.data must be the exact same object
    as in harness.story — not a separately defined duplicate."""
    assert DASHBOARD_DIMS is STORY_DIMS


def test_scoring_rubric_same_object():
    """SCORING_RUBRIC in dashboard.data must be the exact same object
    as in harness.story — not a separately defined duplicate."""
    assert DASHBOARD_RUBRIC is STORY_RUBRIC
