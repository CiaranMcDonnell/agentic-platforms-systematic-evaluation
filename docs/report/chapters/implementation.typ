#import "../template.typ": *

= Implementation

This chapter describes the technical implementation of the evaluation infrastructure: the harness architecture, platform adapter design, pipeline stage modules, metrics collection, and the web-based management console.

== Evaluation Harness Architecture

The evaluation is driven by a purpose-built Python harness (`desmet`) that orchestrates pipeline execution across all platforms. The harness is designed around three principles: platform-agnostic orchestration, automated metric collection, and structured result storage.

@fig-stage-detail shows the per-stage metrics and outputs defined for each pipeline stage, and @fig-dimension-formulas presents the four cross-cutting dimension aggregation formulas.

#include "../diagrams/implementation/pipeline-stage-detail.typ"

=== Core Components

The harness comprises the following core modules:

- *Runner* (`harness/runner.py`): Orchestrates the four-stage pipeline for a given platform and story, invoking the adapter's stage methods sequentially and collecting results.
- *Base Adapter* (`harness/adapter.py`): Abstract base class defining the four-method interface that all platform adapters must implement.
- *Story Loader* (`stages/stage1_stories/loader.py`): Loads and validates YAML story definitions, preparing the `StageContext` passed to each pipeline stage.
- *Metrics Collector* (`harness/metrics.py`): Collects per-stage metrics (tokens, timing, costs) and computes cross-cutting dimension scores.

// TODO: Expand with implementation details — how the runner handles errors,
// how stage results chain into subsequent stages, etc.

@fig-harness-arch shows the component architecture of the evaluation harness.

#include "../diagrams/implementation/harness-architecture.typ"

== Platform Adapter Design

=== Adapter Interface

All platform adapters extend `BasePlatformAdapter` and implement four methods corresponding to the pipeline stages:

// TODO: Include a code listing or table showing the 4-method interface:
// generate_requirements(), generate_code(), generate_tests(), build_and_deploy()
// with their input/output types (StageContext → StageResult).

=== Implemented Adapters

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Platform*], [*Adapter Status*], [*Notes*],
    ),
    [LangGraph], [Implemented], [],
    [CrewAI], [Implemented], [],
    [OpenAI Agents SDK], [Implemented], [3-agent handoff chain with output guardrails],
    [Google ADK], [Implemented], [SequentialAgent + LoopAgent orchestration],
    [Microsoft Agent Framework], [Implemented], [MagenticOne manager-driven orchestration],
    [Flowise], [Stub], [],
    [LangFlow], [Stub], [],
    [Dify], [Stub], [],
    [N8n], [Stub], [],
  ),
  caption: [Platform Adapter Implementation Status],
)

// TODO: For each implemented adapter, describe:
// - How the platform's API/SDK is invoked
// - How token usage is captured (e.g., CrewAI's UsageMetrics from litellm)
// - Any platform-specific challenges or workarounds
// Cite: @wu2023autogen @duan2024exploration @crewai2024 for platform-specific details

== Pipeline Stage Implementation

=== Stage 1: Requirements \& Design

// TODO: Describe the requirements agent, schema definitions (input/output),
// PlantUML template generation. Reference stage2_requirements/ module.
// Cite: @cheng2024genai_re for GenAI requirements engineering approaches

=== Stage 2: Code Generation

// TODO: Describe how requirements + UML are passed to the platform for code generation.
// Reference stage3_codegen/ module (stub status).

=== Stage 3: Test Generation

// TODO: Describe how requirements + generated code are passed for test generation.
// Reference stage4_testing/ module (stub status).
// Cite: @garousi2024ai_testing for AI-powered testing tools survey

=== Stage 4: Build \& Deploy

The final pipeline stage evaluates each platform's ability to orchestrate a complete deployment sequence. Rather than delegating to a CI/CD system such as GitHub Actions, the agent is given direct tool access and must determine the correct execution order itself. This design choice ensures the evaluation measures the platform's orchestration capability, not the CI system's @shahin2017cicd.

The agent interacts with a single `deploy_remote` tool exposing three actions:

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Action*], [*Operation*], [*What it measures*],
    ),
    [`push`], [Commits workspace changes and pushes to the deploy repository via git], [Can the platform trigger artifact delivery?],
    [`restart`], [SSH to the target server, pulls the branch, runs `docker compose up -d --build`], [Can the platform start/restart a service?],
    [`health_check`], [SSH to the target server and curls the service endpoint], [Does the platform verify its own work?],
  ),
  caption: [Deploy stage tool actions and their evaluation purpose],
)

The harness initialises the workspace as a git repository with the deploy remote pre-configured before the stage begins. Each platform--story combination pushes to a dedicated branch (`{platform_id}/{story_id}`), providing isolation within a single repository. On the target server, nginx routes platform-specific subdomains to unique container ports, and a Cloudflare-proxied origin certificate handles TLS termination.

The deploy target runs a restricted user (`desmet`) with a whitelisted shell that permits only `git pull`, `docker compose`, `docker ps`, and `curl`. SSH access is restricted to a Tailscale VPN. This security model prevents any agent-initiated action from affecting other services on the shared server while still providing a realistic deployment environment.

This stage contributes to multiple evaluation dimensions: _Orchestration_ (correct sequencing of push → restart → health check), _Error Recovery_ (retrying a failed restart or diagnosing a health check failure), and _Autonomy_ (whether the agent calls `health_check` unprompted to verify the deployment).

== Metrics Collection and Token Tracking

=== Automatic Instrumentation

The harness automatically captures resource consumption metrics at each pipeline stage:

// TODO: Describe how token usage is tracked — LLM config centralisation,
// provider-specific extraction (OpenAI usage objects, CrewAI UsageMetrics),
// wall-clock timing via context managers, API cost estimation.

=== Cross-cutting Dimension Computation

The four cross-cutting dimensions (Pipeline Completeness, Efficiency, Orchestration, Autonomy) are computed from per-stage metrics using the formulas defined in the Project Approach and Design chapter. The implementation in `harness/metrics.py` directly encodes these formulas. All dimensions measure framework capability, not LLM output quality.

// TODO: Reference the specific formula implementations. Briefly describe
// the fallback behaviour when stage-level data is unavailable.

== Web-Based Management Console

A FastAPI-based web UI (`src/desmet/webui/`) serves as the management console for the evaluation harness, launched via the `desmet` CLI on port 8042 (see @appendix-getting-started). The backend exposes REST endpoints for platform management, benchmark execution, and results visualisation, alongside WebSocket support for live execution logs. The dashboard data layer (`dashboard/data.py`, `dashboard/charts.py`) provides chart generation and platform summary DataFrames consumed by the web UI.

// TODO: Describe the web UI pages and functionality in more detail.

== Extending the Framework

The evaluation framework is designed for extensibility. Researchers or practitioners wishing to evaluate additional agentic platforms or modify the benchmark pipeline can do so with minimal changes. This section documents the extension points.

=== Adding a Platform Adapter

Tool-based adapters extend `ToolAgentAdapter` (`adapters/_base.py`), which provides the four SDLC stage methods and the shared `_execute_stage` template. The adapter author implements a single method --- `_run_agent` --- containing the platform-specific agent execution logic:

#figure(
  ```python
  class ToolAgentAdapter(BasePlatformAdapter):
      TOOL_FORMAT: ToolFormat  # set by subclass

      async def _run_agent(
          self, stage_name, prompt, system_msg,
          tools, trace, context,
      ) -> tuple[int, bool]: ...  # implement this

      # Provided for free:
      async def _execute_stage(...): ...
      async def generate_requirements(...): ...
      async def generate_code(...): ...
      async def generate_tests(...): ...
      async def build_and_deploy(...): ...
  ```,
  caption: [`ToolAgentAdapter` --- one method to implement],
)

To add a new platform:

+ *Create the adapter* --- implement a new Python module in `src/desmet/adapters/` extending `ToolAgentAdapter`. Set `TOOL_FORMAT` and implement `_run_agent` with the platform's SDK invocation logic. Prompt construction, tool creation, trace lifecycle, and result building are handled by the base class.

+ *Register the adapter* --- add an entry in `src/desmet/adapters/registry.py` mapping the platform identifier to the adapter class.

+ *Define platform metadata* --- add the platform's metadata (name, category, version, description) to `config/platforms.yaml`.

No changes to the runner, metrics, or web UI are required. A complete worked example is provided in @appendix-adding-adapter.

=== Adding User Stories

User stories are defined as YAML files in `data/stories/`, organised by difficulty level (basic, intermediate, advanced). Each story specifies a title, description, acceptance criteria, time budget, and expected tool usage. The story loader validates the YAML against the `UserStory` schema and prepares the `StageContext` automatically. Adding a new story requires only a new YAML file conforming to this schema.

=== Configuring a Deploy Target

The deploy stage requires a target server with Docker and git. The framework connects via SSH using environment variables (`DEPLOY_HOST`, `DEPLOY_PORT`, `DEPLOY_USER`, `DEPLOY_KEY_PATH`, `DEPLOY_REPO`). A reverse proxy routes platform-specific subdomains to container ports. The complete server setup procedure, including SSH hardening, restricted shell configuration, and the security model for shared servers, is documented in @appendix-deploy-setup.

== Technical Challenges

// TODO: Document significant implementation challenges encountered:
// - Platform API differences and normalisation
// - Token tracking across different LLM providers
// - Async execution and error handling
// - Ensuring reproducibility across runs
