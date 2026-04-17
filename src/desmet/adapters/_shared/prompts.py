"""Shared prompt builders and agent personas for all platform adapters.

Every adapter builds identical prompts for the four SDLC pipeline stages
(requirements, codegen, testing, deploy).  This module centralises that
logic so each adapter can simply call the builder functions rather than
duplicating the prompt text.

All static prompt content (personas, expected outputs, task lists) is
loaded from ``config/prompts.yaml``; only the dynamic assembly logic
(interpolating user stories, environment context, prior results) lives
here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from desmet.harness.results import RequirementsResult
    from desmet.harness.story import UserStory

_CONFIG_DIR = Path(__file__).resolve().parents[4] / "config"


# =========================================================================
# Environment Context (loaded from config/environment.yaml)
# =========================================================================

_ENV_CONTEXT_CACHE: str | None = None


def _reset_env_cache() -> None:
    global _ENV_CONTEXT_CACHE
    _ENV_CONTEXT_CACHE = None


def load_environment_context() -> str:
    global _ENV_CONTEXT_CACHE
    if _ENV_CONTEXT_CACHE is not None:
        return _ENV_CONTEXT_CACHE

    config_path = _CONFIG_DIR / "environment.yaml"
    if not config_path.exists():
        _ENV_CONTEXT_CACHE = ""
        return _ENV_CONTEXT_CACHE

    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    ws = cfg.get("workspace", {})
    dt = cfg.get("deploy_target", {})

    lines = [
        "## Environment",
        f"- OS: {ws.get('os', 'unknown')} (workspace) / {dt.get('os', 'unknown')} (deploy target)",
        f"- Python: {ws.get('python', 'unknown')} via {ws.get('package_manager', 'unknown')} (never use pip)",
        f"- Package manager: {ws.get('package_manager', 'uv')} (uv sync, uv run, uv pip install)",
        f"- Build: {ws.get('build_command', 'uv build')} (produces .whl + .tar.gz in dist/)",
        f"- Test: {ws.get('test_command', 'uv run pytest')}",
        f"- Diagrams: {ws.get('diagram_renderer', '')} -i input.mermaid -o output.{ws.get('diagram_format', 'svg')}",
        "- Shell: available via execute_shell tool",
        "- Deploy: available via deploy_remote tool (push, restart, health_check)",
    ]

    rules = ws.get("rules", [])
    if rules:
        lines.append("## Rules")
        for rule in rules:
            lines.append(f"- {rule}")

    _ENV_CONTEXT_CACHE = "\n".join(lines)
    return _ENV_CONTEXT_CACHE


# =========================================================================
# Prompt config (loaded from config/prompts.yaml)
# =========================================================================

_PROMPTS_CACHE: dict | None = None


def _load_prompts_config() -> dict:
    global _PROMPTS_CACHE
    if _PROMPTS_CACHE is not None:
        return _PROMPTS_CACHE

    config_path = _CONFIG_DIR / "prompts.yaml"
    with open(config_path) as f:
        _PROMPTS_CACHE = yaml.safe_load(f)
    return _PROMPTS_CACHE


def _reset_prompts_cache() -> None:
    global _PROMPTS_CACHE
    _PROMPTS_CACHE = None
    # Also reset the lazy proxy so it re-loads from YAML
    STAGE_EXPECTED_OUTPUTS.clear()
    STAGE_EXPECTED_OUTPUTS._loaded = False


# =========================================================================
# Agent Persona
# =========================================================================


@dataclass(frozen=True)
class AgentPersona:
    """Immutable description of an agent's role, goal, and backstory."""

    role: str
    goal: str
    backstory: str


# =========================================================================
# Stage → Expected Output (used as CrewAI Task.expected_output)
# =========================================================================


def _get_expected_outputs() -> dict[str, str]:
    return _load_prompts_config()["expected_outputs"]


# Module-level proxy so existing ``STAGE_EXPECTED_OUTPUTS["requirements"]``
# access patterns continue to work without changes to callers.
class _ExpectedOutputsProxy(dict):
    """Lazy dict that loads from YAML on first access."""

    _loaded: bool = False

    def _ensure(self) -> None:
        if not self._loaded:
            self.update(_get_expected_outputs())
            self._loaded = True

    def __getitem__(self, key):
        self._ensure()
        return super().__getitem__(key)

    def __contains__(self, key):
        self._ensure()
        return super().__contains__(key)

    def get(self, key, default=None):
        self._ensure()
        return super().get(key, default)

    def items(self):
        self._ensure()
        return super().items()

    def keys(self):
        self._ensure()
        return super().keys()


STAGE_EXPECTED_OUTPUTS: dict[str, str] = _ExpectedOutputsProxy()


# =========================================================================
# Stage → Agent Persona
# =========================================================================


def _build_persona(raw: dict) -> AgentPersona:
    return AgentPersona(role=raw["role"], goal=raw["goal"], backstory=raw["backstory"])


def get_stage_persona(stage_name: str) -> AgentPersona:
    """Return the :class:`AgentPersona` for *stage_name*.

    Raises :exc:`KeyError` if *stage_name* is not one of
    ``requirements``, ``codegen``, ``testing``, or ``deploy``.
    """
    cfg = _load_prompts_config()
    return _build_persona(cfg["personas"]["stages"][stage_name])


def get_sub_persona(name: str) -> AgentPersona:
    """Return the :class:`AgentPersona` for sub-persona *name*.

    Valid names: ``planner``, ``reviewer``.
    Raises :exc:`KeyError` if *name* is not recognised.
    """
    cfg = _load_prompts_config()
    return _build_persona(cfg["personas"]["sub"][name])


# =========================================================================
# Prompt Builders
# =========================================================================


def _render_tasks(stage_cfg: dict) -> str:
    """Render a numbered task list from a stage config dict."""
    tasks = stage_cfg.get("tasks", [])
    if not tasks:
        return ""
    preamble = stage_cfg.get("tasks_preamble", "## Tasks")
    lines = [preamble]
    for i, task in enumerate(tasks, 1):
        lines.append(f"{i}. {task}")
    return "\n".join(lines) + "\n"


def build_requirements_prompt(story: UserStory) -> str:
    """Build the user-facing prompt for the **requirements** stage."""
    cfg = _load_prompts_config()["stages"]["requirements"]
    env = load_environment_context()

    prompt = f"{cfg['preamble']}\n\n"
    prompt += f"## User Story\n**{story.title}**\n{story.description}\n\n"

    if story.acceptance_criteria:
        prompt += "## Acceptance Criteria\n"
        for ac in story.acceptance_criteria:
            prompt += f"- **{ac.id}**: {ac.description}\n"
        prompt += "\n"

    prompt += f"{env}\n\n"
    prompt += _render_tasks(cfg)
    return prompt


def build_codegen_prompt(
    story: UserStory,
    prior_requirements: RequirementsResult | None = None,
) -> str:
    """Build the user-facing prompt for the **codegen** stage.

    If *prior_requirements* is provided and is a
    :class:`~desmet.harness.base.RequirementsResult`, its non-empty fields
    are appended so the code-generation agent can use them.
    """
    from desmet.harness.results import RequirementsResult

    cfg = _load_prompts_config()["stages"]["codegen"]
    env = load_environment_context()
    prompt = story.prompt

    if prior_requirements is not None:
        prompt += (
            "\n\n## Prior Requirements Analysis\n"
            "The following requirements were produced in the previous stage. "
            "Use them to guide your implementation.\n"
        )
        if isinstance(prior_requirements, RequirementsResult):
            if prior_requirements.functional_requirements:
                prompt += f"\nFunctional requirements: {prior_requirements.functional_requirements}"
            if prior_requirements.non_functional_requirements:
                prompt += f"\nNon-functional requirements: {prior_requirements.non_functional_requirements}"
            if prior_requirements.use_cases:
                prompt += f"\nUse cases: {prior_requirements.use_cases}"
            if prior_requirements.entities:
                prompt += f"\nEntities: {prior_requirements.entities}"
            if prior_requirements.api_endpoints:
                prompt += f"\nAPI endpoints: {prior_requirements.api_endpoints}"

    prompt += f"\n\n{env}\n"

    suffix = cfg.get("suffix", "")
    if suffix:
        prompt += f"\n{suffix}\n"

    prompt += _render_tasks(cfg)
    return prompt


def build_testing_prompt(story: UserStory) -> str:
    """Build the user-facing prompt for the **testing** stage."""
    cfg = _load_prompts_config()["stages"]["testing"]
    env = load_environment_context()

    prompt = f"{cfg['preamble']}\n\n"
    prompt += f"## User Story\n**{story.title}**\n{story.description}\n\n"
    prompt += f"## Prompt\n{story.prompt}\n\n"
    prompt += f"{env}\n\n"
    prompt += _render_tasks(cfg)
    return prompt


def build_deploy_prompt(story: UserStory) -> str:
    """Build the user-facing prompt for the **deploy** stage."""
    cfg = _load_prompts_config()["stages"]["deploy"]
    env = load_environment_context()

    prompt = f"{cfg['preamble']}\n\n"
    prompt += f"## User Story\n**{story.title}**\n{story.description}\n\n"
    prompt += f"{env}\n\n"
    prompt += _render_tasks(cfg)
    return prompt


def build_system_message(story: UserStory) -> str | None:
    """Return a system message for the agent, or ``None``.

    Prefers :attr:`story.system_prompt` if truthy, falls back to
    :attr:`story.context` if non-empty, and returns ``None`` otherwise.
    """
    if story.system_prompt:
        return story.system_prompt
    if story.context:
        return story.context
    return None
