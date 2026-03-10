"""
Shared tool factory for platform adapters.

Provides sandboxed file-system and shell tools in multiple output formats
so that each adapter does not need to redefine them.
"""

from __future__ import annotations

import os
import re
import subprocess
from enum import Enum
from pathlib import Path
from typing import Sequence


class ToolFormat(Enum):
    """Output format for the tool factory."""

    LANGCHAIN = "langchain"  # @tool decorated functions
    CREWAI = "crewai"  # BaseTool subclasses
    OPENAI_FUNCTION = "openai"  # (schema_dict, callable) tuples
    CALLABLE = "callable"  # plain Python callables


AVAILABLE_TOOLS: tuple[str, ...] = (
    "read_file",
    "write_file",
    "list_directory",
    "execute_shell",
    "search_code",
)


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------

def _safe_resolve(workspace: Path, path: str) -> Path:
    """Resolve *path* relative to *workspace*, rejecting traversal escapes.

    Uses ``resolved.relative_to()`` (not string prefix checks) so that
    symlink tricks and ``..`` segments are handled correctly.

    Raises ``ValueError`` if the resolved path falls outside the workspace.
    """
    workspace_resolved = workspace.resolve()
    resolved = (workspace_resolved / path).resolve()
    try:
        resolved.relative_to(workspace_resolved)
    except ValueError:
        raise ValueError(
            f"Path {path!r} resolves outside workspace: {workspace_resolved}"
        )
    return resolved


# ---------------------------------------------------------------------------
# Core tool implementations (format-agnostic)
# ---------------------------------------------------------------------------

def _read_file(workspace: Path, path: str) -> str:
    """Read a file inside the workspace."""
    try:
        full_path = _safe_resolve(workspace, path)
    except ValueError as exc:
        return f"Error: {exc}"
    if full_path.exists():
        return full_path.read_text()
    return f"File not found: {path}"


def _write_file(workspace: Path, path: str, content: str) -> str:
    """Write *content* to a file inside the workspace."""
    try:
        full_path = _safe_resolve(workspace, path)
    except ValueError as exc:
        return f"Error: {exc}"
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content)
    return f"Successfully wrote to {path}"


def _list_directory(workspace: Path, path: str = ".") -> str:
    """List directory entries, sorted alphabetically."""
    try:
        full_path = _safe_resolve(workspace, path)
    except ValueError as exc:
        return f"Error: {exc}"
    if full_path.exists() and full_path.is_dir():
        entries = sorted(
            str(f.relative_to(workspace.resolve())) for f in full_path.iterdir()
        )
        return "\n".join(entries)
    return f"Directory not found: {path}"


def _execute_shell(workspace: Path, command: str) -> str:
    """Run a shell command with cwd=workspace, timeout 30 s."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        return output if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Command timed out"
    except Exception as exc:
        return f"Error: {exc}"


def _search_code(workspace: Path, pattern: str, path: str = ".") -> str:
    """Search files for lines matching *pattern*, capped at 100 results."""
    try:
        full_path = _safe_resolve(workspace, path)
    except ValueError as exc:
        return f"Error: {exc}"

    if not full_path.exists():
        return f"Directory not found: {path}"

    compiled = re.compile(pattern)
    matches: list[str] = []
    workspace_resolved = workspace.resolve()

    # Walk the tree
    for dirpath, _dirnames, filenames in os.walk(full_path):
        for filename in sorted(filenames):
            filepath = Path(dirpath) / filename
            try:
                text = filepath.read_text(errors="replace")
            except (OSError, PermissionError):
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if compiled.search(line):
                    relpath = filepath.relative_to(workspace_resolved)
                    matches.append(f"{relpath}:{lineno}: {line}")
                    if len(matches) >= 100:
                        return "\n".join(matches)

    if not matches:
        return "No matches found"
    return "\n".join(matches)


# ---------------------------------------------------------------------------
# Format builders
# ---------------------------------------------------------------------------

def _build_callable_tools(workspace: Path, tool_names: list[str]) -> list:
    """Return plain callables with meaningful ``__name__`` attributes."""
    tools: list = []

    for name in tool_names:
        if name == "read_file":
            def read_file(*, path: str) -> str:
                """Read the contents of a file."""
                return _read_file(workspace, path)
            tools.append(read_file)

        elif name == "write_file":
            def write_file(*, path: str, content: str) -> str:
                """Write content to a file."""
                return _write_file(workspace, path, content)
            tools.append(write_file)

        elif name == "list_directory":
            def list_directory(*, path: str = ".") -> str:
                """List files in a directory."""
                return _list_directory(workspace, path)
            tools.append(list_directory)

        elif name == "execute_shell":
            def execute_shell(*, command: str) -> str:
                """Execute a shell command."""
                return _execute_shell(workspace, command)
            tools.append(execute_shell)

        elif name == "search_code":
            def search_code(*, pattern: str, path: str = ".") -> str:
                """Search code files for a pattern."""
                return _search_code(workspace, pattern, path)
            tools.append(search_code)

    return tools


def _build_langchain_tools(workspace: Path, tool_names: list[str]) -> list:
    """Return LangChain ``@tool`` decorated functions."""
    from langchain_core.tools import tool as lc_tool

    tools: list = []

    for name in tool_names:
        if name == "read_file":
            @lc_tool
            def read_file(path: str) -> str:
                """Read the contents of a file."""
                return _read_file(workspace, path)
            tools.append(read_file)

        elif name == "write_file":
            @lc_tool
            def write_file(path: str, content: str) -> str:
                """Write content to a file."""
                return _write_file(workspace, path, content)
            tools.append(write_file)

        elif name == "list_directory":
            @lc_tool
            def list_directory(path: str = ".") -> str:
                """List files in a directory."""
                return _list_directory(workspace, path)
            tools.append(list_directory)

        elif name == "execute_shell":
            @lc_tool
            def execute_shell(command: str) -> str:
                """Execute a shell command."""
                return _execute_shell(workspace, command)
            tools.append(execute_shell)

        elif name == "search_code":
            @lc_tool
            def search_code(pattern: str, path: str = ".") -> str:
                """Search code files for a pattern."""
                return _search_code(workspace, pattern, path)
            tools.append(search_code)

    return tools


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_tools(
    workspace: Path,
    allowed_tools: Sequence[str],
    fmt: ToolFormat = ToolFormat.CALLABLE,
) -> list:
    """Create sandboxed tools for the given workspace.

    Parameters
    ----------
    workspace:
        Root directory that all file operations are sandboxed within.
    allowed_tools:
        Tool names to include.  Unknown names are silently skipped.
    fmt:
        Output format — see :class:`ToolFormat`.

    Returns
    -------
    list
        Tools in the requested format.
    """
    # Filter to only known tool names, preserving order
    tool_names = [t for t in allowed_tools if t in AVAILABLE_TOOLS]

    if fmt is ToolFormat.CALLABLE:
        return _build_callable_tools(workspace, tool_names)

    if fmt is ToolFormat.LANGCHAIN:
        return _build_langchain_tools(workspace, tool_names)

    if fmt is ToolFormat.CREWAI:
        raise NotImplementedError("CrewAI tools require crewai package")

    if fmt is ToolFormat.OPENAI_FUNCTION:
        raise NotImplementedError("OpenAI function tools not yet implemented")

    raise ValueError(f"Unknown tool format: {fmt}")
