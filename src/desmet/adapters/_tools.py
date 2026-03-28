"""
Shared tool factory for platform adapters.

Provides sandboxed file-system and shell tools in multiple output formats
so that each adapter does not need to redefine them.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from collections.abc import Sequence
from enum import Enum
from pathlib import Path


class ToolFormat(Enum):
    """Output format for the tool factory."""

    LANGCHAIN = "langchain"  # @tool decorated functions
    CREWAI = "crewai"  # BaseTool subclasses
    OPENAI_AGENTS = "openai_agents"  # OpenAI Agents SDK FunctionTool instances
    CALLABLE = "callable"  # plain Python callables


AVAILABLE_TOOLS: tuple[str, ...] = (
    "read_file",
    "write_file",
    "list_directory",
    "execute_shell",
    "search_code",
    "deploy_remote",
    "check_completion",
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
        return full_path.read_text(encoding="utf-8")
    return f"File not found: {path}"


def _write_file(workspace: Path, path: str, content: str) -> str:
    """Write *content* to a file inside the workspace."""
    try:
        full_path = _safe_resolve(workspace, path)
    except ValueError as exc:
        return f"Error: {exc}"
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")
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


def _find_bash() -> str | None:
    """Find a bash executable (Git Bash or WSL) on Windows, None on Unix."""
    import shutil
    import sys

    if sys.platform != "win32":
        return None  # Unix already uses bash via shell=True

    # Prefer Git Bash, then WSL bash
    for candidate in [
        r"C:\Program Files\Git\usr\bin\bash.exe",
        r"C:\Windows\System32\bash.exe",
    ]:
        if Path(candidate).exists():
            return candidate
    return shutil.which("bash")


_BASH_PATH: str | None = _find_bash()


def _execute_shell(workspace: Path, command: str) -> str:
    """Run a shell command with cwd=workspace, timeout 30 s.

    Uses bash when available (Git Bash / WSL on Windows) instead of
    cmd.exe, which avoids PowerShell profile errors and gives agents
    a Unix-compatible shell.

    NOTE: This tool is intentionally unsandboxed beyond cwd — it can run
    arbitrary shell commands.  Production deployments should rely on
    container-level isolation (Docker) to restrict blast radius.  The
    ``allowed_tools`` list in StageContext can be used to disable this
    tool for stories that don't need shell access.
    """
    try:
        if _BASH_PATH:
            result = subprocess.run(
                [_BASH_PATH, "-c", command],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=30,
            )
        else:
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


def _deploy_port(platform_id: str, story_id: str) -> int:
    """Deterministic port from platform_id + story_id (range 9000-9999)."""
    h = int(hashlib.sha256(f"{platform_id}/{story_id}".encode()).hexdigest(), 16)
    return 9000 + (h % 1000)


def _git_push_url(repo: str) -> str:
    """Convert a deploy repo URL to an HTTPS push URL with token auth.

    Local pushes use HTTPS + token (works with any SSH agent setup).
    The token is read from GITHUB_TOKEN or ``gh auth token``.
    """
    # Already HTTPS
    if repo.startswith("https://"):
        return repo

    # Convert git@github.com:user/repo.git → https://github.com/user/repo.git
    if repo.startswith("git@github.com:"):
        https_url = "https://github.com/" + repo.split(":", 1)[1]
    else:
        return repo  # non-GitHub remote, return as-is

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        try:
            result = subprocess.run(
                ["gh", "auth", "token"], capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                token = result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    if token:
        # https://TOKEN@github.com/user/repo.git
        return https_url.replace("https://", f"https://{token}@")
    return https_url


def _deploy_remote(
    workspace: Path,
    platform_id: str,
    story_id: str,
    action: str,
    url: str = "/health",
) -> str:
    """Execute a remote deploy operation via SSH + git."""
    host = os.environ.get("DEPLOY_HOST")
    ssh_port = os.environ.get("DEPLOY_PORT", "22")
    user = os.environ.get("DEPLOY_USER")
    key = os.environ.get("DEPLOY_KEY_PATH")
    base = os.environ.get("DEPLOY_BASE_PATH", "/opt/desmet")
    deploy_repo = os.environ.get("DEPLOY_REPO", "")

    if not all([host, user, key, deploy_repo]):
        return "Error: DEPLOY_HOST, DEPLOY_USER, DEPLOY_KEY_PATH, and DEPLOY_REPO must be set"

    branch = f"{platform_id}/{story_id}"
    remote_path = f"{base}/{platform_id}/{story_id}"
    port = _deploy_port(platform_id, story_id)
    ssh_opts = f"ssh -i {key} -p {ssh_port} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"

    timeouts = {"push": 120, "restart": 180, "health_check": 30}

    if action == "push":
        # Stage, commit, and push workspace to the deploy repo branch.
        # Uses direct subprocess calls (not shell chaining) for cross-platform
        # compatibility.  The harness initialises the git remote before this.
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=workspace, capture_output=True, timeout=30,
            )
            # Only commit if there are staged changes
            diff = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=workspace, capture_output=True, timeout=10,
            )
            if diff.returncode != 0:
                subprocess.run(
                    ["git", "commit", "-m", "deploy from DESMET evaluation"],
                    cwd=workspace, capture_output=True, timeout=30,
                )
            result = subprocess.run(
                ["git", "push", "deploy", f"HEAD:{branch}", "--force"],
                cwd=workspace, capture_output=True, text=True, timeout=120,
            )
            output = result.stdout + result.stderr
            if result.returncode != 0:
                return f"Error: push failed: {output}"
            return output if output else "Pushed successfully"
        except subprocess.TimeoutExpired:
            return "Error: push timed out"
        except Exception as exc:
            return f"Error: {exc}"

    timeouts = {"restart": 180, "health_check": 30}

    if action == "restart":
        # SSH to server: clone/pull the branch, then docker compose up
        cmd = (
            f'{ssh_opts} {user}@{host} '
            f'"mkdir -p {remote_path} && cd {remote_path} '
            f"&& (git -C . rev-parse 2>/dev/null "
            f"&& git fetch origin {branch} && git checkout FETCH_HEAD "
            f"|| git clone -b {branch} {deploy_repo} .) "
            f"&& COMPOSE_PROJECT_NAME={platform_id}-{story_id} "
            f'PORT={port} docker compose up -d --build"'
        )
    elif action == "health_check":
        cmd = (
            f'{ssh_opts} {user}@{host} '
            f'"curl -sf http://localhost:{port}{url}"'
        )
    else:
        return f"Error: unknown action '{action}'. Use push, restart, or health_check."

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeouts.get(action, 60),
        )
        output = result.stdout + result.stderr
        return output if output else "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: {action} timed out"
    except Exception as exc:
        return f"Error: {exc}"


def _check_completion(workspace: Path, stage: str) -> tuple[bool, str]:
    """Check whether the workspace passes validation for the current stage.

    Returns ``(passed, message)`` so callers can decide what to do with the
    result.  CrewAI uses ``result_as_answer=True`` to short-circuit its
    ReAct loop when validation passes.
    """
    from desmet.adapters._validation import validate_workspace

    passed = validate_workspace(stage, str(workspace))
    if passed:
        return True, (
            "VALIDATION PASSED: All required artifacts for this stage are present. "
            "Task complete."
        )

    hints = {
        "requirements": (
            "Ensure docs/design/ contains .md or .txt files covering "
            "functional, non-functional, and acceptance criteria."
        ),
        "codegen": (
            "Ensure at least one .py file exists and compiles without "
            "syntax errors."
        ),
        "testing": (
            "Ensure test_*.py or *_test.py files exist containing "
            "def test_ functions."
        ),
        "deploy": "Ensure docker-compose.yaml exists in the workspace root.",
    }
    return False, f"VALIDATION FAILED: {hints.get(stage, 'Required artifacts not found.')}"


# ---------------------------------------------------------------------------
# Format builders
# ---------------------------------------------------------------------------

def _build_callable_tools(workspace: Path, tool_names: list[str], platform_id=None, story_id=None, stage_name=None) -> list:
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

        elif name == "deploy_remote":
            def deploy_remote_fn(*, action: str, url: str = "/health") -> str:
                """Deploy to the remote server."""
                return _deploy_remote(workspace, platform_id, story_id, action, url)
            tools.append(deploy_remote_fn)

        elif name == "check_completion":
            def check_completion() -> str:
                """Check if all required artifacts are present in the workspace."""
                _, msg = _check_completion(workspace, stage_name)
                return msg
            tools.append(check_completion)

    return tools


def _build_langchain_tools(workspace: Path, tool_names: list[str], platform_id=None, story_id=None, stage_name=None) -> list:
    """Return LangChain ``@tool`` decorated functions."""
    from langchain.tools import tool as lc_tool

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

        elif name == "deploy_remote":
            @lc_tool
            def deploy_remote(action: str, url: str = "/health") -> str:
                """Deploy to remote server: push artifacts, restart Docker, or health check."""
                return _deploy_remote(workspace, platform_id, story_id, action, url)
            tools.append(deploy_remote)

        elif name == "check_completion":
            @lc_tool
            def check_completion() -> str:
                """Check if all required artifacts are present in the workspace."""
                _, msg = _check_completion(workspace, stage_name)
                return msg
            tools.append(check_completion)

    return tools


def _build_crewai_tools(workspace: Path, tool_names: list[str], platform_id=None, story_id=None, stage_name=None) -> list:
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

    if "deploy_remote" in tool_names:

        class DeployRemoteInput(BaseModel):
            action: str = Field(description="One of: push, restart, health_check")
            url: str = Field(default="/health", description="Health check endpoint path")

        class DeployRemoteTool(CrewAIBaseTool):
            name: str = "deploy_remote"
            description: str = "Deploy to remote server: push artifacts, restart Docker, or health check"
            args_schema: type[BaseModel] = DeployRemoteInput

            def _run(self, action: str, url: str = "/health") -> str:
                return _deploy_remote(workspace, platform_id, story_id, action, url)

        tools.append(DeployRemoteTool())

    if "check_completion" in tool_names:

        class CheckCompletionTool(CrewAIBaseTool):
            name: str = "check_completion"
            description: str = (
                "Check if all required artifacts are present in the workspace. "
                "Call this when you believe the stage task is complete."
            )
            result_as_answer: bool = False

            def _run(self) -> str:
                passed, message = _check_completion(workspace, stage_name)
                if passed:
                    self.result_as_answer = True
                return message

        tools.append(CheckCompletionTool())

    return tools


def _build_openai_agents_tools(workspace: Path, tool_names: list[str], platform_id=None, story_id=None, stage_name=None) -> list:
    """Return OpenAI Agents SDK ``FunctionTool`` instances."""
    from agents import function_tool

    tools: list = []

    if "read_file" in tool_names:
        @function_tool
        def read_file(path: str) -> str:
            """Read the contents of a file at the given relative path."""
            return _read_file(workspace, path)
        tools.append(read_file)

    if "write_file" in tool_names:
        @function_tool
        def write_file(path: str, content: str) -> str:
            """Write content to a file, creating parent directories as needed."""
            return _write_file(workspace, path, content)
        tools.append(write_file)

    if "list_directory" in tool_names:
        @function_tool
        def list_directory(path: str = ".") -> str:
            """List files and directories at the given relative path."""
            return _list_directory(workspace, path)
        tools.append(list_directory)

    if "execute_shell" in tool_names:
        @function_tool
        def execute_shell(command: str) -> str:
            """Execute a shell command in the project directory."""
            return _execute_shell(workspace, command)
        tools.append(execute_shell)

    if "search_code" in tool_names:
        @function_tool
        def search_code(pattern: str, path: str = ".") -> str:
            """Search code files for lines matching a regex pattern."""
            return _search_code(workspace, pattern, path)
        tools.append(search_code)

    if "deploy_remote" in tool_names:
        @function_tool
        def deploy_remote(action: str, url: str = "/health") -> str:
            """Deploy to remote server: push artifacts, restart Docker, or health check."""
            return _deploy_remote(workspace, platform_id, story_id, action, url)
        tools.append(deploy_remote)

    if "check_completion" in tool_names:
        @function_tool
        def check_completion() -> str:
            """Check if all required artifacts are present in the workspace."""
            _, msg = _check_completion(workspace, stage_name)
            return msg
        tools.append(check_completion)

    return tools


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_tools(
    workspace: Path,
    allowed_tools: Sequence[str],
    fmt: ToolFormat = ToolFormat.CALLABLE,
    *,
    platform_id: str | None = None,
    story_id: str | None = None,
    stage_name: str | None = None,
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
    platform_id:
        Platform identifier, required for ``deploy_remote``.
    story_id:
        Story identifier, required for ``deploy_remote``.
    stage_name:
        Current SDLC stage, required for ``check_completion``.

    Returns
    -------
    list
        Tools in the requested format.
    """
    tool_names = [t for t in allowed_tools if t in AVAILABLE_TOOLS]
    # deploy_remote requires platform context
    if platform_id is None or story_id is None:
        tool_names = [t for t in tool_names if t != "deploy_remote"]
    # check_completion requires stage context
    if stage_name is None:
        tool_names = [t for t in tool_names if t != "check_completion"]

    kwargs = dict(platform_id=platform_id, story_id=story_id, stage_name=stage_name)

    if fmt is ToolFormat.CALLABLE:
        return _build_callable_tools(workspace, tool_names, **kwargs)

    if fmt is ToolFormat.LANGCHAIN:
        return _build_langchain_tools(workspace, tool_names, **kwargs)

    if fmt is ToolFormat.CREWAI:
        return _build_crewai_tools(workspace, tool_names, **kwargs)

    if fmt is ToolFormat.OPENAI_AGENTS:
        return _build_openai_agents_tools(workspace, tool_names, **kwargs)

    raise ValueError(f"Unknown tool format: {fmt}")
