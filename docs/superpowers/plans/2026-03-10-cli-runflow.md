# CLI Run Flow Improvements Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `up`, `down`, and `status` commands to `desmet-eval` so Docker infrastructure and platform readiness are managed from the CLI.

**Architecture:** A new `infra.py` module handles Docker Compose interaction and platform status checks. Three new CLI commands in `cli.py` delegate to it. The module is self-contained — no changes to the runner, adapters, or existing commands.

**Tech Stack:** Python 3.10+, typer, Rich tables, subprocess (for `docker compose`), importlib

**Spec:** `docs/superpowers/specs/2026-03-10-cli-runflow-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|----------------|
| `src/desmet/infra.py` | Docker Compose interaction, platform/config status checks |
| `tests/test_infra.py` | Unit tests for `infra.py` |

### Modified Files

| File | Change |
|------|--------|
| `src/desmet/cli.py` | Add `up`, `down`, `status` commands (~80 lines) |

---

## Chunk 1: Infrastructure Module + CLI Commands

### Task 1: Create `infra.py` — constants and status checks

**Files:**
- Create: `src/desmet/infra.py`
- Test: `tests/test_infra.py`
- Reference: `infrastructure/docker-compose.yaml` (container names, profiles)
- Reference: `src/desmet/adapters/registry.py` (platform IDs)

- [ ] **Step 1: Write failing tests for `is_package_importable` and constants**

```python
# tests/test_infra.py
"""Tests for infrastructure management module."""

import subprocess
from unittest.mock import patch, MagicMock

import pytest

from desmet.infra import (
    COMPOSE_FILE,
    PLATFORM_CONTAINERS,
    PLATFORM_PACKAGES,
    PROFILE_TARGETS,
    ConfigStatus,
    PlatformStatus,
    get_config_status,
    get_container_status,
    get_platform_statuses,
    is_package_importable,
)


class TestConstants:
    def test_profile_targets_has_all_visual_platforms(self):
        assert "flowise" in PROFILE_TARGETS
        assert "langflow" in PROFILE_TARGETS
        assert "dify" in PROFILE_TARGETS
        assert "n8n" in PROFILE_TARGETS
        assert "langfuse" in PROFILE_TARGETS

    def test_profile_targets_all_includes_everything(self):
        all_profiles = PROFILE_TARGETS["all"]
        for target in ("flowise", "langflow", "dify", "n8n", "langfuse"):
            assert target in all_profiles

    def test_platform_packages_covers_all_python_platforms(self):
        assert PLATFORM_PACKAGES["langgraph"] == "langgraph"
        assert PLATFORM_PACKAGES["crewai"] == "crewai"

    def test_platform_packages_none_for_docker_platforms(self):
        assert PLATFORM_PACKAGES["flowise"] is None
        assert PLATFORM_PACKAGES["dify"] is None
        assert PLATFORM_PACKAGES["n8n"] is None

    def test_platform_containers_none_for_python_platforms(self):
        assert PLATFORM_CONTAINERS["langgraph"] is None
        assert PLATFORM_CONTAINERS["crewai"] is None

    def test_platform_containers_set_for_docker_platforms(self):
        assert PLATFORM_CONTAINERS["flowise"] == "desmet-flowise"
        assert PLATFORM_CONTAINERS["n8n"] == "desmet-n8n"
        assert PLATFORM_CONTAINERS["dify"] == "desmet-dify-api"

    def test_compose_file_points_to_infrastructure(self):
        assert COMPOSE_FILE.name == "docker-compose.yaml"
        assert "infrastructure" in str(COMPOSE_FILE)


class TestIsPackageImportable:
    def test_importable_stdlib(self):
        assert is_package_importable("json") is True

    def test_not_importable(self):
        assert is_package_importable("nonexistent_package_xyz_123") is False


class TestGetContainerStatus:
    @patch("desmet.infra.subprocess.run")
    def test_running_container(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="running\n"
        )
        assert get_container_status("desmet-flowise") == "running"

    @patch("desmet.infra.subprocess.run")
    def test_not_running_container(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="exited\n"
        )
        assert get_container_status("desmet-flowise") == "exited"

    @patch("desmet.infra.subprocess.run")
    def test_container_not_found(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout=""
        )
        assert get_container_status("desmet-flowise") == "not started"

    @patch("desmet.infra.subprocess.run")
    def test_docker_not_available(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        assert get_container_status("desmet-flowise") == "docker not found"


class TestGetPlatformStatuses:
    @patch("desmet.infra.get_container_status")
    @patch("desmet.infra.is_package_importable")
    def test_python_platform_installed(self, mock_import, mock_container):
        mock_import.return_value = True
        mock_container.return_value = "not started"
        statuses = get_platform_statuses()
        lg = next(s for s in statuses if s.platform_id == "langgraph")
        assert lg.infra_type == "none needed"
        assert lg.status == "ready"

    @patch("desmet.infra.get_container_status")
    @patch("desmet.infra.is_package_importable")
    def test_python_platform_not_installed(self, mock_import, mock_container):
        mock_import.return_value = False
        mock_container.return_value = "not started"
        statuses = get_platform_statuses()
        lg = next(s for s in statuses if s.platform_id == "langgraph")
        assert lg.status == "not installed"

    @patch("desmet.infra.get_container_status")
    @patch("desmet.infra.is_package_importable")
    def test_docker_platform_running(self, mock_import, mock_container):
        mock_import.return_value = False
        mock_container.return_value = "running"
        statuses = get_platform_statuses()
        fw = next(s for s in statuses if s.platform_id == "flowise")
        assert fw.infra_type == "Docker"
        assert fw.status == "running"

    @patch("desmet.infra.get_container_status")
    @patch("desmet.infra.is_package_importable")
    def test_docker_platform_not_started(self, mock_import, mock_container):
        mock_import.return_value = False
        mock_container.return_value = "not started"
        statuses = get_platform_statuses()
        fw = next(s for s in statuses if s.platform_id == "flowise")
        assert fw.status == "not started"


class TestGetConfigStatus:
    @patch.dict("os.environ", {"DESMET_MODEL": "gpt-4o", "OPENAI_API_KEY": "sk-test"}, clear=False)
    def test_model_and_key_detected(self):
        status = get_config_status()
        assert status.model == "gpt-4o"
        assert "OPENAI_API_KEY" in status.api_keys_set

    @patch.dict("os.environ", {
        "DESMET_MODEL": "",
        "DEFAULT_MODEL": "",
        "OPENAI_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
        "GOOGLE_API_KEY": "",
        "OPENROUTER_API_KEY": "",
        "LANGFUSE_PUBLIC_KEY": "",
        "LANGFUSE_SECRET_KEY": "",
    }, clear=False)
    @patch("desmet.infra.is_package_importable", return_value=False)
    def test_defaults_when_no_env(self, _mock_import):
        status = get_config_status()
        assert status.model == "gpt-4o"  # default from llm_config
        assert status.api_keys_set == []
        assert status.langfuse_status == "not installed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_infra.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'desmet.infra'`

- [ ] **Step 3: Implement `infra.py`**

```python
# src/desmet/infra.py
"""
Infrastructure management for DESMET evaluation.

Handles Docker Compose interaction and platform readiness checks.
"""

from __future__ import annotations

import importlib
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from desmet.llm_config import DEFAULT_MODEL

# Path to docker-compose.yaml relative to this file
COMPOSE_FILE = (
    Path(__file__).resolve().parent.parent.parent
    / "infrastructure"
    / "docker-compose.yaml"
)

# CLI target -> docker-compose profile(s)
PROFILE_TARGETS: dict[str, list[str]] = {
    "flowise": ["flowise"],
    "langflow": ["langflow"],
    "dify": ["dify"],
    "n8n": ["n8n"],
    "langfuse": ["langfuse"],
    "all": ["flowise", "langflow", "dify", "n8n", "langfuse"],
}

# Platform ID -> importable Python package name (None = Docker-only)
PLATFORM_PACKAGES: dict[str, str | None] = {
    "langgraph": "langgraph",
    "crewai": "crewai",
    "microsoft_autogen": "autogen",
    "openai_agents_sdk": "agents",
    "google_adk": "google.adk",
    "semantic_kernel": "semantic_kernel",
    "flowise": None,
    "langflow": None,
    "dify": None,
    "n8n": None,
}

# Platform ID -> primary Docker container name (None = no Docker needed)
PLATFORM_CONTAINERS: dict[str, str | None] = {
    "langgraph": None,
    "crewai": None,
    "microsoft_autogen": None,
    "openai_agents_sdk": None,
    "google_adk": None,
    "semantic_kernel": None,
    "flowise": "desmet-flowise",
    "langflow": "desmet-langflow",
    "dify": "desmet-dify-api",
    "n8n": "desmet-n8n",
}

# Platform ID -> human-readable name
PLATFORM_NAMES: dict[str, str] = {
    "langgraph": "LangGraph",
    "crewai": "CrewAI",
    "microsoft_autogen": "AutoGen",
    "openai_agents_sdk": "OpenAI Agents SDK",
    "google_adk": "Google ADK",
    "semantic_kernel": "Semantic Kernel",
    "flowise": "Flowise",
    "langflow": "LangFlow",
    "dify": "Dify",
    "n8n": "n8n",
}

# API key env vars to check
_API_KEY_VARS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
)


@dataclass
class PlatformStatus:
    platform_id: str
    name: str
    infra_type: str  # "none needed" | "Docker"
    status: str  # "ready" | "not installed" | "running" | "not started" | "exited" | "docker not found"


@dataclass
class ConfigStatus:
    model: str
    api_keys_set: list[str] = field(default_factory=list)
    langfuse_status: str = "not configured"


def is_package_importable(package_name: str) -> bool:
    """Check if a Python package can be imported."""
    try:
        importlib.import_module(package_name)
        return True
    except ImportError:
        return False


def get_container_status(container_name: str) -> str:
    """Check the status of a Docker container.

    Returns one of: "running", "exited", "not started", "docker not found".
    """
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return "not started"
        return result.output.strip()
    except FileNotFoundError:
        return "docker not found"
    except subprocess.TimeoutExpired:
        return "not started"


def get_platform_statuses() -> list[PlatformStatus]:
    """Get the status of all 10 platforms."""
    statuses = []
    for pid in PLATFORM_PACKAGES:
        name = PLATFORM_NAMES[pid]
        package = PLATFORM_PACKAGES[pid]
        container = PLATFORM_CONTAINERS[pid]

        if package is not None:
            # Python SDK platform
            installed = is_package_importable(package)
            statuses.append(PlatformStatus(
                platform_id=pid,
                name=name,
                infra_type="none needed",
                status="ready" if installed else "not installed",
            ))
        else:
            # Docker platform
            container_status = get_container_status(container) if container else "not started"
            statuses.append(PlatformStatus(
                platform_id=pid,
                name=name,
                infra_type="Docker",
                status=container_status,
            ))

    return statuses


def get_config_status() -> ConfigStatus:
    """Get the current configuration status."""
    model = (
        os.getenv("DESMET_MODEL")
        or os.getenv("DEFAULT_MODEL")
        or DEFAULT_MODEL
    )

    api_keys_set = [var for var in _API_KEY_VARS if os.getenv(var)]

    # Check Langfuse
    langfuse_pub = os.getenv("LANGFUSE_PUBLIC_KEY")
    langfuse_sec = os.getenv("LANGFUSE_SECRET_KEY")
    if langfuse_pub and langfuse_sec:
        langfuse_status = "configured"
    elif is_package_importable("langfuse"):
        langfuse_status = "installed, not configured"
    else:
        langfuse_status = "not installed"

    return ConfigStatus(
        model=model,
        api_keys_set=api_keys_set,
        langfuse_status=langfuse_status,
    )


def compose_up(target: str) -> subprocess.CompletedProcess:
    """Start Docker services for the given target.

    Raises ValueError if the target is not recognized.
    Raises FileNotFoundError if docker compose is not available.
    """
    if target not in PROFILE_TARGETS:
        raise ValueError(
            f"Unknown target '{target}'. "
            f"Available: {', '.join(sorted(PROFILE_TARGETS))}"
        )

    profiles = PROFILE_TARGETS[target]
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE)]
    for p in profiles:
        cmd.extend(["--profile", p])
    cmd.extend(["up", "-d", "--wait"])

    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def compose_down(target: str | None = None) -> subprocess.CompletedProcess:
    """Stop Docker services.

    If target is given, stops only that profile's services.
    If None, stops all DESMET services (all profiles).
    """
    if target and target not in PROFILE_TARGETS:
        raise ValueError(
            f"Unknown target '{target}'. "
            f"Available: {', '.join(sorted(PROFILE_TARGETS))}"
        )

    # All services use profiles, so we must specify profiles explicitly.
    # Without --profile, docker compose down would be a no-op.
    profiles = PROFILE_TARGETS.get(target, PROFILE_TARGETS["all"]) if target else PROFILE_TARGETS["all"]

    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE)]
    for p in profiles:
        cmd.extend(["--profile", p])
    cmd.append("down")

    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_infra.py -v`
Expected: All PASSED

- [ ] **Step 5: Commit**

```bash
git add src/desmet/infra.py tests/test_infra.py
git commit -m "feat(infra): add infrastructure management module with status checks"
```

---

### Task 2: Add `up`, `down`, `status` CLI commands

**Files:**
- Modify: `src/desmet/cli.py:237-251` (insert before dashboard command)
- Reference: `src/desmet/infra.py` (all public functions)

- [ ] **Step 1: Write failing test for CLI commands**

The CLI commands are thin wrappers, so we test they exist and are callable. Create a small test or verify manually.

```python
# tests/test_cli_commands.py
"""Tests for CLI command registration."""

from typer.testing import CliRunner

from desmet.cli import app

runner = CliRunner()


class TestUpCommand:
    def test_no_args_shows_targets(self):
        result = runner.invoke(app, ["up"])
        assert result.exit_code == 0
        assert "flowise" in result.output
        assert "langfuse" in result.output

    def test_invalid_target(self):
        result = runner.invoke(app, ["up", "nonexistent"])
        assert result.exit_code == 1
        assert "Unknown target" in result.output


class TestDownCommand:
    def test_invalid_target(self):
        result = runner.invoke(app, ["down", "nonexistent"])
        assert result.exit_code == 1
        assert "Unknown target" in result.output


class TestStatusCommand:
    def test_status_runs(self):
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "LangGraph" in result.output or "langgraph" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli_commands.py -v`
Expected: FAIL — commands don't exist yet

- [ ] **Step 3: Add `up` command to `cli.py`**

Add after the `list_stories` command (before `dashboard`), around line 237:

```python
# ---------------------------------------------------------------------------
# up
# ---------------------------------------------------------------------------

@app.command()
def up(
    target: str = typer.Argument(None, help="Target to start: flowise, langflow, dify, n8n, langfuse, all"),
):
    """Start Docker infrastructure for a platform."""
    from desmet.infra import PROFILE_TARGETS, compose_up

    if target is None:
        console.print("[bold]Available targets:[/bold]")
        for name in sorted(PROFILE_TARGETS):
            console.print(f"  {name}")
        console.print("\nUsage: desmet-eval up <target>")
        return

    try:
        console.print(f"Starting [cyan]{target}[/cyan]...")
        result = compose_up(target)
        if result.returncode == 0:
            console.print(f"[green]Started {target} successfully.[/green]")
        else:
            console.print(f"[red]Failed to start {target}:[/red]")
            if result.stderr:
                console.print(result.stderr)
            raise typer.Exit(code=1)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)
    except FileNotFoundError:
        console.print("[red]Error:[/red] docker compose not found. Is Docker installed?")
        raise typer.Exit(code=1)
```

- [ ] **Step 4: Add `down` command to `cli.py`**

```python
# ---------------------------------------------------------------------------
# down
# ---------------------------------------------------------------------------

@app.command()
def down(
    target: str = typer.Argument(None, help="Target to stop (omit to stop all)"),
):
    """Stop Docker infrastructure."""
    from desmet.infra import compose_down

    label = target or "all services"
    try:
        console.print(f"Stopping [cyan]{label}[/cyan]...")
        result = compose_down(target)
        if result.returncode == 0:
            console.print(f"[green]Stopped {label}.[/green]")
        else:
            console.print(f"[red]Failed to stop {label}:[/red]")
            if result.stderr:
                console.print(result.stderr)
            raise typer.Exit(code=1)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)
    except FileNotFoundError:
        console.print("[red]Error:[/red] docker compose not found. Is Docker installed?")
        raise typer.Exit(code=1)
```

- [ ] **Step 5: Add `status` command to `cli.py`**

```python
# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

@app.command()
def status():
    """Show platform readiness and configuration."""
    from desmet.infra import get_config_status, get_platform_statuses

    load_dotenv()

    # Platform table
    statuses = get_platform_statuses()

    table = Table(title="DESMET Platform Status")
    table.add_column("Platform", style="cyan")
    table.add_column("Infrastructure")
    table.add_column("Status")

    status_styles = {
        "ready": "[green]ready[/green]",
        "running": "[green]running[/green]",
        "not installed": "[dim]not installed[/dim]",
        "not started": "[yellow]not started[/yellow]",
        "exited": "[red]exited[/red]",
        "docker not found": "[red]docker not found[/red]",
    }

    for ps in statuses:
        styled = status_styles.get(ps.status, ps.status)
        table.add_row(ps.name, ps.infra_type, styled)

    console.print(table)

    # Config info
    cfg = get_config_status()
    console.print(f"\n  Model   : [bold]{cfg.model}[/bold]")

    if cfg.api_keys_set:
        keys = ", ".join(cfg.api_keys_set)
        console.print(f"  API Keys: [green]{keys}[/green]")
    else:
        console.print("  API Keys: [red]none set[/red]")

    langfuse_style = "[green]" if "configured" in cfg.langfuse_status else "[dim]"
    console.print(f"  Langfuse: {langfuse_style}{cfg.langfuse_status}[/{langfuse_style.strip('[')}]")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli_commands.py tests/test_infra.py -v`
Expected: All PASSED

- [ ] **Step 7: Run the full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All existing tests still pass, plus new tests

- [ ] **Step 8: Manual smoke test**

Run: `python -m desmet.cli status`
Expected: Table showing all 10 platforms with their status

Run: `python -m desmet.cli up`
Expected: List of available targets

- [ ] **Step 9: Commit**

```bash
git add src/desmet/cli.py tests/test_cli_commands.py
git commit -m "feat(cli): add up, down, status commands for infrastructure management"
```
