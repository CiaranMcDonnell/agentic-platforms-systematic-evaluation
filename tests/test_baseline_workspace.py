"""Regression tests for the data/baseline workspace.

The baseline is copied into a fresh per-story workspace at the start of
every evaluation run.  Any agent invoking ``uv run pytest`` (or
``uv sync`` indirectly via ``uv run``) immediately hits ``uv``'s
package-build path.  If the baseline declares itself as a buildable
package but provides no directory matching its project name, hatchling
fails the build and ``uv run pytest`` errors with
``Failed to spawn: pytest``.

This was the root cause of the testing-stage "pytest discovery dance"
in run 7da6614d, where the model burned ~9 tool calls trying different
pytest invocations because the first ``uv run pytest`` failed for
non-obvious reasons.
"""
from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

_BASELINE = Path(__file__).resolve().parents[1] / "data" / "baseline"


class TestBaselinePyproject:
    def test_pyproject_exists(self):
        assert (_BASELINE / "pyproject.toml").exists(), (
            "data/baseline/pyproject.toml is required — adapters copy "
            "this into every story workspace."
        )

    def test_declares_non_package(self):
        """`[tool.uv] package = false` keeps `uv sync` from trying to
        build a hatchling wheel.

        Without this, ``uv run pytest`` on a fresh workspace fails
        because the project name (``sample-app``) doesn't match any
        directory and hatchling refuses to guess what to ship in the
        wheel.
        """
        data = tomllib.loads((_BASELINE / "pyproject.toml").read_text())
        uv_table = data.get("tool", {}).get("uv", {})
        assert uv_table.get("package") is False, (
            "data/baseline/pyproject.toml must set `[tool.uv] package = false` "
            "so `uv run pytest` works on a fresh workspace copy without "
            "triggering a hatchling wheel build that fails."
        )

    def test_pytest_dependency_present(self):
        """pytest must be in the resolved dep set so `uv run pytest`
        finds the executable after `uv sync`.
        """
        data = tomllib.loads((_BASELINE / "pyproject.toml").read_text())
        deps = data.get("project", {}).get("dependencies", [])
        assert any(d.startswith("pytest") and "asyncio" not in d for d in deps), (
            "pytest must remain in the baseline dependencies so the "
            "testing stage can actually run tests"
        )
