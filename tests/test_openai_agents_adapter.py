"""Tests for the OpenAI Agents SDK idiomatic adapter (handoff chain)."""
from __future__ import annotations
import inspect

import pytest


class TestImplementationPlan:
    def test_creates_valid_plan(self):
        from desmet.adapters.sdk.openai_agents import ImplementationPlan
        plan = ImplementationPlan(
            steps=["Create models", "Create views"],
            files_to_create=["models.py", "views.py"],
            files_to_modify=[],
        )
        assert len(plan.steps) == 2
        assert plan.files_to_create == ["models.py", "views.py"]

    def test_plan_requires_steps(self):
        from desmet.adapters.sdk.openai_agents import ImplementationPlan
        with pytest.raises(Exception):
            ImplementationPlan(files_to_create=[], files_to_modify=[])


class TestOpenAIRunContext:
    def test_creates_with_none_plan(self):
        from desmet.adapters.sdk.openai_agents import OpenAIRunContext
        ctx = OpenAIRunContext(stage_context=None, plan=None)
        assert ctx.plan is None

    def test_plan_can_be_set(self):
        from desmet.adapters.sdk.openai_agents import OpenAIRunContext, ImplementationPlan
        ctx = OpenAIRunContext(stage_context=None, plan=None)
        ctx.plan = ImplementationPlan(
            steps=["step 1"], files_to_create=[], files_to_modify=[]
        )
        assert ctx.plan is not None
        assert len(ctx.plan.steps) == 1


class TestOpenAIAdapterStructure:
    def test_imports(self):
        from desmet.adapters.sdk.openai_agents import OpenAIAgentsAdapter
        adapter = OpenAIAgentsAdapter()
        assert adapter.TOOL_FORMAT is not None

    def test_observability_mentions_handoff(self):
        from desmet.adapters.sdk.openai_agents import OpenAIAgentsAdapter
        adapter = OpenAIAgentsAdapter()
        info = adapter.get_observability_info()
        assert "handoff" in info.get("notes", "").lower()

    def test_failure_handling_mentions_guardrail(self):
        from desmet.adapters.sdk.openai_agents import OpenAIAgentsAdapter
        adapter = OpenAIAgentsAdapter()
        info = adapter.get_failure_handling_info()
        assert "guardrail" in info.get("notes", "").lower()
        assert info["has_auto_recovery"] is True


# ── Existing interface tests (kept) ──────────────────────────────────────────

@pytest.fixture
def adapter():
    from desmet.adapters.sdk.openai_agents import OpenAIAgentsAdapter
    return OpenAIAgentsAdapter(config={"model": "gpt-4o"})


class TestOpenAIAgentsAdapterInterface:
    def test_has_generate_requirements(self, adapter):
        assert callable(adapter.generate_requirements)

    def test_has_generate_code(self, adapter):
        assert callable(adapter.generate_code)

    def test_has_generate_tests(self, adapter):
        assert callable(adapter.generate_tests)

    def test_has_build_and_deploy(self, adapter):
        assert callable(adapter.build_and_deploy)

    def test_generate_requirements_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.generate_requirements)

    def test_generate_code_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.generate_code)

    def test_generate_tests_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.generate_tests)

    def test_build_and_deploy_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.build_and_deploy)

    def test_platform_info(self, adapter):
        info = adapter.platform_info
        assert info.id == "openai_agents_sdk"
        assert info.name == "OpenAI Agents SDK"

    def test_tool_format_is_openai_agents(self, adapter):
        from desmet.adapters._shared.tools import ToolFormat
        assert adapter.TOOL_FORMAT == ToolFormat.OPENAI_AGENTS

    def test_has_run_agent(self, adapter):
        assert hasattr(adapter, "_run_agent")
        assert callable(adapter._run_agent)

    def test_run_agent_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter._run_agent)

    def test_has_execute_stage(self, adapter):
        assert hasattr(adapter, "_execute_stage")
        assert callable(adapter._execute_stage)

    def test_no_legacy_stub_methods(self, adapter):
        """Adapter must not raise NotImplementedError on stage methods."""
        import ast
        import pathlib
        src = pathlib.Path("src/desmet/adapters/sdk/openai_agents.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise):
                for child in ast.walk(node):
                    if isinstance(child, ast.Name) and child.id == "NotImplementedError":
                        pytest.fail("Adapter still contains NotImplementedError stubs")

    def test_observability_info(self, adapter):
        info = adapter.get_observability_info()
        assert info["has_tracing"] is True
        assert info["trace_format"] == "RunResult"

    def test_failure_handling_info(self, adapter):
        info = adapter.get_failure_handling_info()
        assert info["has_auto_recovery"] is True


def test_run_agent_validates_on_success_path():
    """On the success path (no tripwire, no MaxTurnsExceeded), policy.validate()
    must be called inside the retry-loop Try.body — not only inside except
    handlers or via the post-loop fallback. Pre-fix, the only validate() calls
    were in except handlers plus the post-loop fallback; the success branch of
    Runner.run was reported as success without ever validating the workspace."""
    import ast
    import inspect
    import textwrap
    from desmet.adapters.sdk import openai_agents

    src = textwrap.dedent(inspect.getsource(openai_agents.OpenAIAgentsAdapter._run_agent))
    tree = ast.parse(src)

    def _is_policy_validate_call(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "validate"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "policy"
        )

    # Collect policy.validate() calls that live inside the body of any Try
    # statement (i.e., the success path), as opposed to ExceptHandler bodies
    # (tripwire / MaxTurnsExceeded) or the top-level post-loop fallback.
    in_try_body: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for stmt in node.body:
                for child in ast.walk(stmt):
                    if _is_policy_validate_call(child):
                        in_try_body.add(id(child))

    success_path_calls = [
        node for node in ast.walk(tree)
        if _is_policy_validate_call(node) and id(node) in in_try_body
    ]
    assert success_path_calls, (
        "No policy.validate() call on the Runner.run success path — adapter "
        "would skip validation when the executor returns a final output "
        "without handing off to the reviewer (guardrail never fires)."
    )


def test_reviewer_receives_inspection_tools_only():
    """Reviewer must be built via split_tools so it does not receive write/execute tools.

    Checks both that split_tools is called AND that the reviewer Agent(...)
    construction uses the reviewer-tools slice (not the full `tools` list).
    """
    import ast
    import inspect
    import textwrap
    from desmet.adapters.sdk import openai_agents

    src = textwrap.dedent(inspect.getsource(openai_agents.OpenAIAgentsAdapter._run_agent))
    assert "split_tools(" in src, (
        "split_tools not used for reviewer tool asymmetry — reviewer likely "
        "receives the full tool set."
    )
    assert "ToolFormat.OPENAI_AGENTS" in src or "OPENAI_AGENTS" in src, (
        "ToolFormat.OPENAI_AGENTS not referenced in _run_agent."
    )

    # Walk the AST and find every Agent(...) call with a `tools=` kwarg.
    # Collect the identifier names used as the `tools` value. The full
    # tool set is passed in as the function parameter `tools`; the
    # executor and reviewer must use *distinct* variable names so neither
    # is handed the raw parameter.
    tree = ast.parse(src)
    tool_arg_names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_agent_call = (
            (isinstance(func, ast.Name) and func.id == "Agent")
            or (isinstance(func, ast.Attribute) and func.attr == "Agent")
        )
        if not is_agent_call:
            continue
        for kw in node.keywords:
            if kw.arg == "tools" and isinstance(kw.value, ast.Name):
                tool_arg_names.append(kw.value.id)

    # Any Agent(tools=tools) — passing the raw parameter through — is a
    # violation: it means that agent receives the full tool set including
    # write/execute tools.
    assert "tools" not in tool_arg_names, (
        "An Agent(...) is constructed with tools=tools (the raw parameter), "
        "which means it receives the full tool set. Reviewer and executor "
        "must each receive a split slice from split_tools(). "
        f"Got tool arg names: {tool_arg_names}"
    )
    # And the two constructions must use different variables (executor_tools
    # vs reviewer_tools) — not the same split slice for both.
    assert len(set(tool_arg_names)) >= 2, (
        "Executor and reviewer appear to share the same tool list — the "
        "asymmetric distribution requires different slices. "
        f"Got tool arg names: {tool_arg_names}"
    )


def test_planner_fallback_records_plan_source():
    """Structured-planner exception handling must record trace.metadata['plan_source']."""
    import inspect

    from desmet.adapters.sdk.openai_agents import OpenAIAgentsAdapter

    src = inspect.getsource(OpenAIAgentsAdapter._run_agent)
    assert 'plan_source' in src
    assert 'trace.metadata' in src or 'metadata["plan_source"]' in src or "metadata['plan_source']" in src
    # Must not silently swallow — either logs, records error, or narrows except.
    assert 'errors.append' in src or '_log.warning' in src


def _usage_responses(n):
    from types import SimpleNamespace

    return [
        SimpleNamespace(usage=SimpleNamespace(input_tokens=10, output_tokens=5))
        for _ in range(n)
    ]


async def _fire_hooks(hooks, responses):
    """Mimic the SDK: RunHooks see every LLM call as it ends."""
    for resp in responses:
        await hooks.on_llm_start(None, None, None, [])
        await hooks.on_llm_end(None, None, resp)


async def _run_with_fake_runner(monkeypatch, tmp_path, structured, executor=None, out=None):
    """Run _run_agent with Runner.run faked: the structured planner behaves as
    *structured* says, the free-text planner makes 1 call, and the executor
    makes 1 call unless *executor(hooks)* is given."""
    from types import SimpleNamespace

    pytest.importorskip("agents")
    import agents

    from desmet.adapters._shared.observation import (
        ObservationCollector,
        ObservationRequirements,
    )
    from desmet.adapters._shared.retry import ProgressReporter, RetryPolicy
    from desmet.adapters.sdk.openai_agents import OpenAIAgentsAdapter
    from desmet.harness.context import StageContext
    from desmet.harness.story import DifficultyLevel, UserStory
    from desmet.harness.trace import AgentTrace

    async def fake_run(agent, input=None, max_turns=None, **kw):
        if agent.output_type is not None:
            return structured()
        if agent.name.endswith("_planner"):
            return SimpleNamespace(
                new_items=[], raw_responses=_usage_responses(1), final_output="1. step",
            )
        hooks = kw["hooks"]
        if executor is not None:
            return await executor(hooks)
        resp = _usage_responses(1)
        await _fire_hooks(hooks, resp)
        return SimpleNamespace(new_items=[], raw_responses=resp, final_output="done")

    monkeypatch.setattr(agents.Runner, "run", staticmethod(fake_run))
    adapter = OpenAIAgentsAdapter()
    adapter._model = "gpt-test"
    policy = RetryPolicy(max_retries=0, stage_name="requirements", workspace=tmp_path)
    monkeypatch.setattr(policy, "validate", lambda: (True, "ok"))
    story = UserStory(
        id="US-001", title="t", description="d",
        difficulty=DifficultyLevel.BASIC, category="smoke", prompt="p",
    )
    context = StageContext(story=story, workspace=tmp_path, platform_id="openai_agents")
    collector = ObservationCollector(
        AgentTrace(),
        requirements=ObservationRequirements(
            usage=False, tool_calls=False, llm_duration=False,
            messages=False, iterations=False,
        ),
    )
    if out is not None:
        out.append(collector.trace)
    _, success = await adapter._run_agent(
        "requirements", "p", None, [], collector, context, policy,
        ProgressReporter(callback=None, collector=collector),
    )
    collector.trace.metadata["_test_success"] = success
    return collector.trace


async def test_structured_planner_max_turns_calls_are_recorded(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from desmet.adapters._shared.budget import llm_calls_used

    def structured():
        from agents.exceptions import MaxTurnsExceeded

        exc = MaxTurnsExceeded("planner ran out of turns")
        exc.run_data = SimpleNamespace(new_items=[], raw_responses=_usage_responses(3))
        raise exc

    trace = await _run_with_fake_runner(monkeypatch, tmp_path, structured)
    # structured planner 3 + free-text planner 1 + executor 1
    assert llm_calls_used(trace) == 5
    assert trace.total_tokens_input == 50


async def test_structured_planner_without_plan_calls_are_recorded(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from desmet.adapters._shared.budget import llm_calls_used

    def structured():
        return SimpleNamespace(
            new_items=[], raw_responses=_usage_responses(1), final_output="not a plan",
        )

    trace = await _run_with_fake_runner(monkeypatch, tmp_path, structured)
    assert llm_calls_used(trace) == 3


def _structured_ok():
    from types import SimpleNamespace

    from desmet.adapters._shared.planning import ImplementationPlan

    return SimpleNamespace(
        new_items=[], raw_responses=_usage_responses(1),
        final_output=ImplementationPlan(steps=["s"], files_to_create=[], files_to_modify=[]),
    )


async def test_executor_usage_recorded_once_via_hooks(monkeypatch, tmp_path):
    """Executor usage comes from RunHooks; raw_responses must not add it again."""
    from desmet.adapters._shared.budget import llm_calls_used

    trace = await _run_with_fake_runner(monkeypatch, tmp_path, _structured_ok)
    assert llm_calls_used(trace) == 2  # planner 1 + executor 1
    assert trace.total_tokens_input == 20


async def test_model_behavior_error_keeps_tokens_and_retries(monkeypatch, tmp_path):
    """A ModelBehaviorError mid-run (e.g. hallucinated tool name) ends the
    attempt, not the stage, and the calls made before it stay counted."""
    from types import SimpleNamespace

    pytest.importorskip("agents")

    from agents.exceptions import ModelBehaviorError

    from desmet.adapters._shared.budget import llm_calls_used

    calls = {"n": 0}

    async def executor(hooks):
        calls["n"] += 1
        resp = _usage_responses(2)
        await _fire_hooks(hooks, resp)
        if calls["n"] == 1:
            exc = ModelBehaviorError("Tool not_a_tool not found")
            exc.run_data = SimpleNamespace(new_items=[], raw_responses=resp)
            raise exc
        return SimpleNamespace(new_items=[], raw_responses=resp, final_output="done")

    trace = await _run_with_fake_runner(monkeypatch, tmp_path, _structured_ok, executor)
    assert calls["n"] == 1  # max_retries=0 in the harness: one attempt
    assert llm_calls_used(trace) == 3  # planner 1 + executor 2 before the error
    assert any("ModelBehaviorError" in e for e in trace.errors)


async def test_api_error_mid_run_keeps_recorded_tokens(monkeypatch, tmp_path):
    """A transport error has no run_data; the calls before it must already be
    in the trace (recorded by hooks), not lost with the exception."""
    openai = pytest.importorskip("openai")
    pytest.importorskip("agents")

    from desmet.adapters._shared.budget import llm_calls_used

    import httpx

    async def executor(hooks):
        await _fire_hooks(hooks, _usage_responses(3))
        raise openai.APIConnectionError(request=httpx.Request("POST", "http://x"))

    out: list = []
    with pytest.raises(openai.APIConnectionError):
        await _run_with_fake_runner(monkeypatch, tmp_path, _structured_ok, executor, out)
    assert llm_calls_used(out[0]) == 4  # planner 1 + executor 3 before the error
    assert out[0].total_tokens_input == 40
