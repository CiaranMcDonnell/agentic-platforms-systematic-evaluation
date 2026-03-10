"""Shared prompt builders and agent personas for all platform adapters.

Every adapter builds identical prompts for the four SDLC pipeline stages
(requirements, codegen, testing, deploy).  This module centralises that
logic so each adapter can simply call the builder functions rather than
duplicating the prompt text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from desmet.harness.base import RequirementsResult
    from desmet.harness.story import UserStory


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
    "requirements": "All requirements documents and UML diagrams written to disk",
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
            "Analyse the user story and produce a structured "
            "requirements specification"
        ),
        backstory=(
            "You are an experienced software architect and business analyst. "
            "You always write artefacts to disk using the provided tools. "
            "You decompose user stories into clear, actionable requirements."
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
    return (
        f"Analyse the following user story and produce a structured "
        f"requirements specification.\n\n"
        f"## User Story\n"
        f"**{story.title}**\n"
        f"{story.description}\n\n"
        f"## Prompt\n{story.prompt}\n\n"
        f"You must:\n"
        f"1. Decompose the story into functional and non-functional requirements.\n"
        f"2. Identify domain entities, relationships and API endpoints.\n"
        f"3. Identify use cases.\n"
        f"4. Produce UML diagrams (class, sequence, use-case) in PlantUML format.\n"
        f"5. Write all artefacts as files in the workspace.\n"
    )


def build_codegen_prompt(
    story: UserStory,
    prior_requirements: RequirementsResult | None = None,
) -> str:
    """Build the user-facing prompt for the **codegen** stage.

    If *prior_requirements* is provided and is a
    :class:`~desmet.harness.base.RequirementsResult`, its non-empty fields
    are appended so the code-generation agent can use them.
    """
    from desmet.harness.base import RequirementsResult as _RR

    prompt = story.prompt

    if prior_requirements is not None:
        prompt += (
            "\n\n## Prior Requirements Analysis\n"
            "The following requirements were produced in the previous stage. "
            "Use them to guide your implementation.\n"
        )
        if isinstance(prior_requirements, _RR):
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

    return prompt


def build_testing_prompt(story: UserStory) -> str:
    """Build the user-facing prompt for the **testing** stage."""
    return (
        f"Write tests for the following user story, execute them, and "
        f"report the results.\n\n"
        f"## User Story\n"
        f"**{story.title}**\n"
        f"{story.description}\n\n"
        f"## Prompt\n{story.prompt}\n\n"
        f"You must:\n"
        f"1. Read the existing code in the workspace.\n"
        f"2. Write comprehensive unit and integration tests.\n"
        f"3. Run the test suite.\n"
        f"4. Report the number of tests run, passed, and failed.\n"
        f"5. If tests fail, attempt to fix the code and re-run.\n"
    )


def build_deploy_prompt(story: UserStory) -> str:
    """Build the user-facing prompt for the **deploy** stage."""
    return (
        f"Build the project and verify it is deployment-ready.\n\n"
        f"## User Story\n"
        f"**{story.title}**\n"
        f"{story.description}\n\n"
        f"You must:\n"
        f"1. Install all dependencies.\n"
        f"2. Run the build step (compilation, bundling, etc.).\n"
        f"3. Run the test suite to verify the build.\n"
        f"4. Verify the build artefact starts or passes a smoke test.\n"
        f"5. Report whether the project is deployment-ready and list any "
        f"dependency or build issues encountered.\n"
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
