# LangSmith Integration + LangGraph Upgrade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the LangGraph adapter to use a `StateGraph` (planner → executor → validator) and add a LangSmith trace viewer tab to the DESMET webUI scoring page.

**Architecture:** The LangGraph adapter is replaced with a proper StateGraph that runs planner/executor/validator nodes per DESMET stage. Each stage invocation pre-generates a `run_id` UUID passed to LangSmith automatically via `LANGCHAIN_TRACING_V2`. A new `langsmith_client.py` proxies LangSmith REST API calls, two new endpoints are added to `api.py`, and the Scoring page gains a second trace tab (Langfuse + LangSmith) for LangGraph runs.

**Tech Stack:** Python `langgraph>=1.0`, `langchain-core`, `httpx`; Svelte 5 (runes); FastAPI; `uv` for Python deps, `bun` for frontend.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/desmet/harness/results.py` | Modify | Add `langsmith_run_id: str \| None = None` to `StageResult` |
| `src/desmet/harness/runner.py` | Modify | Persist `langsmith_run_id` per stage in `_save_stage_traces` |
| `src/desmet/adapters/langgraph.py` | Rewrite | StateGraph with planner/executor/validator nodes |
| `src/desmet/webui/langsmith_client.py` | Create | Async LangSmith REST API client |
| `src/desmet/webui/api.py` | Modify | Add `/api/langsmith/status`, `/api/langsmith/runs/{id}`, update `/api/config` and scoring endpoint |
| `src/desmet/webui/frontend/src/lib/api.ts` | Modify | New types + `StoryScoreData`/`AppConfig` updates + `fetchLangSmithRun` |
| `src/desmet/webui/frontend/src/lib/components/LangSmithTraceViewer.svelte` | Create | LangSmith run tree renderer reusing `SpanNode.svelte` |
| `src/desmet/webui/frontend/src/lib/pages/Scoring.svelte` | Modify | Two-tab trace section for LangGraph runs |
| `.env.example` | Modify | Add `LANGSMITH_API_KEY`, `LANGCHAIN_TRACING_V2`, `LANGCHAIN_PROJECT` |
| `tests/test_langgraph_adapter.py` | Modify | Extend with StateGraph structure tests |
| `tests/test_langsmith_client.py` | Create | Unit tests for the LangSmith client |

---

## Task 1: Add `langsmith_run_id` to `StageResult` and runner persistence

**Files:**
- Modify: `src/desmet/harness/results.py`
- Modify: `src/desmet/harness/runner.py:544-574`
- Test: `tests/test_runner.py` (extend existing)

- [ ] **Step 1: Write failing test for `StageResult.langsmith_run_id`**

  Add to `tests/test_runner.py`:

  ```python
  def test_stage_result_has_langsmith_run_id():
      from desmet.harness.results import StageResult
      result = StageResult(platform_id="langgraph", stage_name="requirements")
      assert result.langsmith_run_id is None  # field exists, defaults to None

  def test_stage_result_langsmith_run_id_can_be_set():
      from desmet.harness.results import StageResult
      result = StageResult(platform_id="langgraph", stage_name="requirements")
      result.langsmith_run_id = "abc-123"
      assert result.langsmith_run_id == "abc-123"
  ```

- [ ] **Step 2: Run tests to confirm they fail**

  ```
  uv run pytest tests/test_runner.py::test_stage_result_has_langsmith_run_id tests/test_runner.py::test_stage_result_langsmith_run_id_can_be_set -v
  ```

  Expected: `AttributeError` — field does not exist yet.

- [ ] **Step 3: Add `langsmith_run_id` to `StageResult`**

  In `src/desmet/harness/results.py`, append after `raw_output: Any = None` (line 57):

  ```python
      # LangSmith run ID (LangGraph only; None for all other adapters)
      langsmith_run_id: str | None = None
  ```

- [ ] **Step 4: Run tests to confirm they pass**

  ```
  uv run pytest tests/test_runner.py::test_stage_result_has_langsmith_run_id tests/test_runner.py::test_stage_result_langsmith_run_id_can_be_set -v
  ```

  Expected: PASS.

- [ ] **Step 5: Write failing test for runner persistence**

  Add to `tests/test_runner.py`:

  ```python
  import json
  from pathlib import Path

  def test_save_stage_traces_includes_langsmith_run_id(tmp_path):
      """langsmith_run_id written per-stage into the JSON trace file."""
      from desmet.harness.runner import EvaluationRunner, RunnerConfig
      from desmet.harness.results import RequirementsResult
      from desmet.harness.story import StoryResult, StoryStatus

      cfg = RunnerConfig(results_dir=tmp_path, logs_dir=tmp_path / "logs")
      # EvaluationRunner.__init__ requires platforms/stories/baseline_repo;
      # bypass by constructing the object without calling __init__ and
      # setting only the attributes _save_stage_traces needs.
      runner = object.__new__(EvaluationRunner)
      runner.config = cfg
      (tmp_path / "logs").mkdir(parents=True, exist_ok=True)

      story_result = StoryResult(
          story_id="US001", platform_id="langgraph", execution_id="exec-1",
          status=StoryStatus.COMPLETED,
      )

      req_result = RequirementsResult(platform_id="langgraph", stage_name="requirements")
      req_result.langsmith_run_id = "ls-run-abc"

      runner._save_stage_traces(story_result, {"requirements": req_result})

      trace_files = list((tmp_path / "logs" / "langgraph" / "US001").glob("*_stages.json"))
      assert trace_files, "No trace file written"
      data = json.loads(trace_files[0].read_text())
      assert data["stages"]["requirements"]["langsmith_run_id"] == "ls-run-abc"
  ```

- [ ] **Step 6: Run test to confirm it fails**

  ```
  uv run pytest tests/test_runner.py::test_save_stage_traces_includes_langsmith_run_id -v
  ```

  Expected: FAIL — `langsmith_run_id` key missing from stage dict.

- [ ] **Step 7: Add `langsmith_run_id` to `stage_entry` in `runner.py`**

  In `src/desmet/harness/runner.py`, find the `stage_entry` dict inside `_save_stage_traces` (around line 546). Add after `"end_time": ...`:

  ```python
              "langsmith_run_id": sr.langsmith_run_id,
  ```

- [ ] **Step 8: Run all runner tests to confirm they pass**

  ```
  uv run pytest tests/test_runner.py -v
  ```

  Expected: all PASS.

- [ ] **Step 9: Commit**

  ```bash
  git add src/desmet/harness/results.py src/desmet/harness/runner.py tests/test_runner.py
  git commit -m "feat(harness): add langsmith_run_id to StageResult and stage trace persistence"
  ```

---

## Task 2: Rewrite LangGraph adapter — StateGraph

**Files:**
- Rewrite: `src/desmet/adapters/langgraph.py`
- Modify: `tests/test_langgraph_adapter.py`

This is the largest task. The adapter is fully rewritten; the public interface (`generate_requirements`, `generate_code`, `generate_tests`, `build_and_deploy`) stays identical.

- [ ] **Step 1: Add StateGraph structure tests**

  Replace the body of `tests/test_langgraph_adapter.py` with:

  ```python
  """Tests for LangGraph StateGraph adapter."""
  import inspect
  import pytest
  from desmet.adapters.langgraph import LangGraphAdapter


  @pytest.fixture
  def adapter():
      return LangGraphAdapter(config={"model": "gpt-5.2-2025-12-11"})


  class TestLangGraphAdapterInterface:
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


  class TestStateGraphStructure:
      def test_build_graph_returns_compiled_state_graph(self, adapter):
          """_build_graph() must return a compiled LangGraph StateGraph."""
          from langgraph.graph.state import CompiledStateGraph
          from unittest.mock import MagicMock
          # build_graph requires an LLM and tools list
          mock_llm = MagicMock()
          mock_llm.bind_tools.return_value = mock_llm
          graph = adapter._build_graph(mock_llm, tools=[])
          assert isinstance(graph, CompiledStateGraph)

      def test_build_graph_has_planner_node(self, adapter):
          from unittest.mock import MagicMock
          mock_llm = MagicMock()
          mock_llm.bind_tools.return_value = mock_llm
          graph = adapter._build_graph(mock_llm, tools=[])
          assert "planner_node" in graph.get_graph().nodes

      def test_build_graph_has_executor_node(self, adapter):
          from unittest.mock import MagicMock
          mock_llm = MagicMock()
          mock_llm.bind_tools.return_value = mock_llm
          graph = adapter._build_graph(mock_llm, tools=[])
          assert "executor_node" in graph.get_graph().nodes

      def test_build_graph_has_validator_node(self, adapter):
          from unittest.mock import MagicMock
          mock_llm = MagicMock()
          mock_llm.bind_tools.return_value = mock_llm
          graph = adapter._build_graph(mock_llm, tools=[])
          assert "validator_node" in graph.get_graph().nodes

      def test_no_legacy_create_agent_import(self):
          """Adapter must not import the legacy langchain.agents.create_agent."""
          import ast, pathlib
          src = pathlib.Path("src/desmet/adapters/langgraph.py").read_text()
          tree = ast.parse(src)
          for node in ast.walk(tree):
              if isinstance(node, (ast.Import, ast.ImportFrom)):
                  mod = getattr(node, "module", "") or ""
                  assert "create_agent" not in mod, "Legacy create_agent import found"


  class TestValidatorLogic:
      def test_validate_requirements_passes_with_keywords(self, adapter, tmp_path):
          """Requirements validator passes when file contains ≥3 keywords."""
          req_file = tmp_path / "requirements.md"
          req_file.write_text(
              "## Functional requirements\n"
              "## Non-functional requirements\n"
              "## Acceptance criteria\n"
              "## Constraint: must be fast\n"
          )
          assert adapter._validate_stage("requirements", str(tmp_path)) is True

      def test_validate_requirements_fails_no_file(self, adapter, tmp_path):
          assert adapter._validate_stage("requirements", str(tmp_path)) is False

      def test_validate_requirements_fails_missing_keywords(self, adapter, tmp_path):
          (tmp_path / "requirements.md").write_text("just some text")
          assert adapter._validate_stage("requirements", str(tmp_path)) is False

      def test_validate_codegen_passes_with_valid_python(self, adapter, tmp_path):
          (tmp_path / "app.py").write_text("def hello(): return 'hi'\n")
          assert adapter._validate_stage("codegen", str(tmp_path)) is True

      def test_validate_codegen_fails_no_python_file(self, adapter, tmp_path):
          assert adapter._validate_stage("codegen", str(tmp_path)) is False

      def test_validate_testing_passes_with_test_file(self, adapter, tmp_path):
          (tmp_path / "test_app.py").write_text("def test_hello(): assert True\n")
          assert adapter._validate_stage("testing", str(tmp_path)) is True

      def test_validate_testing_fails_no_test_functions(self, adapter, tmp_path):
          (tmp_path / "test_app.py").write_text("def helper(): pass\n")
          assert adapter._validate_stage("testing", str(tmp_path)) is False

      def test_validate_deploy_passes_with_compose_file(self, adapter, tmp_path):
          (tmp_path / "docker-compose.yaml").write_text("version: '3'\n")
          assert adapter._validate_stage("deploy", str(tmp_path)) is True

      def test_validate_deploy_fails_no_compose(self, adapter, tmp_path):
          assert adapter._validate_stage("deploy", str(tmp_path)) is False
  ```

- [ ] **Step 2: Run tests to confirm they fail**

  ```
  uv run pytest tests/test_langgraph_adapter.py -v
  ```

  Expected: `TestStateGraphStructure` and `TestValidatorLogic` tests fail — methods don't exist yet.

- [ ] **Step 3: Rewrite `src/desmet/adapters/langgraph.py`**

  Replace the entire file with:

  ```python
  """
  LangGraph Platform Adapter — StateGraph implementation.

  Each DESMET SDLC stage runs an explicit StateGraph:
    START → planner_node → executor_node ⇄ tool_node → validator_node → (retry | END)
  """
  from __future__ import annotations

  import os
  import py_compile
  import tempfile
  import uuid
  from pathlib import Path
  from typing import Annotated, Any

  from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
  from langchain_core.runnables import RunnableConfig
  from langgraph.graph import END, StateGraph
  from langgraph.graph.message import add_messages
  from langgraph.prebuilt import ToolNode
  from typing_extensions import TypedDict

  from desmet.adapters._prompts import (
      build_codegen_prompt,
      build_deploy_prompt,
      build_requirements_prompt,
      build_system_message,
      build_testing_prompt,
  )
  from desmet.adapters._tools import ToolFormat, create_tools
  from desmet.adapters._tracing import (
      build_stage_result,
      finish_trace,
      record_message,
      record_tool_call,
      record_usage,
      start_trace,
  )
  from desmet.adapters.registry import load_platform_info
  from desmet.harness.adapter import BasePlatformAdapter
  from desmet.harness.context import StageContext
  from desmet.harness.models import PlatformInfo
  from desmet.harness.results import (
      CodeResult,
      DeployResult,
      RequirementsResult,
      StageResult,
      TestResult,
  )
  from desmet.llm_config import Provider
  from desmet.llm_config import get_config as get_llm_config
  from desmet.observability import get_langchain_callback

  MAX_RETRIES = 3

  _REQUIREMENTS_KEYWORDS = {"functional", "non-functional", "acceptance", "constraint"}


  class AgentState(TypedDict):
      messages: Annotated[list[BaseMessage], add_messages]
      plan: str
      stage: str
      retry_count: int
      workspace: str
      validator_passed: bool


  class LangGraphAdapter(BasePlatformAdapter):
      """LangGraph adapter using an explicit StateGraph per DESMET stage."""

      TOOL_FORMAT = ToolFormat.LANGCHAIN

      def __init__(self, config: dict[str, Any] | None = None):
          super().__init__(config)
          self._llm = None

      @property
      def platform_info(self) -> PlatformInfo:
          info = load_platform_info("langgraph")
          info.version = self._get_version()
          return info

      def _get_version(self) -> str:
          try:
              import langgraph
              return getattr(langgraph, "__version__", "unknown")
          except ImportError:
              return "not installed"

      async def initialize(self) -> None:
          try:
              cfg = get_llm_config(model=self.config.get("model"))
              self._llm = self._create_chat_model(cfg)
              self._initialized = True
          except ImportError as e:
              raise RuntimeError(f"Failed to import LangGraph: {e}")
          except Exception as e:
              raise RuntimeError(f"Failed to initialize LangGraph: {e}")

      @staticmethod
      def _create_chat_model(cfg):
          if cfg.provider == Provider.ANTHROPIC:
              from langchain_anthropic import ChatAnthropic
              return ChatAnthropic(
                  model=cfg.model, temperature=cfg.temperature, api_key=cfg.api_key,
              )
          from langchain_openai import ChatOpenAI
          kwargs: dict = dict(model=cfg.model, temperature=cfg.temperature, api_key=cfg.api_key)
          if cfg.base_url:
              kwargs["base_url"] = cfg.base_url
          return ChatOpenAI(**kwargs)

      async def shutdown(self) -> None:
          self._llm = None
          self._initialized = False

      async def health_check(self) -> bool:
          if not self._initialized or self._llm is None:
              return False
          try:
              response = await self._llm.ainvoke("Say 'ok'")
              return len(response.content) > 0
          except Exception:
              return False

      # ── Graph construction ────────────────────────────────────────────────

      def _build_graph(self, llm, tools: list):
          """Build and compile the StateGraph for a single stage run."""
          llm_with_tools = llm.bind_tools(tools)

          def planner_node(state: AgentState) -> dict:
              sys = SystemMessage(content=(
                  f"You are a planning assistant for the '{state['stage']}' stage of a "
                  "software development lifecycle. Produce a concise numbered plan."
              ))
              response = llm.invoke([sys] + state["messages"])
              return {"plan": response.content, "messages": [response]}

          def executor_node(state: AgentState) -> dict:
              sys = SystemMessage(content=(
                  f"Stage: {state['stage']}\nPlan:\n{state['plan']}\n"
                  "Execute the next step. Use tools to write files or run commands. "
                  f"Working directory: {state['workspace']}"
              ))
              response = llm_with_tools.invoke([sys] + state["messages"])
              return {"messages": [response]}

          def validator_node(state: AgentState) -> dict:
              passed = self._validate_stage(state["stage"], state["workspace"])
              return {
                  "validator_passed": passed,
                  "retry_count": state["retry_count"] + 1,
              }

          def route_after_validator(state: AgentState) -> str:
              if state["validator_passed"]:
                  return END
              if state["retry_count"] >= MAX_RETRIES:
                  return END
              return "executor_node"

          builder = StateGraph(AgentState)
          builder.add_node("planner_node", planner_node)
          builder.add_node("executor_node", executor_node)
          builder.add_node("tool_node", ToolNode(tools))
          builder.add_node("validator_node", validator_node)
          builder.set_entry_point("planner_node")
          builder.add_edge("planner_node", "executor_node")
          builder.add_edge("tool_node", "executor_node")
          builder.add_conditional_edges("executor_node", self._route_executor)
          builder.add_conditional_edges("validator_node", route_after_validator)
          return builder.compile()

      @staticmethod
      def _route_executor(state: AgentState) -> str:
          """Route executor output: to tool_node if tool calls pending, else validator."""
          last = state["messages"][-1] if state["messages"] else None
          if last and getattr(last, "tool_calls", None):
              return "tool_node"
          return "validator_node"

      # ── Stage validation ──────────────────────────────────────────────────

      def _validate_stage(self, stage: str, workspace: str) -> bool:
          """Deterministic workspace checks — no LLM call."""
          ws = Path(workspace)
          if stage == "requirements":
              for ext in ("*.md", "*.txt"):
                  for f in ws.glob(ext):
                      content = f.read_text(errors="ignore").lower()
                      hits = sum(1 for kw in _REQUIREMENTS_KEYWORDS if kw in content)
                      if hits >= 3:
                          return True
              return False

          if stage == "codegen":
              for py_file in ws.glob("*.py"):
                  try:
                      py_compile.compile(str(py_file), doraise=True)
                      return True
                  except py_compile.PyCompileError:
                      pass
              return False

          if stage == "testing":
              for pattern in ("test_*.py", "*_test.py"):
                  for f in ws.glob(pattern):
                      if "def test_" in f.read_text(errors="ignore"):
                          return True
              return False

          if stage == "deploy":
              return (ws / "docker-compose.yaml").exists()

          return False

      # ── Core agent runner ─────────────────────────────────────────────────

      @staticmethod
      def _langsmith_enabled() -> bool:
          return (
              os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true"
              and bool(os.environ.get("LANGSMITH_API_KEY", ""))
          )

      async def _run_graph(
          self,
          prompt: str,
          system_msg: str | None,
          tools: list,
          trace,
          context: StageContext,
          stage_name: str,
      ) -> tuple[int, bool, str | None]:
          """
          Stream a compiled StateGraph for one SDLC stage.
          Returns (iterations, hit_limit, langsmith_run_id | None).
          """
          graph = self._build_graph(self._llm, tools)

          initial_messages: list[BaseMessage] = []
          if system_msg:
              initial_messages.append(SystemMessage(content=system_msg))
          initial_messages.append(HumanMessage(content=prompt))

          record_message(trace, "user", prompt)

          run_id = uuid.uuid4()
          lf_cb = get_langchain_callback()
          config: RunnableConfig = {
              "run_id": run_id,
              "run_name": f"desmet-langgraph-{stage_name}",
          }
          if lf_cb is not None:
              config["callbacks"] = [lf_cb]

          initial_state: AgentState = {
              "messages": initial_messages,
              "plan": "",
              "stage": stage_name,
              "retry_count": 0,
              "workspace": str(context.workspace),
              "validator_passed": False,
          }

          iteration = 0
          hit_limit = False
          final_state = None

          async for chunk in graph.astream(initial_state, config=config, stream_mode="values"):
              iteration += 1
              final_state = chunk

              messages = chunk.get("messages", [])
              if messages:
                  last = messages[-1]
                  content = getattr(last, "content", "")
                  if content:
                      record_message(trace, getattr(last, "type", "assistant"), str(content))

                  resp_meta = getattr(last, "response_metadata", {})
                  usage = resp_meta.get("token_usage") or resp_meta.get("usage") or {}
                  if isinstance(usage, dict) and usage.get("total_tokens", 0) > 0:
                      record_usage(
                          trace,
                          input_tokens=usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0),
                          output_tokens=usage.get("completion_tokens", 0) or usage.get("output_tokens", 0),
                          cost_usd=float(usage.get("cost") or 0.0),
                      )

                  for tc in getattr(last, "tool_calls", []):
                      record_tool_call(trace, tc.get("name", "unknown"), tc.get("args", {}), "")

              if iteration >= context.max_iterations:
                  hit_limit = True
                  break

          trace.total_iterations = iteration
          finish_trace(trace, final_state=final_state)

          langsmith_run_id = str(run_id) if self._langsmith_enabled() else None
          return iteration, hit_limit, langsmith_run_id

      # ── SDLC stage methods ────────────────────────────────────────────────

      async def _execute_stage(self, stage_name, prompt_fn, result_cls, context):
          trace = start_trace()
          try:
              if stage_name == "codegen":
                  prior = context.get_prior_result("requirements")
                  prompt = prompt_fn(context.story, prior_requirements=prior)
              else:
                  prompt = prompt_fn(context.story)
              system_msg = build_system_message(context.story)
              tools = create_tools(
                  context.workspace, context.allowed_tools, fmt=self.TOOL_FORMAT,
                  platform_id=context.platform_id, story_id=context.story.id,
              )
              iterations, hit_limit, langsmith_run_id = await self._run_graph(
                  prompt, system_msg, tools, trace, context, stage_name,
              )
              result = build_stage_result(
                  result_cls, self.platform_info.id, stage_name,
                  trace, success=not hit_limit, iterations=iterations,
              )
              result.langsmith_run_id = langsmith_run_id
              return result
          except Exception as e:
              finish_trace(trace, error=str(e))
              return build_stage_result(
                  result_cls, self.platform_info.id, stage_name,
                  trace, success=False, iterations=0, error_message=str(e),
              )

      async def generate_requirements(self, context: StageContext) -> RequirementsResult:
          return await self._execute_stage("requirements", build_requirements_prompt, RequirementsResult, context)

      async def generate_code(self, context: StageContext) -> CodeResult:
          return await self._execute_stage("codegen", build_codegen_prompt, CodeResult, context)

      async def generate_tests(self, context: StageContext) -> TestResult:
          return await self._execute_stage("testing", build_testing_prompt, TestResult, context)

      async def build_and_deploy(self, context: StageContext) -> DeployResult:
          return await self._execute_stage("deploy", build_deploy_prompt, DeployResult, context)

      # ── Metadata ─────────────────────────────────────────────────────────

      def get_observability_info(self) -> dict[str, Any]:
          return {
              "has_tracing": True,
              "has_step_through": True,
              "has_replay": False,
              "has_state_inspection": True,
              "has_memory_inspection": False,
              "trace_format": "LangSmith",
              "notes": "Full graph-node tracing via LangSmith (LANGCHAIN_TRACING_V2=true required)",
          }

      def get_failure_handling_info(self) -> dict[str, Any]:
          return {
              "has_checkpointing": False,
              "has_auto_recovery": True,  # validator retry loop
              "has_graceful_degradation": True,
              "supports_human_handoff": False,
              "is_idempotent": True,
              "notes": "Validator retry loop: up to 3 retries per stage before graceful exit",
          }
  ```

- [ ] **Step 4: Run adapter tests**

  ```
  uv run pytest tests/test_langgraph_adapter.py -v
  ```

  Expected: all PASS (validator tests and graph structure tests).

- [ ] **Step 5: Run full test suite to check for regressions**

  ```
  uv run pytest tests/ -v --ignore=tests/test_deploy_remote.py
  ```

  Expected: all existing tests pass.

- [ ] **Step 6: Commit**

  ```bash
  git add src/desmet/adapters/langgraph.py tests/test_langgraph_adapter.py
  git commit -m "feat(langgraph): rewrite adapter to use StateGraph with planner/executor/validator"
  ```

---

## Task 3: LangSmith client

**Files:**
- Create: `src/desmet/webui/langsmith_client.py`
- Create: `tests/test_langsmith_client.py`

- [ ] **Step 1: Write failing tests**

  Create `tests/test_langsmith_client.py`:

  ```python
  """Unit tests for the LangSmith webUI client."""
  import pytest
  from unittest.mock import AsyncMock, patch, MagicMock


  class TestCheckStatus:
      @pytest.mark.asyncio
      async def test_returns_unavailable_when_no_api_key(self, monkeypatch):
          monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
          from desmet.webui.langsmith_client import check_status
          result = await check_status()
          assert result == {"available": False, "project": None}

      @pytest.mark.asyncio
      async def test_returns_available_on_200(self, monkeypatch):
          monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_pt_test")
          from desmet.webui.langsmith_client import check_status
          mock_resp = MagicMock()
          mock_resp.status_code = 200

          with patch("httpx.AsyncClient") as mock_client_cls:
              mock_client = AsyncMock()
              mock_client.__aenter__ = AsyncMock(return_value=mock_client)
              mock_client.__aexit__ = AsyncMock(return_value=False)
              mock_client.get = AsyncMock(return_value=mock_resp)
              mock_client_cls.return_value = mock_client
              result = await check_status()

          assert result["available"] is True

      @pytest.mark.asyncio
      async def test_returns_unavailable_on_exception(self, monkeypatch):
          monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_pt_test")
          from desmet.webui.langsmith_client import check_status

          with patch("httpx.AsyncClient") as mock_client_cls:
              mock_client = AsyncMock()
              mock_client.__aenter__ = AsyncMock(return_value=mock_client)
              mock_client.__aexit__ = AsyncMock(return_value=False)
              mock_client.get = AsyncMock(side_effect=Exception("network error"))
              mock_client_cls.return_value = mock_client
              result = await check_status()

          assert result["available"] is False


  class TestFetchRunTree:
      @pytest.mark.asyncio
      async def test_returns_none_when_no_api_key(self, monkeypatch):
          monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
          from desmet.webui.langsmith_client import fetch_run_tree
          result = await fetch_run_tree("some-run-id")
          assert result is None

      @pytest.mark.asyncio
      async def test_returns_none_on_exception(self, monkeypatch):
          monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_pt_test")
          from desmet.webui.langsmith_client import fetch_run_tree

          with patch("httpx.AsyncClient") as mock_client_cls:
              mock_client = AsyncMock()
              mock_client.__aenter__ = AsyncMock(return_value=mock_client)
              mock_client.__aexit__ = AsyncMock(return_value=False)
              mock_client.get = AsyncMock(side_effect=Exception("network error"))
              mock_client_cls.return_value = mock_client
              result = await fetch_run_tree("some-run-id")

          assert result is None

      @pytest.mark.asyncio
      async def test_assembles_tree_from_flat_children(self, monkeypatch):
          monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_pt_test")
          from desmet.webui.langsmith_client import fetch_run_tree

          root_resp = MagicMock()
          root_resp.raise_for_status = MagicMock()
          root_resp.json = MagicMock(return_value={
              "id": "root-1", "name": "desmet-langgraph-requirements",
              "run_type": "chain", "start_time": "2026-01-01T00:00:00Z",
              "end_time": "2026-01-01T00:01:00Z",
              "total_tokens": 500, "error": None, "tags": [],
              "inputs": None, "outputs": "done", "extra": {"total_tokens": 500},
          })

          child_resp = MagicMock()
          child_resp.raise_for_status = MagicMock()
          child_resp.json = MagicMock(return_value={"runs": [
              {
                  "id": "child-1", "name": "planner_node",
                  "run_type": "chain", "parent_run_id": "root-1",
                  "start_time": "2026-01-01T00:00:01Z",
                  "end_time": "2026-01-01T00:00:10Z",
                  "inputs": None, "outputs": None,
                  "extra": {"total_tokens": 100}, "error": None,
              }
          ]})

          call_count = 0
          async def mock_get(url, **kwargs):
              nonlocal call_count
              call_count += 1
              if call_count == 1:
                  return root_resp
              return child_resp

          with patch("httpx.AsyncClient") as mock_client_cls:
              mock_client = AsyncMock()
              mock_client.__aenter__ = AsyncMock(return_value=mock_client)
              mock_client.__aexit__ = AsyncMock(return_value=False)
              mock_client.get = mock_get
              mock_client_cls.return_value = mock_client
              result = await fetch_run_tree("root-1")

          assert result is not None
          assert result["run"]["id"] == "root-1"
          assert len(result["children"]) == 1
          assert result["children"][0]["name"] == "planner_node"
  ```

- [ ] **Step 2: Run tests to confirm they fail**

  ```
  uv run pytest tests/test_langsmith_client.py -v
  ```

  Expected: `ImportError` — module does not exist yet.

- [ ] **Step 3: Create `src/desmet/webui/langsmith_client.py`**

  ```python
  """Async client for querying the LangSmith REST API.

  Proxies requests server-side so API keys stay out of the browser.
  Degrades gracefully when LangSmith is not configured or unreachable.
  """
  from __future__ import annotations

  import os
  from typing import Any

  import httpx

  _TIMEOUT = 10.0


  def _get_api_key() -> str | None:
      return os.environ.get("LANGSMITH_API_KEY") or None


  def _base_url() -> str:
      return os.environ.get("LANGSMITH_BASE_URL", "https://api.smith.langchain.com").rstrip("/")


  def _headers() -> dict[str, str]:
      return {"X-API-Key": _get_api_key() or ""}


  async def check_status() -> dict[str, Any]:
      """Quick health check — can we reach LangSmith?"""
      key = _get_api_key()
      if not key:
          return {"available": False, "project": None}
      project = os.environ.get("LANGCHAIN_PROJECT")
      try:
          async with httpx.AsyncClient(timeout=3.0) as client:
              r = await client.get(
                  f"{_base_url()}/runs",
                  headers=_headers(),
                  params={"limit": 1},
              )
              return {"available": r.status_code == 200, "project": project}
      except Exception:
          return {"available": False, "project": project}


  def _truncate(value: Any, max_len: int = 500) -> str | None:
      if value is None:
          return None
      s = str(value)
      return s[:max_len] + "... [truncated]" if len(s) > max_len else s


  def _latency_ms(start: str | None, end: str | None) -> int:
      if not start or not end:
          return 0
      from datetime import datetime, timezone
      try:
          fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
          s = datetime.strptime(start, fmt).replace(tzinfo=timezone.utc)
          e = datetime.strptime(end, fmt).replace(tzinfo=timezone.utc)
          return max(0, int((e - s).total_seconds() * 1000))
      except Exception:
          return 0


  def _normalise_run(raw: dict) -> dict:
      """Normalise a raw LangSmith run dict into the DESMET LangSmithRun shape."""
      extra = raw.get("extra") or {}
      token_usage = extra.get("token_usage") or {}
      total = extra.get("total_tokens") or token_usage.get("total_tokens", 0)
      start = raw.get("start_time")
      end = raw.get("end_time")
      return {
          "id": raw.get("id"),
          "name": raw.get("name"),
          "run_type": raw.get("run_type", "chain"),
          "start_time": start,
          "end_time": end,
          "latency_ms": _latency_ms(start, end),
          "model": (extra.get("invocation_params") or {}).get("model_name"),
          "tokens": {
              "input": token_usage.get("prompt_tokens", 0),
              "output": token_usage.get("completion_tokens", 0),
              "total": total,
          },
          "error": raw.get("error"),
          "inputs": _truncate(raw.get("inputs")),
          "outputs": _truncate(raw.get("outputs")),
          "children": [],
      }


  async def fetch_run_tree(run_id: str) -> dict[str, Any] | None:
      """Fetch a LangSmith run and its full child-run tree."""
      key = _get_api_key()
      if not key:
          return None
      try:
          async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
              # Fetch root run
              r = await client.get(
                  f"{_base_url()}/runs/{run_id}",
                  headers=_headers(),
              )
              r.raise_for_status()
              root_raw = r.json()

              # Fetch child runs
              cr = await client.get(
                  f"{_base_url()}/runs",
                  headers=_headers(),
                  params={"parent_run_id": run_id, "limit": 100},
              )
              cr.raise_for_status()
              children_raw = cr.json().get("runs", [])

          # Normalise and assemble tree
          children_by_id: dict[str, dict] = {}
          for c in children_raw:
              node = _normalise_run(c)
              children_by_id[node["id"]] = node

          # Build nested tree from flat list
          roots: list[dict] = []
          for c_raw in children_raw:
              node = children_by_id[c_raw["id"]]
              parent_id = c_raw.get("parent_run_id")
              if parent_id and parent_id in children_by_id:
                  children_by_id[parent_id]["children"].append(node)
              elif parent_id == run_id or parent_id is None:
                  roots.append(node)

          roots.sort(key=lambda n: n.get("start_time") or "")

          start = root_raw.get("start_time")
          end = root_raw.get("end_time")
          extra = root_raw.get("extra") or {}
          total_tokens = extra.get("total_tokens", 0)

          return {
              "run": {
                  "id": root_raw.get("id"),
                  "name": root_raw.get("name"),
                  "run_type": root_raw.get("run_type", "chain"),
                  "start_time": start,
                  "end_time": end,
                  "latency_ms": _latency_ms(start, end),
                  "total_tokens": total_tokens,
                  "error": root_raw.get("error"),
                  "tags": root_raw.get("tags", []),
              },
              "children": roots,
          }
      except Exception:
          return None
  ```

- [ ] **Step 4: Run LangSmith client tests**

  ```
  uv run pytest tests/test_langsmith_client.py -v
  ```

  Expected: all PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add src/desmet/webui/langsmith_client.py tests/test_langsmith_client.py
  git commit -m "feat(webui): add LangSmith REST API client"
  ```

---

## Task 4: Backend API endpoints

**Files:**
- Modify: `src/desmet/webui/api.py`

Three changes to `api.py`:
1. Add `GET /api/langsmith/status`
2. Add `GET /api/langsmith/runs/{run_id}`
3. Update `GET /api/config` to include `langsmith_available`
4. Update `GET /api/dashboard/scoring/{platform_id}/{story_id}` to return `langsmith_run_id`

- [ ] **Step 1: Add LangSmith import to `api.py`**

  After the existing langfuse imports (around line 82), add:

  ```python
  from desmet.webui.langsmith_client import (
      check_status as langsmith_check_status,
  )
  from desmet.webui.langsmith_client import (
      fetch_run_tree as langsmith_fetch_run_tree,
  )
  ```

- [ ] **Step 2: Add `/api/langsmith/status` endpoint**

  Add after the existing `/api/langfuse/status` endpoint:

  ```python
  @app.get("/api/langsmith/status")
  async def langsmith_status():
      """Check LangSmith availability."""
      return await langsmith_check_status()
  ```

- [ ] **Step 3: Add `/api/langsmith/runs/{run_id}` endpoint**

  ```python
  @app.get("/api/langsmith/runs/{run_id}")
  async def langsmith_run(run_id: str):
      """Proxy a LangSmith run tree for the webUI trace viewer."""
      result = await langsmith_fetch_run_tree(run_id)
      if result is None:
          return {"error": "LangSmith unavailable or run not found"}
      return result
  ```

- [ ] **Step 4: Update `GET /api/config` to include `langsmith_available`**

  In `get_config()`, change the return statement to add the key:

  ```python
      langsmith = await langsmith_check_status()
      return {
          "model": cfg.model,
          "provider": provider.value,
          "api_keys_set": cfg.api_keys_set,
          "langfuse_status": cfg.langfuse_status,
          "temperature": float(os.getenv("DESMET_TEMPERATURE", "0.0")),
          "available_models": [
              "gpt-5.4-2026-03-05",
              "claude-opus-4-6", "claude-sonnet-4-6",
          ],
          "allow_custom_model": True,
          "valid_stages": ["requirements", "codegen", "testing", "deploy", "all"],
          "difficulty_levels": ["basic", "intermediate", "advanced"],
          "langsmith_available": langsmith["available"],
      }
  ```

  Note: `get_config()` is already `async def` at line 209 of `api.py` — no change needed to the function signature.

- [ ] **Step 5: Update scoring endpoint to return `langsmith_run_id`**

  In the scoring endpoint (around line 720), after `"langfuse_trace_id": langfuse_tid,` add the langsmith run ID extraction:

  ```python
      # Extract langsmith_run_id from stage data (LangGraph only)
      langsmith_run_id = next(
          (s.get("langsmith_run_id") for s in (raw_trace.get("stages") or {}).values()
           if s.get("langsmith_run_id")),
          None,
      ) if trace_files else None

      return {
          "found": True,
          "scored": is_story_scored(story_metric),
          "scores": scores,
          "notes": notes,
          "wall_clock_seconds": story_metric.get("wall_clock_seconds", 0),
          "iterations": story_metric.get("iterations", 0),
          "tool_calls": story_metric.get("tool_calls", 0),
          "success": story_metric.get("success", False),
          "trace": _sanitize_trace(trace_data) if trace_data else None,
          "langfuse_trace_id": langfuse_tid,
          "langsmith_run_id": langsmith_run_id,
      }
  ```

- [ ] **Step 6: Smoke-test the API**

  Start the webUI and verify the new endpoints respond:

  ```bash
  uv run uvicorn desmet.webui.api:app --port 8000 &
  sleep 3
  curl -s http://localhost:8000/api/langsmith/status | python -m json.tool
  curl -s http://localhost:8000/api/config | python -m json.tool | grep langsmith
  kill %1
  ```

  Expected: `{"available": false, "project": null}` and `"langsmith_available": false` (no key configured).

- [ ] **Step 7: Commit**

  ```bash
  git add src/desmet/webui/api.py
  git commit -m "feat(webui): add LangSmith API endpoints and langsmith_available to config"
  ```

---

## Task 5: Frontend TypeScript types

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/api.ts`

- [ ] **Step 1: Add `langsmith_available` to `AppConfig`**

  In `api.ts`, update the `AppConfig` interface (around line 28) to add the optional field:

  ```typescript
  export interface AppConfig {
    model: string;
    provider: string;
    api_keys_set: string[];
    langfuse_status: string;
    temperature: number;
    available_models: string[];
    allow_custom_model?: boolean;
    valid_stages: string[];
    difficulty_levels: string[];
    langsmith_available?: boolean;   // add this
  }
  ```

- [ ] **Step 2: Add `langsmith_run_id` to `StoryScoreData`**

  Update the `StoryScoreData` interface (around line 95):

  ```typescript
  export interface StoryScoreData {
    found: boolean;
    scored?: boolean;
    scores?: Record<string, number>;
    notes?: Record<string, string>;
    wall_clock_seconds?: number;
    iterations?: number;
    tool_calls?: number;
    success?: boolean;
    trace?: TraceData | null;
    langfuse_trace_id?: string | null;
    langsmith_run_id?: string | null;   // add this
  }
  ```

- [ ] **Step 3: Add LangSmith types and API function**

  After the `// ── Langfuse trace types ────────────────` block (after line 167), add:

  ```typescript
  // ── LangSmith trace types ────────────────

  export interface LangSmithRun {
    id: string;
    name: string;
    run_type: 'llm' | 'tool' | 'chain';
    start_time: string | null;
    end_time: string | null;
    latency_ms: number;
    model: string | null;
    tokens: { input: number; output: number; total: number };
    error: string | null;
    inputs: string | null;
    outputs: string | null;
    children: LangSmithRun[];
  }

  export interface LangSmithRunTree {
    run: {
      id: string;
      name: string;
      run_type: string;
      start_time: string | null;
      end_time: string | null;
      latency_ms: number;
      total_tokens: number;
      error: string | null;
      tags: string[];
    };
    children: LangSmithRun[];
  }
  ```

- [ ] **Step 4: Add `fetchLangSmithRun` function**

  After `// ── Langfuse ────────────────────────────` section (after the existing langfuse functions), add:

  ```typescript
  // ── LangSmith ────────────────────────────

  export const fetchLangSmithStatus = () =>
    request<{ available: boolean; project: string | null }>('/api/langsmith/status');

  export const fetchLangSmithRun = (runId: string) =>
    request<LangSmithRunTree>('/api/langsmith/runs/' + runId);
  ```

- [ ] **Step 5: Verify TypeScript compiles**

  ```bash
  cd src/desmet/webui/frontend && bun run check
  ```

  Expected: no TypeScript errors.

- [ ] **Step 6: Commit**

  ```bash
  git add src/desmet/webui/frontend/src/lib/api.ts
  git commit -m "feat(frontend): add LangSmith TypeScript types and API functions"
  ```

---

## Task 6: `LangSmithTraceViewer.svelte` component

**Files:**
- Create: `src/desmet/webui/frontend/src/lib/components/LangSmithTraceViewer.svelte`

- [ ] **Step 1: Create the component**

  ```svelte
  <script lang="ts">
    import { onMount } from 'svelte';
    import { fetchLangSmithRun } from '../api';
    import type { LangSmithRunTree, LangSmithRun, LangfuseObservation } from '../api';
    import SpanNode from './SpanNode.svelte';

    interface Props {
      runId: string;
    }

    let { runId }: Props = $props();

    let loading = $state(true);
    let error = $state<string | null>(null);
    let runTree = $state<LangSmithRunTree | null>(null);

    onMount(async () => {
      try {
        runTree = await fetchLangSmithRun(runId);
        if (!runTree) error = 'Run not found or LangSmith unavailable.';
      } catch (e) {
        error = 'Failed to load LangSmith trace.';
      } finally {
        loading = false;
      }
    });

    /** Normalise a LangSmithRun into a LangfuseObservation for SpanNode. */
    function normalise(run: LangSmithRun): LangfuseObservation {
      return {
        id: run.id,
        name: run.name,
        type: run.run_type === 'llm' ? 'generation' : 'span',
        start_time: run.start_time,
        end_time: run.end_time,
        latency_ms: run.latency_ms,
        model: run.model,
        tokens: run.tokens,
        cost: 0,
        level: run.error ? 'ERROR' : 'DEFAULT',
        status_message: run.error ?? null,
        input: run.inputs,
        output: run.outputs,
        children: run.children.map(normalise),
      };
    }
  </script>

  {#if loading}
    <div class="ls-state">Loading LangSmith trace…</div>
  {:else if error}
    <div class="ls-state ls-error">{error}</div>
  {:else if runTree}
    <div class="ls-header">
      <span class="ls-name">{runTree.run.name}</span>
      <span class="ls-meta">
        {(runTree.run.latency_ms / 1000).toFixed(2)}s
        · {runTree.run.total_tokens.toLocaleString()} tokens
        {#if runTree.run.tags?.length}· {runTree.run.tags.join(', ')}{/if}
      </span>
    </div>
    <div class="ls-tree">
      {#each runTree.children as child (child.id)}
        <SpanNode observation={normalise(child)} rootLatency={runTree.run.latency_ms} />
      {/each}
    </div>
  {/if}

  <style>
    .ls-state {
      padding: 24px;
      color: var(--text-2);
      font-size: 13px;
      text-align: center;
    }
    .ls-error { color: var(--red, #e53e3e); }
    .ls-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 12px;
      padding: 0 2px;
    }
    .ls-name {
      font-size: 13px;
      font-weight: 600;
      color: var(--text-0);
    }
    .ls-meta {
      font-size: 11px;
      font-family: var(--mono);
      color: var(--text-2);
    }
    .ls-tree { display: flex; flex-direction: column; gap: 2px; }
  </style>
  ```

- [ ] **Step 2: Verify TypeScript / Svelte compiles**

  ```bash
  cd src/desmet/webui/frontend && bun run check
  ```

  Expected: no errors.

- [ ] **Step 3: Commit**

  ```bash
  git add src/desmet/webui/frontend/src/lib/components/LangSmithTraceViewer.svelte
  git commit -m "feat(frontend): add LangSmithTraceViewer component"
  ```

---

## Task 7: Update `Scoring.svelte` — two-tab trace section

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/pages/Scoring.svelte`

- [ ] **Step 1: Add import at top of script block**

  After the existing `import TraceViewer from '../components/TraceViewer.svelte';` line, add:

  ```typescript
  import LangSmithTraceViewer from '../components/LangSmithTraceViewer.svelte';
  import { fetchConfig } from '../api';
  import type { AppConfig } from '../api';
  ```

  Also add a new state variable in the script block:

  ```typescript
  let appConfig = $state<AppConfig | null>(null);
  let activeTab = $state<'langfuse' | 'langsmith'>('langfuse');
  ```

- [ ] **Step 2: Load config in `onMount`**

  Update the `onMount` to also fetch config:

  ```typescript
  onMount(async () => {
    const [pRes, sRes, rub, cfg] = await Promise.all([
      fetchPlatforms(),
      fetchStories(),
      fetchRubric(),
      fetchConfig(),
    ]);
    platforms = (pRes as any).platforms || [];
    stories = (sRes as any).stories || [];
    rubric = rub;
    appConfig = cfg;
    // init scores
    if (rubric) {
      for (const dim of rubric.dimensions) {
        scores[dim] = 0;
        notes[dim] = '';
      }
    }
  });
  ```

- [ ] **Step 3: Replace the trace section in the template**

  Find the existing trace section (around line 184):

  ```svelte
  <!-- Trace -->
  {#if scoreData.langfuse_trace_id}
    <div>
      <h2 style="font-size: 14px; font-weight: 600; margin-bottom: 12px;">Execution Trace (Langfuse)</h2>
      <TraceViewer langfuseTraceId={scoreData.langfuse_trace_id} />
    </div>
  {:else if scoreData.trace?.messages?.length}
    <div>
      <h2 style="font-size: 14px; font-weight: 600; margin-bottom: 12px;">Execution Trace</h2>
      <TraceViewer messages={scoreData.trace.messages} />
    </div>
  {/if}
  ```

  Replace with:

  ```svelte
  <!-- Trace -->
  {#if scoreData.langfuse_trace_id || scoreData.trace?.messages?.length}
    {@const showLangSmithTab =
      selectedPlatform === 'langgraph' &&
      !!scoreData.langsmith_run_id &&
      appConfig?.langsmith_available === true}
    <div>
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
        <h2 style="font-size: 14px; font-weight: 600;">Execution Trace</h2>
        {#if showLangSmithTab}
          <div class="trace-tabs">
            <button
              class="trace-tab"
              class:active={activeTab === 'langfuse'}
              onclick={() => activeTab = 'langfuse'}
            >Langfuse Trace</button>
            <button
              class="trace-tab"
              class:active={activeTab === 'langsmith'}
              onclick={() => activeTab = 'langsmith'}
            >LangSmith Graph</button>
          </div>
        {/if}
      </div>

      {#if showLangSmithTab && activeTab === 'langsmith'}
        <LangSmithTraceViewer runId={scoreData.langsmith_run_id!} />
      {:else if scoreData.langfuse_trace_id}
        <TraceViewer langfuseTraceId={scoreData.langfuse_trace_id} />
      {:else if scoreData.trace?.messages?.length}
        <TraceViewer messages={scoreData.trace.messages} />
      {/if}
    </div>
  {/if}
  ```

- [ ] **Step 4: Add tab styles**

  In the `<style>` block of `Scoring.svelte` (or after the last closing `</style>` if there isn't one), add:

  ```css
  .trace-tabs {
    display: flex;
    gap: 4px;
    background: var(--bg-2);
    border-radius: 6px;
    padding: 3px;
  }
  .trace-tab {
    padding: 5px 14px;
    font-size: 12px;
    font-family: var(--sans);
    font-weight: 500;
    border: none;
    border-radius: 4px;
    background: transparent;
    color: var(--text-2);
    cursor: pointer;
    transition: background 0.1s, color 0.1s;
  }
  .trace-tab.active {
    background: var(--bg-0, #fff);
    color: var(--text-0);
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }
  ```

- [ ] **Step 5: Verify TypeScript / Svelte compiles**

  ```bash
  cd src/desmet/webui/frontend && bun run check
  ```

  Expected: no errors.

- [ ] **Step 6: Build frontend**

  ```bash
  cd src/desmet/webui/frontend && bun run build
  ```

  Expected: build succeeds with no errors.

- [ ] **Step 7: Commit**

  ```bash
  git add src/desmet/webui/frontend/src/lib/pages/Scoring.svelte
  git commit -m "feat(frontend): add two-tab trace section (Langfuse + LangSmith) to Scoring page"
  ```

---

## Task 8: Update `.env.example`

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add LangSmith variables**

  Add the following block to `.env.example` (after the existing Langfuse section):

  ```
  # ── LangSmith (LangGraph tracing — optional) ──────────────────────────
  # Required for LangSmith graph-node trace viewer in the webUI
  LANGSMITH_API_KEY=lsv2_pt_your_personal_access_token_here
  LANGCHAIN_TRACING_V2=true
  LANGCHAIN_PROJECT=desmet-evaluation
  # LANGSMITH_BASE_URL=https://api.smith.langchain.com  # override only if self-hosted
  ```

- [ ] **Step 2: Commit**

  ```bash
  git add .env.example
  git commit -m "docs(env): add LANGSMITH_API_KEY, LANGCHAIN_TRACING_V2, LANGCHAIN_PROJECT"
  ```

---

## Task 9: Integration smoke test

End-to-end verification without a live LangSmith key.

- [ ] **Step 1: Run full test suite**

  ```
  uv run pytest tests/ -v --ignore=tests/test_deploy_remote.py
  ```

  Expected: all tests pass.

- [ ] **Step 2: Start webUI and verify new endpoints**

  ```bash
  uv run uvicorn desmet.webui.api:app --port 8000 &
  sleep 3

  # LangSmith status (no key = unavailable)
  curl -s http://localhost:8000/api/langsmith/status
  # Expected: {"available":false,"project":null}

  # Config includes langsmith_available
  curl -s http://localhost:8000/api/config | python -m json.tool | grep langsmith
  # Expected: "langsmith_available": false

  # Non-existent run returns error gracefully
  curl -s http://localhost:8000/api/langsmith/runs/test-id
  # Expected: {"error":"LangSmith unavailable or run not found"}

  kill %1
  ```

- [ ] **Step 3: Verify frontend builds clean**

  ```bash
  cd src/desmet/webui/frontend && bun run build && bun run check
  ```

  Expected: build succeeds, zero TypeScript errors.

- [ ] **Step 4: Final commit (if any cleanup needed)**

  ```bash
  git add -p
  git commit -m "chore: integration smoke-test cleanup"
  ```

---

## Spec Reference

`docs/superpowers/specs/2026-03-24-langsmith-langgraph-design.md`
