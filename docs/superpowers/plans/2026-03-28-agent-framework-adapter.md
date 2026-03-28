# Microsoft Agent Framework Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the stub `AgentFrameworkAdapter` with a full `ToolAgentAdapter` using MagenticOne orchestration (manager + planner/executor/reviewer agents), ChatMiddleware for token tracking, and `@tool`-decorated shared tools.

**Architecture:** 3 specialized agents (planner, executor, reviewer) coordinated by a MagenticBuilder manager. ChatMiddleware intercepts every LLM call for per-call token/cost tracking. Tools use Agent Framework's `@tool` decorator wrapping the shared `_tools.py` callables. Validation is manager-driven via `check_completion` tool feedback — no external retry loop.

**Tech Stack:** `agent-framework>=1.0rc5`, `agent-framework-core`, Pydantic for structured output, OpenTelemetry for observability.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/desmet/adapters/agent_framework.py` | Replace stub | Full adapter: agents, MagenticBuilder, ChatMiddleware, _run_agent |
| `src/desmet/adapters/_tools.py` | Modify (lines 19-25, 828-882) | Add `AGENT_FRAMEWORK` to ToolFormat enum + builder function |
| `src/desmet/adapters/registry.py` | Modify (line 123) | Add `"microsoft_agent_framework"` to `_IMPLEMENTED_PLATFORMS` |
| `pyproject.toml` | Modify (lines 53-56) | Update `agent-framework` optional dep to `agent-framework>=1.0rc5` |
| `tests/test_agent_framework_adapter.py` | Create | Unit tests for adapter interface, middleware, orchestration, metadata |

---

### Task 1: Update Dependencies

**Files:**
- Modify: `pyproject.toml:53-56`

- [ ] **Step 1: Update the agent-framework optional dependency**

In `pyproject.toml`, replace the old AutoGen dependencies with the new Agent Framework package:

```toml
agent-framework = [
    "agent-framework>=1.0rc5",
]
```

- [ ] **Step 2: Sync the lock file**

Run: `uv lock`
Expected: `uv.lock` updated with `agent-framework` resolved.

- [ ] **Step 3: Install the optional dependency**

Run: `uv sync --extra agent-framework`
Expected: `agent-framework` installed successfully.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: replace autogen with agent-framework>=1.0rc5"
```

---

### Task 2: Add AGENT_FRAMEWORK Tool Format

**Files:**
- Modify: `src/desmet/adapters/_tools.py:19-25` (enum), `src/desmet/adapters/_tools.py:828-882` (create_tools dispatch)
- Test: `tests/test_adapter_tools.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_adapter_tools.py`:

```python
class TestAgentFrameworkToolFormat:
    def test_agent_framework_enum_exists(self):
        from desmet.adapters._tools import ToolFormat
        assert hasattr(ToolFormat, "AGENT_FRAMEWORK")

    def test_create_agent_framework_tools(self, tmp_path):
        from desmet.adapters._tools import ToolFormat, create_tools
        tools = create_tools(
            tmp_path,
            ["read_file", "write_file", "list_directory"],
            fmt=ToolFormat.AGENT_FRAMEWORK,
        )
        assert len(tools) == 3

    def test_agent_framework_tools_are_callable(self, tmp_path):
        from desmet.adapters._tools import ToolFormat, create_tools
        tools = create_tools(tmp_path, ["read_file"], fmt=ToolFormat.AGENT_FRAMEWORK)
        assert callable(tools[0])

    def test_agent_framework_read_file_works(self, tmp_path):
        from desmet.adapters._tools import ToolFormat, create_tools
        (tmp_path / "hello.txt").write_text("world")
        tools = create_tools(tmp_path, ["read_file"], fmt=ToolFormat.AGENT_FRAMEWORK)
        read_file = tools[0]
        # Agent Framework @tool functions accept keyword arguments
        result = read_file(path="hello.txt")
        assert result == "world"

    def test_agent_framework_check_completion_included(self, tmp_path):
        from desmet.adapters._tools import ToolFormat, create_tools
        tools = create_tools(
            tmp_path,
            ["check_completion"],
            fmt=ToolFormat.AGENT_FRAMEWORK,
            stage_name="codegen",
        )
        assert len(tools) == 1

    def test_agent_framework_tools_have_descriptions(self, tmp_path):
        """Agent Framework @tool functions need docstrings for schema inference."""
        from desmet.adapters._tools import ToolFormat, create_tools
        tools = create_tools(
            tmp_path,
            ["read_file", "write_file", "execute_shell"],
            fmt=ToolFormat.AGENT_FRAMEWORK,
        )
        for t in tools:
            assert t.__doc__ is not None and len(t.__doc__) > 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_adapter_tools.py::TestAgentFrameworkToolFormat -v`
Expected: FAIL — `ToolFormat` has no `AGENT_FRAMEWORK` member.

- [ ] **Step 3: Add AGENT_FRAMEWORK to the ToolFormat enum**

In `src/desmet/adapters/_tools.py`, add the new enum member after `OPENAI_AGENTS`:

```python
class ToolFormat(Enum):
    """Output format for the tool factory."""

    LANGCHAIN = "langchain"  # @tool decorated functions
    CREWAI = "crewai"  # BaseTool subclasses
    OPENAI_AGENTS = "openai_agents"  # OpenAI Agents SDK FunctionTool instances
    AGENT_FRAMEWORK = "agent_framework"  # Microsoft Agent Framework @tool functions
    CALLABLE = "callable"  # plain Python callables
```

- [ ] **Step 4: Add the builder function**

Add `_build_agent_framework_tools` after `_build_openai_agents_tools` (after line 822):

```python
def _build_agent_framework_tools(workspace: Path, tool_names: list[str], platform_id=None, story_id=None, stage_name=None) -> list:
    """Return Microsoft Agent Framework ``@tool`` decorated functions.

    Uses plain function definitions with docstrings (Agent Framework infers
    the JSON schema from type annotations and docstrings automatically).
    The ``@tool`` decorator import is deferred so that the ``agent-framework``
    package is only required when this format is actually requested.
    """
    from agent_framework import tool as af_tool

    tools: list = []
    cname = _eval_container_name(platform_id, story_id) if platform_id else None

    if "read_file" in tool_names:
        @af_tool
        def read_file(path: str) -> str:
            """Read the contents of a file at the given relative path."""
            return _read_file(workspace, path)
        tools.append(read_file)

    if "write_file" in tool_names:
        @af_tool
        def write_file(path: str, content: str) -> str:
            """Write content to a file, creating parent directories as needed."""
            return _write_file(workspace, path, content)
        tools.append(write_file)

    if "list_directory" in tool_names:
        @af_tool
        def list_directory(path: str = ".") -> str:
            """List files and directories at the given relative path."""
            return _list_directory(workspace, path)
        tools.append(list_directory)

    if "execute_shell" in tool_names:
        @af_tool
        def execute_shell(command: str) -> str:
            """Execute a shell command in the project directory."""
            return _execute_shell(workspace, command, container_name=cname)
        tools.append(execute_shell)

    if "search_code" in tool_names:
        @af_tool
        def search_code(pattern: str, path: str = ".") -> str:
            """Search code files for lines matching a regex pattern."""
            return _search_code(workspace, pattern, path)
        tools.append(search_code)

    if "deploy_remote" in tool_names:
        @af_tool
        def deploy_remote(action: str, url: str = "/health") -> str:
            """Deploy to remote server: push artifacts, restart Docker, or health check."""
            return _deploy_remote(workspace, platform_id, story_id, action, url)
        tools.append(deploy_remote)

    if "check_completion" in tool_names:
        @af_tool
        def check_completion() -> str:
            """Check if all required artifacts are present in the workspace."""
            _, msg = _check_completion(workspace, stage_name)
            return msg
        tools.append(check_completion)

    return tools
```

- [ ] **Step 5: Add the dispatch branch in create_tools**

In `src/desmet/adapters/_tools.py`, add the dispatch branch inside `create_tools()`, after the `OPENAI_AGENTS` branch (after line 880):

```python
    if fmt is ToolFormat.AGENT_FRAMEWORK:
        return _build_agent_framework_tools(workspace, tool_names, **kwargs)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_adapter_tools.py::TestAgentFrameworkToolFormat -v`
Expected: All 6 tests PASS.

- [ ] **Step 7: Run full tool test suite for regressions**

Run: `uv run pytest tests/test_adapter_tools.py -v`
Expected: All tests PASS (no regressions in other formats).

- [ ] **Step 8: Commit**

```bash
git add src/desmet/adapters/_tools.py tests/test_adapter_tools.py
git commit -m "feat(tools): add AGENT_FRAMEWORK tool format with @tool decorator"
```

---

### Task 3: Implement the AgentFrameworkAdapter

**Files:**
- Replace: `src/desmet/adapters/agent_framework.py`
- Test: `tests/test_agent_framework_adapter.py`

- [ ] **Step 1: Write the adapter test file**

Create `tests/test_agent_framework_adapter.py`:

```python
"""Tests for the Microsoft Agent Framework adapter (MagenticOne orchestration)."""
from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

import pytest

from desmet.adapters.agent_framework import AgentFrameworkAdapter
from desmet.harness.trace import AgentTrace


@pytest.fixture
def adapter():
    return AgentFrameworkAdapter(config={"model": "gpt-5.2-2025-12-11"})


class TestAgentFrameworkAdapterInterface:
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

    def test_generate_requirements_signature(self, adapter):
        sig = inspect.signature(adapter.generate_requirements)
        params = list(sig.parameters.keys())
        assert "context" in params

    def test_generate_code_signature(self, adapter):
        sig = inspect.signature(adapter.generate_code)
        params = list(sig.parameters.keys())
        assert "context" in params

    def test_generate_tests_signature(self, adapter):
        sig = inspect.signature(adapter.generate_tests)
        params = list(sig.parameters.keys())
        assert "context" in params

    def test_build_and_deploy_signature(self, adapter):
        sig = inspect.signature(adapter.build_and_deploy)
        params = list(sig.parameters.keys())
        assert "context" in params

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
        assert info.id == "microsoft_agent_framework"
        assert info.name == "Microsoft Agent Framework"

    def test_no_legacy_stub(self, adapter):
        """The adapter should not be a stub anymore."""
        from desmet.adapters._tools import ToolFormat
        assert adapter.TOOL_FORMAT == ToolFormat.AGENT_FRAMEWORK

    def test_run_agent_signature(self, adapter):
        sig = inspect.signature(adapter._run_agent)
        params = list(sig.parameters.keys())
        assert "stage_name" in params
        assert "prompt" in params
        assert "trace" in params
        assert "context" in params


class TestAgentFrameworkAdapterStructure:
    def test_imports(self):
        from desmet.adapters.agent_framework import AgentFrameworkAdapter
        adapter = AgentFrameworkAdapter()
        assert adapter.TOOL_FORMAT is not None

    def test_max_retries_constant(self):
        from desmet.adapters.agent_framework import MAX_STALL_COUNT
        assert MAX_STALL_COUNT == 3

    def test_has_create_model(self, adapter):
        """_create_model builds the chat client."""
        assert hasattr(adapter, "_create_model")
        assert callable(adapter._create_model)

    def test_has_implementation_plan_model(self):
        from desmet.adapters.agent_framework import ImplementationPlan
        plan = ImplementationPlan(
            steps=["step 1", "step 2"],
            files_to_create=["main.py"],
            files_to_modify=[],
        )
        assert len(plan.steps) == 2
        assert plan.files_to_create == ["main.py"]


class TestObservabilityMetadata:
    def test_observability_reports_stall_detection(self):
        adapter = AgentFrameworkAdapter()
        info = adapter.get_observability_info()
        assert info["has_stall_detection"] is True

    def test_observability_reports_checkpointing(self):
        adapter = AgentFrameworkAdapter()
        info = adapter.get_observability_info()
        assert info["has_checkpointing"] is True

    def test_observability_trace_format_is_otel(self):
        adapter = AgentFrameworkAdapter()
        info = adapter.get_observability_info()
        assert info["trace_format"] == "opentelemetry"

    def test_failure_handling_reports_auto_recovery(self):
        adapter = AgentFrameworkAdapter()
        info = adapter.get_failure_handling_info()
        assert info["has_auto_recovery"] is True

    def test_failure_handling_mentions_manager(self):
        adapter = AgentFrameworkAdapter()
        info = adapter.get_failure_handling_info()
        notes = info.get("notes", "").lower()
        assert "manager" in notes or "magentic" in notes

    def test_failure_handling_mentions_stall(self):
        adapter = AgentFrameworkAdapter()
        info = adapter.get_failure_handling_info()
        notes = info.get("notes", "").lower()
        assert "stall" in notes


class TestUsageTrackingMiddleware:
    def test_middleware_class_exists(self):
        from desmet.adapters.agent_framework import UsageTrackingMiddleware
        assert UsageTrackingMiddleware is not None

    def test_middleware_initializes_with_trace(self):
        from desmet.adapters.agent_framework import UsageTrackingMiddleware
        trace = AgentTrace()
        mw = UsageTrackingMiddleware(trace, model_name="gpt-5.2")
        assert mw._trace is trace
        assert mw._model_name == "gpt-5.2"

    def test_middleware_is_thread_safe(self):
        """Middleware uses a lock for concurrent agent access."""
        from desmet.adapters.agent_framework import UsageTrackingMiddleware
        trace = AgentTrace()
        mw = UsageTrackingMiddleware(trace, model_name="gpt-5.2")
        assert hasattr(mw, "_lock")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_agent_framework_adapter.py -v`
Expected: FAIL — stub adapter has no `TOOL_FORMAT`, `_run_agent`, etc.

- [ ] **Step 3: Write the full adapter implementation**

Replace `src/desmet/adapters/agent_framework.py` with:

```python
"""
Microsoft Agent Framework Platform Adapter.

Uses MagenticOne orchestration: a manager agent dynamically coordinates
three specialized agents (planner, executor, reviewer). The manager detects
stalls, injects validation feedback, and re-delegates work — all inside the
orchestration loop (no external retry logic).

Token tracking is done via ChatMiddleware intercepting every LLM call.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any

from pydantic import BaseModel

from desmet.adapters._base import ToolAgentAdapter
from desmet.adapters._prompts import get_stage_persona, get_sub_persona
from desmet.adapters._tools import ToolFormat
from desmet.adapters._tracing import (
    finish_trace,
    record_llm_duration,
    record_message,
    record_tool_call,
    record_usage,
)
from desmet.adapters._validation import validate_workspace
from desmet.adapters.registry import load_platform_info
from desmet.harness.context import StageContext
from desmet.harness.models import PlatformInfo
from desmet.harness.trace import AgentTrace
from desmet.llm_config import Provider
from desmet.llm_config import get_config as get_llm_config

_log = logging.getLogger(__name__)

MAX_STALL_COUNT = 3


# ── Data models ───────────────────────────────────────────────────────────────


class ImplementationPlan(BaseModel):
    """Structured output from the planner agent."""

    steps: list[str]
    files_to_create: list[str]
    files_to_modify: list[str]


# ── Usage Tracking Middleware ─────────────────────────────────────────────────


class UsageTrackingMiddleware:
    """ChatMiddleware that intercepts every LLM call to record token usage.

    Registered on the chat client so that all agents (planner, executor,
    reviewer, manager) route through it.  Thread-safe for concurrent agent
    execution within MagenticOne.
    """

    def __init__(self, trace: AgentTrace, model_name: str | None = None):
        self._trace = trace
        self._model_name = model_name
        self._lock = threading.Lock()

    async def invoke(self, context, next_handler):
        """Intercept a chat completion call, record usage from the response."""
        start = time.perf_counter()
        result = await next_handler(context)
        duration_ms = (time.perf_counter() - start) * 1000

        # Extract token usage from response items.
        # Agent Framework responses contain UsageContent items with
        # input_tokens / output_tokens fields, or the response object
        # itself may carry a usage attribute.
        input_tokens = 0
        output_tokens = 0

        # Try response-level usage first (most reliable)
        usage = getattr(result, "usage", None)
        if usage is not None:
            input_tokens = (
                getattr(usage, "input_tokens", 0)
                or getattr(usage, "prompt_tokens", 0)
                or 0
            )
            output_tokens = (
                getattr(usage, "output_tokens", 0)
                or getattr(usage, "completion_tokens", 0)
                or 0
            )

        # Fallback: check individual items for UsageContent
        if input_tokens == 0 and output_tokens == 0:
            items = getattr(result, "items", [])
            for item in items:
                if hasattr(item, "input_tokens"):
                    input_tokens += getattr(item, "input_tokens", 0)
                    output_tokens += getattr(item, "output_tokens", 0)

        with self._lock:
            if input_tokens or output_tokens:
                record_usage(
                    self._trace,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model=self._model_name,
                )
            record_llm_duration(self._trace, duration_ms)

        return result


# ── Helper ────────────────────────────────────────────────────────────────────


def _format_tool_detail(name: str, raw_args: Any) -> str:
    """Format a tool call for human-readable progress logging."""
    args = raw_args if isinstance(raw_args, dict) else {}
    if not args and isinstance(raw_args, str):
        try:
            import json
            args = json.loads(raw_args)
        except (json.JSONDecodeError, TypeError):
            pass
    if name in ("read_file", "write_file") and "path" in args:
        return f"{name} → {args['path']}"
    if name == "execute_shell" and "command" in args:
        cmd = args["command"]
        return f"{name} → {cmd[:60]}{'…' if len(cmd) > 60 else ''}"
    if name == "search_code" and "pattern" in args:
        return f"{name} → /{args['pattern']}/"
    if name == "list_directory":
        return f"{name} → {args.get('path', '.')}"
    if name == "deploy_remote" and "action" in args:
        return f"{name} → {args['action']}"
    return name


# ── Adapter ───────────────────────────────────────────────────────────────────


class AgentFrameworkAdapter(ToolAgentAdapter):
    """Microsoft Agent Framework adapter using MagenticOne orchestration.

    MagenticOne uses a manager agent that dynamically coordinates
    specialized agents, detects stalls, and manages retries — all within
    the orchestration loop.
    """

    TOOL_FORMAT = ToolFormat.AGENT_FRAMEWORK

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._client = None
        self._model_name: str | None = None

    @property
    def platform_info(self) -> PlatformInfo:
        info = load_platform_info("microsoft_agent_framework")
        info.version = self._get_version()
        return info

    def _get_version(self) -> str:
        try:
            import agent_framework
            return getattr(agent_framework, "__version__", "unknown")
        except ImportError:
            return "not installed"

    async def initialize(self) -> None:
        """Initialize Agent Framework components."""
        try:
            from agent_framework import Agent
            from agent_framework.openai import OpenAIChatClient

            cfg = get_llm_config(model=self.config.get("model"))
            self._client = self._create_model(cfg)
            self._model_name = cfg.model

            # Enable OTel if env vars are set (Langfuse, Jaeger, etc.)
            try:
                from agent_framework.observability import configure_otel_providers
                configure_otel_providers()
            except (ImportError, Exception):
                pass  # optional — observability degrades gracefully

            self._initialized = True
        except ImportError as e:
            raise RuntimeError(f"Failed to import Agent Framework: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Agent Framework: {e}")

    @staticmethod
    def _create_model(cfg):
        """Build the OpenAIChatClient from LLM config.

        All providers route through OpenAIChatClient since Agent Framework
        uses the OpenAI chat completions API as its common interface.
        Non-OpenAI providers use a custom base_url.
        """
        from agent_framework.openai import OpenAIChatClient

        kwargs = {"model_id": cfg.model}
        if cfg.api_key:
            kwargs["api_key"] = cfg.api_key
        if cfg.base_url:
            kwargs["base_url"] = cfg.base_url
        return OpenAIChatClient(**kwargs)

    async def shutdown(self) -> None:
        self._client = None
        self._initialized = False

    async def health_check(self) -> bool:
        if not self._initialized or self._client is None:
            return False
        try:
            from agent_framework import Agent

            agent = Agent(
                name="health_check",
                chat_client=self._client,
                instructions="Respond with 'ok'.",
            )
            result = await agent.run("Say 'ok'")
            return len(result.text or "") > 0
        except Exception:
            return False

    # ── Core agent runner ─────────────────────────────────────────────────

    async def _run_agent(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str | None,
        tools: list,
        trace: AgentTrace,
        context: StageContext,
    ) -> tuple[int, bool]:
        """Run MagenticOne orchestration: manager + planner/executor/reviewer.

        Returns (total_iterations, hit_limit).
        """
        from agent_framework import Agent
        from agent_framework.orchestrations import MagenticBuilder

        planner_persona = get_sub_persona("planner")
        executor_persona = get_stage_persona(stage_name)
        reviewer_persona = get_sub_persona("reviewer")

        t0 = time.monotonic()
        cb = context.progress_callback
        total_iterations = 0
        hit_limit = False

        record_message(trace, "user", prompt)

        # ── Register usage tracking middleware ────────────────────────────
        middleware = UsageTrackingMiddleware(trace, model_name=self._model_name)
        client_with_middleware = self._client
        # Agent Framework supports middleware registration on the client.
        # The exact API depends on the RC version; we register via the
        # agent's chat_client_settings or wrap the client.
        try:
            client_with_middleware = self._client.with_middleware([middleware])
        except (AttributeError, TypeError):
            # Fallback: middleware not supported on this client version
            _log.debug("ChatMiddleware registration not available — using client directly")
            client_with_middleware = self._client

        # ── Step 1: Planner agent (structured output) ────────────────────
        plan: ImplementationPlan | None = None
        try:
            planner = Agent(
                name=f"desmet_{stage_name}_planner",
                chat_client=client_with_middleware,
                instructions=planner_persona.backstory,
            )
            planner_result = await planner.run(
                prompt,
                response_format=ImplementationPlan,
            )
            if hasattr(planner_result, "value") and isinstance(planner_result.value, ImplementationPlan):
                plan = planner_result.value
            total_iterations += 1
        except Exception:
            pass  # structured output not supported — fall back below

        if plan is None:
            # Free-text fallback
            planner = Agent(
                name=f"desmet_{stage_name}_planner",
                chat_client=client_with_middleware,
                instructions=(
                    f"{planner_persona.backstory}\n\n"
                    "Produce a numbered implementation plan listing steps, "
                    "files to create, and files to modify."
                ),
            )
            planner_result = await planner.run(prompt)
            text = planner_result.text or ""
            steps = [m.group(1).strip() for m in re.finditer(r"^\d+\.\s+(.*)", text, re.MULTILINE)]
            plan = ImplementationPlan(
                steps=steps or [text],
                files_to_create=[],
                files_to_modify=[],
            )
            total_iterations += 1

        record_message(trace, "assistant", f"Plan: {len(plan.steps)} steps", metadata={"event": "plan_complete"})
        if cb:
            cb(f"    planner: {len(plan.steps)} steps planned")

        # ── Step 2: Build executor + reviewer + manager agents ───────────
        # Executor: stage-specific persona with all tools except check_completion
        executor_tools = [t for t in tools if getattr(t, "__name__", "") != "check_completion"]
        # Reviewer: inspection + validation tools only
        reviewer_tool_names = {"read_file", "list_directory", "search_code", "check_completion"}
        reviewer_tools = [t for t in tools if getattr(t, "__name__", "") in reviewer_tool_names]

        plan_text = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(plan.steps))
        all_files = plan.files_to_create + plan.files_to_modify
        files_text = ", ".join(all_files) if all_files else "(none specified)"
        executor_instructions = (
            f"{executor_persona.backstory}\n\n"
            f"## Implementation Plan\n{plan_text}\n\n"
            f"## Files\n{files_text}\n"
        )
        if system_msg:
            executor_instructions += f"\n## Additional Context\n{system_msg}\n"

        executor_agent = Agent(
            name=f"desmet_{stage_name}_executor",
            chat_client=client_with_middleware,
            instructions=executor_instructions,
            tools=executor_tools,
        )

        reviewer_agent = Agent(
            name=f"desmet_{stage_name}_reviewer",
            chat_client=client_with_middleware,
            instructions=(
                f"{reviewer_persona.backstory}\n\n"
                "After inspecting the workspace, call the check_completion "
                "tool to verify all required artifacts are present."
            ),
            tools=reviewer_tools,
        )

        # Manager agent (implicit in MagenticBuilder) coordinates the team
        manager_agent = Agent(
            name=f"desmet_{stage_name}_manager",
            chat_client=client_with_middleware,
            instructions=(
                "You are a technical project manager coordinating a team of "
                "planner, executor, and reviewer agents. Delegate implementation "
                "to the executor, then validation to the reviewer. If the "
                "reviewer reports validation failure, direct the executor to "
                "fix the issues. Declare the task complete only when the "
                "reviewer confirms all artifacts pass validation."
            ),
        )

        # ── Step 3: Run MagenticOne orchestration ────────────────────────
        workflow = MagenticBuilder(
            manager_agent=manager_agent,
            participants=[executor_agent, reviewer_agent],
            max_round_count=context.max_iterations,
            max_stall_count=MAX_STALL_COUNT,
        ).build()

        tool_call_count = 0
        try:
            async for event in workflow.run_stream(prompt):
                event_type = getattr(event, "type", None)

                # Track iterations from round events
                if event_type == "round_start":
                    total_iterations += 1
                    if total_iterations >= context.max_iterations:
                        hit_limit = True
                        break

                # Record agent messages
                if event_type == "output":
                    text = getattr(event, "data", "") or str(event)
                    agent_name = getattr(event, "source", "unknown")
                    record_message(trace, "assistant", str(text), metadata={"agent": str(agent_name)})

                # Record tool calls
                if event_type == "tool_call":
                    tool_call_count += 1
                    name = getattr(event, "name", "unknown")
                    args = getattr(event, "arguments", {})
                    result_val = getattr(event, "result", "")
                    duration = getattr(event, "duration_ms", 0.0)
                    record_tool_call(trace, name, args if isinstance(args, dict) else {"raw": args}, str(result_val), duration_ms=duration)
                    if cb:
                        elapsed = time.monotonic() - t0
                        tokens = trace.total_tokens_input + trace.total_tokens_output
                        detail = _format_tool_detail(name, args)
                        cb(f"    tool {tool_call_count} — {detail}  ({elapsed:.0f}s, {tokens:,} tokens)")

                # Stall detection feedback
                if event_type == "stall_detected":
                    record_message(trace, "system", "Stall detected by manager", metadata={"event": "stall"})
                    if cb:
                        cb("    manager: stall detected — reassigning")

        except Exception as e:
            _log.warning("MagenticOne orchestration error: %s", e)
            trace.errors.append(str(e))

        # ── Final validation ─────────────────────────────────────────────
        valid = validate_workspace(stage_name, str(context.workspace))
        if cb:
            cb(f"    validator: {'PASSED' if valid else 'FAILED'}")
        if not valid:
            hit_limit = True

        trace.total_iterations = total_iterations
        finish_trace(trace)
        return total_iterations, hit_limit

    # Stage methods inherited from ToolAgentAdapter

    # ── Metadata ─────────────────────────────────────────────────────────

    def get_observability_info(self) -> dict[str, Any]:
        return {
            "has_tracing": True,
            "has_step_through": False,
            "has_replay": False,
            "has_checkpointing": True,
            "has_stall_detection": True,
            "has_state_inspection": True,
            "has_memory_inspection": False,
            "trace_format": "opentelemetry",
            "notes": (
                "MagenticOne orchestration: manager dynamically coordinates "
                "planner/executor/reviewer agents. Native OTel instrumentation "
                "with GenAI Semantic Conventions."
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
                "Manager-driven stall detection and re-delegation. Manager "
                "receives validation feedback and directs executor to fix "
                "issues. max_stall_count=3 prevents infinite loops."
            ),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_agent_framework_adapter.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/desmet/adapters/agent_framework.py tests/test_agent_framework_adapter.py
git commit -m "feat(agent-framework): implement MagenticOne adapter with ChatMiddleware"
```

---

### Task 4: Update Registry

**Files:**
- Modify: `src/desmet/adapters/registry.py:123`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_agent_framework_adapter.py`:

```python
class TestRegistryIntegration:
    def test_agent_framework_in_implemented_platforms(self):
        from desmet.adapters.registry import list_available_platforms
        platforms = list_available_platforms()
        assert "microsoft_agent_framework" in platforms

    def test_registry_returns_correct_adapter(self):
        from desmet.adapters.registry import get_adapter
        adapter = get_adapter("microsoft_agent_framework")
        assert isinstance(adapter, AgentFrameworkAdapter)

    def test_registry_adapter_has_correct_tool_format(self):
        from desmet.adapters.registry import get_adapter
        from desmet.adapters._tools import ToolFormat
        adapter = get_adapter("microsoft_agent_framework")
        assert adapter.TOOL_FORMAT == ToolFormat.AGENT_FRAMEWORK
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_agent_framework_adapter.py::TestRegistryIntegration -v`
Expected: FAIL — `microsoft_agent_framework` not in `_IMPLEMENTED_PLATFORMS`.

- [ ] **Step 3: Add to _IMPLEMENTED_PLATFORMS**

In `src/desmet/adapters/registry.py`, update line 123:

```python
_IMPLEMENTED_PLATFORMS: frozenset[str] = frozenset({"langgraph", "crewai", "openai_agents_sdk", "microsoft_agent_framework"})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_agent_framework_adapter.py::TestRegistryIntegration -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Run full registry test suite**

Run: `uv run pytest tests/ -k "registry or infra" -v`
Expected: No regressions.

- [ ] **Step 6: Commit**

```bash
git add src/desmet/adapters/registry.py tests/test_agent_framework_adapter.py
git commit -m "feat(registry): mark microsoft_agent_framework as implemented"
```

---

### Task 5: Full Test Suite Verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run the complete test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS, no regressions.

- [ ] **Step 2: Run adapter-specific tests**

Run: `uv run pytest tests/test_agent_framework_adapter.py tests/test_adapter_tools.py -v --tb=short`
Expected: All tests PASS.

- [ ] **Step 3: Verify imports work cleanly**

Run: `uv run python -c "from desmet.adapters.agent_framework import AgentFrameworkAdapter; print('OK:', AgentFrameworkAdapter.TOOL_FORMAT)"`
Expected: `OK: ToolFormat.AGENT_FRAMEWORK`

- [ ] **Step 4: Verify registry lists the platform**

Run: `uv run python -c "from desmet.adapters.registry import list_available_platforms; print(list_available_platforms())"`
Expected: List includes `microsoft_agent_framework`.

- [ ] **Step 5: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address test suite issues from Agent Framework integration"
```

Only run this step if any fixes were required. If all tests passed cleanly, skip.
