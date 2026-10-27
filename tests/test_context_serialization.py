"""Tests for StageContext JSON serialization."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from desmet.adapters._shared.prompts import build_codegen_prompt
from desmet.harness.context import StageContext
from desmet.harness.results import RequirementsResult, UMLDiagram
from desmet.harness.story import UserStory, DifficultyLevel


def _make_story() -> UserStory:
    return UserStory(
        id="test_story",
        title="Test Story",
        description="A test story",
        difficulty=DifficultyLevel.BASIC,
        category="test",
        prompt="Build something",
    )


class TestStageContextSerialization:
    def test_to_dict_returns_dict(self, tmp_path):
        ctx = StageContext(story=_make_story(), workspace=tmp_path, platform_id="crewai")
        result = ctx.to_dict()
        assert isinstance(result, dict)
        assert result["platform_id"] == "crewai"

    def test_to_dict_workspace_is_string(self, tmp_path):
        ctx = StageContext(story=_make_story(), workspace=tmp_path)
        result = ctx.to_dict()
        assert isinstance(result["workspace"], str)

    def test_to_dict_excludes_progress_callback(self, tmp_path):
        ctx = StageContext(
            story=_make_story(), workspace=tmp_path,
            progress_callback=lambda msg: None,
        )
        result = ctx.to_dict()
        assert "progress_callback" not in result

    def test_to_dict_is_json_serializable(self, tmp_path):
        ctx = StageContext(story=_make_story(), workspace=tmp_path, platform_id="crewai")
        result = ctx.to_dict()
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

    def test_roundtrip(self, tmp_path):
        ctx = StageContext(
            story=_make_story(),
            workspace=tmp_path,
            platform_id="langgraph",
            max_iterations=30,
            temperature=0.5,
            model="gpt-5.4-2026-03-05",
        )
        d = ctx.to_dict()
        json_str = json.dumps(d)
        restored = StageContext.from_dict(json.loads(json_str))
        assert restored.platform_id == "langgraph"
        assert restored.max_iterations == 30
        assert restored.temperature == 0.5
        assert restored.model == "gpt-5.4-2026-03-05"
        assert restored.story.id == "test_story"
        assert isinstance(restored.workspace, Path)

    def test_from_dict_sets_workspace_as_path(self, tmp_path):
        ctx = StageContext(story=_make_story(), workspace=tmp_path)
        d = ctx.to_dict()
        restored = StageContext.from_dict(d)
        assert isinstance(restored.workspace, Path)


@pytest.mark.parametrize(
    "success,frs", [(True, [{"id": "FR-1", "text": "add items"}]), (False, [])]
)
def test_codegen_prompt_identical_after_container_roundtrip(tmp_path, success, frs):
    story = _make_story()
    ctx = StageContext(story=story, workspace=tmp_path)
    ctx.add_artifacts(
        "requirements",
        RequirementsResult(
            platform_id="p",
            stage_name="requirements",
            success=success,
            functional_requirements=frs,
            uml_diagrams=[UMLDiagram(diagram_type="class", title="t", content="classDiagram")],
        ),
    )
    wire = json.loads(json.dumps(ctx.to_dict()))
    back = StageContext.from_dict(wire)
    prior = back.get_prior_result("requirements")
    assert isinstance(prior, RequirementsResult)
    assert isinstance(prior.uml_diagrams[0], UMLDiagram)
    assert build_codegen_prompt(story, prior_requirements=prior) == build_codegen_prompt(
        story, prior_requirements=ctx.get_prior_result("requirements")
    )
