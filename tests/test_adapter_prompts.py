"""Tests for the shared adapter prompts module."""

from __future__ import annotations

import pytest

from desmet.adapters._shared.prompts import (
    STAGE_EXPECTED_OUTPUTS,
    AgentPersona,
    build_codegen_prompt,
    build_deploy_prompt,
    build_requirements_prompt,
    build_system_message,
    build_testing_prompt,
    get_stage_persona,
    get_sub_persona,
)
from desmet.harness.results import RequirementsResult
from desmet.harness.story import DifficultyLevel, UserStory

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_story(**overrides) -> UserStory:
    """Create a minimal UserStory with sensible defaults."""
    defaults = {
        "id": "US999",
        "title": "Test Story Title",
        "description": "A test story description.",
        "difficulty": DifficultyLevel.BASIC,
        "category": "code_generation",
        "prompt": "Implement the widget factory.",
    }
    defaults.update(overrides)
    return UserStory(**defaults)


# ---------------------------------------------------------------------------
# TestBuildRequirementsPrompt
# ---------------------------------------------------------------------------


class TestBuildRequirementsPrompt:
    """build_requirements_prompt includes title, description, and story.prompt."""

    def test_includes_title(self):
        story = _make_story(title="Auth Module")
        result = build_requirements_prompt(story)
        assert "**Auth Module**" in result

    def test_includes_description(self):
        story = _make_story(description="Implement JWT authentication.")
        result = build_requirements_prompt(story)
        assert "Implement JWT authentication." in result

    def test_includes_prompt(self):
        story = _make_story(title="Auth Module", description="Build a REST API with auth.")
        result = build_requirements_prompt(story)
        assert "Build a REST API with auth." in result

    def test_does_not_include_acceptance_criteria(self):
        from desmet.harness.story import AcceptanceCriterion

        story = _make_story(
            acceptance_criteria=[
                AcceptanceCriterion(id="AC1", description="Should pass tests"),
            ],
        )
        result = build_requirements_prompt(story)
        # Acceptance criteria ARE now included in the requirements prompt
        assert "AC1" in result
        assert "Should pass tests" in result

    def test_contains_analysis_instructions(self):
        result = build_requirements_prompt(_make_story())
        assert "Decompose the story into functional and non-functional requirements" in result
        assert "UML diagrams" in result


# ---------------------------------------------------------------------------
# TestBuildCodegenPrompt
# ---------------------------------------------------------------------------


class TestBuildCodegenPrompt:
    """build_codegen_prompt includes story.prompt; prior requirements are optional."""

    def test_includes_story_prompt(self):
        story = _make_story(prompt="Write a calculator module.")
        result = build_codegen_prompt(story)
        assert "Write a calculator module." in result

    def test_no_prior_requirements_section_when_none(self):
        result = build_codegen_prompt(_make_story())
        assert "Prior Requirements Analysis" not in result

    def test_no_prior_requirements_section_when_default(self):
        result = build_codegen_prompt(_make_story(), prior_requirements=None)
        assert "Prior Requirements Analysis" not in result

    def test_with_prior_requirements_includes_fields(self):
        prior = RequirementsResult(
            platform_id="test",
            stage_name="requirements",
            functional_requirements=[{"id": "FR1", "desc": "Login"}],
            non_functional_requirements=[{"id": "NFR1", "desc": "< 200ms"}],
            use_cases=[{"id": "UC1", "desc": "User logs in"}],
            entities=[{"name": "User"}],
            api_endpoints=[{"path": "/login"}],
        )
        result = build_codegen_prompt(_make_story(), prior_requirements=prior)
        assert "Prior Requirements Analysis" in result
        assert "Functional requirements:" in result
        assert "FR1" in result
        assert "Non-functional requirements:" in result
        assert "NFR1" in result
        assert "Use cases:" in result
        assert "UC1" in result
        assert "Entities:" in result
        assert "User" in result
        assert "API endpoints:" in result
        assert "/login" in result

    def test_omits_empty_prior_fields(self):
        prior = RequirementsResult(
            platform_id="test",
            stage_name="requirements",
            functional_requirements=[{"id": "FR1"}],
            # All other lists are empty by default
        )
        result = build_codegen_prompt(_make_story(), prior_requirements=prior)
        assert "Functional requirements:" in result
        assert "Non-functional requirements:" not in result
        assert "Use cases:" not in result
        assert "Entities:" not in result
        assert "API endpoints:" not in result


# ---------------------------------------------------------------------------
# TestBuildDeployPrompt
# ---------------------------------------------------------------------------


class TestBuildDeployPrompt:
    """build_deploy_prompt includes title+description but EXCLUDES story.prompt."""

    def test_includes_title(self):
        story = _make_story(title="Deploy Service")
        result = build_deploy_prompt(story)
        assert "**Deploy Service**" in result

    def test_includes_description(self):
        story = _make_story(description="Deploy the micro-service.")
        result = build_deploy_prompt(story)
        assert "Deploy the micro-service." in result

    def test_excludes_story_prompt(self):
        story = _make_story(
            prompt="UNIQUE_PROMPT_TEXT_SHOULD_NOT_APPEAR",
            title="Title",
            description="Desc",
        )
        result = build_deploy_prompt(story)
        assert "UNIQUE_PROMPT_TEXT_SHOULD_NOT_APPEAR" not in result

    def test_includes_build_instructions(self):
        result = build_deploy_prompt(_make_story())
        assert "uv sync" in result
        assert "deploy_remote" in result

    def test_includes_dockerfile_creation_step(self):
        result = build_deploy_prompt(_make_story())
        assert "Dockerfile" in result
        # The Dockerfile step must specify the full uvicorn invocation as
        # one contiguous string so the agent copies it verbatim into CMD.
        # Asserting the two halves separately would let a future edit
        # split the sentence and silently degrade the contract.
        assert "uvicorn app.main:app --host 0.0.0.0 --port 8000" in result

    def test_includes_compose_creation_step(self):
        result = build_deploy_prompt(_make_story())
        assert "docker-compose.yaml" in result
        # The compose step must include the worked example with literal
        # ${PORT}:8000 so the agent copies the exact form the validator
        # checks for.
        assert "${PORT}:8000" in result

    def test_explains_port_env_injection(self):
        """The prompt must tell the agent WHY ${PORT} matters — without
        the explanation an agent might 'fix' a complaint by hardcoding.
        """
        result = build_deploy_prompt(_make_story())
        assert ".env" in result
        assert "PORT" in result
        # And it must explicitly forbid hardcoding.
        assert "do not hardcode" in result.lower()

    def test_includes_build_directive_in_example(self):
        """The worked compose example must use `build: .` (the Dockerfile
        path) — not `image: ...`. This is what makes the deploy actually
        package the baseline rather than pulling a published image.
        """
        result = build_deploy_prompt(_make_story())
        assert "build: ." in result

    def test_compose_example_is_visually_separated_from_prose(self):
        """The Minimal example block must be visually distinct from the
        surrounding prose — via a Markdown code fence and a blank line
        before the header. Without this, an agent skimming the prompt
        sees the example as continuation text instead of a discrete
        artifact, and the structure becomes load-bearing-by-luck.
        """
        result = build_deploy_prompt(_make_story())
        # Fenced code block is the strongest signal that "this is a literal
        # artifact" — require it.
        assert "```yaml" in result
        # And ensure the example header isn't glued to the previous prose.
        assert "\n\nMinimal example:" in result

    def test_required_deliverables_section_precedes_steps(self):
        """The two deployment artefacts are non-negotiable and must be
        surfaced BEFORE the task list.  Orchestrators that replan mid-run
        (observed on Microsoft Agent Framework) lose the tail of the
        prompt and end up producing generic Flask apps / requirements.txt
        files instead of the artefacts the validator checks for.  Pulling
        the contract into an up-front, unavoidable header keeps it in
        scope across replans.
        """
        result = build_deploy_prompt(_make_story())
        deliverables_idx = result.find("Required Deliverables")
        steps_idx = result.find("## Steps")
        assert deliverables_idx != -1, (
            "Deploy prompt must include a 'Required Deliverables' section"
        )
        assert steps_idx != -1, "Deploy prompt must still include the Steps section"
        assert deliverables_idx < steps_idx, (
            "'Required Deliverables' must appear before '## Steps' so a "
            "replanning orchestrator can't drop the artefact contract."
        )

    def test_required_deliverables_names_both_artefacts(self):
        """The up-front section must name both files verbatim so a skim
        lands on them even without reading further."""
        result = build_deploy_prompt(_make_story())
        deliverables = result.split("## Steps")[0]
        deliverables_section = deliverables[deliverables.find("Required Deliverables") :]
        assert "Dockerfile" in deliverables_section
        assert "docker-compose.yaml" in deliverables_section

    def test_scope_guard_forbids_out_of_story_artefacts(self):
        """An agent that replans mid-run sometimes invents a Flask app or
        unrelated requirements.txt. The prompt must explicitly scope the
        deployment to the user story artefacts only.
        """
        result = build_deploy_prompt(_make_story()).lower()
        # Either phrasing is acceptable — we just need an explicit scope
        # clause that names the prohibition.  Checking for the key word
        # "scope" keeps this flexible across rewrites.
        assert "scope" in result or "do not invent" in result or "do not create" in result

    def test_health_check_is_the_terminal_action(self):
        """A successful health_check must be an explicit stop point.

        Regression guard: on a live Sonnet run, CrewAI Deploy completed
        the real work in 15 tool calls, validator passed, and then the
        agent burned another 257k tokens running ``search_code /./ ``
        and ``list_directory`` exploration calls for no reason. The
        existing 'then STOP' line was too soft to hold against a
        strong model looking for more to do.
        """
        result = build_deploy_prompt(_make_story()).lower()
        # The prompt must tie termination to the health_check outcome
        # specifically — a generic "stop when done" is what we already
        # had and it wasn't enough.
        assert "health_check" in result
        # And must explicitly forbid further tool use after success.
        assert (
            "do not call any more tools" in result
            or "do not call further tools" in result
            or "do not invoke any further tools" in result
            or "do not run any further tools" in result
        )


# ---------------------------------------------------------------------------
# TestBuildTestingPrompt
# ---------------------------------------------------------------------------


class TestBuildTestingPrompt:
    """build_testing_prompt includes story.prompt."""

    def test_includes_story_prompt(self):
        story = _make_story(prompt="Write unit tests for the parser.")
        result = build_testing_prompt(story)
        assert "Write unit tests for the parser." in result

    def test_includes_title_and_description(self):
        story = _make_story(title="Test Parser", description="Parser desc.")
        result = build_testing_prompt(story)
        assert "**Test Parser**" in result
        assert "Parser desc." in result

    def test_includes_testing_instructions(self):
        result = build_testing_prompt(_make_story())
        assert "Read the existing code in the workspace" in result
        assert "Report the number of tests run, passed, and failed" in result


# ---------------------------------------------------------------------------
# TestBuildSystemMessage
# ---------------------------------------------------------------------------


class TestBuildSystemMessage:
    """build_system_message prefers system_prompt, falls back to context, else None."""

    def test_returns_none_when_no_context_or_system_prompt(self):
        story = _make_story(context="", system_prompt=None)
        assert build_system_message(story) is None

    def test_prefers_system_prompt_over_context(self):
        story = _make_story(
            system_prompt="You are a senior developer.",
            context="Some context here.",
        )
        assert build_system_message(story) == "You are a senior developer."

    def test_falls_back_to_context(self):
        story = _make_story(
            system_prompt=None,
            context="Background context for the agent.",
        )
        assert build_system_message(story) == "Background context for the agent."

    def test_returns_none_for_empty_strings(self):
        story = _make_story(system_prompt="", context="")
        assert build_system_message(story) is None


# ---------------------------------------------------------------------------
# TestGetStagePersona
# ---------------------------------------------------------------------------


class TestGetStagePersona:
    """get_stage_persona returns the correct AgentPersona for each stage."""

    def test_requirements_persona(self):
        persona = get_stage_persona("requirements")
        assert isinstance(persona, AgentPersona)
        assert persona.role == "Requirements Analyst"
        assert "requirements documents" in persona.goal
        assert "business analyst" in persona.backstory

    def test_codegen_persona(self):
        persona = get_stage_persona("codegen")
        assert persona.role == "Software Developer"
        assert "programming task" in persona.goal
        assert "software developer" in persona.backstory

    def test_testing_persona(self):
        persona = get_stage_persona("testing")
        assert persona.role == "QA Engineer"
        assert "tests" in persona.goal.lower()
        assert "QA engineer" in persona.backstory

    def test_deploy_persona(self):
        persona = get_stage_persona("deploy")
        assert persona.role == "DevOps Engineer"
        assert "deployment-ready" in persona.goal
        assert "DevOps engineer" in persona.backstory

    def test_unknown_stage_raises_key_error(self):
        with pytest.raises(KeyError):
            get_stage_persona("nonexistent")

    def test_persona_is_frozen(self):
        persona = get_stage_persona("requirements")
        with pytest.raises(AttributeError):
            persona.role = "Hacker"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TestStageExpectedOutputs
# ---------------------------------------------------------------------------


class TestStageExpectedOutputs:
    """STAGE_EXPECTED_OUTPUTS contains all 4 stages with correct values."""

    def test_has_all_four_keys(self):
        assert set(STAGE_EXPECTED_OUTPUTS.keys()) == {
            "requirements",
            "codegen",
            "testing",
            "deploy",
        }

    def test_requirements_value(self):
        val = STAGE_EXPECTED_OUTPUTS["requirements"]
        assert "Requirements documents" in val
        assert "check_completion" in val

    def test_codegen_value(self):
        val = STAGE_EXPECTED_OUTPUTS["codegen"]
        assert "source files" in val
        assert "check_completion" in val

    def test_testing_value(self):
        val = STAGE_EXPECTED_OUTPUTS["testing"]
        assert "test suite executed" in val
        assert "check_completion" in val

    def test_deploy_value(self):
        val = STAGE_EXPECTED_OUTPUTS["deploy"]
        assert "deployment verified" in val
        assert "check_completion" in val


# ---------------------------------------------------------------------------
# TestGetSubPersona
# ---------------------------------------------------------------------------


class TestGetSubPersona:
    """get_sub_persona returns correct AgentPersona for planner and reviewer."""

    def test_planner_persona(self):
        persona = get_sub_persona("planner")
        assert isinstance(persona, AgentPersona)
        assert persona.role == "Technical Lead"
        assert "plan" in persona.goal.lower()

    def test_reviewer_persona(self):
        persona = get_sub_persona("reviewer")
        assert isinstance(persona, AgentPersona)
        assert persona.role == "Code Reviewer"
        assert "validate" in persona.goal.lower()

    def test_reviewer_backstory_does_not_mention_check_completion(self):
        persona = get_sub_persona("reviewer")
        assert "check_completion" not in persona.backstory

    def test_unknown_sub_persona_raises_key_error(self):
        with pytest.raises(KeyError):
            get_sub_persona("nonexistent")

    def test_sub_persona_is_frozen(self):
        persona = get_sub_persona("planner")
        with pytest.raises(AttributeError):
            persona.role = "Hacker"
