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
