"""Unit tests for RetryPolicy."""

from __future__ import annotations

from pathlib import Path

from desmet.adapters._shared.retry import RetryPolicy


def test_total_attempts_default():
    policy = RetryPolicy()
    assert policy.total_attempts() == 4  # 3 retries + 1 initial


def test_total_attempts_custom():
    policy = RetryPolicy(max_retries=5)
    assert policy.total_attempts() == 6


def test_validate_passing_workspace(tmp_path):
    """A workspace with a valid requirements doc passes validation."""
    docs = tmp_path / "docs" / "design"
    docs.mkdir(parents=True)
    (docs / "requirements.md").write_text(
        "# Requirements\n\nFunctional requirements:\n- Login\n\n"
        "Non-functional requirements:\n- Performance\n\n"
        "Acceptance criteria:\n- Tests pass\n"
    )
    policy = RetryPolicy(
        max_retries=3,
        stage_name="requirements",
        workspace=tmp_path,
    )
    passed, feedback = policy.validate()
    assert passed is True
    assert "PASSED" in feedback


def test_validate_failing_workspace(tmp_path):
    """An empty workspace fails validation."""
    policy = RetryPolicy(
        max_retries=3,
        stage_name="requirements",
        workspace=tmp_path,
    )
    passed, feedback = policy.validate()
    assert passed is False
    assert "FAILED" in feedback


def test_default_max_retries():
    policy = RetryPolicy()
    assert policy.max_retries == 3
