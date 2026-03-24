"""Shared workspace validation for platform adapters.

Deterministic checks (no LLM call) that verify whether an SDLC stage
produced the expected artefacts in the workspace directory.
"""
from __future__ import annotations

import py_compile
from pathlib import Path

_REQUIREMENTS_KEYWORDS = {"functional", "non-functional", "acceptance", "constraint"}


def validate_workspace(stage: str, workspace: str) -> bool:
    """Check whether *workspace* contains expected artefacts for *stage*.

    Returns ``True`` if validation passes, ``False`` otherwise.
    """
    ws = Path(workspace)

    if stage == "requirements":
        for ext in ("*.md", "*.txt"):
            for f in ws.glob(ext):
                content = f.read_text(errors="ignore").lower()
                hits = sum(1 for kw in _REQUIREMENTS_KEYWORDS if kw in content)
                if hits >= 3:
                    return True
        return False

    if stage == "codegen":
        for py_file in ws.glob("*.py"):
            try:
                py_compile.compile(str(py_file), doraise=True)
                return True
            except py_compile.PyCompileError:
                pass
        return False

    if stage == "testing":
        for pattern in ("test_*.py", "*_test.py"):
            for f in ws.glob(pattern):
                if "def test_" in f.read_text(errors="ignore"):
                    return True
        return False

    if stage == "deploy":
        return (ws / "docker-compose.yaml").exists()

    return False
