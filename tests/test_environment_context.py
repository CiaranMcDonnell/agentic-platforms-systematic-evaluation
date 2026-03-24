"""Tests for environment context loading and prompt injection."""
from types import SimpleNamespace

from desmet.adapters._prompts import (
    build_codegen_prompt,
    build_deploy_prompt,
    build_requirements_prompt,
    build_testing_prompt,
    load_environment_context,
)


def _make_story():
    return SimpleNamespace(
        title="Test", description="Test desc", prompt="Test prompt",
        acceptance_criteria=[], context="", system_prompt="",
    )


def test_load_environment_context_returns_string():
    result = load_environment_context()
    assert isinstance(result, str)
    assert "## Environment" in result


def test_environment_context_contains_key_info():
    result = load_environment_context()
    assert "uv" in result
    assert "pytest" in result
    assert "deploy_remote" in result


def test_environment_context_contains_rules():
    result = load_environment_context()
    assert "Never use pip" in result


def test_requirements_prompt_includes_environment():
    prompt = build_requirements_prompt(_make_story())
    assert "## Environment" in prompt
    assert "uv" in prompt
    assert "mmdc" in prompt


def test_deploy_prompt_includes_environment():
    prompt = build_deploy_prompt(_make_story())
    assert "## Environment" in prompt
    assert "deploy_remote" in prompt


def test_codegen_prompt_includes_environment():
    prompt = build_codegen_prompt(_make_story())
    assert "## Environment" in prompt


def test_testing_prompt_includes_environment():
    prompt = build_testing_prompt(_make_story())
    assert "## Environment" in prompt
    assert "uv" in prompt


def test_all_stage_prompts_include_environment():
    story = _make_story()
    for builder in [build_requirements_prompt, build_testing_prompt, build_deploy_prompt]:
        prompt = builder(story)
        assert "## Environment" in prompt, f"{builder.__name__} missing environment block"
        assert "uv" in prompt
    prompt = build_codegen_prompt(story)
    assert "## Environment" in prompt
