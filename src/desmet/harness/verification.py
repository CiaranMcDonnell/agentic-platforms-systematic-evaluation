"""Post-execution verification: archive the workspace and run its tests.

Stage validators only check that artefacts *exist* (a compilable ``.py``,
a ``test_*.py`` with ``def test_``), and the baseline workspace already
satisfies several of them.  This module records whether the produced code
actually works by running the workspace's pytest suite after the pipeline
finishes.

The suite is LLM-generated code, so it runs inside the harness base image
(``docker run --rm``), never on the host.  It runs against the archived
copy so the dependency install doesn't leave a ``.venv`` behind in the
live workspace.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

_ARCHIVE_IGNORE = shutil.ignore_patterns(
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"
)
_JUNIT_FILE = ".desmet_pytest.xml"
_ACCEPTANCE_DIR = ".desmet_acceptance"
_ACCEPTANCE_JUNIT = ".desmet_acceptance.xml"
_UV_CACHE_VOLUME = "desmet-verify-uv-cache"
_TIMEOUT_SECONDS = 600
# Hidden acceptance tests live outside the baseline the agent sees:
# data/acceptance/<story_id>/test_*.py
ACCEPTANCE_ROOT = Path(__file__).resolve().parents[3] / "data" / "acceptance"
# test_AC_001_2_valid_emails[...]  ->  AC-001-2
_AC_NAME_RE = re.compile(r"^test_AC_(\d+)_(\d+)")


@dataclass
class VerificationResult:
    artifact_path: str | None = None
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    # pytest exit code: 0 all passed, 1 failures, 5 no tests collected;
    # None when the suite couldn't be run at all (docker error, timeout).
    pytest_exit_code: int | None = None
    # Hidden acceptance tests: criterion id -> all of its tests passed.
    # Empty when the story has no acceptance tests.
    criteria_results: dict[str, bool] = field(default_factory=dict)
    acceptance_exit_code: int | None = None


def archive_workspace(workspace: Path, dest: Path) -> Path:
    """Copy *workspace* to *dest* (replacing it), skipping environments and caches."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(workspace, dest, ignore=_ARCHIVE_IGNORE)
    return dest


def _testcases(path: Path) -> list[tuple[str, bool | None]]:
    """``(name, passed)`` per testcase in a JUnit report; ``None`` = skipped."""
    cases = []
    for tc in ET.parse(path).getroot().iter("testcase"):
        if tc.find("skipped") is not None:
            cases.append((tc.get("name", ""), None))
        else:
            failed = tc.find("failure") is not None or tc.find("error") is not None
            cases.append((tc.get("name", ""), not failed))
    return cases


def _parse_junit(path: Path) -> tuple[int, int, int]:
    """Return ``(run, passed, failed)`` from a pytest JUnit XML report."""
    cases = _testcases(path)
    passed = sum(1 for _, ok in cases if ok is True)
    failed = sum(1 for _, ok in cases if ok is False)
    return len(cases), passed, failed


def _criteria_from_junit(path: Path) -> dict[str, bool]:
    """Group ``test_AC_<story>_<n>_*`` cases by criterion; all must pass."""
    criteria: dict[str, bool] = {}
    for name, ok in _testcases(path):
        m = _AC_NAME_RE.match(name)
        if m is None or ok is None:
            continue
        ac = f"AC-{m.group(1)}-{m.group(2)}"
        criteria[ac] = criteria.get(ac, True) and ok
    return criteria


def _run_pytest(workspace: Path, image: str, pytest_args: str) -> int | None:
    """Run pytest in *workspace* inside *image*; return its exit code."""
    ws_abs = str(workspace.resolve()).replace("\\", "/")
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{ws_abs}:/workspace",
        "-v", f"{_UV_CACHE_VOLUME}:/home/agent/.cache/uv",
        "-w", "/workspace",
        image,
        "bash", "-c",
        # `python -m pytest` puts the project root on sys.path so the
        # acceptance tests can import app/utils like the agent's tests do.
        f"uv run --no-progress python -m pytest -q -p no:cacheprovider {pytest_args}",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            env={**os.environ, "MSYS_NO_PATHCONV": "1"},
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning("pytest_not_run", error=str(e))
        return None
    if proc.returncode not in (0, 1):
        logger.warning(
            "pytest_abnormal_exit",
            exit_code=proc.returncode,
            output=(proc.stdout + proc.stderr)[-500:],
        )
    return proc.returncode


def run_workspace_tests(workspace: Path, image: str) -> VerificationResult:
    """Run the workspace's own pytest suite inside *image* and summarise it."""
    junit = workspace / _JUNIT_FILE
    junit.unlink(missing_ok=True)
    result = VerificationResult()
    result.pytest_exit_code = _run_pytest(workspace, image, f"--junitxml=/workspace/{_JUNIT_FILE}")
    if junit.exists():
        try:
            result.tests_run, result.tests_passed, result.tests_failed = _parse_junit(junit)
        except ET.ParseError as e:
            logger.warning("workspace_tests_unparseable", error=str(e))
    return result


def run_acceptance_tests(
    workspace: Path, acceptance_dir: Path, image: str
) -> tuple[dict[str, bool], int | None]:
    """Copy *acceptance_dir* into *workspace* and run it there.

    Returns ``(criteria_results, exit_code)``.  A criterion whose tests
    never ran (e.g. an import error aborted collection) is absent from
    the dict, so callers should compare against the story's criteria.
    """
    target = workspace / _ACCEPTANCE_DIR
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(acceptance_dir, target)
    junit = workspace / _ACCEPTANCE_JUNIT
    junit.unlink(missing_ok=True)
    exit_code = _run_pytest(
        workspace, image, f"{_ACCEPTANCE_DIR} --junitxml=/workspace/{_ACCEPTANCE_JUNIT}"
    )
    criteria: dict[str, bool] = {}
    if junit.exists():
        try:
            criteria = _criteria_from_junit(junit)
        except ET.ParseError as e:
            logger.warning("acceptance_tests_unparseable", error=str(e))
    return criteria, exit_code


def verify_execution(
    workspace: Path,
    archive_dir: Path,
    image: str,
    story_id: str | None = None,
    acceptance_criteria: list[str] | None = None,
) -> VerificationResult:
    """Archive *workspace*, then run its own tests and the hidden acceptance tests.

    Both suites run against the archive.  The workspace suite runs first so
    the acceptance tests can't influence it.  Every id in
    *acceptance_criteria* gets an entry: criteria whose tests never ran
    count as failed.
    """
    archived = archive_workspace(workspace, archive_dir)
    result = run_workspace_tests(archived, image)
    result.artifact_path = str(archived)

    acceptance_dir = ACCEPTANCE_ROOT / story_id if story_id else None
    if acceptance_dir is not None and acceptance_dir.is_dir():
        criteria, result.acceptance_exit_code = run_acceptance_tests(
            archived, acceptance_dir, image
        )
        for ac in acceptance_criteria or []:
            criteria.setdefault(ac, False)
        result.criteria_results = criteria

    logger.info(
        "workspace_verified",
        artifact_path=result.artifact_path,
        tests_run=result.tests_run,
        tests_passed=result.tests_passed,
        tests_failed=result.tests_failed,
        pytest_exit_code=result.pytest_exit_code,
        criteria_results=result.criteria_results,
    )
    return result
