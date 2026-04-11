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
    [LangGraph], [Implemented], [Three-node StateGraph with InMemorySaver checkpointing],
    [CrewAI], [Implemented], [Sequential Crew with role-based agents and iteration budget control],
    [OpenAI Agents SDK], [Implemented], [3-agent handoff chain with output guardrails],
    [Google ADK], [Implemented], [SequentialAgent + LoopAgent orchestration],
    [Microsoft Agent Framework], [Implemented], [MagenticOne manager-driven orchestration],
    [Flowise], [Implemented], [REST API chatflow creation and execution via Docker],
    [LangFlow], [Implemented], [REST API flow creation and execution via Docker],
    [Dify], [Implemented], [Dual Console/Service API with app lifecycle management],
    [N8n], [Implemented], [REST API v1 workflow creation with credential provisioning],
  ),
  caption: [Platform Adapter Implementation Status],
)

Each implemented adapter extends `ToolAgentAdapter` and provides a single method---`_run_agent`---containing the platform-specific agent execution logic. The shared base class handles prompt construction, tool creation, trace lifecycle, retry orchestration, and result building. The descriptions below focus on each adapter's idiomatic use of its platform's native capabilities.

*LangGraph* (`adapters/langgraph.py`): Implements a three-node `StateGraph` with `InMemorySaver` checkpointing. The parent graph threads `ParentState` (plan text, retry count, validator feedback) through planner → executor → reviewer nodes, with a conditional edge from the reviewer back to the executor on validation failure. Each node is a compiled subgraph with private `SubgraphState` accumulating `BaseMessage` history via LangGraph's `add_messages` reducer. This architecture exploits LangGraph's native state persistence: conversation history survives across retries without manual serialisation, and the checkpoint mechanism enables post-hoc replay of agent interactions for trace analysis @langchain2024langgraph.

*CrewAI* (`adapters/crewai.py`): Constructs a sequential `Crew` with three role-based agents (planner, executor, reviewer), each configured with a backstory, goal, and tool set. CrewAI's iteration budget is distributed across agents using a 20/60/20 split (planner/executor/reviewer) on first attempt, shifting to 0/80/20 on retry to allocate more capacity to the executor. A `check_completion` tool with `result_as_answer=True` enables the executor to signal early completion, preventing the 50-iteration token burn that occurs when CrewAI agents exhaust their iteration limit without producing a final answer @crewai2024. Token usage is captured via a native `OpenAICompletion` callback registered through CrewAI's event bus.

*OpenAI Agents SDK* (`adapters/openai_agents.py`): Uses a three-agent handoff chain where each agent is defined with a system prompt, tool set, and optional structured output schema. The planner agent produces an `ImplementationPlan` via Pydantic-validated structured output. Agent transitions use the SDK's native handoff mechanism, passing conversation context forward. The reviewer agent carries an output guardrail---a workspace validator that checks for expected artefacts---which triggers a retry loop on failure, using the SDK's built-in guardrail-to-retry pipeline @openai2025agents_sdk.

*Google ADK* (`adapters/google_adk.py`): Orchestrates agents using ADK's compositional primitives: a `SequentialAgent` chains planner → `LoopAgent` → validation, where the `LoopAgent` wraps the executor--reviewer pair with a native `exit_loop` tool that the reviewer invokes when validation passes. Non-Gemini models are supported via LiteLLM format strings (e.g., `openai/gpt-4o`), enabling the same adapter to evaluate ADK's orchestration with different LLM providers. Per-call token and tool usage is captured through ADK callbacks registered on each agent @google2025adk.

*Microsoft Agent Framework* (`adapters/agent_framework.py`): Employs `MagenticBuilder` to construct a manager-driven team with built-in stall detection and round-count limits. The manager agent delegates tasks to specialist agents (planner, executor, reviewer), monitors progress, and triggers automatic re-planning when stall detection fires after `MAX_STALL_COUNT` consecutive unproductive rounds. Token usage is intercepted by a `UsageTrackingMiddleware` layer inserted into the chat pipeline, which records per-call usage from the LLM response objects before forwarding them to the `ObservationCollector` @microsoft2025agent_framework.

The four visual/workflow platform adapters share a different base class---`VisualAgentAdapter` (`adapters/_visual_base.py`)---which provides the `_execute_visual_stage` retry loop and result building. Unlike the SDK-based adapters that invoke platform libraries in-process, visual adapters communicate with their platforms over REST APIs, with each platform running as a Docker container managed by the harness infrastructure.

*Flowise* (`adapters/flowise.py`): Communicates with Flowise via its REST API to programmatically create AI Agent chatflows for each pipeline stage. The adapter constructs chatflow definitions from JSON templates (`adapters/flowise_templates.py`) that wire together an Agent node with the appropriate tool nodes and an LLM configuration. Each stage creates a chatflow, sends the stage prompt via the `/api/v1/prediction` endpoint, extracts the response and any tool call metadata, then deletes the chatflow to maintain isolation between stages.

*LangFlow* (`adapters/langflow.py`): Follows the same pattern as Flowise but targets LangFlow's flow API. Flow definitions are constructed from templates (`adapters/langflow_templates.py`) that assemble component graphs---including an Agent component, tool components, and an LLM provider component---matching LangFlow's internal graph representation. Flows are created, executed via the `/api/v1/run` endpoint, and cleaned up after each stage.

*Dify* (`adapters/dify.py`): Differs from the other visual adapters by requiring two APIs: the Console API (`/console/api/`) for app management (creating agent apps, configuring model providers, publishing) and the Service API (`/v1/`) for execution using per-app API keys. The adapter lifecycle for each stage is: authenticate → create agent app → configure the model provider → publish the app → generate an API key → execute via the Service API → delete the app @dify2024. This dual-API architecture adds complexity but reflects Dify's design as a multi-tenant platform where app management and execution are separated.

*N8n* (`adapters/n8n.py`): Communicates with n8n's REST API v1 to create and execute AI Agent workflows. The adapter provisions LLM credentials in n8n's credential store before workflow creation, then constructs workflow definitions containing an AI Agent node wired to tool nodes. Workflows are activated, triggered via the `/api/v1/workflows/{id}/run` endpoint, and deactivated after execution. N8n's execution model is polling-based: the adapter submits the trigger and polls the execution endpoint until the workflow completes or times out.

== Pipeline Stage Implementation

=== Stage 1: Requirements \& Design

The first pipeline stage transforms a user story into structured requirements and a UML design artefact. The story definition is loaded from YAML by the story loader (`harness/loader.py`), which validates the schema and prepares a `StageContext` containing the story metadata, workspace path, allowed tools, and a progress callback for live reporting.

The stage follows the shared three-agent pattern (planner → executor → reviewer) provided by `ToolAgentAdapter._execute_stage`. The planner agent receives the story description and acceptance criteria via `build_requirements_prompt` and produces an `ImplementationPlan`---a Pydantic model specifying implementation steps, file paths, and dependencies. If the LLM's response cannot be parsed as valid JSON, a plaintext fallback parser extracts numbered steps from the raw output, ensuring robustness across models with varying structured-output fidelity.

The executor agent receives enriched instructions constructed by `build_executor_instructions`, which injects a `## Plan` section (the parsed plan steps) and a `## Files` inventory (target files from the story definition) into the system prompt. The executor writes structured requirements to the workspace via the `write_file` tool and generates PlantUML diagram source via the `generate_uml` tool. The reviewer agent then validates that the workspace contains the expected artefacts; if validation fails, the executor retries with the reviewer's feedback appended to its conversation history.

The stage output is a `RequirementsResult` containing the structured requirements JSON, PlantUML source string, and execution metadata (iterations, tool calls, token usage).

=== Stage 2: Code Generation

The code generation stage receives the requirements and UML design from Stage~1 via the `StageContext` chaining mechanism: `context.get_prior_result("requirements")` retrieves the preceding stage's output, which `build_codegen_prompt` incorporates into the executor's prompt alongside the original story description. This chaining ensures the code generation agent has full context without re-deriving requirements.

The executor agent writes source files to an isolated workspace directory using the `write_file` tool. Each platform--story combination receives a clean workspace initialised from a baseline project template (`data/baseline/`), providing a consistent starting point (e.g., `pyproject.toml`, directory structure) without constraining the agent's implementation choices. The `read_file` and `list_files` tools enable the agent to inspect its own output and the baseline structure.

Tool dispatch, retry logic, and result construction are handled entirely by the `_execute_stage` template method. The adapter-specific `_run_agent` implementation manages only the platform SDK invocation---for example, LangGraph compiles and invokes its `StateGraph`, while CrewAI kicks off a sequential `Crew`. After execution, the base class runs a workspace audit (`audit_workspace`) that checks for out-of-scope file modifications, logging warnings if the agent wrote files outside the expected target paths.

The stage output is a `CodeResult` recording the files produced, tool call count, and execution metadata.

=== Stage 3: Test Generation

The test generation stage receives the requirements and generated source code from prior stages and produces a test suite. The executor agent is provided with the full workspace contents (source files from Stage~2) and tasked with writing tests that exercise the acceptance criteria defined in the story.

This stage introduces two capabilities not present in earlier stages. First, the `run_tests` tool enables the agent to invoke a test runner (pytest for Python projects, jest for JavaScript) and receive structured output including pass/fail counts, failure messages, and coverage data where available. Second, an error-recovery loop allows the agent to iteratively fix failing tests: when `run_tests` reports failures, the agent can read the failing test output, modify the test or source code, and re-invoke the runner---continuing until tests pass or the iteration budget is exhausted.

The reviewer agent in this stage operates under asymmetric tool distribution: it receives only inspection tools (`read_file`, `list_files`) and cannot modify the workspace. This design ensures the reviewer provides an independent assessment of test adequacy without the ability to ``fix'' issues itself, preserving the separation between generation and review that the scoring rubric evaluates under the _Orchestration_ dimension.

The stage output is a `TestResult` recording tests run, tests passed, coverage delta, and execution metadata.

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

=== Automatic Instrumentation <sec-metrics>

The harness captures resource consumption metrics at each pipeline stage through three mechanisms:

- *Token tracking*: The `_execute_stage` template method wraps each stage invocation in an `ObservationCollector` that records per-LLM-call token counts. Each adapter feeds provider-specific usage data into the collector---for example, OpenAI-compatible adapters extract `usage.prompt_tokens` and `usage.completion_tokens` from response objects, while CrewAI uses a native `OpenAICompletion` callback registered on the event bus, and the Agent Framework inserts a `UsageTrackingMiddleware` into the chat pipeline. The collector aggregates these per-call counts into stage-level totals.

- *Wall-clock timing*: The `EvaluationRunner` records `datetime.now(timezone.utc)` before and after each stage invocation, yielding `wall_clock_seconds` per stage. Stage-level timings are aggregated into story-level totals for efficiency scoring.

- *Cost estimation*: API costs are estimated from token counts using per-provider pricing tables. Since pricing varies by model and provider, costs are recorded as estimates and flagged as such in the results.

All metrics are persisted to a DuckDB-backed `ResultStore` (`harness/store.py`) that maintains two tables: `runs` (run-level metadata including model, temperature, platform/story filters) and `executions` (per-platform-per-story execution records with all quantitative metrics and rubric scores). The store supports both programmatic querying (via DuckDB SQL) and DataFrame export (via Pandas), enabling the dashboard data layer to generate charts and summary tables without re-parsing JSON artefacts.

=== Cross-cutting Dimension Computation

The `MetricsCollector` class (`harness/metrics.py`) computes the four cross-cutting dimension scores defined in the Design chapter. The `calculate_dimension_scores` method operates on a list of `StoryMetrics` facades (each wrapping a `StoryResult` with additional metrics-only fields) and produces `DimensionScore` entries on a 1--5 Likert scale.

Pipeline Completeness combines the story completion ratio with the average pipeline completeness rubric score (0--3). Efficiency combines three components---time ratio (wall-clock relative to budget), token ratio (total tokens relative to a 100,000-token budget), and cost ratio (API cost relative to a \$0.50-per-story budget)---falling back to a two-component average when cost data is unavailable. Orchestration averages the three orchestration-related rubric scores (tool integration, error recovery, trace quality) and rescales from 0--3 to 1--5. Autonomy is computed as $5 - min(4, overline(I))$ where $overline(I)$ is the mean human interventions per stage, ensuring that fewer interventions yield higher scores.

When repeated runs are configured (`RunnerConfig.repeats > 1`), the collector also computes `VarianceMetrics`---mean and population standard deviation for wall-clock time, token usage, cost, tool calls, iterations, and success rate---enabling assessment of result stability across non-deterministic LLM outputs.

== Web-Based Management Console <sec-webui>

The evaluation harness includes a purpose-built web-based management console that serves as the primary instrument for conducting evaluations. Rather than a convenience wrapper around CLI commands, the console operationalises the evaluation methodology: it embeds the scoring rubric, provides trace-level evidence for qualitative judgements, visualises multi-agent orchestration patterns, and produces the cross-platform comparison analysis. This section describes its architecture, capabilities, and role in the evaluation workflow.

=== Architecture

The console follows a two-tier architecture. The backend is a FastAPI application (`src/desmet/webui/api.py`) exposing approximately 45 REST endpoints and two WebSocket channels---one for live log streaming during pipeline execution, one for Docker image build progress. The frontend is a Svelte~5 single-page application compiled to static assets and served by the backend on port~8042. Reactive state management uses Svelte~5 runes (`$state`, `$derived`) with a centralised data layer (`data.svelte`) that polls the backend for infrastructure health, platform status, and run progress.

The console launches automatically via the `desmet` CLI (see @appendix-getting-started) and starts the Langfuse tracing infrastructure as a core dependency on startup. All evaluation data flows through the same `ResultStore` (DuckDB-backed, see @sec-metrics) used by the CLI, ensuring consistency between console-driven and programmatic evaluations.

=== Evaluation Workflow Pages

The console is organised into two navigation groups---_Manage_ (pipeline execution) and _Results_ (analysis and scoring)---reflecting the two phases of an evaluation session.

==== Pipeline Execution

Five pages support the execution phase:

- *Dashboard*: Provides an at-a-glance overview of the evaluation environment. Cards display infrastructure service health (Langfuse, Redis, Postgres), the number of implemented platform adapters, available LLM providers with per-provider model counts discovered at startup, and a summary of recent evaluation runs. Infrastructure services can be started and stopped directly from the dashboard. @fig-webui-dashboard shows the dashboard layout.

#figure(
  image("../figures/webui/dashboard.png", width: 95%),
  caption: [Management console dashboard showing infrastructure health, LLM provider discovery, and recent evaluation runs],
) <fig-webui-dashboard>

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

  The scoring form presents each of the six rubric dimensions (pipeline completeness, tool integration, error recovery, time efficiency, autonomy, trace quality) with a 0--3 slider and a free-text notes field. Scores are persisted via the `ResultStore` and immediately reflected in the comparison charts. Previously submitted scores are pre-loaded when revisiting a platform--story combination, enabling iterative refinement. @fig-webui-scoring shows the scoring page layout.

#figure(
  image("../figures/webui/scoring.png", width: 95%),
  caption: [Scoring page showing per-dimension rubric sliders (top) and Langfuse execution trace with timeline, messages, and tool calls (bottom)],
) <fig-webui-scoring>

- *Story Detail*: Provides a per-story cross-platform view. For a selected story, displays each platform's execution metrics (tokens, time, cost, iterations, tool calls) and scoring status. A _Score this_ link navigates directly to the Scoring page with the platform and story pre-selected, streamlining the evaluator's workflow through the story set.

- *Comparison*: The synthesis page that produces the cross-platform analysis. A radar chart overlays all scored platforms on the four cross-cutting dimensions (Pipeline Completeness, Efficiency, Orchestration, Autonomy). A bar chart ranks platforms by overall score. A score matrix heatmap shows per-platform per-dimension scores with colour intensity encoding magnitude. Dimension-specific bar charts can be selected from a dropdown for detailed single-dimension comparison. @fig-webui-comparison shows the comparison page.

#figure(
  image("../figures/webui/comparison.png", width: 95%),
  caption: [Comparison page showing efficiency breakdown bar charts and per-story wall-clock time comparison across platforms],
) <fig-webui-comparison>

=== Agent Communication Graph

The agent graph is a novel visualisation component that makes multi-agent orchestration patterns directly observable. During qualitative scoring, the evaluator can inspect how agents communicated, delegated, and coordinated---information that is critical for scoring the _Orchestration_ dimension but difficult to extract from raw trace logs.

The graph is constructed from Langfuse trace data via a server-side endpoint (`/api/dashboard/graph/{platform_id}/{story_id}`) that extracts agent nodes and message edges from the observation tree. The frontend renders this as an interactive directed graph using the following pipeline:

+ *Trace parsing*: The backend traverses the Langfuse observation hierarchy, identifying agent-level spans (generations and chains) and extracting parent--child relationships and message content.

+ *Graph construction*: Agent nodes are grouped into cluster containers reflecting the platform's orchestration topology---for example, a CrewAI sequential crew appears as a container with planner, executor, and reviewer nodes arranged in sequence, while a MagenticOne team shows a central manager node with edges to specialist agents.

+ *ELK layout*: The graph input is passed to ELK (Eclipse Layout Kernel) via `elkjs` for automatic hierarchical layout, producing positioned nodes and routed edges that minimise crossings.

+ *Interactive rendering*: The laid-out graph is rendered using `@xyflow/svelte` with custom node components (`AgentNode` for leaf agents, `AgentClusterNode` for containers) and custom edge components (`TransitionEdge` with animated message flow). Clicking a node opens an `ObservationDrawer` showing the full LLM call detail (prompt, response, token usage, timing). A `TimelineCard` component shows the chronological execution sequence alongside the spatial graph.

This visualisation directly supports the evaluation methodology: the graph reveals whether a platform's agents actually collaborated (multiple agents with bidirectional edges) or merely executed sequentially (linear chain), whether the reviewer agent received the executor's output, and whether error recovery involved re-planning or simple retry. These observations inform the qualitative scoring of Orchestration and Autonomy dimensions. @fig-webui-agent-graph shows the agent graph for a representative multi-agent execution.

#figure(
  image("../figures/webui/agent-graph.png", width: 95%),
  caption: [Agent communication graph showing multi-agent orchestration topology with cluster containers, message edges, and observation detail drawer],
) <fig-webui-agent-graph>

=== Observability Integration

The console integrates with two observability providers to give the evaluator comprehensive trace evidence:

- *Langfuse*: The primary tracing backend, started automatically on console launch. The `TraceViewer` component renders the full observation tree with expandable spans. The `SpanNode` component shows per-span token counts, duration, and a truncated preview of input/output content. The `TimelineView` provides a horizontal timeline of all spans for temporal analysis. Trace data is fetched via the Langfuse client SDK (`webui/langfuse_client.py`), which handles authentication, pagination, and observation tree assembly.

- *LangSmith*: A secondary provider enabled for LangGraph evaluations. The `LangSmithTraceViewer` component renders the LangGraph-specific run tree, including state checkpoint data and graph node transitions. Availability is checked lazily on first access and indicated in the Scoring page tab bar.

Dual-provider support allows the evaluator to cross-reference traces---for example, comparing Langfuse's framework-agnostic span tree with LangSmith's LangGraph-specific state transitions to verify that checkpoint data is being recorded correctly.

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

Several significant implementation challenges were encountered during adapter development. These are documented both as technical contributions and as evidence of the depth of platform-specific adaptation required.

*CrewAI token tracking breakage.* CrewAI version 1.6 removed its `litellm` dependency, breaking the token usage callback mechanism that earlier versions relied on. The fix required switching to CrewAI's native `OpenAICompletion` callback combined with a `BaseInterceptor` registered through the event bus, which intercepts LLM responses before they reach the agent and records usage data into the `ObservationCollector`. This highlights the fragility of depending on internal framework APIs that change without deprecation warnings.

*CrewAI early termination.* Without explicit termination control, CrewAI agents would exhaust their 50-iteration budget even after producing valid output, consuming tokens on increasingly circular reasoning. The solution was a `check_completion` tool with `result_as_answer=True`---when the agent calls this tool, CrewAI treats the tool's return value as the agent's final answer and terminates the iteration loop. This reduced token consumption per stage by approximately 60\% for the CrewAI adapter.

*CrewAI native function calling.* CrewAI's native function calling mode (where tool definitions are passed to the LLM's function calling API) is broken for non-OpenAI providers at the time of writing. When using Anthropic or Google models via CrewAI, the framework falls back to ReAct-style text parsing, where tool invocations are extracted from the LLM's textual output using regex patterns. This forced the adapter to support both code paths and introduces a confound: CrewAI's orchestration overhead differs depending on whether the underlying provider supports native function calling.

*Adapter parity vs.\ idiomatic usage.* Achieving a controlled comparison requires shared structure (same prompts, same tools, same scoring) while preserving each platform's native patterns. The solution was a layered architecture: the `ToolAgentAdapter` base class provides the shared template (prompt construction, tool creation, retry policy, result building), while each adapter's `_run_agent` method uses the platform's idiomatic orchestration. For example, LangGraph uses compiled subgraphs with checkpointing, CrewAI uses sequential crews with role-based agents, and the Agent Framework uses MagenticOne manager-driven teams. This design ensures that measured differences reflect genuine platform capabilities rather than adapter implementation choices.

*Deploy stage security model.* The deploy stage requires agents to execute commands on a remote server via SSH---a significant security surface. The mitigation is a defence-in-depth approach: the target server runs a restricted user (`desmet`) with a whitelisted shell permitting only `git pull`, `docker compose up`, `docker ps`, and `curl`; SSH access is restricted to a Tailscale VPN mesh; and each platform--story combination pushes to a dedicated git branch, providing isolation within a single deploy repository. This model prevents any agent-initiated action from affecting other services while still providing a realistic deployment environment for evaluation.
