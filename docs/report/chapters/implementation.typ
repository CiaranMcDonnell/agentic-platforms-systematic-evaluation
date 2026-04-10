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

== Web-Based Management Console <sec-webui>

The evaluation harness includes a purpose-built web-based management console that serves as the primary instrument for conducting evaluations. Rather than a convenience wrapper around CLI commands, the console operationalises the evaluation methodology: it embeds the scoring rubric, provides trace-level evidence for qualitative judgements, visualises multi-agent orchestration patterns, and produces the cross-platform comparison analysis. This section describes its architecture, capabilities, and role in the evaluation workflow.

=== Architecture

The console follows a two-tier architecture. The backend is a FastAPI application (`src/desmet/webui/api.py`) exposing approximately 45 REST endpoints and two WebSocket channels---one for live log streaming during pipeline execution, one for Docker image build progress. The frontend is a Svelte~5 single-page application compiled to static assets and served by the backend on port~8042. Reactive state management uses Svelte~5 runes (`$state`, `$derived`) with a centralised data layer (`data.svelte`) that polls the backend for infrastructure health, platform status, and run progress.

The console launches automatically via the `desmet` CLI (see @appendix-getting-started) and starts the Langfuse tracing infrastructure as a core dependency on startup. All evaluation data flows through the same `ResultStore` (DuckDB-backed, see @sec-metrics) used by the CLI, ensuring consistency between console-driven and programmatic evaluations.

=== Evaluation Workflow Pages

The console is organised into two navigation groups---_Manage_ (pipeline execution) and _Results_ (analysis and scoring)---reflecting the two phases of an evaluation session.

==== Pipeline Execution

Five pages support the execution phase:

- *Dashboard*: Provides an at-a-glance overview of the evaluation environment. Cards display infrastructure service health (Langfuse, Redis, Postgres), the number of implemented platform adapters, available LLM providers with per-provider model counts discovered at startup, and a summary of recent evaluation runs. Infrastructure services can be started and stopped directly from the dashboard.

- *Platforms*: Lists all nine platforms with their adapter implementation status, category, and Docker container state. For platforms backed by Docker services (visual/workflow platforms), start and stop controls are provided. The page also surfaces platform-level developer metrics where available.

- *Stories*: Displays all user stories loaded from `data/stories/`, filterable by difficulty level (basic, intermediate, advanced). Each story card shows the title, description, acceptance criteria count, time budget, and maximum iteration limit. Selecting a story navigates to a detail view with the full acceptance criteria list.

- *New Run*: The launch page for pipeline execution. The evaluator selects one or more platforms, one or more stories, and optionally overrides the LLM model and temperature. Clicking _Start_ creates a run record in the `ResultStore`, initialises the `EvaluationRunner`, and redirects to the Run Detail page for live monitoring.

- *Run Detail*: Displays real-time execution progress via a WebSocket connection. A live log viewer streams structured log output from the runner, including stage transitions, tool invocations, token usage snapshots, and error events. A status badge tracks the run lifecycle (queued → running → completed / failed / cancelled). A cancel button sends a stop signal to the runner, enabling early termination of runs that are consuming excessive tokens or time.

==== Analysis and Scoring

Four pages support the results analysis phase:

- *Results Overview*: Presents aggregate metrics across all completed runs. ECharts-rendered visualisations include completion rate bar charts (per platform), dimension score bar charts (per dimension across platforms), efficiency breakdowns (time vs.\ token vs.\ cost components), and story-level comparison charts. All charts are generated server-side and delivered as ECharts option JSON, ensuring consistent rendering.

- *Scoring*: The centrepiece of the evaluation workflow. This page operationalises the 0--3 scoring rubric defined in the Design chapter. The evaluator selects a platform--story combination and is presented with three tabbed evidence panels alongside the scoring form:

  + _Langfuse trace_: A hierarchical span tree rendered from Langfuse observation data, showing each LLM call, tool invocation, and agent transition with token counts, timing, and input/output content. Spans are rendered as a nested timeline with expandable detail drawers.

  + _LangSmith trace_: For LangGraph runs, a complementary run tree fetched from LangSmith, providing LangGraph-specific state snapshots and checkpoint data.

  + _Agent graph_: A directed graph visualisation of the multi-agent communication topology (described in detail below).

  The scoring form presents each of the six rubric dimensions (pipeline completeness, tool integration, error recovery, time efficiency, autonomy, trace quality) with a 0--3 slider and a free-text notes field. Scores are persisted via the `ResultStore` and immediately reflected in the comparison charts. Previously submitted scores are pre-loaded when revisiting a platform--story combination, enabling iterative refinement.

- *Story Detail*: Provides a per-story cross-platform view. For a selected story, displays each platform's execution metrics (tokens, time, cost, iterations, tool calls) and scoring status. A _Score this_ link navigates directly to the Scoring page with the platform and story pre-selected, streamlining the evaluator's workflow through the story set.

- *Comparison*: The synthesis page that produces the cross-platform analysis. A radar chart overlays all scored platforms on the four cross-cutting dimensions (Pipeline Completeness, Efficiency, Orchestration, Autonomy). A bar chart ranks platforms by overall score. A score matrix heatmap shows per-platform per-dimension scores with colour intensity encoding magnitude. Dimension-specific bar charts can be selected from a dropdown for detailed single-dimension comparison.

=== Agent Communication Graph

The agent graph is a novel visualisation component that makes multi-agent orchestration patterns directly observable. During qualitative scoring, the evaluator can inspect how agents communicated, delegated, and coordinated---information that is critical for scoring the _Orchestration_ dimension but difficult to extract from raw trace logs.

The graph is constructed from Langfuse trace data via a server-side endpoint (`/api/dashboard/graph/{platform_id}/{story_id}`) that extracts agent nodes and message edges from the observation tree. The frontend renders this as an interactive directed graph using the following pipeline:

+ *Trace parsing*: The backend traverses the Langfuse observation hierarchy, identifying agent-level spans (generations and chains) and extracting parent--child relationships and message content.

+ *Graph construction*: Agent nodes are grouped into cluster containers reflecting the platform's orchestration topology---for example, a CrewAI sequential crew appears as a container with planner, executor, and reviewer nodes arranged in sequence, while a MagenticOne team shows a central manager node with edges to specialist agents.

+ *ELK layout*: The graph input is passed to ELK (Eclipse Layout Kernel) via `elkjs` for automatic hierarchical layout, producing positioned nodes and routed edges that minimise crossings.

+ *Interactive rendering*: The laid-out graph is rendered using `@xyflow/svelte` with custom node components (`AgentNode` for leaf agents, `AgentClusterNode` for containers) and custom edge components (`TransitionEdge` with animated message flow). Clicking a node opens an `ObservationDrawer` showing the full LLM call detail (prompt, response, token usage, timing). A `TimelineCard` component shows the chronological execution sequence alongside the spatial graph.

This visualisation directly supports the evaluation methodology: the graph reveals whether a platform's agents actually collaborated (multiple agents with bidirectional edges) or merely executed sequentially (linear chain), whether the reviewer agent received the executor's output, and whether error recovery involved re-planning or simple retry. These observations inform the qualitative scoring of Orchestration and Autonomy dimensions.

=== Observability Integration

The console integrates with two observability providers to give the evaluator comprehensive trace evidence:

- *Langfuse*: The primary tracing backend, started automatically on console launch. The `TraceViewer` component renders the full observation tree with expandable spans. The `SpanNode` component shows per-span token counts, duration, and a truncated preview of input/output content. The `TimelineView` provides a horizontal timeline of all spans for temporal analysis. Trace data is fetched via the Langfuse client SDK (`webui/langfuse_client.py`), which handles authentication, pagination, and observation tree assembly.

- *LangSmith*: A secondary provider enabled for LangGraph evaluations. The `LangSmithTraceViewer` component renders the LangGraph-specific run tree, including state checkpoint data and graph node transitions. Availability is checked lazily on first access and indicated in the Scoring page tab bar.

Dual-provider support allows the evaluator to cross-reference traces---for example, comparing Langfuse's framework-agnostic span tree with LangSmith's LangGraph-specific state transitions to verify that checkpoint data is being recorded correctly.

// TODO: Consider adding a figure showing the Scoring page layout with the three evidence tabs and scoring form side by side.

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
