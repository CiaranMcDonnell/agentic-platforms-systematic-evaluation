"""Tests for post-execution workspace verification."""

import subprocess
from pathlib import Path
from unittest.mock import patch

from desmet.harness.verification import (
    _criteria_from_junit,
    _parse_junit,
    archive_workspace,
    run_workspace_tests,
)

_JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="5">
  <testcase name="test_AC_001_1_signature"/>
  <testcase name="test_AC_001_2_valid[a@b.com]"/>
  <testcase name="test_AC_001_2_valid[x+y@b.co.uk]"><failure message="assert False"/></testcase>
  <testcase name="test_AC_001_3_invalid[user@]"><error message="boom"/></testcase>
  <testcase name="test_unrelated"><skipped message="skip"/></testcase>
</testsuite></testsuites>
"""


def test_parse_junit_counts_errors_as_failures(tmp_path: Path):
    f = tmp_path / "r.xml"
    f.write_text(_JUNIT)
    assert _parse_junit(f) == (5, 2, 2)


def test_criteria_require_every_test_of_a_criterion_to_pass(tmp_path: Path):
    f = tmp_path / "r.xml"
    f.write_text(_JUNIT)
    assert _criteria_from_junit(f) == {
        "AC-001-1": True,
        "AC-001-2": False,
        "AC-001-3": False,
    }


def test_archive_skips_environments_and_caches(tmp_path: Path):
    ws = tmp_path / "ws"
    (ws / "app").mkdir(parents=True)
    (ws / "app" / "main.py").write_text("x = 1")
    (ws / ".venv" / "lib").mkdir(parents=True)
    (ws / "app" / "__pycache__").mkdir()

    dest = archive_workspace(ws, tmp_path / "out" / "exec-1")

    assert (dest / "app" / "main.py").exists()
    assert not (dest / ".venv").exists()
    assert not (dest / "app" / "__pycache__").exists()


def test_missing_report_keeps_exit_code(tmp_path: Path):
    proc = subprocess.CompletedProcess(args=[], returncode=2, stdout="", stderr="sync failed")
    with patch("desmet.harness.verification.subprocess.run", return_value=proc):
        result = run_workspace_tests(tmp_path, "img")
    assert result.pytest_exit_code == 2
    assert result.tests_run == 0


def test_timeout_leaves_exit_code_none(tmp_path: Path):
    with patch(
        "desmet.harness.verification.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=1),
    ):
        result = run_workspace_tests(tmp_path, "img")
    assert result.pytest_exit_code is None
