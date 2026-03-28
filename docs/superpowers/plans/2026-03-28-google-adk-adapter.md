# Google ADK Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Google ADK stub adapter with a full implementation using SequentialAgent + LoopAgent orchestration, matching the same ToolAgentAdapter base class pattern as the 4 existing adapters.

**Architecture:** SequentialAgent pipeline with 3 sub-agents (planner → LoopAgent[executor, reviewer]). Planner uses structured output. LoopAgent provides native retry via exit_loop. Callbacks capture token/tool usage for ObservationCollector.

**Tech Stack:** `google-adk[extensions]` (Agent, SequentialAgent, LoopAgent, Runner, InMemorySessionService), `ToolFormat.CALLABLE`, shared `_planning`, `_prompts`, `_tools`, `_observation`, `_retry` modules.

---

### Task 1: Test scaffold — adapter class structure and imports

**Files:**
- Create: `tests/test_google_adk_adapter.py`

- [ ] **Step 1: Write the structural tests**

```python
"""Tests for the Google ADK adapter (SequentialAgent + LoopAgent orchestration)."""
from __future__ import annotations

import inspect

import pytest

from desmet.adapters._tools import ToolFormat


@pytest.fixture
def adapter():
    from desmet.adapters.google_adk import GoogleADKAdapter
    return GoogleADKAdapter(config={"model": "gemini-2.5-flash"})


class TestGoogleADKAdapterInterface:
    def test_imports(self):
        from desmet.adapters.google_adk import GoogleADKAdapter
        adapter = GoogleADKAdapter()
        assert adapter.TOOL_FORMAT == ToolFormat.CALLABLE

    def test_has_generate_requirements(self, adapter):
        assert hasattr(adapter, "generate_requirements")
        assert callable(adapter.generate_requirements)

    def test_has_generate_code(self, adapter):
        assert hasattr(adapter, "generate_code")
        assert callable(adapter.generate_code)

    def test_has_generate_tests(self, adapter):
        assert hasattr(adapter, "generate_tests")
        assert callable(adapter.generate_tests)

    def test_has_build_and_deploy(self, adapter):
        assert hasattr(adapter, "build_and_deploy")
        assert callable(adapter.build_and_deploy)

    def test_has_run_agent(self, adapter):
        assert hasattr(adapter, "_run_agent")
        assert callable(adapter._run_agent)

    def test_run_agent_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter._run_agent)

    def test_has_execute_stage(self, adapter):
        assert hasattr(adapter, "_execute_stage")
        assert callable(adapter._execute_stage)

    def test_generate_requirements_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.generate_requirements)

    def test_generate_code_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.generate_code)

    def test_generate_tests_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.generate_tests)

    def test_build_and_deploy_is_coroutine(self, adapter):
        assert inspect.iscoroutinefunction(adapter.build_and_deploy)

    def test_run_agent_signature(self, adapter):
        sig = inspect.signature(adapter._run_agent)
        params = list(sig.parameters.keys())
        assert "stage_name" in params
        assert "prompt" in params
        assert "collector" in params
        assert "context" in params
        assert "policy" in params
        assert "progress" in params

    def test_no_legacy_stub(self, adapter):
        """Adapter must not raise NotImplementedError on stage methods."""
        import ast
        import pathlib
        src = pathlib.Path("src/desmet/adapters/google_adk.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise):
                for child in ast.walk(node):
                    if isinstance(child, ast.Name) and child.id == "NotImplementedError":
                        pytest.fail("Adapter still contains NotImplementedError stubs")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_google_adk_adapter.py -v`
Expected: FAIL — `GoogleADKAdapter` is still a stub, imports will fail on `TOOL_FORMAT` check.

---

### Task 2: Adapter skeleton — class, lifecycle, platform info

**Files:**
- Modify: `src/desmet/adapters/google_adk.py` (replace entire stub)

- [ ] **Step 1: Write the adapter skeleton**

Replace the entire contents of `src/desmet/adapters/google_adk.py` with:

```python
"""
Google ADK Platform Adapter — SequentialAgent + LoopAgent orchestration.

Architecture:
  SequentialAgent: planner → LoopAgent[executor ⇄ reviewer] → validation
  Planner uses structured output (output_schema=ImplementationPlan).
  LoopAgent provides native retry via exit_loop tool.
  Callbacks capture per-call token/tool usage for ObservationCollector.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from desmet.adapters._base import ToolAgentAdapter
from desmet.adapters._observation import ObservationCollector
from desmet.adapters._planning import (
    ImplementationPlan,
    build_executor_instructions,
    format_plan_text,
    parse_plan_text,
)
from desmet.adapters._prompts import get_stage_persona, get_sub_persona
from desmet.adapters._retry import ProgressReporter, RetryPolicy
from desmet.adapters._tools import ToolFormat, split_tools
from desmet.adapters.registry import load_platform_info
from desmet.harness.context import StageContext
from desmet.harness.models import PlatformInfo
from desmet.llm_config import Provider
from desmet.llm_config import get_config as get_llm_config

_log = logging.getLogger(__name__)


class GoogleADKAdapter(ToolAgentAdapter):
    """Google ADK adapter using SequentialAgent + LoopAgent orchestration."""

    TOOL_FORMAT = ToolFormat.CALLABLE

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._model_id: str | None = None
        self._model_name: str | None = None

    @property
    def platform_info(self) -> PlatformInfo:
        info = load_platform_info("google_adk")
        info.version = self._get_version()
        return info

    def _get_version(self) -> str:
        try:
            import google.adk
            return getattr(google.adk, "__version__", "unknown")
        except ImportError:
            return "not installed"

    def _get_model_name(self) -> str | None:
        return self._model_name

    def _resolve_model_id(self, cfg) -> str:
        """Build the model string for ADK agents.

        Gemini models pass through directly. Non-Gemini models use LiteLLM
        format (``provider/model``) which requires ``google-adk[extensions]``.
        """
        if cfg.provider == Provider.GOOGLE:
            return cfg.model
        prefix_map = {
            Provider.OPENAI: "openai",
            Provider.OPENROUTER: "openrouter",
            Provider.ANTHROPIC: "anthropic",
        }
        prefix = prefix_map.get(cfg.provider, "openai")
        return f"{prefix}/{cfg.model}"

    async def initialize(self) -> None:
        try:
            from google.adk.agents import Agent  # noqa: F401
            from google.adk.agents import SequentialAgent, LoopAgent  # noqa: F401
            from google.adk.runners import Runner  # noqa: F401

            cfg = get_llm_config(model=self.config.get("model"))
            self._model_id = self._resolve_model_id(cfg)
            self._model_name = cfg.model
            self._initialized = True
        except ImportError as e:
            raise RuntimeError(
                f"Failed to import Google ADK: {e}. "
                'Install with: uv pip install "google-adk[extensions]"'
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Google ADK: {e}")

    async def shutdown(self) -> None:
        self._model_id = None
        self._initialized = False

    async def health_check(self) -> bool:
        if not self._initialized or self._model_id is None:
            return False
        try:
            from google.adk.agents import Agent
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService

            agent = Agent(
                name="health_check",
                model=self._model_id,
                instruction="Respond with 'ok'.",
            )
            runner = Runner(
                app_name="desmet_health",
                agent=agent,
                session_service=InMemorySessionService(),
            )
            from google.genai import types
            session = await runner.session_service.create_session(
                app_name="desmet_health", user_id="health",
            )
            async for event in runner.run_async(
                user_id="health",
                session_id=session.id,
                new_message=types.Content(
                    role="user", parts=[types.Part(text="Say 'ok'")],
                ),
            ):
                if event.is_final_response() and event.content:
                    return True
            return False
        except Exception:
            return False

    # ── Core agent runner ─────────────────────────────────────────────

    async def _run_agent(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str | None,
        tools: list,
        collector: ObservationCollector,
        context: StageContext,
        policy: RetryPolicy,
        progress: ProgressReporter,
    ) -> tuple[int, bool]:
        """Run SequentialAgent pipeline: planner → LoopAgent[executor, reviewer].

        Returns (total_iterations, hit_limit).
        """
        raise NotImplementedError("_run_agent not yet implemented")

    # ── Metadata ──────────────────────────────────────────────────────

    def get_observability_info(self) -> dict[str, Any]:
        return {
            "has_tracing": True,
            "has_step_through": False,
            "has_replay": True,
            "has_state_inspection": True,
            "has_memory_inspection": False,
            "trace_format": "Event stream",
            "notes": (
                "SequentialAgent pipeline: planner (structured output) → "
                "LoopAgent[executor ⇄ reviewer]. Event-driven streaming "
                "with after_model_callback for per-call token tracking. "
                "Session state carries plan between agents."
            ),
        }

    def get_failure_handling_info(self) -> dict[str, Any]:
        return {
            "has_checkpointing": True,
            "has_auto_recovery": True,
            "has_graceful_degradation": True,
            "supports_human_handoff": False,
            "is_idempotent": True,
            "notes": (
                "LoopAgent retry with exit_loop tool for native retry. "
                "RunConfig.max_llm_calls as iteration ceiling. "
                "Session state persists across loop iterations."
            ),
        }
```

- [ ] **Step 2: Run tests to verify structural tests pass**

Run: `uv run pytest tests/test_google_adk_adapter.py -v`
Expected: All `TestGoogleADKAdapterInterface` tests PASS except `test_no_legacy_stub` (which will FAIL because `_run_agent` still has `NotImplementedError`).

- [ ] **Step 3: Commit**

```bash
git add src/desmet/adapters/google_adk.py tests/test_google_adk_adapter.py
git commit -m "feat(google-adk): adapter skeleton with lifecycle and platform info"
```

---

### Task 3: Tests and implementation — metadata and observability

**Files:**
- Modify: `tests/test_google_adk_adapter.py`

- [ ] **Step 1: Write metadata tests**

Append to `tests/test_google_adk_adapter.py`:

```python
class TestGoogleADKAdapterStructure:
    def test_platform_info(self):
        from desmet.adapters.google_adk import GoogleADKAdapter
        adapter = GoogleADKAdapter()
        info = adapter.platform_info
        assert info.id == "google_adk"
        assert info.name == "Google ADK"

    def test_resolve_model_google(self):
        from desmet.adapters.google_adk import GoogleADKAdapter
        from desmet.llm_config import LLMConfig, Provider
        adapter = GoogleADKAdapter()
        cfg = LLMConfig(
            model="gemini-2.5-flash", temperature=0.0,
            provider=Provider.GOOGLE, api_key="test",
        )
        assert adapter._resolve_model_id(cfg) == "gemini-2.5-flash"

    def test_resolve_model_openai(self):
        from desmet.adapters.google_adk import GoogleADKAdapter
        from desmet.llm_config import LLMConfig, Provider
        adapter = GoogleADKAdapter()
        cfg = LLMConfig(
            model="gpt-5.4-2026-03-05", temperature=0.0,
            provider=Provider.OPENAI, api_key="test",
        )
        assert adapter._resolve_model_id(cfg) == "openai/gpt-5.4-2026-03-05"

    def test_resolve_model_anthropic(self):
        from desmet.adapters.google_adk import GoogleADKAdapter
        from desmet.llm_config import LLMConfig, Provider
        adapter = GoogleADKAdapter()
        cfg = LLMConfig(
            model="claude-sonnet-4-20250514", temperature=0.0,
            provider=Provider.ANTHROPIC, api_key="test",
        )
        assert adapter._resolve_model_id(cfg) == "anthropic/claude-sonnet-4-20250514"

    def test_resolve_model_openrouter(self):
        from desmet.adapters.google_adk import GoogleADKAdapter
        from desmet.llm_config import LLMConfig, Provider
        adapter = GoogleADKAdapter()
        cfg = LLMConfig(
            model="anthropic/claude-sonnet-4", temperature=0.0,
            provider=Provider.OPENROUTER, api_key="test",
        )
        assert adapter._resolve_model_id(cfg) == "openrouter/anthropic/claude-sonnet-4"


class TestObservabilityMetadata:
    def test_observability_reports_replay(self):
        from desmet.adapters.google_adk import GoogleADKAdapter
        info = GoogleADKAdapter().get_observability_info()
        assert info["has_replay"] is True

    def test_observability_reports_state_inspection(self):
        from desmet.adapters.google_adk import GoogleADKAdapter
        info = GoogleADKAdapter().get_observability_info()
        assert info["has_state_inspection"] is True

    def test_observability_trace_format(self):
        from desmet.adapters.google_adk import GoogleADKAdapter
        info = GoogleADKAdapter().get_observability_info()
        assert info["trace_format"] == "Event stream"

    def test_observability_mentions_sequential(self):
        from desmet.adapters.google_adk import GoogleADKAdapter
        info = GoogleADKAdapter().get_observability_info()
        assert "sequential" in info.get("notes", "").lower()

    def test_failure_handling_reports_auto_recovery(self):
        from desmet.adapters.google_adk import GoogleADKAdapter
        info = GoogleADKAdapter().get_failure_handling_info()
        assert info["has_auto_recovery"] is True

    def test_failure_handling_mentions_loop(self):
        from desmet.adapters.google_adk import GoogleADKAdapter
        info = GoogleADKAdapter().get_failure_handling_info()
        assert "loop" in info.get("notes", "").lower()

    def test_failure_handling_mentions_exit_loop(self):
        from desmet.adapters.google_adk import GoogleADKAdapter
        info = GoogleADKAdapter().get_failure_handling_info()
        assert "exit_loop" in info.get("notes", "").lower()


class TestLifecycle:
    def test_initialize_is_coroutine(self):
        from desmet.adapters.google_adk import GoogleADKAdapter
        assert inspect.iscoroutinefunction(GoogleADKAdapter().initialize)

    def test_shutdown_is_coroutine(self):
        from desmet.adapters.google_adk import GoogleADKAdapter
        assert inspect.iscoroutinefunction(GoogleADKAdapter().shutdown)

    def test_health_check_is_coroutine(self):
        from desmet.adapters.google_adk import GoogleADKAdapter
        assert inspect.iscoroutinefunction(GoogleADKAdapter().health_check)

    @pytest.mark.asyncio
    async def test_shutdown_clears_state(self):
        from desmet.adapters.google_adk import GoogleADKAdapter
        adapter = GoogleADKAdapter()
        await adapter.shutdown()
        assert adapter._model_id is None
        assert adapter._initialized is False
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/test_google_adk_adapter.py::TestGoogleADKAdapterStructure -v && uv run pytest tests/test_google_adk_adapter.py::TestObservabilityMetadata -v && uv run pytest tests/test_google_adk_adapter.py::TestLifecycle -v`
Expected: All PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_google_adk_adapter.py
git commit -m "test(google-adk): metadata, model resolution, and lifecycle tests"
```

---

### Task 4: Implement _run_agent — planner phase

This is the core of the adapter. The planner runs as a standalone `LlmAgent` with `output_schema=ImplementationPlan` before the SequentialAgent pipeline is assembled.

**Files:**
- Modify: `src/desmet/adapters/google_adk.py`

- [ ] **Step 1: Write the planner helper method**

Add the following method to `GoogleADKAdapter`, above `_run_agent`:

```python
    async def _run_planner(
        self,
        stage_name: str,
        prompt: str,
        collector: ObservationCollector,
        progress: ProgressReporter,
        temperature: float = 0.0,
    ) -> ImplementationPlan:
        """Run planner agent with structured output, falling back to text parsing.

        Returns an ImplementationPlan. Records planner messages and usage
        via the collector.
        """
        from google.adk.agents import Agent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        planner_persona = get_sub_persona("planner")

        # Try structured output first
        plan: ImplementationPlan | None = None
        try:
            planner = Agent(
                name=f"desmet_{stage_name}_planner",
                model=self._model_id,
                instruction=planner_persona.backstory,
                output_schema=ImplementationPlan,
                output_key="plan",
                generate_content_config=types.GenerateContentConfig(
                    temperature=temperature,
                ),
            )
            session_svc = InMemorySessionService()
            runner = Runner(
                app_name="desmet_planner",
                agent=planner,
                session_service=session_svc,
            )
            session = await session_svc.create_session(
                app_name="desmet_planner", user_id="eval",
            )

            t0 = time.monotonic()
            async for event in runner.run_async(
                user_id="eval",
                session_id=session.id,
                new_message=types.Content(
                    role="user", parts=[types.Part(text=prompt)],
                ),
            ):
                if event.content and event.content.parts:
                    text = "".join(
                        p.text for p in event.content.parts if hasattr(p, "text") and p.text
                    )
                    if text:
                        collector.record_message(
                            "assistant", text,
                            metadata={"agent": "planner"},
                        )
                # Extract usage from event
                usage = getattr(event, "usage_metadata", None)
                if usage:
                    collector.record_llm_response(raw_usage=usage)

            duration_ms = (time.monotonic() - t0) * 1000
            collector.record_llm_response(raw_usage=None, duration_ms=duration_ms)

            # Extract plan from session state
            plan_data = session.state.get("plan")
            if isinstance(plan_data, ImplementationPlan):
                plan = plan_data
            elif isinstance(plan_data, dict):
                plan = ImplementationPlan.model_validate(plan_data)
            elif isinstance(plan_data, str):
                try:
                    plan = ImplementationPlan.model_validate_json(plan_data)
                except Exception:
                    plan = parse_plan_text(plan_data)
        except Exception as e:
            _log.debug("Structured planner failed: %s — falling back to text", e)

        # Fallback: free-text planning
        if plan is None:
            try:
                planner = Agent(
                    name=f"desmet_{stage_name}_planner_fallback",
                    model=self._model_id,
                    instruction=(
                        f"{planner_persona.backstory}\n\n"
                        "Produce a numbered implementation plan listing steps, "
                        "files to create, and files to modify."
                    ),
                    generate_content_config=types.GenerateContentConfig(
                        temperature=temperature,
                    ),
                )
                session_svc = InMemorySessionService()
                runner = Runner(
                    app_name="desmet_planner_fallback",
                    agent=planner,
                    session_service=session_svc,
                )
                session = await session_svc.create_session(
                    app_name="desmet_planner_fallback", user_id="eval",
                )

                plan_text = ""
                t0 = time.monotonic()
                async for event in runner.run_async(
                    user_id="eval",
                    session_id=session.id,
                    new_message=types.Content(
                        role="user", parts=[types.Part(text=prompt)],
                    ),
                ):
                    if event.content and event.content.parts:
                        text = "".join(
                            p.text for p in event.content.parts
                            if hasattr(p, "text") and p.text
                        )
                        if text:
                            plan_text += text
                            collector.record_message(
                                "assistant", text,
                                metadata={"agent": "planner"},
                            )

                duration_ms = (time.monotonic() - t0) * 1000
                collector.record_llm_response(raw_usage=None, duration_ms=duration_ms)
                plan = parse_plan_text(plan_text)
            except Exception:
                plan = ImplementationPlan(
                    steps=["Execute the task as described"],
                    files_to_create=[],
                    files_to_modify=[],
                )

        progress.agent_status("planner", f"{len(plan.steps)} steps planned")
        return plan
```

- [ ] **Step 2: Run existing tests to verify nothing broke**

Run: `uv run pytest tests/test_google_adk_adapter.py -v -k "not test_no_legacy_stub"`
Expected: All PASS (legacy stub test still expected to fail since `_run_agent` raises `NotImplementedError`).

- [ ] **Step 3: Commit**

```bash
git add src/desmet/adapters/google_adk.py
git commit -m "feat(google-adk): planner phase with structured output and text fallback"
```

---

### Task 5: Fix split_tools for CALLABLE format

`split_tools()` in `_tools.py` uses `getattr(tool, "name", "")` for all non-AGENT_FRAMEWORK formats. But `CALLABLE` tools are plain `def` functions — they have `__name__`, not `.name`. Without this fix, `split_tools` returns all tools as executor tools and zero reviewer tools.

**Files:**
- Modify: `src/desmet/adapters/_tools.py:960-961`
- Modify: `tests/test_adapter_tools.py`

- [ ] **Step 1: Write a failing test for split_tools with CALLABLE format**

Add to `tests/test_adapter_tools.py`:

```python
class TestSplitToolsCallable:
    def test_split_tools_callable_format(self, tmp_path):
        from desmet.adapters._tools import ToolFormat, create_tools, split_tools
        tools = create_tools(
            tmp_path, ["read_file", "write_file", "check_completion"],
            fmt=ToolFormat.CALLABLE, stage_name="codegen",
        )
        executor, reviewer = split_tools(tools, ToolFormat.CALLABLE)
        executor_names = [t.__name__ for t in executor]
        reviewer_names = [t.__name__ for t in reviewer]
        assert "check_completion" not in executor_names
        assert "read_file" in reviewer_names
        assert "check_completion" in reviewer_names
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_adapter_tools.py::TestSplitToolsCallable -v`
Expected: FAIL — reviewer list is empty because `.name` returns `""` for callables.

- [ ] **Step 3: Fix split_tools to handle CALLABLE format**

In `src/desmet/adapters/_tools.py`, line 960-961, change:

```python
    def _name(tool) -> str:
        if fmt is ToolFormat.AGENT_FRAMEWORK:
            return getattr(tool, "__name__", "")
        return getattr(tool, "name", "")
```

to:

```python
    def _name(tool) -> str:
        if fmt in (ToolFormat.AGENT_FRAMEWORK, ToolFormat.CALLABLE):
            return getattr(tool, "__name__", "")
        return getattr(tool, "name", "")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_adapter_tools.py::TestSplitToolsCallable -v`
Expected: PASS.

- [ ] **Step 5: Run all tool tests to verify no regressions**

Run: `uv run pytest tests/test_adapter_tools.py -v`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add src/desmet/adapters/_tools.py tests/test_adapter_tools.py
git commit -m "fix: split_tools handles CALLABLE format via __name__"
```

---

### Task 6: Implement _run_agent — SequentialAgent pipeline with LoopAgent

**Files:**
- Modify: `src/desmet/adapters/google_adk.py`

- [ ] **Step 1: Replace the _run_agent NotImplementedError with the full implementation**

Replace the `_run_agent` method body with:

```python
    async def _run_agent(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str | None,
        tools: list,
        collector: ObservationCollector,
        context: StageContext,
        policy: RetryPolicy,
        progress: ProgressReporter,
    ) -> tuple[int, bool]:
        """Run SequentialAgent pipeline: planner → LoopAgent[executor, reviewer].

        Returns (total_iterations, hit_limit).
        """
        from google.adk.agents import Agent, LoopAgent, SequentialAgent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.adk.tools import exit_loop
        from google.genai import types

        total_iterations = 0
        hit_limit = False

        collector.record_message("user", prompt)

        # ── Step 1: Planner ──────────────────────────────────────────────
        plan = await self._run_planner(
            stage_name, prompt, collector, progress,
            temperature=context.temperature,
        )
        total_iterations += 1

        # ── Step 2: Build executor and reviewer agents ───────────────────
        executor_persona = get_stage_persona(stage_name)
        reviewer_persona = get_sub_persona("reviewer")

        executor_instructions = build_executor_instructions(
            executor_persona, plan, system_msg,
        )

        executor_tools, reviewer_tools = split_tools(tools, self.TOOL_FORMAT)

        gen_config = types.GenerateContentConfig(
            temperature=context.temperature,
        )

        # Callback closures for observation tracking
        def _after_model_callback(callback_context, response):
            """Record token usage from every LLM call."""
            usage = getattr(response, "usage_metadata", None)
            if usage:
                collector.record_llm_response(raw_usage=usage)
            return None

        def _after_tool_callback(tool_context, result, tool):
            """Record tool execution for observation."""
            tool_name = getattr(tool, "name", "") or getattr(tool, "__name__", "unknown")
            args = getattr(tool_context, "function_call_args", {}) or {}
            collector.record_tool_execution(tool_name, args, str(result) if result else "")
            progress.tool_call(tool_name, args)
            return None

        executor_agent = Agent(
            name=f"desmet_{stage_name}_executor",
            model=self._model_id,
            instruction=executor_instructions,
            tools=executor_tools,
            generate_content_config=gen_config,
            after_model_callback=_after_model_callback,
            after_tool_callback=_after_tool_callback,
        )

        reviewer_agent = Agent(
            name=f"desmet_{stage_name}_reviewer",
            model=self._model_id,
            instruction=(
                f"{reviewer_persona.backstory}\n\n"
                "After the executor finishes, inspect the workspace using "
                "the available tools and call check_completion to verify "
                "all artifacts are present.\n"
                "If check_completion reports VALIDATION PASSED, call exit_loop "
                "to signal completion.\n"
                "If validation fails, describe what is missing so the executor "
                "can fix it on the next iteration."
            ),
            tools=reviewer_tools + [exit_loop],
            generate_content_config=gen_config,
            after_model_callback=_after_model_callback,
            after_tool_callback=_after_tool_callback,
        )

        # ── Step 3: Build LoopAgent + SequentialAgent ────────────────────
        loop_budget = max(3, context.max_iterations - 1)

        execute_loop = LoopAgent(
            name=f"desmet_{stage_name}_loop",
            max_iterations=loop_budget,
            sub_agents=[executor_agent, reviewer_agent],
        )

        pipeline = SequentialAgent(
            name=f"desmet_{stage_name}_pipeline",
            sub_agents=[execute_loop],
        )

        # ── Step 4: Stream events ────────────────────────────────────────
        session_svc = InMemorySessionService()
        runner = Runner(
            app_name=f"desmet_{stage_name}",
            agent=pipeline,
            session_service=session_svc,
        )
        session = await session_svc.create_session(
            app_name=f"desmet_{stage_name}", user_id="eval",
        )

        run_config = types.RunConfig(max_llm_calls=context.max_iterations)

        run_t0 = time.monotonic()
        try:
            async for event in runner.run_async(
                user_id="eval",
                session_id=session.id,
                new_message=types.Content(
                    role="user", parts=[types.Part(text=prompt)],
                ),
                run_config=run_config,
            ):
                author = getattr(event, "author", "") or ""

                # Record text content
                if event.content and event.content.parts:
                    text = "".join(
                        p.text for p in event.content.parts
                        if hasattr(p, "text") and p.text
                    )
                    if text:
                        collector.record_message(
                            "assistant", text,
                            metadata={"agent": author},
                        )

                # Count agent turns (not user messages)
                if author and author != "user":
                    total_iterations += 1

                # Report agent activity
                if event.is_final_response():
                    collector.record_message(
                        "assistant",
                        "".join(
                            p.text for p in (event.content.parts if event.content else [])
                            if hasattr(p, "text") and p.text
                        ) or "(final)",
                        metadata={"event": "final_output"},
                    )

                # Check iteration limit
                if total_iterations >= context.max_iterations:
                    hit_limit = True
                    break

        except Exception as e:
            _log.warning("ADK pipeline error: %s", e)
            collector.trace.errors.append(str(e))

        run_duration_ms = (time.monotonic() - run_t0) * 1000

        # Estimate LLM time (total minus tool time)
        tool_time = sum(tc.duration_ms for tc in collector.trace.tool_calls)
        llm_time_estimate = max(0.0, run_duration_ms - tool_time)
        collector.record_llm_response(raw_usage=None, duration_ms=llm_time_estimate)

        # ── Step 5: Final validation ─────────────────────────────────────
        passed, feedback = policy.validate()
        if passed:
            progress.validation_passed()
        else:
            progress.validation_failed(1, 1, feedback)

        collector.mark_iterations(total_iterations)
        return total_iterations, hit_limit
```

- [ ] **Step 2: Run all adapter tests**

Run: `uv run pytest tests/test_google_adk_adapter.py -v`
Expected: All PASS including `test_no_legacy_stub` (no more `NotImplementedError`).

- [ ] **Step 3: Commit**

```bash
git add src/desmet/adapters/google_adk.py
git commit -m "feat(google-adk): implement _run_agent with SequentialAgent + LoopAgent pipeline"
```

---

### Task 7: Registry integration

**Files:**
- Modify: `src/desmet/adapters/registry.py:123`
- Modify: `tests/test_google_adk_adapter.py`

- [ ] **Step 1: Write registry tests**

Append to `tests/test_google_adk_adapter.py`:

```python
class TestRegistryIntegration:
    def test_google_adk_in_implemented_platforms(self):
        from desmet.adapters.registry import list_available_platforms
        platforms = list_available_platforms()
        assert "google_adk" in platforms

    def test_registry_returns_correct_adapter(self):
        from desmet.adapters.registry import get_adapter
        from desmet.adapters.google_adk import GoogleADKAdapter
        adapter = get_adapter("google_adk")
        assert isinstance(adapter, GoogleADKAdapter)

    def test_registry_adapter_has_correct_tool_format(self):
        from desmet.adapters.registry import get_adapter
        adapter = get_adapter("google_adk")
        assert adapter.TOOL_FORMAT == ToolFormat.CALLABLE
```

- [ ] **Step 2: Run registry tests to verify they fail**

Run: `uv run pytest tests/test_google_adk_adapter.py::TestRegistryIntegration -v`
Expected: FAIL — `google_adk` not in `_IMPLEMENTED_PLATFORMS`.

- [ ] **Step 3: Add google_adk to _IMPLEMENTED_PLATFORMS**

In `src/desmet/adapters/registry.py`, line 123, change:

```python
_IMPLEMENTED_PLATFORMS: frozenset[str] = frozenset({"langgraph", "crewai", "openai_agents_sdk", "microsoft_agent_framework"})
```

to:

```python
_IMPLEMENTED_PLATFORMS: frozenset[str] = frozenset({"langgraph", "crewai", "openai_agents_sdk", "microsoft_agent_framework", "google_adk"})
```

- [ ] **Step 4: Run registry tests to verify they pass**

Run: `uv run pytest tests/test_google_adk_adapter.py::TestRegistryIntegration -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/desmet/adapters/registry.py tests/test_google_adk_adapter.py
git commit -m "feat(google-adk): register adapter in _IMPLEMENTED_PLATFORMS"
```

---

### Task 8: Update pyproject.toml dependencies

**Files:**
- Modify: `pyproject.toml:56-58`

- [ ] **Step 1: Update the google-adk optional dependency to include extensions**

In `pyproject.toml`, line 56-58, change:

```toml
google-adk = [
    "google-adk>=1.0.0",
]
```

to:

```toml
google-adk = [
    "google-adk[extensions]>=1.0.0",
]
```

This pulls in LiteLLM for non-Gemini model support.

- [ ] **Step 2: Verify the pyproject.toml parses correctly**

Run: `uv pip install -e ".[google-adk]" --dry-run 2>&1 | head -5`
Expected: No parse errors. Shows resolved packages (may fail on actual install if ADK not available — dry-run is sufficient).

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "build: add google-adk extensions for LiteLLM support"
```

---

### Task 9: Run full test suite and verify

**Files:**
- No new files

- [ ] **Step 1: Run all Google ADK adapter tests**

Run: `uv run pytest tests/test_google_adk_adapter.py -v`
Expected: All tests PASS.

- [ ] **Step 2: Run the full adapter test suite to verify no regressions**

Run: `uv run pytest tests/test_adapter_interface.py tests/test_adapter_tools.py tests/test_adapter_planning.py tests/test_adapter_prompts.py tests/test_adapter_tracing.py -v`
Expected: All existing tests still PASS.

- [ ] **Step 3: Run the other adapter tests to confirm nothing broke**

Run: `uv run pytest tests/test_langgraph_adapter.py tests/test_crewai_adapter.py tests/test_openai_agents_adapter.py tests/test_agent_framework_adapter.py -v`
Expected: All PASS — no regressions.
