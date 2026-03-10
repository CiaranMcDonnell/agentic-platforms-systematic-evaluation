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
    """Run a shell command with cwd=workspace, timeout 30 s.

    NOTE: This tool is intentionally unsandboxed beyond cwd — it can run
    arbitrary shell commands.  Production deployments should rely on
    container-level isolation (Docker) to restrict blast radius.  The
    ``allowed_tools`` list in StageContext can be used to disable this
    tool for stories that don't need shell access.
    """
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

    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        return f"Invalid search pattern: {exc}"
    matches: list[str] = []
    workspace_resolved = workspace.resolve()

    # Walk the tree, skipping common non-text directories and large files
    skip_dirs = {".git", "node_modules", "__pycache__", "venv", ".venv"}
    max_file_size = 1_048_576  # 1 MB

    for dirpath, dirnames, filenames in os.walk(full_path):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for filename in sorted(filenames):
            filepath = Path(dirpath) / filename
            try:
                if filepath.stat().st_size > max_file_size:
                    continue
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


def _build_crewai_tools(workspace: Path, tool_names: list[str]) -> list:
    """Return CrewAI ``BaseTool`` subclasses.

    Each tool is a class with a Pydantic ``args_schema`` so that CrewAI
    can advertise typed parameters to the LLM.  The imports are deferred
    so that the ``crewai`` package is only required when this format is
    actually requested.
    """
    from crewai.tools import BaseTool as CrewAIBaseTool
    from pydantic import BaseModel, Field

    tools: list = []

    if "read_file" in tool_names:

        class ReadFileInput(BaseModel):
            path: str = Field(description="Relative path to the file to read")

        class ReadFileTool(CrewAIBaseTool):
            name: str = "read_file"
            description: str = "Read the contents of a file at the given relative path"
            args_schema: type[BaseModel] = ReadFileInput

            def _run(self, path: str) -> str:
                return _read_file(workspace, path)

        tools.append(ReadFileTool())

    if "write_file" in tool_names:

        class WriteFileInput(BaseModel):
            path: str = Field(description="Relative path to write the file to")
            content: str = Field(description="Content to write to the file")

        class WriteFileTool(CrewAIBaseTool):
            name: str = "write_file"
            description: str = "Write content to a file, creating parent directories as needed"
            args_schema: type[BaseModel] = WriteFileInput

            def _run(self, path: str, content: str) -> str:
                return _write_file(workspace, path, content)

        tools.append(WriteFileTool())

    if "list_directory" in tool_names:

        class ListDirectoryInput(BaseModel):
            path: str = Field(default=".", description="Relative path to the directory to list")

        class ListDirectoryTool(CrewAIBaseTool):
            name: str = "list_directory"
            description: str = "List files and directories at the given relative path"
            args_schema: type[BaseModel] = ListDirectoryInput

            def _run(self, path: str = ".") -> str:
                return _list_directory(workspace, path)

        tools.append(ListDirectoryTool())

    if "execute_shell" in tool_names:

        class ExecuteShellInput(BaseModel):
            command: str = Field(description="Shell command to execute")

        class ExecuteShellTool(CrewAIBaseTool):
            name: str = "execute_shell"
            description: str = "Execute a shell command in the project directory"
            args_schema: type[BaseModel] = ExecuteShellInput

            def _run(self, command: str) -> str:
                return _execute_shell(workspace, command)

        tools.append(ExecuteShellTool())

    if "search_code" in tool_names:

        class SearchCodeInput(BaseModel):
            pattern: str = Field(description="Regex pattern to search for")
            path: str = Field(default=".", description="Relative path to search in")

        class SearchCodeTool(CrewAIBaseTool):
            name: str = "search_code"
            description: str = "Search code files for lines matching a regex pattern"
            args_schema: type[BaseModel] = SearchCodeInput

            def _run(self, pattern: str, path: str = ".") -> str:
                return _search_code(workspace, pattern, path)

        tools.append(SearchCodeTool())

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
        return _build_crewai_tools(workspace, tool_names)

    if fmt is ToolFormat.OPENAI_FUNCTION:
        raise NotImplementedError("OpenAI function tools not yet implemented")

    raise ValueError(f"Unknown tool format: {fmt}")
