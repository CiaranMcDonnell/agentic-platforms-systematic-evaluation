"""
Shared tool factory for platform adapters.

Provides sandboxed file-system and shell tools in multiple output formats
so that each adapter does not need to redefine them.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shlex
import subprocess
from collections import defaultdict
from collections.abc import Sequence
from enum import Enum
from pathlib import Path

_log = logging.getLogger(__name__)


class ToolFormat(Enum):
    """Output format for the tool factory."""

    LANGCHAIN = "langchain"  # @tool decorated functions
    CREWAI = "crewai"  # BaseTool subclasses
    OPENAI_AGENTS = "openai_agents"  # OpenAI Agents SDK FunctionTool instances
    AGENT_FRAMEWORK = "agent_framework"  # Microsoft Agent Framework @tool functions
    # Google ADK callables (no param defaults — Gemini schema rejects them)
    GOOGLE_ADK = "google_adk"
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
        raise ValueError(f"Path {path!r} resolves outside workspace: {workspace_resolved}")
    return resolved


# ---------------------------------------------------------------------------
# Loop detection — catches agents repeating low-value tool calls
# ---------------------------------------------------------------------------

# Window size: how many recent calls to inspect for loop patterns.
# Independent of _CROSS_TOOL_THRESHOLD below — the two windows track
# different buffers (per-tool history vs cross-tool target history) so
# _LOOP_WINDOW < _CROSS_TOOL_THRESHOLD is not a contradiction.
_LOOP_WINDOW = 8

# Consecutive-identical threshold (stricter, fires faster).
_CONSECUTIVE_THRESHOLD = 4

# Cross-tool target threshold — fires when the same file/target appears
# in N consecutive calls across ANY tools (catches agents thrashing on
# one file with different tools: write → render → read → write → …).
_CROSS_TOOL_THRESHOLD = 10

# Shell commands that produce no meaningful progress.  When the entire
# window consists of these, the agent is stuck exploring rather than
# doing real work.
_RECON_RE = re.compile(
    r"^\s*(?:/\S+/)?"  # optional path prefix (/bin/, /usr/bin/, …)
    r"(?:ls|dir|pwd|echo|date|id|whoami|true|hostname|uname"
    r"|cat|head|tail|wc|file|stat|which|type)\b"
)

# File-path extraction for shell commands (best-effort heuristic).
# Matches paths ending in known source/doc extensions.  "Primary" targets
# (source files the agent is trying to produce) take priority over
# "config" files like tool configs.
_SHELL_TARGET_PRIMARY_RE = re.compile(
    r"([\w./-]+\.(?:mermaid|md|py|ts|tsx|js|jsx|yaml|yml|html|css|svg|txt))"
)
_SHELL_TARGET_ANY_RE = re.compile(
    r"([\w./-]+\.(?:mermaid|md|py|ts|tsx|js|jsx|json|yaml|yml|html|css|svg|txt))"
)
# Paths in these directories are tool/config — ignore them when there's
# a primary match elsewhere in the command.
_SHELL_TARGET_IGNORE_PREFIXES = ("/", "~/", "/etc/", "/usr/", "/tmp/")

# Per-workspace:tool sliding window of recent call keys (per-tool loop check).
_call_history: dict[str, list[str]] = defaultdict(list)

# Per-workspace sliding window of recent cross-tool targets (file paths).
_cross_tool_history: dict[str, list[str]] = defaultdict(list)

# Per-workspace set of targets that have been declared "locked" because
# a loop was detected on them.  Subsequent tool calls touching any of
# these targets are refused for the rest of the stage — the LLM cannot
# "work around" the loop warning by switching tools or varying the
# arguments.  Reset between stages via reset_loop_tracker().
_locked_targets: dict[str, set[str]] = defaultdict(set)


def _extract_target(tool_name: str, call_key: str) -> str | None:
    """Extract a file-path target from a tool call, if possible.

    Returns a normalized path for file-oriented tools, or the first
    file-like argument found in a shell command.  Returns ``None`` when
    no clear target exists (e.g. ``pwd``, ``echo hello``).
    """
    if tool_name in ("read_file", "write_file"):
        target = call_key.strip()
        return target if target else None
    if tool_name == "list_directory":
        # Directories aren't "work targets" in the same sense — skip them
        # to avoid false positives on repeated directory listings.
        return None
    if tool_name == "search_code":
        # Key format is "pattern:path" — the path portion is the target
        if ":" in call_key:
            _, path = call_key.rsplit(":", 1)
            return path.strip() or None
        return None
    if tool_name == "execute_shell":
        # Prefer workspace-relative source/doc files over absolute tool-config paths
        for match in _SHELL_TARGET_PRIMARY_RE.finditer(call_key):
            path = match.group(1)
            if not any(path.startswith(p) for p in _SHELL_TARGET_IGNORE_PREFIXES):
                return path
        # Fallback: any match, including json
        for match in _SHELL_TARGET_ANY_RE.finditer(call_key):
            path = match.group(1)
            if not any(path.startswith(p) for p in _SHELL_TARGET_IGNORE_PREFIXES):
                return path
        return None
    return None


def _check_loop(workspace: str, tool_name: str, call_key: str) -> str | None:
    """Return an error string if a loop is detected, else ``None``.

    Detects three patterns:
    1. **Consecutive identical** — the same call_key N times in a row.
    2. **Reconnaissance spin** — the last *window* calls are all low-value
       shell commands (``ls``, ``pwd``, ``echo``, …) with low diversity,
       meaning the agent is cycling instead of making progress.
    3. **Cross-tool target thrash** — the same file/target appears in
       ``_CROSS_TOOL_THRESHOLD`` consecutive calls across any tools
       (agent stuck writing → rendering → reading → writing on one file).

    Once a loop is detected on a target (check 3), that target is added
    to a per-workspace "locked" set.  Any subsequent tool call whose
    extracted target is in the locked set is refused immediately — this
    prevents the LLM from working around the initial warning by
    switching tools or changing arguments.
    """
    # ── Check 0: locked target (sticky enforcement) ──────────────────
    target = _extract_target(tool_name, call_key)
    if target is not None and target in _locked_targets[workspace]:
        _log.warning(
            "[DEFENSE] REFUSED %s on locked target '%s'",
            tool_name,
            target,
        )
        return (
            f"REFUSED: '{target}' is locked after a previous loop was "
            f"detected on it. You CANNOT edit, render, or read this "
            f"file again in this stage. Move on to the next task or "
            f"stop and let the reviewer validate what you have produced. "
            f"Further attempts on this file will be ignored."
        )

    tracker_key = f"{workspace}:{tool_name}"
    history = _call_history[tracker_key]
    history.append(call_key)

    # Keep only the last _LOOP_WINDOW entries
    if len(history) > _LOOP_WINDOW:
        _call_history[tracker_key] = history[-_LOOP_WINDOW:]
        history = _call_history[tracker_key]

    # ── Check 1: consecutive identical ────────────────────────────────
    tail = history[-_CONSECUTIVE_THRESHOLD:]
    if len(tail) == _CONSECUTIVE_THRESHOLD and len(set(tail)) == 1:
        _call_history[tracker_key] = []
        _log.warning(
            "[DEFENSE] LOOP DETECTED — %s called %d times in a row with identical args",
            tool_name,
            _CONSECUTIVE_THRESHOLD,
        )
        return (
            f"LOOP DETECTED: '{tool_name}' was called {_CONSECUTIVE_THRESHOLD} "
            f"times in a row with identical arguments. You are stuck in a loop. "
            f"STOP repeating this action and try a completely different approach. "
            f"If a command keeps failing, skip it and move on to the next task."
        )

    # ── Check 2: reconnaissance spin (execute_shell only) ─────────────
    if tool_name == "execute_shell" and len(history) >= _LOOP_WINDOW:
        window = history[-_LOOP_WINDOW:]
        all_recon = all(_RECON_RE.match(cmd) for cmd in window)
        low_diversity = len(set(window)) <= 3
        if all_recon and low_diversity:
            _call_history[tracker_key] = []
            _log.warning(
                "[DEFENSE] LOOP DETECTED — %d reconnaissance shell commands with no progress",
                _LOOP_WINDOW,
            )
            return (
                f"LOOP DETECTED: the last {_LOOP_WINDOW} shell commands were all "
                f"reconnaissance commands (ls, pwd, echo, …) with no productive "
                f"work. You are stuck in a loop. STOP running exploratory "
                f"commands and attempt the actual task (e.g. render "
                f"diagrams, write files). Once done, stop and let the "
                f"reviewer validate."
            )

    # ── Check 3: cross-tool target thrash ─────────────────────────────
    # Note: `target` was extracted at the top of the function (for the
    # locked-target check).  Reuse it here.
    if target is not None:
        cross = _cross_tool_history[workspace]
        cross.append(target)
        if len(cross) > _CROSS_TOOL_THRESHOLD * 2:
            _cross_tool_history[workspace] = cross[-_CROSS_TOOL_THRESHOLD * 2 :]
            cross = _cross_tool_history[workspace]
        cross_tail = cross[-_CROSS_TOOL_THRESHOLD:]
        if len(cross_tail) == _CROSS_TOOL_THRESHOLD and len(set(cross_tail)) == 1:
            _cross_tool_history[workspace] = []
            # LOCK this target for the rest of the stage — any further
            # tool call on it will be refused by the locked-target check
            # at the top of this function.
            _locked_targets[workspace].add(target)
            _log.warning(
                "[DEFENSE] LOOP DETECTED + LOCKED — %d cross-tool ops on '%s'",
                _CROSS_TOOL_THRESHOLD,
                target,
            )
            return (
                f"LOOP DETECTED: you have made {_CROSS_TOOL_THRESHOLD} "
                f"consecutive operations on '{target}' across multiple tools. "
                f"This file is now LOCKED for the rest of the stage — any "
                f"further read, write, or render on '{target}' will be "
                f"refused. Move on to the next task or stop and let the "
                f"reviewer validate what you have produced."
            )

    return None


def reset_loop_tracker() -> None:
    """Clear all loop detection state (call between evaluation runs)."""
    _call_history.clear()
    _cross_tool_history.clear()
    _locked_targets.clear()


# ---------------------------------------------------------------------------
# Stage-specific shell command filtering
# ---------------------------------------------------------------------------

# Commands allowed during the requirements stage (allowlist).
# Only stages listed here are filtered; unlisted stages have unrestricted shell.
_REQUIREMENTS_SHELL_ALLOW = frozenset(
    {
        # Filesystem inspection
        "ls",
        "cat",
        "head",
        "tail",
        "find",
        "grep",
        "egrep",
        "fgrep",
        "wc",
        "file",
        "stat",
        "tree",
        "diff",
        "sort",
        "uniq",
        "realpath",
        "readlink",
        "basename",
        "dirname",
        # File management
        "mkdir",
        "cp",
        "mv",
        "rm",
        "touch",
        "chmod",
        # Diagram rendering
        "mmdc",
        # Shell basics
        "echo",
        "printf",
        "pwd",
        "which",
        "type",
        "true",
        "false",
        "test",
        "[",
        "env",
        "date",
        # Text processing
        "sed",
        "awk",
        "cut",
        "tr",
        "tee",
        "xargs",
    }
)

_STAGE_SHELL_ALLOWLIST: dict[str, frozenset[str]] = {
    "requirements": _REQUIREMENTS_SHELL_ALLOW,
}

_CMD_SPLIT_RE = re.compile(r"[|;&]+")


def _extract_command_names(command: str) -> list[str]:
    """Extract command names from a (possibly piped/chained) shell command."""
    parts = _CMD_SPLIT_RE.split(command)
    names: list[str] = []
    for part in parts:
        tokens = part.strip().split()
        if not tokens:
            continue
        # Skip leading env-var assignments (FOO=bar cmd ...)
        idx = 0
        while idx < len(tokens) and re.match(r"^[A-Za-z_]\w*=", tokens[idx]):
            idx += 1
        if idx < len(tokens):
            # Strip path prefix (/usr/bin/mmdc → mmdc)
            names.append(tokens[idx].rsplit("/", 1)[-1])
    return names


def _check_shell_stage(stage: str | None, command: str) -> str | None:
    """Return an error string if *command* is blocked for *stage*, else ``None``."""
    if stage is None:
        return None
    allowlist = _STAGE_SHELL_ALLOWLIST.get(stage)
    if allowlist is None:
        return None
    cmd_names = _extract_command_names(command)
    blocked = [c for c in cmd_names if c not in allowlist]
    if not blocked:
        return None
    return (
        f"BLOCKED: Command{'s' if len(blocked) > 1 else ''} "
        f"{', '.join(repr(c) for c in blocked)} not permitted during "
        f"the {stage} stage. Only documentation and diagram tools are "
        f"allowed (e.g. mmdc, mkdir, cat). Use write_file to create "
        f"files directly."
    )


# ---------------------------------------------------------------------------
# Stage-specific write_file extension filtering
# ---------------------------------------------------------------------------

# File extensions allowed when write_file is called during each stage.
# Only stages listed here are filtered; unlisted stages have unrestricted
# write access. Motivation: prevent scope drift where an executor writes
# code files during a docs-only stage (observed with Microsoft Agent
# Framework writing email_validator.py during requirements).
_REQUIREMENTS_WRITE_ALLOW = frozenset({".md", ".txt", ".mermaid"})

_STAGE_WRITE_ALLOWLIST: dict[str, frozenset[str]] = {
    "requirements": _REQUIREMENTS_WRITE_ALLOW,
}


def _check_write_stage(stage: str | None, path: str) -> str | None:
    """Return an error string if writing *path* is blocked for *stage*, else ``None``."""
    if stage is None:
        return None
    allowlist = _STAGE_WRITE_ALLOWLIST.get(stage)
    if allowlist is None:
        return None
    suffix = Path(path).suffix.lower()
    if suffix in allowlist:
        return None
    allowed = ", ".join(sorted(allowlist))
    return (
        f"BLOCKED: write_file to {path!r} is not permitted during the "
        f"{stage} stage. Only documentation artifacts are allowed "
        f"(extensions: {allowed}). Write design docs and diagrams only; "
        f"implementation files belong in later stages."
    )


# ---------------------------------------------------------------------------
# Core tool implementations (format-agnostic)
# ---------------------------------------------------------------------------

_MAX_READ_SIZE = 5_242_880  # 5 MB


def _read_file(workspace: Path, path: str) -> str:
    """Read a file inside the workspace."""
    loop_err = _check_loop(str(workspace), "read_file", path)
    if loop_err:
        return loop_err
    try:
        full_path = _safe_resolve(workspace, path)
    except ValueError as exc:
        return f"Error: {exc}"
    if not full_path.exists():
        return f"File not found: {path}"
    if full_path.stat().st_size > _MAX_READ_SIZE:
        return f"Error: file too large ({full_path.stat().st_size} bytes, limit {_MAX_READ_SIZE})"
    return full_path.read_text(encoding="utf-8")


def _strip_markdown_fences(content: str) -> str:
    """Remove a leading ``` fence (with or without a language tag) and the
    matching trailing fence.  LLMs frequently wrap mermaid (and other
    source) output in markdown code fences by default, which makes
    downstream tools like ``mmdc`` reject the file.  Stripping fences is
    a no-op for content that was never fenced.
    """
    stripped = content.strip()
    if not stripped.startswith("```"):
        return content
    first_nl = stripped.find("\n")
    if first_nl == -1:
        return content
    body = stripped[first_nl + 1 :].rstrip()
    if body.endswith("```"):
        body = body[:-3].rstrip()
    return body + "\n"


def _write_file(workspace: Path, path: str, content: str, *, stage: str | None = None) -> str:
    """Write *content* to a file inside the workspace."""
    stage_err = _check_write_stage(stage, path)
    if stage_err:
        return stage_err
    loop_err = _check_loop(str(workspace), "write_file", path)
    if loop_err:
        return loop_err
    try:
        full_path = _safe_resolve(workspace, path)
    except ValueError as exc:
        return f"Error: {exc}"
    if full_path.suffix == ".mermaid":
        content = _strip_markdown_fences(content)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")
    return f"Successfully wrote to {path}"


def _list_directory(workspace: Path, path: str = ".") -> str:
    """List directory entries, sorted alphabetically."""
    loop_err = _check_loop(str(workspace), "list_directory", path)
    if loop_err:
        return loop_err
    try:
        full_path = _safe_resolve(workspace, path)
    except ValueError as exc:
        return f"Error: {exc}"
    if full_path.exists() and full_path.is_dir():
        entries = sorted(str(f.relative_to(workspace.resolve())) for f in full_path.iterdir())
        return "\n".join(entries)
    return f"Directory not found: {path}"


_SHELL_TIMEOUT = 120  # mermaid rendering w/ Puppeteer needs >30s


def _execute_shell(workspace: Path, command: str, *, stage: str | None = None) -> str:
    """Run a shell command locally inside the workspace.

    The agent already runs inside a per-platform Docker container
    (started by ``container_runner``), so commands execute directly —
    no nested container needed.
    """
    # Stage-based command filtering (requirements = allowlist only)
    stage_err = _check_shell_stage(stage, command)
    if stage_err:
        return stage_err

    loop_err = _check_loop(str(workspace), "execute_shell", command)
    if loop_err:
        return loop_err

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=_SHELL_TIMEOUT,
        )
        output = result.stdout + result.stderr
        if len(output) > 2000:
            output = output[:1000] + "\n...(truncated)...\n" + output[-800:]
        # Surface non-zero exit codes explicitly so the agent can tell
        # a silent-fail command (e.g. mmdc rejecting bad mermaid syntax)
        # apart from a successful no-output command.
        if result.returncode != 0:
            body = output if output else "(no output)"
            return f"[EXIT={result.returncode}] {body}"
        return output if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Command timed out"
    except Exception as exc:
        return f"Error: {exc}"


def _search_code(workspace: Path, pattern: str, path: str = ".") -> str:
    """Search files for lines matching *pattern*, capped at 100 results."""
    loop_err = _check_loop(str(workspace), "search_code", f"{pattern}:{path}")
    if loop_err:
        return loop_err
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
    """Return the deploy port for *platform_id*.

    Reads ``deploy_port`` from ``config/platforms.yaml``.  Falls back to
    a hash-based port in 8100-8199 when the config field is missing.
    The *story_id* parameter is retained for API compatibility but is
    ignored — each platform gets one fixed port matching the nginx
    reverse-proxy configuration.
    """
    from desmet.platforms_config import get_platform_field

    configured = get_platform_field(platform_id, "deploy_port")
    if configured is not None:
        return int(configured)
    # Fallback: deterministic per-platform port outside infrastructure range
    h = int(hashlib.sha256(platform_id.encode()).hexdigest(), 16)
    return 8100 + (h % 100)


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
                ["gh", "auth", "token"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                token = result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    if token:
        # https://TOKEN@github.com/user/repo.git
        return https_url.replace("https://", f"https://{token}@")
    return https_url


def _deploy_local(
    workspace: Path,
    platform_id: str,
    story_id: str,
    action: str,
    url: str = "/health",
) -> str:
    """Execute a local deploy operation via Docker Compose."""
    port = _deploy_port(platform_id, story_id)

    if action == "push":
        return "Local mode — workspace is already available, no push needed."

    if action == "restart":
        compose_project = f"{platform_id}-{story_id}".lower()
        env_file = workspace / ".env"
        existing = env_file.read_text() if env_file.exists() else ""
        lines = [
            ln
            for ln in existing.splitlines()
            if not ln.startswith("COMPOSE_PROJECT_NAME=") and not ln.startswith("PORT=")
        ]
        lines.append(f"COMPOSE_PROJECT_NAME={compose_project}")
        lines.append(f"PORT={port}")
        env_file.write_text("\n".join(lines) + "\n")

        try:
            result = subprocess.run(
                ["docker", "compose", "up", "-d", "--build"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=180,
            )
            output = result.stdout + result.stderr
            if result.returncode != 0:
                return f"Error: docker compose failed: {output}"
            return output if output else "Started successfully"
        except subprocess.TimeoutExpired:
            return "Error: docker compose timed out"
        except FileNotFoundError:
            return "Error: docker command not found"
        except Exception as exc:
            return f"Error: {exc}"

    if action == "health_check":
        try:
            result = subprocess.run(
                ["curl", "-sf", f"http://localhost:{port}{url}"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return f"Health check failed (exit {result.returncode}): {result.stderr}"
            return result.stdout if result.stdout else "OK"
        except subprocess.TimeoutExpired:
            return "Error: health check timed out"
        except FileNotFoundError:
            return "Error: curl command not found"
        except Exception as exc:
            return f"Error: {exc}"

    return f"Error: unknown action '{action}'. Valid: push, restart, health_check"


def _deploy_remote(
    workspace: Path,
    platform_id: str,
    story_id: str,
    action: str,
    url: str = "/health",
) -> str:
    """Execute a remote deploy operation via SSH + git."""
    # ── Local deploy mode ──────────────────────────────────────────────
    deploy_mode = os.environ.get("DESMET_DEPLOY_MODE", "remote")
    if deploy_mode == "local":
        return _deploy_local(workspace, platform_id, story_id, action, url)

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
    # StrictModes=no is required because the deploy key is bind-mounted
    # into the container from the host (see container_runner._ensure_container).
    # On Windows hosts and on certain Linux bind-mount setups the file
    # appears with permissions wider than 600 inside the container, which
    # would otherwise cause OpenSSH to refuse to use it.  The actual
    # privilege boundary is enforced by the restricted shell on the
    # deploy server (see docs/spec/deploy-infrastructure.md), not by
    # client-side mode bits.
    ssh_opts = (
        f"ssh -i {shlex.quote(key)} -p {shlex.quote(ssh_port)} "
        f"-o IdentitiesOnly=yes "
        f"-o StrictHostKeyChecking=accept-new "
        f"-o StrictModes=no"
    )

    if action == "push":
        # Stage, commit, and push workspace to the deploy repo branch.
        # Uses direct subprocess calls (not shell chaining) for cross-platform
        # compatibility.  The harness initialises the git remote before this.
        #
        # ``-c safe.directory=*`` is required because the workspace is
        # bind-mounted from the host into a container running as the
        # ``agent`` user.  Git's "dubious ownership" check would refuse
        # to operate on the repo otherwise.  Limiting the override to
        # the deploy command line (rather than git config --global) keeps
        # the relaxation scoped to this single subprocess invocation.
        git_safe = ["git", "-c", f"safe.directory={workspace}", "-c", "safe.directory=*"]
        try:
            subprocess.run(
                [*git_safe, "add", "-A"],
                cwd=workspace,
                capture_output=True,
                timeout=30,
            )
            # Only commit if there are staged changes
            diff = subprocess.run(
                [*git_safe, "diff", "--cached", "--quiet"],
                cwd=workspace,
                capture_output=True,
                timeout=10,
            )
            if diff.returncode != 0:
                subprocess.run(
                    [*git_safe, "commit", "-m", "deploy from DESMET evaluation"],
                    cwd=workspace,
                    capture_output=True,
                    timeout=30,
                )
            result = subprocess.run(
                [*git_safe, "push", "deploy", f"HEAD:{branch}", "--force"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=120,
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
        # SSH to server: clone or pull the branch, then docker compose up.
        # The restricted shell (desmet-shell) allows:
        #   git clone [-b branch] <url> <path>
        #   cd <path> && git pull|fetch|status|log
        #   docker compose --project-directory <path> <subcommand>
        import subprocess as _sp

        q_branch = shlex.quote(branch)
        q_remote = shlex.quote(remote_path)
        q_repo = shlex.quote(deploy_repo)
        q_user_host = f"{shlex.quote(user)}@{shlex.quote(host)}"

        # Step 1: git clone (first deploy) or cd && git pull (subsequent)
        clone_result = _sp.run(
            f'{ssh_opts} {q_user_host} "git clone -b {q_branch} {q_repo} {q_remote}"',
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if clone_result.returncode != 0:
            # Already cloned — pull latest
            _sp.run(
                f'{ssh_opts} {q_user_host} "cd {q_remote} && git fetch origin {q_branch}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
            _sp.run(
                f'{ssh_opts} {q_user_host} "cd {q_remote} && git pull origin {q_branch}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
            )

        # Step 2: docker compose up.
        # Write .env into workspace before the git push (done in the push
        # action) so docker compose reads COMPOSE_PROJECT_NAME and PORT
        # automatically from the working directory.
        compose_project = f"{platform_id}-{story_id}".lower()
        env_file = workspace / ".env"
        # Write/overwrite compose vars (filter out old values, append new)
        existing = env_file.read_text() if env_file.exists() else ""
        lines = [
            ln
            for ln in existing.splitlines()
            if not ln.startswith("COMPOSE_PROJECT_NAME=") and not ln.startswith("PORT=")
        ]
        lines.append(f"COMPOSE_PROJECT_NAME={compose_project}")
        lines.append(f"PORT={port}")
        env_file.write_text("\n".join(lines) + "\n")

        # Re-push so .env is on the server
        _sp.run(
            ["git", "add", "-A"],
            cwd=workspace,
            capture_output=True,
            timeout=10,
        )
        _sp.run(
            ["git", "commit", "-m", "add compose env"],
            cwd=workspace,
            capture_output=True,
            timeout=10,
        )
        _sp.run(
            ["git", "push", "deploy", f"HEAD:{branch}", "--force"],
            cwd=workspace,
            capture_output=True,
            timeout=60,
        )
        # Pull on server
        _sp.run(
            f'{ssh_opts} {q_user_host} "cd {q_remote} && git pull origin {q_branch}"',
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )

        cmd = f'{ssh_opts} {q_user_host} "cd {q_remote} && docker compose up -d --build"'
    elif action == "health_check":
        q_url = shlex.quote(url)
        q_user_host = f"{shlex.quote(user)}@{shlex.quote(host)}"
        cmd = f'{ssh_opts} {q_user_host} "curl -sf http://localhost:{port}{q_url}"'
    else:
        return f"Error: unknown action '{action}'. Use push, restart, or health_check."

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
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
    from desmet.adapters._shared.validation import validate_workspace

    passed = validate_workspace(stage, str(workspace))
    if passed:
        return True, (
            "VALIDATION PASSED: All required artifacts for this stage are present. Task complete."
        )

    hints = {
        "requirements": (
            "Ensure docs/design/ contains .md or .txt files covering "
            "functional, non-functional, and acceptance criteria."
        ),
        "codegen": ("Ensure at least one .py file exists and compiles without syntax errors."),
        "testing": ("Ensure test_*.py or *_test.py files exist containing def test_ functions."),
        "deploy": (
            "Ensure both `Dockerfile` and `docker-compose.yaml` exist in the "
            "workspace root, and that docker-compose.yaml uses `${PORT}` "
            "literally on the host side of the port mapping (e.g. "
            '`"${PORT}:8000"`). The harness injects PORT via .env at deploy time.'
        ),
    }
    return False, f"VALIDATION FAILED: {hints.get(stage, 'Required artifacts not found.')}"


# ---------------------------------------------------------------------------
# Format builders
# ---------------------------------------------------------------------------


def _build_callable_tools(
    workspace: Path, tool_names: list[str], platform_id=None, story_id=None, stage_name=None
) -> list:
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
                return _write_file(workspace, path, content, stage=stage_name)

            tools.append(write_file)

        elif name == "list_directory":

            def list_directory(*, path: str = ".") -> str:
                """List files in a directory."""
                return _list_directory(workspace, path)

            tools.append(list_directory)

        elif name == "execute_shell":

            def execute_shell(*, command: str) -> str:
                """Execute a shell command."""
                return _execute_shell(workspace, command, stage=stage_name)

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


def _build_langchain_tools(
    workspace: Path, tool_names: list[str], platform_id=None, story_id=None, stage_name=None
) -> list:
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
                return _write_file(workspace, path, content, stage=stage_name)

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
                return _execute_shell(workspace, command, stage=stage_name)

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


def _build_crewai_tools(
    workspace: Path, tool_names: list[str], platform_id=None, story_id=None, stage_name=None
) -> list:
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
                return _write_file(workspace, path, content, stage=stage_name)

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
                return _execute_shell(workspace, command, stage=stage_name)

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
            description: str = (
                "Deploy to remote server: push artifacts, restart Docker, or health check"
            )
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
                self.result_as_answer = passed
                return message

        tools.append(CheckCompletionTool())

    return tools


def _build_openai_agents_tools(
    workspace: Path, tool_names: list[str], platform_id=None, story_id=None, stage_name=None
) -> list:
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
            return _write_file(workspace, path, content, stage=stage_name)

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
            return _execute_shell(workspace, command, stage=stage_name)

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


def _build_agent_framework_tools(
    workspace: Path, tool_names: list[str], platform_id=None, story_id=None, stage_name=None
) -> list:
    """Return plain callables for Microsoft Agent Framework.

    Produces the same functions as the CALLABLE format.  The Agent Framework
    adapter wraps these with ``@tool`` at runtime when the SDK is available.
    """
    tools: list = []

    if "read_file" in tool_names:

        def read_file(path: str) -> str:
            """Read the contents of a file at the given relative path."""
            return _read_file(workspace, path)

        tools.append(read_file)

    if "write_file" in tool_names:

        def write_file(path: str, content: str) -> str:
            """Write content to a file, creating parent directories as needed."""
            return _write_file(workspace, path, content, stage=stage_name)

        tools.append(write_file)

    if "list_directory" in tool_names:

        def list_directory(path: str = ".") -> str:
            """List files and directories at the given relative path."""
            return _list_directory(workspace, path)

        tools.append(list_directory)

    if "execute_shell" in tool_names:

        def execute_shell(command: str) -> str:
            """Execute a shell command in the project directory."""
            return _execute_shell(workspace, command, stage=stage_name)

        tools.append(execute_shell)

    if "search_code" in tool_names:

        def search_code(pattern: str, path: str = ".") -> str:
            """Search code files for lines matching a regex pattern."""
            return _search_code(workspace, pattern, path)

        tools.append(search_code)

    if "deploy_remote" in tool_names:

        def deploy_remote(action: str, url: str = "/health") -> str:
            """Deploy to remote server: push artifacts, restart Docker, or health check."""
            return _deploy_remote(workspace, platform_id, story_id, action, url)

        tools.append(deploy_remote)

    if "check_completion" in tool_names:

        def check_completion() -> str:
            """Check if all required artifacts are present in the workspace."""
            _, msg = _check_completion(workspace, stage_name)
            return msg

        tools.append(check_completion)

    return tools


def _build_google_adk_tools(
    workspace: Path, tool_names: list[str], platform_id=None, story_id=None, stage_name=None
) -> list:
    """Return plain callables for Google ADK with NO parameter defaults.

    Gemini's function-declaration schema rejects Python parameter defaults —
    ADK strips them and emits a WARNING per tool per stage. By removing
    the defaults at the Python level, the schema builder has nothing to
    strip and the logs stay clean. The LLM is required to pass every
    argument explicitly (docstrings say so).
    """
    tools: list = []

    if "read_file" in tool_names:

        def read_file(path: str) -> str:
            """Read the contents of a file at the given relative path."""
            return _read_file(workspace, path)

        tools.append(read_file)

    if "write_file" in tool_names:

        def write_file(path: str, content: str) -> str:
            """Write content to a file, creating parent directories as needed."""
            return _write_file(workspace, path, content, stage=stage_name)

        tools.append(write_file)

    if "list_directory" in tool_names:

        def list_directory(path: str) -> str:
            """List files and directories at the given relative path. Pass "." for the workspace root."""
            return _list_directory(workspace, path)

        tools.append(list_directory)

    if "execute_shell" in tool_names:

        def execute_shell(command: str) -> str:
            """Execute a shell command in the project directory."""
            return _execute_shell(workspace, command, stage=stage_name)

        tools.append(execute_shell)

    if "search_code" in tool_names:

        def search_code(pattern: str, path: str) -> str:
            """Search code files for lines matching a regex pattern. Pass "." to search the whole workspace."""
            return _search_code(workspace, pattern, path)

        tools.append(search_code)

    if "deploy_remote" in tool_names:

        def deploy_remote(action: str, url: str) -> str:
            """Deploy to remote server: push artifacts, restart Docker, or health check. Pass "/health" for the default health URL."""
            return _deploy_remote(workspace, platform_id, story_id, action, url)

        tools.append(deploy_remote)

    if "check_completion" in tool_names:

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

    if fmt is ToolFormat.AGENT_FRAMEWORK:
        return _build_agent_framework_tools(workspace, tool_names, **kwargs)

    if fmt is ToolFormat.GOOGLE_ADK:
        return _build_google_adk_tools(workspace, tool_names, **kwargs)

    raise ValueError(f"Unknown tool format: {fmt}")


# ---------------------------------------------------------------------------
# Tool splitting (executor / reviewer)
# ---------------------------------------------------------------------------

_REVIEWER_TOOL_NAMES = frozenset({"read_file", "list_directory", "search_code", "check_completion"})


def split_tools(tools: list, fmt: ToolFormat) -> tuple[list, list]:
    """Split *tools* into ``(executor_tools, reviewer_tools)``.

    Executor: all except ``check_completion``.
    Reviewer: ``read_file``, ``list_directory``, ``search_code``, ``check_completion``.

    For AGENT_FRAMEWORK, CALLABLE, and GOOGLE_ADK formats (plain callables),
    tool names are read from ``__name__``. For all other formats, ``.name`` is used.
    """

    def _name(tool) -> str:
        if fmt in (ToolFormat.AGENT_FRAMEWORK, ToolFormat.CALLABLE, ToolFormat.GOOGLE_ADK):
            return getattr(tool, "__name__", "")
        return getattr(tool, "name", "")

    executor_tools = [t for t in tools if _name(t) != "check_completion"]
    reviewer_tools = [t for t in tools if _name(t) in _REVIEWER_TOOL_NAMES]
    return executor_tools, reviewer_tools
