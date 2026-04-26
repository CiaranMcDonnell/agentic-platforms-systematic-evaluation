#import "../template.typ": *

= Implementation

== Evaluation Harness Architecture

The evaluation is driven by a purpose-built Python harness (`desmet`) that orchestrates pipeline execution across all platforms. The core modules are a *Runner* (`harness/runner.py`) that orchestrates the four-stage pipeline for a given platform and scenario; a *Base Adapter* (`harness/adapter.py`) defining the four-method interface all platform adapters must implement; a *Scenario Loader* (`harness/story_loader.py`) that validates YAML scenario definitions and prepares the `StageContext` passed to each stage; and a *Metrics Collector* (`harness/metrics.py`) that records per-stage metrics and computes cross-cutting dimension scores. @fig-harness-arch shows the component architecture.

#include "../diagrams/implementation/harness-architecture.typ"

== Platform Adapter Design

All platform adapters extend `BasePlatformAdapter` and implement four methods corresponding to the pipeline stages: `generate_requirements`, `generate_code`, `generate_tests`, and `build_and_deploy`. Tool-based adapters (SDK and multi-agent) extend the intermediate `ToolAgentAdapter`, which provides a shared `_execute_stage` template---prompt construction, tool creation, trace lifecycle, retry orchestration, and result building---leaving each adapter with only one platform-specific method (`_run_agent`). Visual/workflow adapters extend `VisualAgentAdapter` (`adapters/_shared/visual_base.py`), which provides an analogous `_execute_visual_stage` retry loop for REST-mediated platforms running as Docker containers.

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Platform*], [*Adapter Status*], [*Notes*],
    ),
    [LangGraph], implemented-cell, [Three-node StateGraph with InMemorySaver checkpointing],
    [CrewAI], implemented-cell, [Sequential Crew with role-based agents and iteration budget control],
    [OpenAI Agents SDK], implemented-cell, [3-agent handoff chain with output guardrails],
    [Google ADK], implemented-cell, [SequentialAgent + LoopAgent orchestration],
    [Microsoft Agent Framework], implemented-cell, [MagenticOne manager-driven orchestration],
    [Flowise], implemented-cell, [Spec-driven chatflow builder using the live node catalogue, with per-run tool and credential registration],
    [LangFlow], implemented-cell, [Catalogue-wrapped React-Flow graph with pre-computed tool introspection and a per-run API key],
    [Dify], partial-cell, [Init, auth, and app creation automated; Layer~3 execution blocked by the marketplace-only plugin ecosystem introduced in Dify~v1.0 (see @limitations)],
    [n8n], implemented-cell, [REST API v1 workflow creation with provider-specific credential mapping (`openRouterApi`, `openAiApi`, `anthropicApi`)],
  ),
  caption: [Platform Adapter Implementation Status],
)

*SDK and multi-agent adapters.* Each adapter uses its platform's idiomatic orchestration primitives. LangGraph implements a three-node `StateGraph` with `InMemorySaver` checkpointing, threading `ParentState` (plan text, retry count, validator feedback) through planner → executor → reviewer nodes with a conditional edge from the reviewer back to the executor on validation failure @langchain2024langgraph. CrewAI constructs a sequential `Crew` with role-based agents, using an iteration budget split (20/60/20 first attempt, 0/80/20 on retry) and a `check_completion` tool with `result_as_answer=True` to prevent the 50-iteration token burn that occurs when agents exhaust their iteration limit without producing a final answer @crewai2024. OpenAI Agents SDK uses a three-agent handoff chain with Pydantic-validated structured planner output and a reviewer output guardrail that triggers retry on validation failure @openai2025agents_sdk. Google ADK composes a `SequentialAgent` chaining planner → `LoopAgent` (executor--reviewer pair) with a native `exit_loop` tool, supporting non-Gemini models via LiteLLM format strings @google2025adk. Microsoft Agent Framework employs `MagenticBuilder` to construct a manager-driven team with built-in stall detection and a `UsageTrackingMiddleware` layer inserted into the chat pipeline for token interception @microsoft2025agent_framework.

*Visual/workflow adapters.* Each visual adapter fetches live component catalogues at stage start and builds flows programmatically rather than shipping static JSON templates that break across platform versions.

Flowise retrieves per-component specifications via `GET /api/v1/nodes/{name}` and classifies inputs using its own `INPUT_PARAMS_TYPE` constant, expressing connections as `{{nodeId.data.instance}}` references inside the target's `inputs` dictionary (the mechanism Flowise's runtime actually resolves); tools and credentials are registered per-run via `POST /api/v1/tools` and `POST /api/v1/credentials`.

LangFlow wraps full-catalogue entries (`GET /api/v1/all`) with targeted field overrides and required three version-specific mechanics: overriding `load_from_db: true` on credential fields, minting an `x-api-key` header for `/api/v1/run/{flow_id}`, and re-creating `PythonCodeStructuredTool` template artefacts by parsing tool code with Python's `ast` module.

Dify is a partial integration: init, auth, CSRF handshake, and agent-app creation automate cleanly, but Dify~1.13's marketplace-only plugin ecosystem blocks end-to-end execution since no LLM provider ships in-box (discussed as a finding in @limitations) @dify2024.

n8n provides the richest visual-platform execution log: `runData` is keyed by node name with per-node `startedAt` and `executionTime`, enabling per-node event reconstruction and real per-tool-call timing, with credentials provisioned via provider-specific types (`openRouterApi`, `openAiApi`, `anthropicApi`).

== Pipeline Stage Implementation

The four pipeline stages share a common execution pattern provided by `ToolAgentAdapter._execute_stage`: a planner agent produces a structured `ImplementationPlan` (Pydantic-validated, with plaintext fallback for LLMs with weaker structured-output fidelity), an executor agent receives enriched instructions containing parsed plan steps and target files via `build_executor_instructions`, and a reviewer agent validates the workspace under asymmetric tool distribution (inspection-only tools, no write access). If validation fails, the executor retries with the reviewer's feedback appended to its conversation history. Stage outputs chain forward via `context.get_prior_result()`. After each stage, the base class runs a workspace audit (`audit_workspace`) that checks for out-of-scope file modifications.

*Stage~1 — Requirements and design.* Writes structured requirements and Mermaid diagram sources, rendering them via the Mermaid CLI (`mmdc`) through `execute_shell` so downstream stages and reviewers can inspect the rendered SVG.

*Stage~2 — Code generation.* Writes source files into an isolated workspace initialised from a baseline template (`data/baseline/`).

*Stage~3 — Test generation.* Introduces the `run_tests` tool (pytest for Python, jest for JavaScript) with an error-recovery loop enabling the agent to iteratively fix failing tests until tests pass or the iteration budget is exhausted.

*Stage~4 — Build and deployment.* Rather than delegating to a CI/CD system @shahin2017cicd, the agent is given direct tool access and must determine the correct execution order itself. Targeting a remote host is a deliberate measurement choice: a local-only deploy would collapse into a single-tool invocation, erasing the _Orchestration_ signal the stage is designed to capture. SSH-to-remote forces multi-step coordination across git, SSH, and Docker---push, pull, build, restart, probe (see @appendix-deploy-setup).

A single `deploy_remote` tool exposes three actions---`push` (commit and push workspace changes to the deploy repository), `restart` (SSH to target, pull branch, `docker compose up -d --build`), and `health_check` (SSH and curl the service endpoint). Each platform--scenario combination pushes to a dedicated branch (`{platform_id}/{story_id}`); on the target server a restricted `desmet` user with a whitelisted shell (permitting only `git pull`, `docker compose`, `docker ps`, `curl`) and Tailscale-restricted SSH access provides defence-in-depth isolation (see @appendix-deploy-setup). This stage contributes to _Orchestration_ (push → restart → health check sequencing), _Error Recovery_ (retrying failed restarts), and _Autonomy_ (calling `health_check` unprompted to verify deployments).

== Metrics Collection and Token Tracking <sec-metrics>

The harness captures resource consumption metrics at each pipeline stage through three mechanisms.

*Token tracking.* Uses an `ObservationCollector` wrapped around each stage invocation, with adapter-specific sources feeding per-LLM-call counts into the collector: OpenAI-compatible adapters extract `usage.prompt_tokens`/`usage.completion_tokens`, CrewAI uses a native `OpenAICompletion` plus a `BaseInterceptor` registered on the event bus (replacing the `litellm`-based path removed in CrewAI~v1.6), and the Agent Framework inserts a `UsageTrackingMiddleware` into the chat pipeline.

*Wall-clock timing.* Recorded by the `EvaluationRunner` at stage boundaries.

*Cost estimation.* Derives from token counts and per-provider pricing tables.

All metrics are persisted to a DuckDB-backed `ResultStore` (`harness/store.py`) that maintains `runs` (run-level metadata) and `executions` (per-platform-per-scenario records) tables, supporting both DuckDB SQL queries and Pandas DataFrame export. The `MetricsCollector` computes the four cross-cutting dimension scores defined in the Design chapter from lists of `StoryMetrics` facades; when repeated runs are configured (`RunnerConfig.repeats > 1`), it also produces `VarianceMetrics` (mean and population standard deviation across runs) enabling assessment of result stability under non-deterministic LLM outputs.

=== Hybrid Auto-Derived and Manual Scoring

The four cross-cutting dimensions are computed by `EvaluationMetrics.calculate_dimension_scores` in `harness/metrics.py` under a deliberate split: three dimensions are auto-derived end-to-end from trace signals, while _Autonomy_ retains the evaluator's 0--3 rubric score as its primary input. _Pipeline Completeness_ blends the scenario completion ratio with the averaged rubric score seeded from each `StageResult.success` flag; _Efficiency_ is fully automatic, combining wall-clock, token, cost, and memory ratios against configured budgets; and _Orchestration_ averages three rubric fields (`tool_integration`, `error_recovery`, `trace_quality`) that the trace audit populates from observation data. _Autonomy_ is scored manually through the web-based management console because judging whether an intervention is substantive versus a routine tool response requires human interpretation; the manual rubric is optionally blended 50/50 with `human_interventions` only when adapters log non-zero values. Full rubric criteria appear in @appendix-scoring-rubric.

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Dimension*], [*Source*], [*Signal*],
    ),
    [Pipeline Completeness], [Auto-derived], [Completion ratio + rubric seeded from `StageResult.success`],
    [Efficiency], [Auto-derived], [Wall-clock, token, cost, and memory ratios against budgets],
    [Orchestration], [Auto-derived], [Averaged `tool_integration`, `error_recovery`, `trace_quality` from trace audit],
    [Autonomy], [Manual], [Evaluator 0--3 rubric via @sec-webui; optional 50/50 blend with logged `human_interventions`],
  ),
  caption: [Auto-derived versus manual cross-cutting dimensions.],
)

=== Metric Coverage Across Visual Platforms <sec-metric-coverage>

The SDK-based adapters all emit the same metric set directly into the `AgentTrace` because they invoke platform libraries in-process and instrument the LLM call site. Visual platforms, in contrast, expose a single REST response per stage, and the level of execution detail varies substantially across platforms. @tab-visual-metric-coverage summarises which framework-metric signals are recoverable from each visual platform's default response.

#figure(
  table(
    columns: 5,
    stroke: 0.5pt,
    inset: 6pt,
    align: (left, center, center, center, center),
    table.header(
      [*Metric*], [*n8n*], [*Flowise*], [*LangFlow*], [*Dify*],
    ),
    [`tokens_per_stage`], [✓], [—], [✓], [✓#super[\*]],
    [`tool_calls_count`], [✓], [✓], [✓], [—],
    [`redundant_tool_call_rate`], [✓], [✓], [✓], [—],
    [`tool_failure_rate`], [✓], [✓], [✓], [—],
    [`first_action_latency_ms`], [✓], [—], [—], [—],
    [`framework_overhead_ms`], [✓], [—], [—], [—],
    [per-node events], [✓], [—], [—], [—],
  ),
  caption: [Framework-metric signals recoverable from each visual platform.],
) <tab-visual-metric-coverage>

In @tab-visual-metric-coverage, ✓ denotes a signal surfaced and parsed by the adapter and --- denotes a signal not exposed by the platform. Dify exposes aggregate token usage via `metadata.usage` on chat responses, but end-to-end agent execution is blocked by the plugin-based model ecosystem (see @limitations). Unavailable signals are reported as `None` rather than synthesised from proxies.

n8n's per-node `runData` log is the only visual-platform signal that permits latency and overhead decomposition. Flowise captures tool inputs, outputs, and per-call error flags but drops token usage for `toolAgent` flows regardless of streaming mode. LangFlow surfaces token usage and tool calls through several structurally different response paths depending on version, which the adapter walks defensively. Dify exposes aggregate token usage but not per-tool-call traces. Each adapter's `get_observability_info()` declares these capability flags programmatically (`exposes_per_tool_call`, `exposes_tool_timing`, `exposes_token_usage`, `exposes_node_events`), so downstream analyses can cite the observability boundary rather than treating all zeros identically.

== Web-Based Management Console <sec-webui>

The evaluation harness includes a purpose-built web-based management console that is the primary instrument for conducting evaluations: it embeds the scoring rubric, provides trace-level evidence for qualitative judgements, visualises multi-agent orchestration patterns, and produces the cross-platform comparison analysis.

*Backend.* A FastAPI application (`src/desmet/webui/api.py`) exposes approximately 45 REST endpoints and two WebSocket channels (live log streaming during pipeline execution; Docker image build progress).

*Frontend.* A Svelte~5 single-page application compiled to static assets and served by the backend on port~8042, with reactive state management via runes (`$state`, `$derived`) and a centralised data layer polling for infrastructure health, platform status, and run progress. The console launches automatically via the `desmet` CLI (see @appendix-getting-started) and starts the Langfuse tracing infrastructure as a core dependency. All evaluation data flows through the same `ResultStore` used by the CLI.

*Navigation.* Pages are organised into two groups: _Manage_ (Dashboard for infrastructure/adapter status, Platforms for Docker service control, Scenarios for browsing the user-scenario catalogue, New Run for pipeline launch, Run Detail for live WebSocket log streaming) and _Results_ (Overview with ECharts aggregate visualisations, Scoring, Scenario Detail for per-scenario cross-platform metrics, Comparison for radar/ranking/heatmap charts).

=== New Run Page

The New Run page collects the full set of parameters needed to dispatch the pipeline---stage selection, target platforms, scenario selection, model, and execution mode---on a single screen and validates them before enabling the _Start Benchmark Run_ action. It is organised as two stacked blocks: a top filter bar (@fig-webui-newrun-filters) and a three-column selection body (@fig-webui-newrun-selection).

*Filter bar.* The top row (@fig-webui-newrun-filters) exposes three global filters. _Difficulty_ chips (Basic / Intermediate / Advanced) filter the scenario list to a subset of the catalogue. _Stages_ toggles select which of the four pipeline stages (Requirements, Codegen, Testing, Deploy) will execute; stages can be deselected to run a partial pipeline for faster iteration during adapter development. _Model_ is a free-text identifier (e.g. `claude-sonnet-4-6`) that propagates through the centralised LLM config and is recorded in the run metadata so results remain traceable to the model used.

#figure(
  placement: none,
  image("../figures/webui/new-run_filters.png", width: 95%),
  caption: [New Run page, filter bar: difficulty chips, stage toggles, and model selector.],
) <fig-webui-newrun-filters>

*Selection body.* The body (@fig-webui-newrun-selection) presents three independent columns. The _Platforms_ column lists every registered adapter with a readiness badge (green _ready_ when the adapter's prerequisites are met; red _not ready_ when a required dependency, credential, or Docker service is missing) and supports multi-select. The _Scenarios_ column lists the catalogue filtered by the active difficulty chips, each row showing the scenario ID, title, tags, and description preview. The right-hand sidebar surfaces _Provider Status_ (OpenAI / Anthropic / Google credentials configured or not) and a _Recent Runs_ history for quick re-launch. The bottom action bar summarises the current selection ("N platforms, M scenarios, stages: ..."), exposes the _Dry Run_, _Replay_, and _Local/Remote_ execution-mode toggles, and enables _Start Benchmark Run_ only when at least one platform and one scenario are selected.

#figure(
  placement: none,
  image("../figures/webui/new-run_selection.png", width: 95%),
  caption: [New Run page, selection body: platforms (left), scenarios (centre), provider status/recent runs (right), and the launch action bar at the bottom.],
) <fig-webui-newrun-selection>

=== Scoring Page

The Scoring page is the centrepiece of the evaluation workflow, operationalising the 0--3 rubric defined in the Design chapter. It is composed of four stacked panels: a run-level summary header (@fig-webui-scoring-header), a rubric form (@fig-webui-scoring-rubric), an execution-trace panel (@fig-webui-scoring-trace), and an agent communication graph (@fig-webui-scoring-graph).

*Run summary.* The header (@fig-webui-scoring-header) lets the evaluator select a platform--scenario combination and surfaces the automated framework metrics for the selected run---wall-clock time, iteration count, tool calls, success flag, tokens per stage, iteration ratio, tool failure rate, first-action latency, redundant calls, and framework overhead---providing the quantitative context that grounds the manual rubric judgement.

#figure(
  placement: none,
  image("../figures/webui/scoring_header.png", width: 95%),
  caption: [Scoring page header: platform/scenario selection and automated framework metrics.],
) <fig-webui-scoring-header>

*Rubric form and aggregation.* The rubric form (@fig-webui-scoring-rubric) presents each of the six 0--3 dimensions as a row of four labelled buttons with a free-text notes field; scores persist via the `ResultStore` and are pre-loaded when revisiting a combination, enabling iterative refinement. Previously submitted scores feed immediately into the Comparison page's radar chart overlay (four cross-cutting dimensions), ranking bar chart, and score-matrix heatmap.

#figure(
  placement: none,
  image("../figures/webui/desmet_rubric.png", width: 95%),
  caption: [Rubric form: six 0--3 dimensions with per-level anchors and notes.],
) <fig-webui-scoring-rubric>

*Evidence panels.* Alongside the scoring form, the evaluator is presented with three tabbed evidence panels: a Langfuse span tree rendered as a nested timeline with expandable detail drawers (@fig-webui-scoring-trace); a LangSmith run tree (for LangGraph runs) with state snapshots and checkpoint data; and a novel _agent communication graph_---a directed visualisation constructed from Langfuse observation data that makes multi-agent orchestration patterns directly observable.

#figure(
  placement: none,
  image("../figures/webui/execution_trace.png", width: 95%),
  caption: [Execution-trace panel: Langfuse span timeline with per-span type colouring and token/cost summary.],
) <fig-webui-scoring-trace>

*Agent communication graph.* The graph panel (@fig-webui-scoring-graph) groups agent nodes into cluster containers reflecting the platform's topology (a CrewAI sequential crew appears as a container with planner, executor, and reviewer arranged in sequence; a MagenticOne team shows a central manager with edges to specialists), laid out hierarchically via ELK (`elkjs`), and rendered using `@xyflow/svelte` with custom node and animated-edge components. Clicking a node opens an observation drawer showing the full LLM call detail (prompt, response, token usage, timing). The graph directly supports scoring the _Orchestration_ and _Autonomy_ dimensions---revealing whether agents genuinely collaborated or merely executed sequentially, whether the reviewer received the executor's output, and whether error recovery involved re-planning or simple retry.

#figure(
  placement: none,
  image("../figures/webui/agent-graph.png", width: 95%),
  caption: [Agent communication graph: agents grouped by topology with directed, animated edges derived from Langfuse observations.],
) <fig-webui-scoring-graph>

=== Comparison Page

The Comparison page aggregates results across every (platform, scenario) pair in the active run set into a single cross-platform view. It is organised as four stacked blocks: a headline summary (@fig-webui-comparison-rankings), a per-dimension rubric block (@fig-webui-comparison-rubric), a quantitative framework-metrics table (@fig-webui-comparison-metrics), and an efficiency breakdown (@fig-webui-comparison-efficiency).

*Headline summary.* The top row (@fig-webui-comparison-rankings) pairs the _Platform Rankings_ horizontal bar chart---aggregate 0--5 score per platform, colour-coded and sorted descending---with the _Completion Rates_ chart, which records the fraction of attempted scenarios that reached the success state. A platform can rank high on score while failing to complete some scenarios, and vice versa.

#figure(
  placement: none,
  image("../figures/webui/comparison_rankings_rates.png", width: 95%),
  caption: [Comparison page, headline summary: aggregate rubric score (left) and completion rate (right) per platform.],
) <fig-webui-comparison-rankings>

*Rubric matrix and radar.* The second block (@fig-webui-comparison-rubric) renders the manually-assigned rubric scores in two complementary forms. The _Rubric Score Matrix_ is a colour-coded heatmap with rows per platform and columns for the six 0--3 dimensions (PC, TI, ER, TE, AU, TQ), with a trailing column counting the number of scored scenarios; cells are red at 0 and green at 3 to make low-scoring dimensions jump out. The _DESMET Dimension Comparison_ radar chart overlays the four aggregated 1--5 cross-cutting dimensions (Pipeline Completeness, Efficiency, Orchestration, Autonomy) for every platform in one polygon each, supporting shape-based visual comparison.

#figure(
  placement: none,
  image("../figures/webui/comparison_rubric_radar.png", width: 95%),
  caption: [Comparison page, rubric block: 0--3 score matrix (left) and four-dimension radar overlay (right).],
) <fig-webui-comparison-rubric>

*Framework metrics table.* The third block (@fig-webui-comparison-metrics) tabulates the automated metrics captured by the harness during execution, averaged per stage and pivoted so platforms are columns: tokens per stage, iteration ratio, first-action latency, redundant-call fraction, tool-failure rate, framework overhead, USD cost, total tokens, and number of scored scenarios. This is the quantitative counterpart to the qualitative rubric and supports the cost/efficiency findings in the Evaluation chapter.

#figure(
  placement: none,
  image("../figures/webui/comparison_framework_metrics.png", width: 95%),
  caption: [Comparison page, framework metrics: per-stage averages pivoted by platform.],
) <fig-webui-comparison-metrics>

*Efficiency breakdown.* The final block (@fig-webui-comparison-efficiency) plots three efficiency signals side by side per platform---average wall-clock time (seconds), average iteration count, and average tool calls---making it easy to identify platforms that win on one axis but lose on another (for example, low iteration count paired with high wall-clock time, or vice versa).

#figure(
  placement: none,
  image("../figures/webui/comparison_efficiency_breakdown.png", width: 95%),
  caption: [Comparison page, efficiency breakdown: average wall-clock time, iterations, and tool calls per platform.],
) <fig-webui-comparison-efficiency>

== Extending the Framework

The evaluation framework is designed for extensibility. Adding a new tool-based adapter requires implementing a single `_run_agent` method on a subclass of `ToolAgentAdapter`, registering the class in `src/desmet/adapters/registry.py`, and adding platform metadata to `config/platforms.yaml`---no changes to the runner, metrics, or web UI are required. New scenarios are added as YAML files in `data/stories/` conforming to the `UserStory` schema. Deploy targets are configured via environment variables (`DEPLOY_HOST`, `DEPLOY_PORT`, `DEPLOY_USER`, `DEPLOY_KEY_PATH`, `DEPLOY_REPO`). A complete worked example for adapter addition is provided in @appendix-adding-adapter; deploy server setup is documented in @appendix-deploy-setup.

== Adapter Parity vs. Idiomatic Usage

Controlled comparison required shared structure (same prompts, tools, and scoring) while preserving each platform's native patterns. The `ToolAgentAdapter` base class provides the shared template (prompt construction, tool creation, retry policy, result building), while each adapter's `_run_agent` uses the platform's idiomatic orchestration---LangGraph's compiled subgraphs, CrewAI's sequential crews, the Agent Framework's MagenticOne teams. Measured differences therefore reflect genuine platform capabilities, not adapter choices. Specific challenges (CrewAI's v1.6 `litellm` removal breaking token tracking; the 50-iteration runaway loop; broken native function calling on non-OpenAI providers forcing a ReAct-text fallback) are documented in @appendix-adding-adapter alongside their fixes.
