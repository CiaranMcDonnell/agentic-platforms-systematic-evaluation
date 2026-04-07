#import "../template.typ": *

= Adding a Platform Adapter <appendix-adding-adapter>

This appendix provides a step-by-step guide for integrating a new agentic platform into the DESMET evaluation framework. The process involves implementing a single Python class and adding two small config entries. No changes to the runner, metrics engine, scoring engine, or web UI are required — the framework auto-discovers new adapters.

== Overview

The framework uses a three-level adapter hierarchy:

#figure(
  ```
  BasePlatformAdapter (ABC — harness/adapter.py)
    ├─ ToolAgentAdapter (adapters/_base.py)
    │    ├─ LangGraphAdapter
    │    ├─ CrewAIAdapter
    │    ├─ OpenAIAgentsAdapter
    │    ├─ AgentFrameworkAdapter
    │    └─ GoogleADKAdapter
    │
    └─ VisualAgentAdapter (adapters/_visual_base.py)
         ├─ FlowiseAdapter
         ├─ LangFlowAdapter
         ├─ DifyAdapter
         └─ N8nAdapter
  ```,
  caption: [Adapter class hierarchy],
)

Which base class you extend depends on how the platform is accessed:

#figure(
  table(
    columns: 2,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header([*Base class*], [*Use when the platform is...*]),
    [`ToolAgentAdapter`], [A Python SDK you import and call in-process (LangGraph, CrewAI, etc.).  You implement `_run_agent()`.],
    [`VisualAgentAdapter`], [A Docker service with a REST API (Flowise, Dify, etc.).  You implement `_run_workflow()` and `_collect_execution_metrics()`.],
  ),
  caption: [Choosing a base class],
)

Both base classes provide the same things for free:
- The retry loop with `audit_workspace()` validation
- Prompt construction from `_prompts.py`
- Trace lifecycle (start/finish/build result)
- The four SDLC stage methods (`generate_requirements`, `generate_code`, `generate_tests`, `build_and_deploy`)

Adapter authors only write the platform-specific method (`_run_agent` or `_run_workflow`) — everything else is inherited.

#figure(
  table(
    columns: 2,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header([*Step*], [*Artefact*]),
    [1. Add platform metadata], [`config/platforms.yaml`],
    [2. Implement the adapter], [`src/desmet/adapters/my_platform.py`],
    [3. Register in the registry], [`src/desmet/adapters/registry.py`],
    [4. Run the smoke test], [`data/stories/basic/US000_adapter_smoke_test.yaml`],
  ),
  caption: [Steps to add a new platform adapter],
)

== Step 1: Platform Metadata

Add an entry to `config/platforms.yaml`:

#figure(
  ```yaml
  platforms:
    # ... existing entries ...
    - id: my_platform
      name: My Platform
      category: agent_sdk_runtime        # or multi_agent_framework, visual_workflow_platform
      runtime: Python                     # or NodeJS, Docker
      vendor: Vendor Name
      description: Brief description of the platform
      documentation_url: https://docs.example.com
      repository_url: https://github.com/example/platform
      pip_extra: my-platform              # name of the optional extra in pyproject.toml (coded only)
      python_package: my_platform_sdk     # import name for health-check (coded only)
      deploy_port: 8010                   # unique port in 8000-8099 range
      colour: "#ff6b6b"                   # for dashboard charts
  ```,
  caption: [Platform metadata entry in `platforms.yaml`],
)

Valid categories are `multi_agent_framework`, `agent_sdk_runtime`, and `visual_workflow_platform`. Valid runtimes are `Python`, `NodeJS`, and `Docker`.

For coded platforms, also add the SDK as an optional extra in `pyproject.toml`:

#figure(
  ```toml
  [project.optional-dependencies]
  my-platform = ["my-platform-sdk>=1.0.0"]
  ```,
  caption: [Optional dependency in `pyproject.toml`],
)

== Step 2a: Implementing a Tool-Based Adapter (Coded Platform)

Extend `ToolAgentAdapter` and implement `_run_agent`. The shared pipeline handles everything else.

=== The `_run_agent` Signature

#figure(
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
      """Run the platform's agent for one SDLC stage.

      Returns (iterations, hit_limit).
      """
  ```,
  caption: [`_run_agent` method signature],
)

Parameter purposes:

#figure(
  table(
    columns: 2,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header([*Parameter*], [*Purpose*]),
    [`stage_name`], [One of `"requirements"`, `"codegen"`, `"testing"`, `"deploy"`.],
    [`prompt`], [Fully-built stage prompt from `build_requirements_prompt()` etc.],
    [`system_msg`], [Optional system message from `build_system_message()`.],
    [`tools`], [Tools already in the platform's native format (see `TOOL_FORMAT` below).],
    [`collector`], [Observation collector — record LLM responses, messages, and tool calls here.],
    [`context`], [`StageContext` with budgets, constraints, and prior artefacts.],
    [`policy`], [`RetryPolicy` — call `.validate()` after each attempt and `.total_attempts()` for the limit.],
    [`progress`], [`ProgressReporter` — call `.tool_call()`, `.agent_status()`, `.validation_passed()` etc.],
  ),
  caption: [`_run_agent` parameter reference],
)

=== Minimal Coded-Adapter Example

#figure(
  ```python
  from desmet.adapters._base import ToolAgentAdapter
  from desmet.adapters._observation import ObservationCollector
  from desmet.adapters._retry import ProgressReporter, RetryPolicy
  from desmet.adapters._tools import ToolFormat
  from desmet.adapters.registry import load_platform_info
  from desmet.harness.context import StageContext
  from desmet.harness.models import PlatformInfo

  class MyPlatformAdapter(ToolAgentAdapter):
      TOOL_FORMAT = ToolFormat.CALLABLE

      @property
      def platform_info(self) -> PlatformInfo:
          info = load_platform_info("my_platform")
          info.version = self._get_version()
          return info

      def _get_version(self) -> str:
          try:
              import my_platform_sdk
              return my_platform_sdk.__version__
          except ImportError:
              return "not installed"

      async def initialize(self) -> None:
          from desmet.llm_config import get_config
          cfg = get_config(model=self.config.get("model"))
          self._client = my_platform_sdk.Client(api_key=cfg.api_key, model=cfg.model)
          self._initialized = True

      async def shutdown(self) -> None:
          self._client = None
          self._initialized = False

      async def health_check(self) -> bool:
          return self._initialized and self._client is not None

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
          collector.record_message("user", prompt)

          total_iterations = 0
          for attempt in range(policy.total_attempts()):
              result = await self._client.run(
                  prompt=prompt, system=system_msg, tools=tools,
                  max_iterations=context.max_iterations,
              )

              # Record observation data
              collector.record_llm_response(
                  raw_usage={"prompt_tokens": result.input_tokens,
                             "completion_tokens": result.output_tokens},
              )
              for tc in result.tool_calls:
                  collector.record_tool_execution(tc.name, tc.args, tc.result)
                  progress.tool_call(tc.name, tc.args)

              total_iterations += result.steps

              # Validate workspace and retry if needed
              passed, feedback = policy.validate()
              if passed:
                  progress.validation_passed()
                  break
              progress.validation_failed(attempt + 1, policy.total_attempts(), feedback)

          collector.mark_iterations(total_iterations)
          hit_limit = total_iterations >= context.max_iterations
          return total_iterations, hit_limit
  ```,
  caption: [Complete minimal coded-adapter implementation],
)

The four SDLC stage methods are inherited from `ToolAgentAdapter` — no need to implement them.

=== Tool Formats

Set the class attribute `TOOL_FORMAT` so `create_tools()` produces tools in the format your SDK expects:

#figure(
  table(
    columns: 2,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header([*Format*], [*Use for*]),
    [`LANGCHAIN`], [LangGraph (returns `@tool`-decorated functions)],
    [`CREWAI`], [CrewAI (returns `BaseTool` subclasses)],
    [`OPENAI_AGENTS`], [OpenAI Agents SDK (returns `FunctionTool` instances)],
    [`AGENT_FRAMEWORK`], [Microsoft Agent Framework (returns `@tool` functions)],
    [`CALLABLE`], [Any platform (returns plain Python callables)],
  ),
  caption: [Tool format options],
)

== Step 2b: Implementing a Visual Adapter (Platform with REST API)

Extend `VisualAgentAdapter` and implement `_run_workflow()` and `_collect_execution_metrics()`. The retry loop, trace management, and SDLC methods are all inherited.

=== The `_run_workflow` Signature

#figure(
  ```python
  async def _run_workflow(
      self,
      stage_name: str,
      prompt: str,
      system_msg: str,
      workspace: str,
  ) -> dict:
      """Execute one workflow attempt on the platform.

      Creates the workflow, executes it, cleans it up, and returns the
      raw execution data dict.  Called once per retry attempt.
      """
  ```,
  caption: [`_run_workflow` method signature],
)

The `workspace` path is already translated to the container-side path (`/desmet-results/...`) by `_translate_workspace()` — your workflow templates should use it directly for shell commands and file operations.

=== Minimal Visual-Adapter Example

#figure(
  ```python
  import httpx
  from desmet.adapters._tracing import record_usage
  from desmet.adapters._visual_base import VisualAgentAdapter
  from desmet.adapters.registry import load_platform_info
  from desmet.harness.models import PlatformInfo

  class MyVisualAdapter(VisualAgentAdapter):
      def __init__(self, config: dict | None = None):
          config = config or {}
          super().__init__(
              base_url=config.get("base_url", "http://localhost:8080"),
              api_key=config.get("api_key"),
              config=config,
          )
          self._client: httpx.AsyncClient | None = None
          self._model_name: str | None = None

      @property
      def platform_info(self) -> PlatformInfo:
          return load_platform_info("my_platform")

      async def initialize(self) -> None:
          self._client = httpx.AsyncClient(
              base_url=self.base_url, timeout=300.0,
          )
          # Verify reachability
          resp = await self._client.get("/health")
          if resp.status_code != 200:
              raise RuntimeError(f"Platform not reachable at {self.base_url}")
          from desmet.llm_config import get_config
          self._model_name = get_config(model=self.config.get("model")).model
          self._initialized = True

      async def shutdown(self) -> None:
          if self._client:
              await self._client.aclose()
              self._client = None
          self._initialized = False

      async def health_check(self) -> bool:
          if self._client is None:
              return False
          try:
              resp = await self._client.get("/health")
              return resp.status_code == 200
          except Exception:
              return False

      # ── VisualPlatformAdapter contract ──────────────────────────
      async def create_workflow(self, definition: dict) -> str:
          resp = await self._client.post("/api/workflows", json=definition)
          resp.raise_for_status()
          return resp.json()["id"]

      async def execute_workflow(self, workflow_id: str, inputs: dict) -> dict:
          resp = await self._client.post(
              f"/api/workflows/{workflow_id}/run", json=inputs,
          )
          resp.raise_for_status()
          return resp.json()

      async def delete_workflow(self, workflow_id: str) -> None:
          await self._client.delete(f"/api/workflows/{workflow_id}")

      # ── VisualAgentAdapter abstract methods ─────────────────────
      async def _run_workflow(
          self, stage_name: str, prompt: str,
          system_msg: str, workspace: str,
      ) -> dict:
          # Build your workflow JSON with the prompt, system message, and
          # workspace path interpolated.  Each run is a full create →
          # execute → cleanup cycle.
          definition = build_my_workflow(
              stage_name, prompt, system_msg, workspace,
              model=self._model_name,
          )
          workflow_id = await self.create_workflow(definition)
          try:
              return await self.execute_workflow(workflow_id, {"prompt": prompt})
          finally:
              try:
                  await self.delete_workflow(workflow_id)
              except Exception:
                  pass

      def _collect_execution_metrics(self, trace, exec_data: dict) -> None:
          usage = exec_data.get("token_usage", {})
          inp = usage.get("prompt_tokens", 0)
          out = usage.get("completion_tokens", 0)
          if inp or out:
              record_usage(trace, int(inp), int(out), model=self._model_name)
  ```,
  caption: [Complete minimal visual-adapter implementation],
)

For visual platforms that run in Docker, also add a service entry to `infrastructure/docker-compose.yaml` and add the workspace volume mount (`${DESMET_RESULTS_DIR:-../results}:/desmet-results`) so the platform's code-execution environment can see the stage workspace.

== Step 3: Register the Adapter

Add the adapter to `ADAPTER_REGISTRY` in `src/desmet/adapters/registry.py`:

#figure(
  ```python
  ADAPTER_REGISTRY: dict[str, tuple[str, str]] = {
      # ... existing entries ...
      "my_platform": (
          "desmet.adapters.my_platform",
          "MyPlatformAdapter",
      ),
  }
  ```,
  caption: [Registering a new adapter],
)

That's the only bookkeeping. The `list_available_platforms()` function auto-derives implementation status by importing the adapter and checking it isn't a `_is_desmet_stub` class — there is no hand-maintained "implemented" list to update.

== Step 4: Verify

Run the smoke-test story on the new adapter:

#figure(
  ```bash
  uv run desmet
  # In the web UI: New Run → select my_platform → stories: US-000 → Start
  ```,
  caption: [Running the smoke test],
)

`US000_adapter_smoke_test` is a trivial hello-world task with a 120 s time budget and 8-iteration max. It validates the full requirements → codegen → testing → deploy pipeline without burning significant tokens.  If US-000 passes, the adapter is wired up correctly.

Results appear in the dashboard automatically. The new platform shows up in all web UI pages (platform list, new run form, dashboard, scoring panel) with no frontend changes needed.

== Web UI Integration

The management console discovers platforms dynamically through the `/api/platforms` endpoint, which reads from the adapter registry and `platforms.yaml` at runtime. Once registered, the new platform automatically appears in:

- *Platform list* --- shown with its category, runtime, and readiness status
- *New Run form* --- available as a selectable platform for benchmark runs
- *Dashboard* --- included in radar charts, rankings, and scoring matrices after results are collected
- *Scoring panel* --- ready for manual rubric grading per story

The web UI distinguishes between _registered_ platforms (in `ADAPTER_REGISTRY`) and _implemented_ platforms (import-succeeds + not a stub). Stub and unimportable adapters appear in the UI but cannot be selected for runs.

== Adding a New Tool Format

If the platform's SDK requires tools in a format not covered by the existing `ToolFormat` enum, a new format builder can be added to `src/desmet/adapters/_tools.py`:

+ Add a new entry to the `ToolFormat` enum
+ Implement a `_build_<format>_tools()` function following the pattern of existing builders
+ Add a branch to the `create_tools()` dispatcher

Each builder receives the same set of format-agnostic tool implementations (file I/O, shell execution, code search, deploy) and wraps them in the platform's expected interface. This ensures tool behaviour is consistent across all platforms regardless of format.

== Platform-Specific Docker Setup

Coded platforms build Docker images from `infrastructure/Dockerfile.platform`, which takes a `PLATFORM_EXTRA` build-arg and installs only that platform's `uv` optional extra. This gives each platform its own isolated Python environment without requiring a per-platform Dockerfile.

If your platform needs custom system packages, a different base image, or compile steps, create `infrastructure/Dockerfile.<platform-id>` and `container_runner.dockerfile_path()` will prefer it over the shared template. See `infrastructure/Dockerfile.framework.example` for a complete reference with examples.
