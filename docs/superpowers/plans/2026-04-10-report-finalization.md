# Report Finalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete all remaining TODO sections in the DESMET academic report (Pass 1 — everything writeable from the codebase) and elevate the web-based management console as a primary contribution.

**Architecture:** Each task edits a single `.typ` file by replacing TODO comments with Typst prose. All content is derived from the existing codebase — no evaluation data is needed. Pass 2 (results-dependent) is out of scope for this plan.

**Tech Stack:** Typst markup language, no code changes

**Spec:** `docs/superpowers/specs/2026-04-10-report-finalization-design.md`

---

### Task 1: Expand WebUI Section (Implementation Chapter §4.6)

**Files:**
- Modify: `docs/report/chapters/implementation.typ` — replace the single-paragraph §4.6 with full multi-page section

- [ ] **Step 1: Read the current §4.6 content**

Open `docs/report/chapters/implementation.typ` and locate the section starting with `== Web-Based Management Console`. It currently contains one paragraph and a TODO comment.

- [ ] **Step 2: Replace §4.6 with expanded content**

Replace everything from `== Web-Based Management Console` up to (but NOT including) `== Extending the Framework` with the following Typst content:

```typst
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
```

- [ ] **Step 3: Verify the file compiles**

Run: `typst compile docs/report/DESMET_Agentic_Platforms.typ --root docs/report/ 2>&1 | head -5`

Expected: No errors (warnings are acceptable). If a label reference error occurs for `@sec-metrics`, it will be resolved in Task 4 when that section is expanded.

- [ ] **Step 4: Commit**

```bash
git add docs/report/chapters/implementation.typ
git commit -m "docs(report): expand webui section as primary contribution (§4.6)"
```

---

### Task 2: Expand Pipeline Stage Implementation (Implementation Chapter §4.3)

**Files:**
- Modify: `docs/report/chapters/implementation.typ` — replace TODO stubs in stages 1-3

- [ ] **Step 1: Locate the pipeline stage section**

In `docs/report/chapters/implementation.typ`, find the section `== Pipeline Stage Implementation` and its subsections for stages 1-3 (which currently contain only TODO comments). Stage 4 (Build & Deploy) is already complete — do NOT modify it.

- [ ] **Step 2: Replace Stage 1 TODO**

Replace the content of `=== Stage 1: Requirements \& Design` (the TODO comment block) with:

```typst
=== Stage 1: Requirements \& Design

The first pipeline stage transforms a user story into structured requirements and a UML design artefact. The story definition is loaded from YAML by `StoryLoader`, which validates the schema and prepares a `StageContext` containing the story metadata, workspace path, allowed tools, and a progress callback for live reporting.

The stage follows the shared three-agent pattern (planner → executor → reviewer) provided by `ToolAgentAdapter._execute_stage`. The planner agent receives the story description and acceptance criteria via `build_requirements_prompt` and produces an `ImplementationPlan`---a Pydantic model specifying implementation steps, file paths, and dependencies. If the LLM's response cannot be parsed as valid JSON, a plaintext fallback parser extracts numbered steps from the raw output, ensuring robustness across models with varying structured-output fidelity.

The executor agent receives enriched instructions constructed by `build_executor_instructions`, which injects a `## Plan` section (the parsed plan steps) and a `## Files` inventory (target files from the story definition) into the system prompt. The executor writes structured requirements to the workspace via the `write_file` tool and generates PlantUML diagram source via the `generate_uml` tool. The reviewer agent then validates that the workspace contains the expected artefacts; if validation fails, the executor retries with the reviewer's feedback appended to its conversation history.

The stage output is a `RequirementsResult` containing the structured requirements JSON, PlantUML source string, and execution metadata (iterations, tool calls, token usage).
```

- [ ] **Step 3: Replace Stage 2 TODO**

Replace the content of `=== Stage 2: Code Generation` (the TODO comment block) with:

```typst
=== Stage 2: Code Generation

The code generation stage receives the requirements and UML design from Stage~1 via the `StageContext` chaining mechanism: `context.get_prior_result("requirements")` retrieves the preceding stage's output, which `build_codegen_prompt` incorporates into the executor's prompt alongside the original story description. This chaining ensures the code generation agent has full context without re-deriving requirements.

The executor agent writes source files to an isolated workspace directory using the `write_file` tool. Each platform--story combination receives a clean workspace initialised from a baseline project template (`data/baseline/`), providing a consistent starting point (e.g., `pyproject.toml`, directory structure) without constraining the agent's implementation choices. The `read_file` and `list_files` tools enable the agent to inspect its own output and the baseline structure.

Tool dispatch, retry logic, and result construction are handled entirely by the `_execute_stage` template method. The adapter-specific `_run_agent` implementation manages only the platform SDK invocation---for example, LangGraph compiles and invokes its `StateGraph`, while CrewAI kicks off a sequential `Crew`. After execution, the base class runs a workspace audit (`audit_workspace`) that checks for out-of-scope file modifications, logging warnings if the agent wrote files outside the expected target paths.

The stage output is a `CodeResult` recording the files produced, tool call count, and execution metadata.
```

- [ ] **Step 4: Replace Stage 3 TODO**

Replace the content of `=== Stage 3: Test Generation` (the TODO comment block) with:

```typst
=== Stage 3: Test Generation

The test generation stage receives the requirements and generated source code from prior stages and produces a test suite. The executor agent is provided with the full workspace contents (source files from Stage~2) and tasked with writing tests that exercise the acceptance criteria defined in the story.

This stage introduces two capabilities not present in earlier stages. First, the `run_tests` tool enables the agent to invoke a test runner (pytest for Python projects, jest for JavaScript) and receive structured output including pass/fail counts, failure messages, and coverage data where available. Second, an error-recovery loop allows the agent to iteratively fix failing tests: when `run_tests` reports failures, the agent can read the failing test output, modify the test or source code, and re-invoke the runner---continuing until tests pass or the iteration budget is exhausted.

The reviewer agent in this stage operates under asymmetric tool distribution: it receives only inspection tools (`read_file`, `list_files`) and cannot modify the workspace. This design ensures the reviewer provides an independent assessment of test adequacy without the ability to ``fix'' issues itself, preserving the separation between generation and review that the scoring rubric evaluates under the _Orchestration_ dimension.

The stage output is a `TestResult` recording tests run, tests passed, coverage delta, and execution metadata.
```

- [ ] **Step 5: Verify compilation**

Run: `typst compile docs/report/DESMET_Agentic_Platforms.typ --root docs/report/ 2>&1 | head -5`

Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add docs/report/chapters/implementation.typ
git commit -m "docs(report): describe pipeline stages 1-3 (§4.3)"
```

---

### Task 3: Expand Adapter Implementation Details (Implementation Chapter §4.2)

**Files:**
- Modify: `docs/report/chapters/implementation.typ` — replace the TODO after the adapter status table

- [ ] **Step 1: Locate the adapter section**

In `docs/report/chapters/implementation.typ`, find `=== Implemented Adapters`. There is a table followed by a TODO comment block requesting per-adapter descriptions. The table should be kept; the TODO block should be replaced.

- [ ] **Step 2: Replace the adapter TODO with per-adapter descriptions**

Replace the TODO comment block (starting with `// TODO: For each implemented adapter, describe:`) with:

```typst
Each implemented adapter extends `ToolAgentAdapter` and provides a single method---`_run_agent`---containing the platform-specific agent execution logic. The shared base class handles prompt construction, tool creation, trace lifecycle, retry orchestration, and result building. The descriptions below focus on each adapter's idiomatic use of its platform's native capabilities.

*LangGraph* (`adapters/langgraph.py`): Implements a three-node `StateGraph` with `InMemorySaver` checkpointing. The parent graph threads `ParentState` (plan text, retry count, validator feedback) through planner → executor → reviewer nodes, with a conditional edge from the reviewer back to the executor on validation failure. Each node is a compiled subgraph with private `SubgraphState` accumulating `BaseMessage` history via LangGraph's `add_messages` reducer. This architecture exploits LangGraph's native state persistence: conversation history survives across retries without manual serialisation, and the checkpoint mechanism enables post-hoc replay of agent interactions for trace analysis @langchain2024langgraph.

*CrewAI* (`adapters/crewai.py`): Constructs a sequential `Crew` with three role-based agents (planner, executor, reviewer), each configured with a backstory, goal, and tool set. CrewAI's iteration budget is distributed across agents using a 20/60/20 split (planner/executor/reviewer) on first attempt, shifting to 0/80/20 on retry to allocate more capacity to the executor. A `check_completion` tool with `result_as_answer=True` enables the executor to signal early completion, preventing the 50-iteration token burn that occurs when CrewAI agents exhaust their iteration limit without producing a final answer @crewai2024. Token usage is captured via a native `OpenAICompletion` callback registered through CrewAI's event bus.

*OpenAI Agents SDK* (`adapters/openai_agents.py`): Uses a three-agent handoff chain where each agent is defined with a system prompt, tool set, and optional structured output schema. The planner agent produces an `ImplementationPlan` via Pydantic-validated structured output. Agent transitions use the SDK's native handoff mechanism, passing conversation context forward. The reviewer agent carries an output guardrail---a workspace validator that checks for expected artefacts---which triggers a retry loop on failure, using the SDK's built-in guardrail-to-retry pipeline @openai2025agents_sdk.

*Google ADK* (`adapters/google_adk.py`): Orchestrates agents using ADK's compositional primitives: a `SequentialAgent` chains planner → `LoopAgent` → validation, where the `LoopAgent` wraps the executor--reviewer pair with a native `exit_loop` tool that the reviewer invokes when validation passes. Non-Gemini models are supported via LiteLLM format strings (e.g., `openai/gpt-4o`), enabling the same adapter to evaluate ADK's orchestration with different LLM providers. Per-call token and tool usage is captured through ADK callbacks registered on each agent @google2025adk.

*Microsoft Agent Framework* (`adapters/agent_framework.py`): Employs `MagenticBuilder` to construct a manager-driven team with built-in stall detection and round-count limits. The manager agent delegates tasks to specialist agents (planner, executor, reviewer), monitors progress, and triggers automatic re-planning when stall detection fires after `MAX_STALL_COUNT` consecutive unproductive rounds. Token usage is intercepted by a `UsageTrackingMiddleware` layer inserted into the chat pipeline, which records per-call usage from the LLM response objects before forwarding them to the `ObservationCollector` @microsoft2025agent_framework.
```

- [ ] **Step 3: Verify compilation**

Run: `typst compile docs/report/DESMET_Agentic_Platforms.typ --root docs/report/ 2>&1 | head -5`

Expected: No errors. If any `@citation` keys are missing from `references.bib`, add them (check `references.bib` for existing keys first).

- [ ] **Step 4: Commit**

```bash
git add docs/report/chapters/implementation.typ
git commit -m "docs(report): describe per-adapter implementation details (§4.2)"
```

---

### Task 4: Expand Metrics Collection & Technical Challenges (Implementation Chapter §4.5, §4.7)

**Files:**
- Modify: `docs/report/chapters/implementation.typ` — replace TODOs in §4.5 and §4.7

- [ ] **Step 1: Replace Automatic Instrumentation TODO (§4.5)**

In `docs/report/chapters/implementation.typ`, locate the subsection `=== Automatic Instrumentation` under `== Metrics Collection and Token Tracking`. Replace the TODO comment with:

```typst
=== Automatic Instrumentation <sec-metrics>

The harness captures resource consumption metrics at each pipeline stage through three mechanisms:

- *Token tracking*: The `_execute_stage` template method wraps each stage invocation in an `ObservationCollector` that records per-LLM-call token counts. Each adapter feeds provider-specific usage data into the collector---for example, OpenAI-compatible adapters extract `usage.prompt_tokens` and `usage.completion_tokens` from response objects, while CrewAI uses a native `OpenAICompletion` callback registered on the event bus, and the Agent Framework inserts a `UsageTrackingMiddleware` into the chat pipeline. The collector aggregates these per-call counts into stage-level totals.

- *Wall-clock timing*: The `EvaluationRunner` records `datetime.now(timezone.utc)` before and after each stage invocation, yielding `wall_clock_seconds` per stage. Stage-level timings are aggregated into story-level totals for efficiency scoring.

- *Cost estimation*: API costs are estimated from token counts using per-provider pricing tables. Since pricing varies by model and provider, costs are recorded as estimates and flagged as such in the results.

All metrics are persisted to a DuckDB-backed `ResultStore` (`harness/store.py`) that maintains two tables: `runs` (run-level metadata including model, temperature, platform/story filters) and `executions` (per-platform-per-story execution records with all quantitative metrics and rubric scores). The store supports both programmatic querying (via DuckDB SQL) and DataFrame export (via Pandas), enabling the dashboard data layer to generate charts and summary tables without re-parsing JSON artefacts.
```

- [ ] **Step 2: Replace Cross-cutting Dimension Computation TODO (§4.5)**

In the same section, locate `=== Cross-cutting Dimension Computation`. Replace the TODO comment with:

```typst
=== Cross-cutting Dimension Computation

The `MetricsCollector` class (`harness/metrics.py`) computes the four cross-cutting dimension scores defined in the Design chapter. The `calculate_dimension_scores` method operates on a list of `StoryMetrics` facades (each wrapping a `StoryResult` with additional metrics-only fields) and produces `DimensionScore` entries on a 1--5 Likert scale.

Pipeline Completeness combines the story completion ratio with the average pipeline completeness rubric score (0--3). Efficiency combines three components---time ratio (wall-clock relative to budget), token ratio (total tokens relative to a 100,000-token budget), and cost ratio (API cost relative to a \$0.50-per-story budget)---falling back to a two-component average when cost data is unavailable. Orchestration averages the three orchestration-related rubric scores (tool integration, error recovery, trace quality) and rescales from 0--3 to 1--5. Autonomy is computed as $5 - min(4, overline(I))$ where $overline(I)$ is the mean human interventions per stage, ensuring that fewer interventions yield higher scores.

When repeated runs are configured (`RunnerConfig.repeats > 1`), the collector also computes `VarianceMetrics`---mean and population standard deviation for wall-clock time, token usage, cost, tool calls, iterations, and success rate---enabling assessment of result stability across non-deterministic LLM outputs.
```

- [ ] **Step 3: Replace Technical Challenges TODO (§4.7)**

Locate `== Technical Challenges` (currently a single TODO comment). Replace the TODO with:

```typst
== Technical Challenges

Several significant implementation challenges were encountered during adapter development. These are documented both as technical contributions and as evidence of the depth of platform-specific adaptation required.

*CrewAI token tracking breakage.* CrewAI version 1.6 removed its `litellm` dependency, breaking the token usage callback mechanism that earlier versions relied on. The fix required switching to CrewAI's native `OpenAICompletion` callback combined with a `BaseInterceptor` registered through the event bus, which intercepts LLM responses before they reach the agent and records usage data into the `ObservationCollector`. This highlights the fragility of depending on internal framework APIs that change without deprecation warnings.

*CrewAI early termination.* Without explicit termination control, CrewAI agents would exhaust their 50-iteration budget even after producing valid output, consuming tokens on increasingly circular reasoning. The solution was a `check_completion` tool with `result_as_answer=True`---when the agent calls this tool, CrewAI treats the tool's return value as the agent's final answer and terminates the iteration loop. This reduced token consumption per stage by approximately 60\% for the CrewAI adapter.

*CrewAI native function calling.* CrewAI's native function calling mode (where tool definitions are passed to the LLM's function calling API) is broken for non-OpenAI providers at the time of writing. When using Anthropic or Google models via CrewAI, the framework falls back to ReAct-style text parsing, where tool invocations are extracted from the LLM's textual output using regex patterns. This forced the adapter to support both code paths and introduces a confound: CrewAI's orchestration overhead differs depending on whether the underlying provider supports native function calling.

*Adapter parity vs.\ idiomatic usage.* Achieving a controlled comparison requires shared structure (same prompts, same tools, same scoring) while preserving each platform's native patterns. The solution was a layered architecture: the `ToolAgentAdapter` base class provides the shared template (prompt construction, tool creation, retry policy, result building), while each adapter's `_run_agent` method uses the platform's idiomatic orchestration. For example, LangGraph uses compiled subgraphs with checkpointing, CrewAI uses sequential crews with role-based agents, and the Agent Framework uses MagenticOne manager-driven teams. This design ensures that measured differences reflect genuine platform capabilities rather than adapter implementation choices.

*Deploy stage security model.* The deploy stage requires agents to execute commands on a remote server via SSH---a significant security surface. The mitigation is a defence-in-depth approach: the target server runs a restricted user (`desmet`) with a whitelisted shell permitting only `git pull`, `docker compose up`, `docker ps`, and `curl`; SSH access is restricted to a Tailscale VPN mesh; and each platform--story combination pushes to a dedicated git branch, providing isolation within a single deploy repository. This model prevents any agent-initiated action from affecting other services while still providing a realistic deployment environment for evaluation.
```

- [ ] **Step 4: Verify compilation**

Run: `typst compile docs/report/DESMET_Agentic_Platforms.typ --root docs/report/ 2>&1 | head -5`

Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add docs/report/chapters/implementation.typ
git commit -m "docs(report): describe metrics collection and technical challenges (§4.5, §4.7)"
```

---

### Task 5: Complete Evaluation Method Chapter

**Files:**
- Modify: `docs/report/chapters/evaluation-method.typ` — fill all remaining TODO sections

- [ ] **Step 1: Replace Story Selection Rationale TODO (§5.1.1)**

In `docs/report/chapters/evaluation-method.typ`, locate `=== Story Selection Rationale`. Replace the TODO comment with:

```typst
=== Story Selection Rationale

The four user stories were selected to satisfy three criteria: coverage of complexity tiers, exercise of all pipeline stages, and differentiation of platform capabilities.

Complexity coverage is achieved through three tiers: US001 (basic) tests the pipeline end-to-end with a single-file utility function, minimising task complexity so that pipeline failures can be attributed to framework issues rather than task difficulty. US010 and US030 (intermediate) introduce multi-file generation and API integration (US010) or frontend--backend coordination (US030), requiring the agent to manage cross-file dependencies and produce multiple artefacts. US020 (advanced) demands multi-component coordination with security requirements (authentication), exercising the full range of planning, generation, testing, and deployment capabilities.

Each story is designed to exercise all four pipeline stages: every story has acceptance criteria suitable for requirements extraction (Stage~1), produces source code (Stage~2), supports automated testing (Stage~3), and can be packaged and deployed as a runnable service (Stage~4). This ensures that per-stage metrics are available for every platform--story combination, enabling the cross-cutting dimension aggregations defined in the Design chapter.

The stories are deliberately scoped to be achievable within a single LLM context window to avoid conflating framework orchestration capability with context-length limitations. The most complex story (US020) requires approximately 15 files across authentication, routing, and testing modules---substantial enough to differentiate platforms but not so large that token budget exhaustion becomes the dominant failure mode.
```

- [ ] **Step 2: Replace Story Definitions TODO (§5.1.2)**

Locate `=== Story Definitions`. Replace the TODO comment (keeping the existing table) with the following content inserted BEFORE the existing `#figure(table(...))`:

```typst
=== Story Definitions

Each story is defined in YAML with metadata fields consumed by the harness: `id`, `title`, `description`, `category`, `difficulty`, `acceptance_criteria` (a list of criterion objects with verification methods), `time_budget_seconds`, `max_iterations`, and references to associated prompt and Gherkin files. The following listing shows the schema for US001:

#figure(
  ```yaml
  id: US-001
  title: Add Email Validation Utility Function
  description: >
    As a developer integrating user registration, I want a
    reusable email validation utility function so that I can
    consistently validate email inputs across the application.
  category: code_generation
  difficulty: basic
  tags: [utility, validation, regex]
  prompt_file: prompts/basic/US001_add_utility_function.md
  gherkin_file: gherkin/basic/US001_add_utility_function.feature
  target_files: [utils/validation.py]
  acceptance_criteria:
    - id: AC-001-1
      description: Function exists with correct signature
      verification_method: automated
    - id: AC-001-2
      description: Valid emails return True
      verification_method: test
    - id: AC-001-3
      description: Invalid emails return False
      verification_method: test
    - id: AC-001-4
      description: Edge cases handled gracefully
      verification_method: test
  time_budget_seconds: 300
  max_iterations: 50
  ```,
  caption: [User Story YAML Schema (US001)],
)
```

Then update the existing summary table to fill in the acceptance criteria counts: US001 = 4, US010 = 5, US030 = 6, US020 = 7 (verify these by reading the actual YAML files in `data/stories/` — adjust if the actual counts differ).

- [ ] **Step 3: Replace Data Format Flow TODO (§5.2.1)**

Locate the TODO comment under `=== Input Artefacts` (after the three bullet points). Replace it with:

```typst
These three formats form a pipeline: YAML story definitions provide the structured metadata that the harness uses to configure each run (time budgets, iteration limits, expected files). The harness constructs stage-specific prompts from the standardised prompt templates, injecting story-specific context (description, acceptance criteria, prior stage outputs) into each template. Gherkin feature files serve as ground truth for acceptance criteria coverage assessment---the harness can compare the agent's generated requirements against the Gherkin specifications to identify coverage gaps, though this comparison serves as a control variable rather than a scoring input (see §5.3 below).
```

- [ ] **Step 4: Replace Output Artefacts TODO (§5.2.2)**

Locate the TODO comment under `=== Output Artefacts`. Replace it with:

```typst
Each pipeline stage produces a `StageResult` object (defined in `harness/results.py`) serialised to JSON in the results directory. Stage-specific result types extend the base: `RequirementsResult` stores structured requirements JSON and PlantUML source; `CodeResult` records files written and tool call metadata; `TestResult` captures test pass/fail counts, coverage data, and test runner output; `DeployResult` records push, restart, and health check outcomes. All result types include common fields: `platform_id`, `stage_name`, `success`, `iterations`, `tool_calls`, `tokens_input`, `tokens_output`, `wall_clock_seconds`, and `langfuse_trace_id` for trace cross-referencing. Generated artefacts (source code, test files, build logs) are retained in the workspace directory for manual inspection.
```

- [ ] **Step 5: Add WebUI as execution instrument (§5.3)**

Locate the subsection `=== Execution Methodology` within `== Execution Setup`. Find the numbered list item that mentions "management console". After the existing numbered list, add a new paragraph:

```typst
In practice, the management console (described in @sec-webui) serves as the primary execution instrument. The evaluator uses the _New Run_ page to select platforms, stories, and model configuration; monitors execution progress via the live WebSocket log stream in the _Run Detail_ page; and assigns qualitative rubric scores via the _Scoring_ page with Langfuse trace evidence, LangSmith run trees, and the agent communication graph visible alongside the scoring form. This workflow ensures that qualitative scoring decisions are grounded in trace-level evidence rather than post-hoc recollection.
```

- [ ] **Step 6: Replace Ethical Considerations TODO (§5.4)**

Locate `== Ethical Considerations`. Replace the TODO comment with:

```typst
== Ethical Considerations

The evaluation was designed with the following ethical considerations:

- *Data privacy*: All user stories are synthetic software engineering tasks containing no personal, sensitive, or proprietary data. No real user data is processed at any stage of the pipeline.
- *API cost transparency*: Each pipeline stage records estimated API costs based on token usage and provider pricing. The total evaluation cost across all platform--story combinations is reported in the results to enable informed replication decisions by future researchers.
- *Open-source licensing*: All nine platforms under evaluation are open-source (MIT, Apache~2.0, or fair-code licensed). The evaluation harness itself is developed as an open-source project, enabling independent verification of results.
- *Reproducibility*: All prompts, model configurations, story definitions, and evaluation results are version-controlled in the project repository. The harness records the exact model identifier and temperature used for each run, enabling precise replication of the evaluation conditions.
- *Single-evaluator bias*: The qualitative rubric scores reflect a single evaluator's judgement. This limitation is mitigated through structured rubrics with explicit criteria at each score level (0--3), reducing but not eliminating subjectivity. The scoring panel in the management console records free-text justification notes for each dimension score, providing an audit trail for future multi-evaluator validation studies.
```

- [ ] **Step 7: Verify compilation**

Run: `typst compile docs/report/DESMET_Agentic_Platforms.typ --root docs/report/ 2>&1 | head -5`

Expected: No errors. If `@sec-webui` is not yet defined (depends on Task 1 being done first), a warning is acceptable.

- [ ] **Step 8: Commit**

```bash
git add docs/report/chapters/evaluation-method.typ
git commit -m "docs(report): complete evaluation method chapter (§5.1-5.4)"
```

---

### Task 6: Complete Limitations Chapter

**Files:**
- Modify: `docs/report/chapters/limitations.typ` — fill all TODO sections

- [ ] **Step 1: Replace Limitations TODO (§7.1)**

In `docs/report/chapters/limitations.typ`, replace the TODO comment under `== Limitations` with:

```typst
== Limitations

Several limitations of the proposed approach should be acknowledged. First, the evaluation uses four user stories spanning three complexity tiers. While these stories were designed to exercise all pipeline stages and differentiate platform capabilities, four stories cannot represent the full diversity of software engineering tasks---results may not generalise to domains such as data engineering, mobile development, or systems programming.

Second, Layer~3 pipeline benchmarking is conducted for five of the nine platforms (LangGraph, CrewAI, OpenAI Agents SDK, Google ADK, Microsoft Agent Framework). The remaining four visual/workflow platforms (Flowise, LangFlow, Dify, N8n) are assessed at Layers~1 and~2 only, as their REST API interfaces require a fundamentally different adapter architecture. The framework is designed for straightforward adapter extension (see @appendix-adding-adapter), but the current results provide limited Layer~3 insight into the visual platform category.

Third, all evaluations use a single LLM model to isolate framework capability from model capability. While this is a deliberate methodological choice, it means results may not transfer to other models---a framework that performs well with one model's function-calling behaviour may struggle with another's.

Fourth, qualitative rubric scores are assigned by a single evaluator. Despite structured criteria at each score level, borderline cases (e.g., distinguishing a score of~2 from~3 on error recovery) involve subjective judgement. The management console records free-text justification notes to support future multi-evaluator validation.

Finally, agentic platforms evolve rapidly. The evaluation represents a point-in-time snapshot; findings may not generalise to future platform versions. All platform versions are recorded in the results metadata to enable temporal context when interpreting findings.
```

- [ ] **Step 2: Replace Internal Validity TODO (§7.2.1)**

Replace the TODO comment under `=== Internal Validity` with:

```typst
=== Internal Validity

*Single-evaluator bias.* All qualitative rubric scores reflect one person's judgement. This is mitigated by structured rubrics with explicit criteria at each score level @kitchenham1997desmet and by the management console's scoring workflow, which presents trace evidence alongside the rubric to ground judgements in observable data rather than recollection.

*Rubric subjectivity.* Despite structured criteria, borderline cases require judgement calls---for example, whether a platform that recovers from one error but not another warrants a score of~2 or~3 on error recovery. The free-text notes field in the scoring panel provides an audit trail for such decisions.

*Prompt sensitivity.* All platforms receive the same standardised prompts via shared prompt templates. However, platforms process prompts differently---some inject additional system instructions, others restructure the conversation history---which may affect LLM behaviour in ways not captured by the framework-centric metrics.

*Order effects.* Platforms are evaluated sequentially, and later evaluations may benefit from the evaluator's accumulated familiarity with the scoring rubric and common failure modes. This is partially mitigated by the structured rubric, which anchors scores to specific observable criteria rather than relative comparison.

*LLM non-determinism.* Language model outputs are inherently stochastic. Repeated runs of the same platform--story combination may yield different results. All prompts, configurations, and outputs are recorded for reproducibility, and the harness supports repeated runs with variance metrics computation @taherdoost2019likert.
```

- [ ] **Step 3: Replace External Validity TODO (§7.2.2)**

Replace the TODO comment under `=== External Validity` with:

```typst
=== External Validity

*Story representativeness.* Four user stories cannot represent the full population of software engineering tasks. The stories were selected for complexity-tier coverage and pipeline-stage exercise (see §5.1.1), but results should be interpreted as indicative of relative platform capability within the evaluated task types rather than as absolute performance predictions.

*Platform version sensitivity.* Agentic platforms are under active development, with breaking changes occurring between minor versions---as evidenced by the CrewAI token tracking breakage documented in the Technical Challenges section. Findings are tied to the specific platform versions recorded in the evaluation metadata and may not generalise to future releases.

*LLM model dependency.* Using a single LLM model controls for model capability but limits generalisability. A platform's orchestration effectiveness may vary with different models---for example, a framework that relies heavily on structured output may perform differently with models that have weaker JSON generation capabilities.

*Category representativeness.* Nine platforms across three categories provide reasonable but not exhaustive coverage of the agentic platform landscape. Notably, proprietary tools (e.g., Devin, Cursor Agent) and domain-specific platforms (e.g., biomedical agent frameworks) are excluded. The three-category taxonomy (multi-agent frameworks, SDK runtimes, visual platforms) captures the major architectural paradigms but may not account for emerging hybrid approaches.
```

- [ ] **Step 4: Replace Construct Validity TODO (§7.2.3)**

Replace the TODO comment under `=== Construct Validity` with:

```typst
=== Construct Validity

*Framework-centric vs.\ output quality metrics.* The evaluation's central design choice is to measure framework capability rather than LLM output quality, since the same model is used across all platforms. However, this separation is imperfect: platforms differ in how they construct system prompts, structure conversation history, and handle tool results, all of which can influence output quality through the framework's interaction with the model. The framework-centric metrics capture orchestration behaviour (tool reliability, error recovery, trace fidelity) but may not fully account for framework-induced output quality differences.

*Rubric scale granularity.* The 0--3 rubric scale was chosen to reduce inter-rater ambiguity in a single-evaluator context @kitchenham1997desmet @taherdoost2019likert. This coarser scale trades measurement precision for scoring reliability---meaningful differences between closely-performing platforms may be obscured when both map to the same integer score. The cross-cutting dimension aggregation (averaging across stories) partially mitigates this by producing continuous scores on a 1--5 scale.

*Aggregation formula design.* The cross-cutting dimension formulas involve design choices: equal weighting across stories, specific normalisation constants (100,000-token budget, \$0.50-per-story cost budget), and equal weighting across dimension components. Alternative weighting schemes could yield different platform rankings. The formulas are documented explicitly to enable sensitivity analysis, and the raw per-stage metrics are retained to support alternative aggregation approaches @kitchenham1998desmet_eval.
```

- [ ] **Step 5: Verify compilation**

Run: `typst compile docs/report/DESMET_Agentic_Platforms.typ --root docs/report/ 2>&1 | head -5`

Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add docs/report/chapters/limitations.typ
git commit -m "docs(report): complete limitations and threats to validity (§7.1-7.2)"
```

---

### Task 7: Write Conclusions Skeleton

**Files:**
- Modify: `docs/report/chapters/conclusions.typ` — replace all TODO sections

- [ ] **Step 1: Replace Summary of Contributions TODO (§8.1)**

In `docs/report/chapters/conclusions.typ`, replace the TODO comment under `== Summary of Contributions` with:

```typst
== Summary of Contributions

This project makes three contributions to the evaluation of agentic platforms for software engineering:

+ *Evaluation framework.* A DESMET-based three-layer evaluation methodology combining qualitative screening (industry readiness, platform characteristics) with pipeline benchmarking. The framework extends Broccia et al.'s @broccia2025humainflow visual-platform-only comparison to all three architectural categories (multi-agent frameworks, SDK runtimes, visual workflow platforms) and adds empirical benchmarking as a third evaluation layer. The framework's design---separating industry readiness (Layer~1), platform capabilities (Layer~2), and pipeline performance (Layer~3)---enables practitioners to evaluate platforms at the depth appropriate to their decision-making stage.

+ *Empirical comparison.* A cross-platform evaluation of nine agentic platforms, covering a different and broader set of frameworks than prior work. Where Yin et al. @yin2025comprehensive evaluate seven code-centric frameworks and Derouiche et al. @derouiche2025agentic compare six frameworks architecturally, this study spans nine platforms across three architectural categories using a unified evaluation methodology with four cross-cutting dimensions: Pipeline Completeness, Efficiency, Orchestration, and Autonomy.

+ *Evaluation tooling.* The `desmet` evaluation harness and web-based management console, designed as a reusable evaluation instrument rather than a single-use research artefact. The harness's template-method adapter pattern requires implementors to define a single method (`_run_agent`), with prompt construction, tool creation, trace lifecycle, retry orchestration, and result building provided by the base class. The management console operationalises the scoring rubric through an interactive scoring panel with integrated trace evidence (Langfuse span trees, LangSmith run trees) and a novel agent communication graph visualisation that makes multi-agent orchestration patterns directly observable. The framework is extensible to future platforms without changes to the runner, metrics, or console (see @appendix-adding-adapter).
```

- [ ] **Step 2: Replace Key Findings TODO (§8.2)**

Replace the TODO comment under `== Key Findings` with:

```typst
== Key Findings

// RESULTS-DEPENDENT: fill after evaluations are complete.
// Structure: "The evaluation reveals that [cross-category patterns]. Across the
// benchmarked platforms, [completeness/autonomy finding]. [Orchestration finding].
// [Efficiency finding]. These findings suggest [practical implication]."
```

- [ ] **Step 3: Replace Goals Achieved TODO (§8.3)**

Replace the TODO comment under `== Goals Achieved` with:

```typst
== Goals Achieved

The project's five aims, as defined in the Introduction, are assessed below:

+ *Construct a systematic evaluation framework*: Achieved. The three-layer DESMET-based framework is fully designed, documented, and operationalised through the evaluation harness and management console.

+ *Evaluate nine platforms across three layers*: // RESULTS-DEPENDENT: state extent of completion once evaluations are done.

+ *Identify comparative strengths and weaknesses across categories*: // RESULTS-DEPENDENT: summarise whether cross-category patterns emerged.

+ *Provide actionable guidance for practitioners*: // RESULTS-DEPENDENT: summarise whether the findings support practical recommendations.

+ *Deliver a reusable evaluation harness and taxonomy*: Achieved. The `desmet` harness with its template-method adapter pattern, management console, and scoring infrastructure is designed for extension. The platform taxonomy (multi-agent frameworks, SDK runtimes, visual platforms) provides a vocabulary for categorising future platforms.
```

- [ ] **Step 4: Replace Future Work TODO (§8.4)**

Replace the TODO comment under `== Future Work` with:

```typst
== Future Work

Several directions for future research emerge from this study:

- *Multi-evaluator validation.* The most significant methodological improvement would be repeating the qualitative scoring with multiple independent evaluators to compute inter-rater reliability (Cohen's $kappa$). The management console's scoring infrastructure---with its trace-evidence integration and per-dimension notes---is designed to support this: additional evaluators can score the same platform--story combinations independently, and the stored justification notes enable disagreement analysis.

- *Visual platform adapter implementation.* Extending Layer~3 benchmarking to the four visual/workflow platforms (Flowise, LangFlow, Dify, N8n) would complete the cross-category comparison. These platforms expose REST APIs for workflow execution, requiring a different adapter architecture than the SDK-based adapters but fitting within the existing harness framework.

- *Longitudinal evaluation.* Agentic platforms evolve rapidly---CrewAI's breaking changes between minor versions illustrate this. A longitudinal study repeating the evaluation across platform versions would reveal whether capability gaps are narrowing and whether relative rankings are stable over time.

- *Extended pipeline stages.* The four-stage pipeline could be expanded with additional software engineering tasks: debugging (given a failing test, locate and fix the bug), refactoring (improve code quality without changing behaviour), and code review (assess a pull request for correctness and style). Each additional stage would exercise different framework capabilities.

- *Alternative LLM models.* Repeating the evaluation with different LLM models (e.g., Claude, Gemini, open-source models via Ollama) would test the assumption that framework-centric metrics are model-independent and reveal whether some platforms are better optimised for specific model families.

- *Community-contributed adapters.* The template-method adapter pattern (see @appendix-adding-adapter) is designed for community extension. Publishing the harness as a standalone package with adapter contribution guidelines would enable the research community to expand platform coverage beyond the nine platforms evaluated in this study.
```

- [ ] **Step 5: Verify compilation**

Run: `typst compile docs/report/DESMET_Agentic_Platforms.typ --root docs/report/ 2>&1 | head -5`

Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add docs/report/chapters/conclusions.typ
git commit -m "docs(report): write conclusions skeleton with contributions and future work (§8)"
```

---

### Task 8: Verify Full Report Compilation and Cross-References

**Files:**
- Read-only verification of all modified files

- [ ] **Step 1: Compile the full report**

Run: `typst compile docs/report/DESMET_Agentic_Platforms.typ --root docs/report/ 2>&1`

Review all warnings and errors. Common issues:
- Undefined label references (`@sec-webui`, `@sec-metrics`) — verify both are defined in Task 1 and Task 4 respectively
- Missing bibliography keys — check `references.bib` for all `@citation` keys used in new content
- Figure numbering conflicts — unlikely but check

- [ ] **Step 2: Fix any compilation issues**

If any errors or relevant warnings are found, fix them in the appropriate file and re-compile.

- [ ] **Step 3: Verify cross-reference integrity**

Check that:
- `@sec-webui` (defined in Task 1) is reachable from evaluation-method.typ (Task 5, Step 5)
- `@sec-metrics` (defined in Task 4) is reachable from implementation.typ (Task 1)
- `@appendix-adding-adapter` is referenced correctly in Tasks 3, 7
- `@appendix-getting-started` is referenced correctly in Task 1

- [ ] **Step 4: Final commit if any fixes were needed**

```bash
git add docs/report/
git commit -m "docs(report): fix cross-references and compilation issues"
```

Only create this commit if changes were needed. If compilation was clean, skip this step.
