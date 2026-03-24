"""Shared prompt builders and agent personas for all platform adapters.

Every adapter builds identical prompts for the four SDLC pipeline stages
(requirements, codegen, testing, deploy).  This module centralises that
logic so each adapter can simply call the builder functions rather than
duplicating the prompt text.
"""

from __future__ import annotations

import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from desmet.harness.results import RequirementsResult
    from desmet.harness.story import UserStory


# =========================================================================
# Environment Context
# =========================================================================

_ENV_CONTEXT_CACHE: str | None = None


def _reset_env_cache() -> None:
    global _ENV_CONTEXT_CACHE
    _ENV_CONTEXT_CACHE = None


def load_environment_context() -> str:
    global _ENV_CONTEXT_CACHE
    if _ENV_CONTEXT_CACHE is not None:
        return _ENV_CONTEXT_CACHE

    config_path = Path(__file__).resolve().parents[3] / "config" / "environment.yaml"
    if not config_path.exists():
        return ""

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
        lines.append(f"- Rules: {' '.join(rules)}")

    _ENV_CONTEXT_CACHE = "\n".join(lines)
    return _ENV_CONTEXT_CACHE


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

STAGE_EXPECTED_OUTPUTS: dict[str, str] = {
    "requirements": "All requirements documents written, UML diagrams in Mermaid format, and each diagram rendered to SVG via execute_shell",
    "codegen": "All required files written to disk using the write_file tool",
    "testing": "Test files written, test suite executed, and results reported",
    "deploy": "Build completed, deployment readiness verified, and any issues reported",
}

# =========================================================================
# Stage → Agent Persona
# =========================================================================

_STAGE_PERSONAS: dict[str, AgentPersona] = {
    "requirements": AgentPersona(
        role="Requirements Analyst",
        goal=(
            "Analyse the user story and produce requirements documents "
            "and UML diagrams in docs/design/"
        ),
        backstory=(
            "You are an experienced business analyst and software architect. "
            "You decompose user stories into structured requirements "
            "specifications, domain models, and UML diagrams."
        ),
    ),
    "codegen": AgentPersona(
        role="Software Developer",
        goal="Complete the assigned programming task by writing all required files",
        backstory=(
            "You are an experienced software developer and architect. "
            "You always write files to disk using the provided tools. "
            "You create complete, well-structured documents and code."
        ),
    ),
    "testing": AgentPersona(
        role="QA Engineer",
        goal="Write comprehensive tests, execute them, and report results",
        backstory=(
            "You are an experienced QA engineer and test automation specialist. "
            "You write thorough unit and integration tests, execute them, "
            "and report precise pass/fail counts."
        ),
    ),
    "deploy": AgentPersona(
        role="DevOps Engineer",
        goal="Build the project and verify it is deployment-ready",
        backstory=(
            "You are an experienced DevOps engineer. "
            "You build projects, resolve dependency issues, "
            "and verify deployment readiness."
        ),
    ),
}


def get_stage_persona(stage_name: str) -> AgentPersona:
    """Return the :class:`AgentPersona` for *stage_name*.

    Raises :exc:`KeyError` if *stage_name* is not one of
    ``requirements``, ``codegen``, ``testing``, or ``deploy``.
    """
    return _STAGE_PERSONAS[stage_name]


# =========================================================================
# Prompt Builders
# =========================================================================


def build_requirements_prompt(story: UserStory) -> str:
    """Build the user-facing prompt for the **requirements** stage."""
    env = load_environment_context()
    prompt = (
        f"You are performing Stage 1: Requirements Analysis.\n"
        f"Your role is to analyse a user story and produce a structured "
        f"requirements specification with supporting diagrams.\n\n"
        f"## User Story\n"
        f"**{story.title}**\n"
        f"{story.description}\n\n"
    )

    if story.acceptance_criteria:
        prompt += "## Acceptance Criteria\n"
        for ac in story.acceptance_criteria:
            prompt += f"- **{ac.id}**: {ac.description}\n"
        prompt += "\n"

    prompt += f"{env}\n\n"

    prompt += (
        "## Tasks\n"
        "1. Decompose the story into functional and non-functional requirements.\n"
        "2. Identify domain entities, relationships, and API endpoints.\n"
        "3. Identify use cases.\n"
        "4. Produce UML diagrams (class, sequence, use-case) in Mermaid format.\n"
        "5. Write all requirements documents and diagrams to `docs/design/`.\n"
        "6. IMPORTANT: After writing all Mermaid diagrams, render EACH one to SVG "
        "using execute_shell. For every .mermaid file, run:\n"
        "   execute_shell: bunx @mermaid-js/mermaid-cli mmdc -i <file>.mermaid -o <file>.svg\n"
        "   Do not skip this step. Each .mermaid file must have a corresponding .svg.\n"
    )

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
    return prompt


def build_testing_prompt(story: UserStory) -> str:
    """Build the user-facing prompt for the **testing** stage."""
    env = load_environment_context()
    return (
        f"Write tests for the following user story, execute them, and "
        f"report the results.\n\n"
        f"## User Story\n"
        f"**{story.title}**\n"
        f"{story.description}\n\n"
        f"## Prompt\n{story.prompt}\n\n"
        f"{env}\n\n"
        f"You must:\n"
        f"1. Read the existing code in the workspace.\n"
        f"2. Write comprehensive unit and integration tests.\n"
        f"3. Run the test suite.\n"
        f"4. Report the number of tests run, passed, and failed.\n"
        f"5. If tests fail, attempt to fix the code and re-run.\n"
    )


def build_deploy_prompt(story: UserStory) -> str:
    """Build the user-facing prompt for the **deploy** stage."""
    env = load_environment_context()
    return (
        f"Build, deploy, and verify the project on the remote server.\n\n"
        f"## User Story\n"
        f"**{story.title}**\n"
        f"{story.description}\n\n"
        f"{env}\n\n"
        f"## Steps\n"
        f"1. Install dependencies: uv sync\n"
        f"2. Run the test suite: uv run pytest\n"
        f"3. Build the package: uv build\n"
        f'4. Push to remote server: deploy_remote(action="push")\n'
        f'5. Start/restart the service: deploy_remote(action="restart")\n'
        f'6. Verify the deployment: deploy_remote(action="health_check")\n'
        f"7. Report success or failure with any issues encountered.\n"
    )


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
