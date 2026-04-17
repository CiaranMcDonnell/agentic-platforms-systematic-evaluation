"""Tests for the shared planning module ``desmet.adapters._shared.planning``."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from desmet.adapters._shared.planning import (
    ImplementationPlan,
    build_executor_instructions,
    format_plan_text,
    parse_plan_text,
)
from desmet.adapters._shared.prompts import AgentPersona


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture()
def sample_plan() -> ImplementationPlan:
    return ImplementationPlan(
        steps=["Create models", "Create views"],
        files_to_create=["models.py"],
        files_to_modify=["views.py"],
    )


@pytest.fixture()
def persona() -> AgentPersona:
    return AgentPersona(
        role="Software Developer",
        goal="Build the feature",
        backstory="You are an experienced developer.",
    )


# =========================================================================
# TestImplementationPlan
# =========================================================================


class TestImplementationPlan:
    def test_creates_with_all_fields(self) -> None:
        plan = ImplementationPlan(
            steps=["step one", "step two"],
            files_to_create=["a.py"],
            files_to_modify=["b.py"],
        )
        assert plan.steps == ["step one", "step two"]
        assert plan.files_to_create == ["a.py"]
        assert plan.files_to_modify == ["b.py"]

    def test_empty_lists_are_valid(self) -> None:
        plan = ImplementationPlan(
            steps=[], files_to_create=[], files_to_modify=[]
        )
        assert plan.steps == []
        assert plan.files_to_create == []
        assert plan.files_to_modify == []

    def test_serializes_to_dict(self) -> None:
        plan = ImplementationPlan(
            steps=["a"], files_to_create=["b.py"], files_to_modify=["c.py"]
        )
        d = plan.model_dump()
        assert d == {
            "steps": ["a"],
            "files_to_create": ["b.py"],
            "files_to_modify": ["c.py"],
        }

    def test_is_pydantic_base_model(self) -> None:
        assert issubclass(ImplementationPlan, BaseModel)


# =========================================================================
# TestFormatPlanText
# =========================================================================


class TestFormatPlanText:
    def test_numbered_steps(self, sample_plan: ImplementationPlan) -> None:
        plan_text, _ = format_plan_text(sample_plan)
        assert "1. Create models" in plan_text
        assert "2. Create views" in plan_text

    def test_files_combined(self, sample_plan: ImplementationPlan) -> None:
        _, files_text = format_plan_text(sample_plan)
        assert "models.py" in files_text
        assert "views.py" in files_text

    def test_no_files_shows_none_specified(self) -> None:
        plan = ImplementationPlan(
            steps=["do something"], files_to_create=[], files_to_modify=[]
        )
        _, files_text = format_plan_text(plan)
        assert files_text == "(none specified)"

    def test_returns_tuple_of_two_strings(
        self, sample_plan: ImplementationPlan
    ) -> None:
        result = format_plan_text(sample_plan)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)


# =========================================================================
# TestBuildExecutorInstructions
# =========================================================================


class TestBuildExecutorInstructions:
    def test_includes_backstory(
        self, persona: AgentPersona, sample_plan: ImplementationPlan
    ) -> None:
        result = build_executor_instructions(persona, sample_plan)
        assert persona.backstory in result

    def test_includes_plan_heading(
        self, persona: AgentPersona, sample_plan: ImplementationPlan
    ) -> None:
        result = build_executor_instructions(persona, sample_plan)
        assert "## Implementation Plan" in result
        assert "1. Create models" in result

    def test_includes_files_heading(
        self, persona: AgentPersona, sample_plan: ImplementationPlan
    ) -> None:
        result = build_executor_instructions(persona, sample_plan)
        assert "## Files" in result
        assert "models.py" in result

    def test_no_system_msg_omits_additional_context(
        self, persona: AgentPersona, sample_plan: ImplementationPlan
    ) -> None:
        result = build_executor_instructions(persona, sample_plan)
        assert "## Additional Context" not in result

    def test_system_msg_appended(
        self, persona: AgentPersona, sample_plan: ImplementationPlan
    ) -> None:
        result = build_executor_instructions(
            persona, sample_plan, system_msg="Extra info here"
        )
        assert "## Additional Context" in result
        assert "Extra info here" in result

    def test_stage_and_workspace_appended(
        self, persona: AgentPersona, sample_plan: ImplementationPlan
    ) -> None:
        result = build_executor_instructions(
            persona, sample_plan, stage="codegen", workspace="/tmp/ws"
        )
        assert "Stage: codegen" in result
        assert "Working directory: /tmp/ws" in result

    def test_no_stage_no_workspace_lines(
        self, persona: AgentPersona, sample_plan: ImplementationPlan
    ) -> None:
        result = build_executor_instructions(persona, sample_plan)
        assert "Stage:" not in result


# =========================================================================
# TestParsePlanText
# =========================================================================


class TestParsePlanText:
    def test_numbered_steps(self) -> None:
        text = "1. Create models\n2. Create views\n3. Write tests"
        plan = parse_plan_text(text)
        assert len(plan.steps) == 3
        assert plan.steps[0] == "Create models"
        assert plan.steps[1] == "Create views"
        assert plan.steps[2] == "Write tests"

    def test_dashed_steps(self) -> None:
        text = "- First step\n- Second step"
        plan = parse_plan_text(text)
        assert len(plan.steps) == 2
        assert plan.steps[0] == "First step"
        assert plan.steps[1] == "Second step"

    def test_parallel_markers_stripped(self) -> None:
        text = "1. [PARALLEL] Create models\n2. Create views"
        plan = parse_plan_text(text)
        assert "[PARALLEL]" not in plan.steps[0]
        assert "Create models" in plan.steps[0]

    def test_returns_implementation_plan(self) -> None:
        text = "1. First step\n2. Second step"
        plan = parse_plan_text(text)
        assert isinstance(plan, ImplementationPlan)
        assert plan.files_to_create == []
        assert plan.files_to_modify == []

    def test_empty_text_returns_single_step(self) -> None:
        plan = parse_plan_text("")
        assert len(plan.steps) == 1

    def test_unparseable_uses_full_text(self) -> None:
        text = "Just do the thing"
        plan = parse_plan_text(text)
        assert len(plan.steps) == 1
        assert plan.steps[0] == "Just do the thing"

    def test_mixed_numbered_and_dashed(self) -> None:
        text = "1. First\n- Second\n2. Third"
        plan = parse_plan_text(text)
        assert len(plan.steps) == 3

    def test_include_parallel_returns_tuple(self) -> None:
        text = "1. [PARALLEL] Create models\n2. Create views"
        result = parse_plan_text(text, include_parallel=True)
        assert isinstance(result, tuple)
        plan, flags = result
        assert isinstance(plan, ImplementationPlan)
        assert flags[0] is True
        assert flags[1] is False
