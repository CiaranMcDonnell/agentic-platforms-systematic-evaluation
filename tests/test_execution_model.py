"""Tests for the canonical execution model.

The fixtures under ``tests/fixtures/execution`` are slimmed copies of real
runs (one Langfuse span tree and one local stage file per platform). The
model has to turn every one of them into the same shape: stages in pipeline
order, agent turns with a normalised role, and llm/tool steps.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from desmet.harness.execution_model import (
    ROLE_ORDER,
    STAGE_ORDER,
    ExecutionModel,
    build_from_langfuse,
    build_from_stage_file,
)

FIXTURES = Path(__file__).parent / "fixtures" / "execution"
PLATFORMS = [
    "crewai",
    "langgraph",
    "google_adk",
    "microsoft_agent_framework",
    "openai_agents_sdk",
]


def _langfuse(platform: str) -> dict:
    return json.loads((FIXTURES / f"{platform}_langfuse.json").read_text(encoding="utf-8"))


def _stage_file(platform: str) -> dict:
    return json.loads((FIXTURES / f"{platform}_stages.json").read_text(encoding="utf-8"))


def _roles(model: ExecutionModel, stage_key: str) -> list[str]:
    stage = next(s for s in model.stages if s.key == stage_key)
    return [t.role for t in stage.turns]


def _step_names(model: ExecutionModel) -> set[str]:
    return {step.raw_name for s in model.stages for t in s.turns for step in t.steps}


# ── Shape shared by every platform ──────────────────────────────────────


@pytest.mark.parametrize("platform", PLATFORMS)
def test_langfuse_model_has_pipeline_stages_in_order(platform):
    model = build_from_langfuse(_langfuse(platform), platform_id=platform, story_id="US-001")

    assert model.source == "langfuse"
    assert [s.key for s in model.stages] == list(STAGE_ORDER)


@pytest.mark.parametrize("platform", PLATFORMS)
def test_langfuse_model_turns_have_known_roles(platform):
    model = build_from_langfuse(_langfuse(platform), platform_id=platform, story_id="US-001")

    all_turns = [t for s in model.stages for t in s.turns]
    assert all_turns, "no agent turns recovered"
    unknown = {t.raw_name for t in all_turns if t.role not in ROLE_ORDER}
    assert not unknown, f"unmapped agent names: {unknown}"
    assert all(t.role != "other" for t in all_turns), [
        t.raw_name for t in all_turns if t.role == "other"
    ]


@pytest.mark.parametrize("platform", PLATFORMS)
def test_langfuse_model_steps_are_llm_or_tool(platform):
    model = build_from_langfuse(_langfuse(platform), platform_id=platform, story_id="US-001")

    kinds = {step.kind for s in model.stages for t in s.turns for step in t.steps}
    assert kinds <= {"llm", "tool"}
    assert "llm" in kinds
    assert "tool" in kinds


@pytest.mark.parametrize("platform", PLATFORMS)
def test_langfuse_model_round_trips_through_json(platform):
    model = build_from_langfuse(_langfuse(platform), platform_id=platform, story_id="US-001")

    payload = json.loads(json.dumps(model.to_dict()))
    assert payload["platform_id"] == platform
    assert [s["key"] for s in payload["stages"]] == list(STAGE_ORDER)
    assert payload["summary"]["llm_calls"] > 0


# ── Platform-specific normalisation ─────────────────────────────────────


def test_langgraph_plumbing_chains_are_not_steps():
    model = build_from_langfuse(_langfuse("langgraph"), platform_id="langgraph", story_id="US-001")

    names = _step_names(model)
    for plumbing in ("route_executor", "RunnableSequence", "RunnableLambda", "LangGraph", "tool_node"):
        assert plumbing not in names
    assert "ChatOpenAI" in names
    assert "write_file" in names


def test_langgraph_each_stage_runs_planner_executor_reviewer():
    model = build_from_langfuse(_langfuse("langgraph"), platform_id="langgraph", story_id="US-001")

    for stage in model.stages:
        roles = [t.role for t in stage.turns]
        assert roles[:3] == ["planner", "executor", "reviewer"], (stage.key, roles)


def test_crewai_persona_names_map_to_roles():
    model = build_from_langfuse(_langfuse("crewai"), platform_id="crewai", story_id="US-001")

    by_raw = {t.raw_name: t.role for s in model.stages for t in s.turns}
    assert by_raw["Technical Lead"] == "planner"
    assert by_raw["Code Reviewer"] == "reviewer"
    assert by_raw["Software Developer"] == "executor"
    assert by_raw["QA Engineer"] == "executor"


def test_crewai_tool_names_drop_run_suffix():
    model = build_from_langfuse(_langfuse("crewai"), platform_id="crewai", story_id="US-001")

    tool_names = {step.name for s in model.stages for t in s.turns for step in t.steps if step.kind == "tool"}
    assert "read_file" in tool_names
    assert not any(n.endswith(".run") for n in tool_names)


def test_google_adk_orphan_agents_are_assigned_to_stages_by_name():
    """ADK's OTEL spans are not parented under the harness stage spans."""
    model = build_from_langfuse(_langfuse("google_adk"), platform_id="google_adk", story_id="US-001")

    for stage in model.stages:
        roles = set(_roles(model, stage.key))
        assert {"planner", "executor", "reviewer"} <= roles, (stage.key, roles)


def test_google_adk_picks_latest_attempt_only():
    """Three story attempts live in one trace; the model reports the last one."""
    model = build_from_langfuse(_langfuse("google_adk"), platform_id="google_adk", story_id="US-001")

    assert model.attempts == 3
    codegen = next(s for s in model.stages if s.key == "codegen")
    planners = [t for t in codegen.turns if t.role == "planner"]
    # One planner plus its fallback retry, not three attempts' worth.
    assert len(planners) == 2
    assert [t.is_retry for t in planners] == [False, True]


def test_google_adk_pipeline_and_loop_wrappers_are_not_turns():
    model = build_from_langfuse(_langfuse("google_adk"), platform_id="google_adk", story_id="US-001")

    raw = {t.raw_name for s in model.stages for t in s.turns}
    assert not any(n.endswith(("_pipeline", "_loop")) for n in raw)


def test_agent_framework_manager_turns_and_no_message_plumbing():
    model = build_from_langfuse(
        _langfuse("microsoft_agent_framework"),
        platform_id="microsoft_agent_framework",
        story_id="US-001",
    )

    roles = {t.role for s in model.stages for t in s.turns}
    assert "manager" in roles
    names = _step_names(model)
    assert "message.send" not in names
    assert not any(n.startswith("edge_group") or n.startswith("workflow.") for n in names)


def test_agent_framework_harness_summaries_do_not_double_count_llm_calls():
    """``agent-<name>`` generations are harness summaries, not LLM calls."""
    model = build_from_langfuse(
        _langfuse("microsoft_agent_framework"),
        platform_id="microsoft_agent_framework",
        story_id="US-001",
    )

    llm_names = {step.raw_name for s in model.stages for t in s.turns for step in t.steps if step.kind == "llm"}
    assert not any(n.startswith("agent-") for n in llm_names)


def test_openai_tool_spans_become_tool_steps():
    model = build_from_langfuse(
        _langfuse("openai_agents_sdk"), platform_id="openai_agents_sdk", story_id="US-001"
    )

    steps = [step for s in model.stages for t in s.turns for step in t.steps]
    tools = [step for step in steps if step.kind == "tool"]
    assert {t.name for t in tools} >= {"write_file", "read_file"}
    llm = [step for step in steps if step.kind == "llm"]
    assert all(step.model for step in llm)


# ── Transitions and summary ─────────────────────────────────────────────


def test_transitions_follow_turn_order_within_a_stage():
    model = build_from_langfuse(_langfuse("langgraph"), platform_id="langgraph", story_id="US-001")

    reqs = next(s for s in model.stages if s.key == "requirements")
    turn_ids = [t.id for t in reqs.turns]
    pairs = [(tr.source, tr.target) for tr in model.transitions if tr.source in turn_ids]
    assert (turn_ids[0], turn_ids[1]) in pairs
    assert (turn_ids[1], turn_ids[2]) in pairs


def test_stage_boundaries_produce_stage_transitions():
    model = build_from_langfuse(_langfuse("langgraph"), platform_id="langgraph", story_id="US-001")

    stage_kinds = [tr for tr in model.transitions if tr.kind == "stage"]
    assert len(stage_kinds) == len(STAGE_ORDER) - 1


def test_reviewer_back_to_executor_is_a_retry_transition():
    model = build_from_langfuse(
        _langfuse("microsoft_agent_framework"),
        platform_id="microsoft_agent_framework",
        story_id="US-001",
    )

    turns = {t.id: t for s in model.stages for t in s.turns}
    # MagenticOne routes reviewer → manager → executor; the manager hop must
    # not hide the loop.
    retry_targets = [turns[tr.target] for tr in model.transitions if tr.kind == "retry"]
    assert any(t.role == "executor" and t.is_retry for t in retry_targets), (
        "expected reviewer→executor loop in Agent Framework run"
    )
    assert model.summary["retries"] >= 1


def test_summary_aggregates_per_stage_and_role():
    model = build_from_langfuse(_langfuse("crewai"), platform_id="crewai", story_id="US-001")

    testing = next(s for s in model.stages if s.key == "testing")
    executor = testing.summary["executor"]
    assert executor["turns"] == 1
    assert executor["llm_calls"] == 7
    assert executor["tool_calls"] == 10
    assert executor["tokens"] > 0
    assert model.summary["tool_calls"] == sum(
        s.summary[r]["tool_calls"] for s in model.stages for r in s.summary
    )


# ── Local stage-file builder ────────────────────────────────────────────


def test_stage_file_builder_matches_langfuse_shape_for_langgraph():
    model = build_from_stage_file(_stage_file("langgraph"))

    assert model.source == "local"
    assert model.platform_id == "langgraph"
    assert [s.key for s in model.stages] == list(STAGE_ORDER)
    for stage in model.stages:
        roles = [t.role for t in stage.turns]
        assert roles[:3] == ["planner", "executor", "reviewer"], (stage.key, roles)


def test_stage_file_builder_attributes_tool_calls_to_executor():
    model = build_from_stage_file(_stage_file("langgraph"))

    reqs = next(s for s in model.stages if s.key == "requirements")
    executor = next(t for t in reqs.turns if t.role == "executor")
    tool_steps = [step for step in executor.steps if step.kind == "tool"]
    assert len(tool_steps) == 18
    assert all(step.success is not None for step in tool_steps)


def test_stage_file_builder_untagged_messages_fall_back_to_single_turn():
    """CrewAI's local trace carries no agent tags: one 'other' turn per stage."""
    model = build_from_stage_file(_stage_file("crewai"))

    assert model.notes, "expected a note explaining the missing attribution"
    populated = [s for s in model.stages if s.turns]
    assert populated, "no stage produced a turn"
    for stage in populated:
        assert len(stage.turns) == 1
        assert stage.turns[0].role == "other"
        assert stage.turns[0].llm_calls > 0
    # Stages that failed before any message still appear, flagged as failed.
    failed = [s for s in model.stages if not s.turns]
    assert all(s.success is False for s in failed)


def test_stage_file_builder_reports_stage_level_tokens():
    """Local messages carry no per-call usage; the stage totals must survive."""
    data = _stage_file("langgraph")
    model = build_from_stage_file(data)

    for stage in model.stages:
        raw = data["stages"][stage.key]
        expected = int(raw["tokens_input"]) + int(raw["tokens_output"])
        assert stage.tokens == expected
    assert model.summary["tokens"] == sum(s.tokens for s in model.stages)


def test_langfuse_stage_tokens_sum_turn_tokens():
    model = build_from_langfuse(_langfuse("langgraph"), platform_id="langgraph", story_id="US-001")

    for stage in model.stages:
        assert stage.tokens == sum(t.tokens for t in stage.turns)
        assert stage.tokens > 0


def test_stage_file_builder_strips_stage_prefix_from_agent_names():
    model = build_from_stage_file(_stage_file("microsoft_agent_framework"))

    testing = next(s for s in model.stages if s.key == "testing")
    roles = set(t.role for t in testing.turns)
    assert {"planner", "executor"} <= roles


def test_stage_file_builder_reports_stage_level_cost():
    data = _stage_file("google_adk")
    model = build_from_stage_file(data)

    for stage in model.stages:
        assert stage.cost_usd == pytest.approx(float(data["stages"][stage.key]["cost_usd"]))
    assert model.summary["cost_usd"] == pytest.approx(sum(s.cost_usd for s in model.stages))


def test_priced_langfuse_steps_take_precedence_over_reported_cost():
    model = build_from_langfuse(_langfuse("langgraph"), platform_id="langgraph", story_id="US-001")
    stage = model.stages[0]
    stage.reported_cost_usd = 9.0
    assert stage.cost_usd == 9.0  # fixture observations are unpriced

    step = next(s for t in stage.turns for s in t.steps if s.kind == "llm")
    step.cost_usd = 0.25
    assert stage.cost_usd == pytest.approx(0.25)
