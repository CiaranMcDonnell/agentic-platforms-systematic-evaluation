"""
Story Loader

Loads UserStory instances from YAML files, resolving external prompt (.md) and
gherkin (.feature) file references.  Backward-compatible: inline ``prompt``/
``context``/``gherkin`` fields still work when file references are absent.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

from .story import AcceptanceCriterion, DifficultyLevel, UserStory

logger = logging.getLogger(__name__)


class StoryLoadError(Exception):
    """Raised when a story file is malformed or a referenced file is missing."""


# ---------------------------------------------------------------------------
# Evaluation settings (cached from config/platforms.yaml)
# ---------------------------------------------------------------------------

_eval_settings_cache: dict | None = None


def _load_evaluation_settings() -> dict:
    """Load ``evaluation_settings`` from ``config/platforms.yaml``.

    Returns a dict like::

        {
            "time_budgets": {"basic": 600, "intermediate": 1200, "advanced": 2400},
            "iteration_limits": {"basic": 25, "intermediate": 40, "advanced": 60},
        }

    Falls back to empty sub-dicts if the section is absent.
    """
    global _eval_settings_cache  # noqa: PLW0603
    if _eval_settings_cache is not None:
        return _eval_settings_cache

    cfg_path = _find_repo_root() / "config" / "platforms.yaml"
    if cfg_path.exists():
        with open(cfg_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        _eval_settings_cache = data.get("evaluation_settings", {})
    else:
        _eval_settings_cache = {}

    return _eval_settings_cache


# ---------------------------------------------------------------------------
# Internal parsers
# ---------------------------------------------------------------------------

def _parse_prompt_file(content: str) -> tuple[str, str]:
    """Split a prompt ``.md`` file into *(prompt, context)*.

    Expected format::

        # Prompt
        <task instruction text>

        # Context
        <environment/codebase background>

    Returns ``(prompt, context)`` — *context* may be empty if the section is
    absent.
    """
    sections: dict[str, list[str]] = {}
    current: str | None = None

    for line in content.splitlines():
        header = re.match(r"^#\s+(.+)$", line)
        if header:
            current = header.group(1).strip().lower()
            assert current is not None  # re.Match.group() always returns str
            sections[current] = []
        elif current is not None:
            sections[current].append(line)

    prompt = "\n".join(sections.get("prompt", [])).strip()
    context = "\n".join(sections.get("context", [])).strip()

    if not prompt:
        raise StoryLoadError("Prompt file has no '# Prompt' section or it is empty")

    return prompt, context


def _parse_feature_file(content: str) -> dict[str, str]:
    """Map acceptance-criterion IDs to their Gherkin body text.

    Looks for ``Scenario: AC-xxx-x - …`` lines and collects subsequent
    Given/When/Then/And lines as the body for that AC ID.

    Returns ``{"AC-001-1": "Given …\\nWhen …\\nThen …", …}``.
    """
    mapping: dict[str, str] = {}
    current_id: str | None = None
    body_lines: list[str] = []

    for line in content.splitlines():
        scenario = re.match(r"^\s*Scenario:\s+(AC-[\w-]+)\b", line)
        if scenario:
            # Flush previous scenario
            if current_id is not None:
                mapping[current_id] = "\n".join(body_lines).strip()
            current_id = scenario.group(1)
            body_lines = []
        elif current_id is not None:
            stripped = line.strip()
            if stripped.startswith(("Given ", "When ", "Then ", "And ", "But ")):
                body_lines.append(stripped)

    # Flush last scenario
    if current_id is not None:
        mapping[current_id] = "\n".join(body_lines).strip()

    return mapping


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_DATA_DIR: Path | None = None
_REPO_ROOT: Path | None = None


def _find_repo_root() -> Path:
    """Walk up from this file to find the repo root (contains pyproject.toml)."""
    global _REPO_ROOT  # noqa: PLW0603
    if _REPO_ROOT is None:
        candidate = Path(__file__).resolve().parent
        while candidate != candidate.parent:
            if (candidate / "pyproject.toml").exists():
                _REPO_ROOT = candidate
                break
            candidate = candidate.parent
        else:
            raise StoryLoadError("Cannot locate project root (pyproject.toml)")
    return _REPO_ROOT


def _resolve_data_dir(data_dir: Path | str | None = None) -> Path:
    """Return the ``data/`` directory, auto-detected if *data_dir* is None."""
    if data_dir is not None:
        return Path(data_dir)
    global _DATA_DIR  # noqa: PLW0603
    if _DATA_DIR is None:
        _DATA_DIR = _find_repo_root() / "data"
    return _DATA_DIR


def resolve_baseline_dir(baseline_dir: Path | str | None = None) -> Path:
    """Return the baseline repository directory.

    Defaults to ``data/baseline/`` under the project root.
    """
    if baseline_dir is not None:
        return Path(baseline_dir)
    return _resolve_data_dir() / "baseline"


def load_story(
    yaml_path: Path | str,
    data_dir: Path | str | None = None,
) -> UserStory:
    """Load a single story YAML and resolve any external file references.

    Parameters
    ----------
    yaml_path:
        Path to the story ``.yaml`` file.
    data_dir:
        Root ``data/`` directory used to resolve ``prompt_file`` and
        ``gherkin_file`` references.  Auto-detected when *None*.
    """
    yaml_path = Path(yaml_path)
    data_dir = _resolve_data_dir(data_dir)

    if not yaml_path.exists():
        raise StoryLoadError(f"Story file not found: {yaml_path}")

    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise StoryLoadError(f"Expected a YAML mapping in {yaml_path}")

    # --- Resolve prompt / context ----------------------------------------
    prompt = raw.get("prompt", "")
    context = raw.get("context", "")

    prompt_file = raw.get("prompt_file")
    if prompt_file:
        pf = data_dir / prompt_file
        if pf.exists():
            prompt, context = _parse_prompt_file(pf.read_text(encoding="utf-8"))
        elif prompt:
            logger.warning("prompt_file not found: %s — using inline prompt", pf)
        else:
            raise StoryLoadError(f"prompt_file not found: {pf} (and no inline prompt)")

    # --- Resolve gherkin per criterion -----------------------------------
    gherkin_map: dict[str, str] = {}
    gherkin_file = raw.get("gherkin_file")
    if gherkin_file:
        gf = data_dir / gherkin_file
        if gf.exists():
            gherkin_map = _parse_feature_file(gf.read_text(encoding="utf-8"))
        else:
            logger.warning("gherkin_file not found: %s — skipping gherkin enrichment", gf)

    # --- Build acceptance criteria ---------------------------------------
    criteria: list[AcceptanceCriterion] = []
    for ac_raw in raw.get("acceptance_criteria", []):
        ac_id = ac_raw["id"]
        gherkin = ac_raw.get("gherkin") or gherkin_map.get(ac_id)
        criteria.append(AcceptanceCriterion(
            id=ac_id,
            description=ac_raw.get("description", ""),
            gherkin=gherkin,
            verification_method=ac_raw.get("verification_method", "manual"),
        ))

    # --- Resolve per-difficulty defaults from evaluation_settings ---------
    difficulty = DifficultyLevel(raw["difficulty"])
    eval_settings = _load_evaluation_settings()
    default_budget = eval_settings.get("time_budgets", {}).get(difficulty.value, 600)
    default_iters = eval_settings.get("iteration_limits", {}).get(difficulty.value, 50)

    # --- Build UserStory -------------------------------------------------
    return UserStory(
        id=raw["id"],
        title=raw["title"],
        description=raw.get("description", ""),
        difficulty=difficulty,
        category=raw.get("category", ""),
        prompt=prompt,
        context=context,
        tags=raw.get("tags", []),
        acceptance_criteria=criteria,
        time_budget_seconds=raw.get("time_budget_seconds", default_budget),
        max_iterations=raw.get("max_iterations", default_iters),
        target_files=raw.get("target_files", []),
        expected_files_created=raw.get("expected_files_created", []),
        expected_files_modified=raw.get("expected_files_modified", []),
        version=raw.get("version", "1.0"),
        author=raw.get("author", ""),
    )


def load_all_stories(
    stories_dir: Path | str | None = None,
    data_dir: Path | str | None = None,
    difficulty: str | None = None,
) -> list[UserStory]:
    """Discover and load all story YAMLs.

    Parameters
    ----------
    stories_dir:
        Directory containing difficulty sub-folders with YAML files.
        Defaults to ``data/stories/``.
    data_dir:
        Root ``data/`` directory.  Auto-detected when *None*.
    difficulty:
        Optional filter — ``"basic"``, ``"intermediate"``, or ``"advanced"``.
    """
    data_dir = _resolve_data_dir(data_dir)
    if stories_dir is None:
        stories_dir = data_dir / "stories"
    else:
        stories_dir = Path(stories_dir)

    if not stories_dir.exists():
        raise StoryLoadError(f"Stories directory not found: {stories_dir}")

    yaml_files = sorted(stories_dir.rglob("*.yaml"))

    if difficulty:
        yaml_files = [
            p for p in yaml_files
            if p.parent.name == difficulty
        ]

    stories: list[UserStory] = []
    for yf in yaml_files:
        stories.append(load_story(yf, data_dir))

    return stories
