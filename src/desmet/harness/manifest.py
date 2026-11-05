"""Reproducibility manifest recorded on each run row."""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from desmet import cost_calculator, llm_config
from desmet.adapters._shared import prompts


def _git(repo_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    return result.stdout if result.returncode == 0 else None


def _run_execution_mode(config: Any, platform_ids: Iterable[str] | None) -> str:
    """The single execution mode of the run, or "mixed" when platforms differ."""
    overrides = config.platform_execution_modes
    if platform_ids is None:
        modes = {config.execution_mode, *overrides.values()}
    else:
        modes = {overrides.get(pid, config.execution_mode) for pid in platform_ids}
    return modes.pop() if len(modes) == 1 else "mixed"


def collect_manifest(
    config: Any,
    repo_root: Path,
    platform_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Collect the settings that identify what produced a run's results.

    *platform_ids* are the platforms in the run; execution is decided per
    platform, so the run-level mode is "mixed" when they differ.
    """
    sha = _git(repo_root, "rev-parse", "HEAD")
    status = _git(repo_root, "status", "--porcelain")
    llm = llm_config.get_config()
    prompts_file = prompts._CONFIG_DIR / "prompts.yaml"
    return {
        "git_sha": sha.strip() if sha is not None and status is not None else None,
        "git_dirty": bool(status.strip()) if sha is not None and status is not None else None,
        "provider": llm.provider.value,
        "deploy_mode": config.deploy_mode,
        "execution_mode": _run_execution_mode(config, platform_ids),
        "stage_timeout_seconds": config.stage_timeout_seconds,
        "prompts_sha256": hashlib.sha256(prompts_file.read_bytes()).hexdigest(),
        "pricing_snapshot": cost_calculator.pricing_snapshot(llm.model),
    }
