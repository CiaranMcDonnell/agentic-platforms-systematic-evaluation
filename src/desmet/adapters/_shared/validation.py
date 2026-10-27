"""Shared workspace validation for platform adapters.

Deterministic checks (no LLM call) that verify whether an SDLC stage
produced the expected artefacts in the workspace directory.
"""

from __future__ import annotations

import json
import os
import py_compile
from pathlib import Path

_REQUIREMENTS_KEYWORDS = {"functional", "non-functional", "acceptance", "constraint"}


_SKIP_DIRS = {".venv", "venv", "node_modules", ".git", "__pycache__"}

# Written into each workspace by the runner: JSON list of the files the
# baseline shipped with, so validators can ignore artefacts the agent
# didn't produce (e.g. the baseline's own unrendered design diagrams).
BASELINE_FILES_NAME = ".desmet-baseline-files.json"


def _baseline_files(ws: Path) -> set[str]:
    try:
        return set(json.loads((ws / BASELINE_FILES_NAME).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def _walk_files(root: Path, pattern: str):
    """Yield files matching *pattern* under *root*, skipping venvs and similar.

    Uses ``os.walk`` instead of ``Path.glob`` to avoid traversing
    Linux symlinks (e.g. ``.venv/lib64 → lib``) that Windows cannot
    access ([WinError 1920]).
    """
    import fnmatch

    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda _: None):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if fnmatch.fnmatch(fn, pattern):
                yield Path(dirpath) / fn


def _has_requirements_doc(design_dir: Path) -> bool:
    """A .md/.txt in *design_dir* mentioning at least two requirement kinds."""
    for pattern in ("*.md", "*.txt"):
        for f in _walk_files(design_dir, pattern):
            content = f.read_text(errors="ignore").lower()
            if sum(1 for kw in _REQUIREMENTS_KEYWORDS if kw in content) >= 2:
                return True
    return False


def _diagrams_rendered(ws: Path, design_dir: Path, baseline: set[str]) -> bool:
    """At least one new Mermaid diagram, and every new one rendered to a sibling SVG.

    ``mmdc`` only writes the SVG when the source parses, so a missing or
    empty SVG means the diagram is not valid Mermaid.  Diagrams that
    shipped with the baseline are ignored.
    """
    sources = [
        src
        for src in (*_walk_files(design_dir, "*.mermaid"), *_walk_files(design_dir, "*.mmd"))
        if str(src.relative_to(ws)).replace("\\", "/") not in baseline
    ]
    if not sources:
        return False
    for src in sources:
        svg = src.with_suffix(".svg")
        try:
            if "<svg" not in svg.read_text(errors="ignore")[:4096]:
                return False
        except OSError:
            return False
    return True


def validate_workspace(stage: str, workspace: str) -> bool:
    """Check whether *workspace* contains expected artefacts for *stage*.

    Returns ``True`` if validation passes, ``False`` otherwise.
    """
    ws = Path(workspace)

    if stage == "requirements":
        # Requirements artifacts must live under docs/design/
        design_dir = ws / "docs" / "design"
        if not design_dir.exists():
            return False
        return _has_requirements_doc(design_dir) and _diagrams_rendered(
            ws, design_dir, _baseline_files(ws)
        )

    if stage == "codegen":
        for py_file in _walk_files(ws, "*.py"):
            try:
                py_compile.compile(str(py_file), doraise=True)
                return True
            except py_compile.PyCompileError:
                pass
        return False

    if stage == "testing":
        for f in _walk_files(ws, "test_*.py"):
            if "def test_" in f.read_text(errors="ignore"):
                return True
        for f in _walk_files(ws, "*_test.py"):
            if "def test_" in f.read_text(errors="ignore"):
                return True
        return False

    if stage == "deploy":
        compose = ws / "docker-compose.yaml"
        dockerfile = ws / "Dockerfile"
        if not compose.exists() or not dockerfile.exists():
            return False
        # Lint: compose must use the harness-injected ${PORT} variable on
        # the host side, otherwise health_check will curl the wrong port.
        try:
            return "${PORT}" in compose.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return False

    return False


# ---------------------------------------------------------------------------
# Post-stage scope audit
# ---------------------------------------------------------------------------

# File extensions that indicate code artifacts.
_CODE_EXTENSIONS = frozenset(
    {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".go",
        ".rs",
        ".rb",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".swift",
        ".kt",
    }
)

_DEPLOY_ARTIFACT_NAMES = {"Dockerfile", "docker-compose.yaml", "docker-compose.yml"}


def audit_workspace(
    stage: str,
    workspace: str,
    baseline_files: set[str] | None = None,
) -> list[str]:
    """Return scope-violation warnings for *stage*.

    Compares the current workspace against *baseline_files* (if provided)
    to only flag files created by the agent, not pre-existing baseline files.
    """
    ws = Path(workspace)
    warnings: list[str] = []

    if stage != "requirements":
        return warnings

    for dirpath, dirnames, filenames in os.walk(ws, onerror=lambda _: None):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            fpath = Path(dirpath) / fn
            rel = str(fpath.relative_to(ws)).replace("\\", "/")
            if baseline_files is not None and rel in baseline_files:
                continue
            if fpath.suffix in _CODE_EXTENSIONS:
                warnings.append(
                    f"Scope violation: {rel} — code file created during requirements stage"
                )
            if fn in _DEPLOY_ARTIFACT_NAMES:
                warnings.append(
                    f"Scope violation: {rel} — "
                    f"deployment artifact created during requirements stage"
                )

    return warnings


def snapshot_workspace(workspace: str) -> dict[str, tuple[int, int]]:
    """Map each workspace file to ``(mtime_ns, size)``.

    Taken before and after a stage so ``build_stage_result`` can tell
    whether the agent actually changed the workspace, independent of
    how faithfully the platform reported its tool calls.
    """
    ws = Path(workspace)
    snapshot: dict[str, tuple[int, int]] = {}
    for dirpath, dirnames, filenames in os.walk(ws, onerror=lambda _: None):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            fpath = Path(dirpath) / fn
            try:
                st = fpath.stat()
            except OSError:
                continue
            rel = str(fpath.relative_to(ws)).replace("\\", "/")
            snapshot[rel] = (st.st_mtime_ns, st.st_size)
    return snapshot
