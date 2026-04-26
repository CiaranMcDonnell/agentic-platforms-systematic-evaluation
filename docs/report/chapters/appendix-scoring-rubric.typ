#import "../template.typ": *

= Scoring Rubric Reference <appendix-scoring-rubric>

Six dimensions are scored on a 0--3 scale per platform--scenario pair and feed into the four cross-cutting dimension scores (Pipeline Completeness, Efficiency, Orchestration, Autonomy) described in the Project Approach and Design chapter.

All dimensions measure _framework capability_. They do not assess the quality of LLM-generated output, which is held constant by using the same model and temperature across all platforms.

Scoring is hybrid: three dimensions are auto-derived end-to-end from trace signals, three are auto-initialised from trace signals and optionally adjusted by the evaluator in the management console, and one is assigned manually. @tab-rubric-source summarises the split.

#figure(
  table(
    columns: (auto, auto, 1fr),
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header([*Dimension*], [*Source*], [*Signal*]),
    [Pipeline Completeness], [Auto], [`StageResult.success` flag per stage + scenario completion ratio],
    [Tool Integration], [Auto-init], [Seeded from tool-call success ratio; evaluator confirms or adjusts],
    [Error Recovery], [Auto-init], [Seeded from retry-after-error evidence in the trace; evaluator confirms or adjusts],
    [Time Efficiency], [Auto], [`wall_clock_seconds / time_budget_seconds` and token-budget ratio],
    [Autonomy], [Manual], [Evaluator judgement; optionally blended 50/50 with logged `human_interventions`],
    [Trace Quality], [Auto-init], [Seeded from Langfuse span completeness; evaluator confirms or adjusts],
  ),
  caption: [Auto vs. manual provenance of each rubric dimension. _Auto_ dimensions are computed directly from harness signals; _Auto-init_ dimensions are pre-scored by the harness and the evaluator confirms or adjusts; _Manual_ dimensions are assigned directly.],
) <tab-rubric-source>

== Rubric Dimensions

=== Pipeline Completeness

Measures whether the framework can execute all four SDLC stages end-to-end without manual intervention to bridge stages.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header([*Score*], [*Criteria*]),
    [*0*], [Cannot run any stage. The adapter fails during initialisation, or the platform cannot invoke tools or produce output.],
    [*1*], [Runs 1--2 stages. The platform can complete requirements analysis or code generation but fails on later stages (e.g. cannot execute tests or deploy).],
    [*2*], [Runs 3 stages. The platform handles most of the pipeline but fails on one stage, typically deployment or test execution.],
    [*3*], [Runs all 4 stages end-to-end. Requirements, code generation, testing, and deployment all complete without manual stage bridging.],
  ),
  caption: [Pipeline Completeness rubric (0--3)],
)

=== Tool Integration

Measures how reliably the framework's tool-calling mechanism works --- whether the platform can correctly invoke, parse, and handle responses from the sandboxed tools provided by the harness.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header([*Score*], [*Criteria*]),
    [*0*], [No tool use. The platform generates text responses but never invokes any of the provided tools (read_file, write_file, execute_shell, etc.).],
    [*1*], [Tools defined but frequently fail. The platform attempts tool calls but encounters parsing errors, incorrect argument formats, or fails to process tool outputs. More than half of tool calls fail.],
    [*2*], [Tools work with workarounds. Most tool calls succeed, but some require retry or produce malformed arguments that the tool wrapper must compensate for. The platform occasionally calls non-existent tools.],
    [*3*], [Clean, reliable tool execution. All tool calls use correct argument schemas, tool outputs are parsed and incorporated into reasoning, and the platform uses tools appropriately for the task.],
  ),
  caption: [Tool Integration rubric (0--3)],
)

=== Error Recovery

Measures the framework's ability to detect, handle, and recover from errors during pipeline execution --- including tool failures, validation rejections, and unexpected states.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header([*Score*], [*Criteria*]),
    [*0*], [Crashes on first error. Any tool failure, timeout, or unexpected response causes the platform to halt with an unhandled exception.],
    [*1*], [Errors halt the pipeline. The platform catches errors but stops execution rather than attempting recovery. Error messages are logged but no corrective action is taken.],
    [*2*], [Logs errors and continues partially. The platform handles some errors gracefully, skipping failed operations and continuing with the remaining pipeline. However, it does not attempt to fix the root cause.],
    [*3*], [Self-corrects and retries. The platform detects failures, diagnoses the issue (e.g. reads error output from a failed shell command), adjusts its approach, and retries. The pipeline completes despite encountering errors.],
  ),
  caption: [Error Recovery rubric (0--3)],
)

=== Time Efficiency

Measures the framework's orchestration overhead relative to the scenario's time budget. This captures how much time the framework spends on coordination, parsing, and retries beyond what the LLM calls themselves require.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header([*Score*], [*Criteria*]),
    [*0*], [Exceeded budget by 2x or more. The platform took more than twice the allotted time, typically due to excessive retries, output parsing loops, or redundant LLM calls.],
    [*1*], [Exceeded budget. Wall-clock time surpassed the time budget but by less than 2x.],
    [*2*], [Met budget. Completed within the allotted time budget.],
    [*3*], [Under budget. Completed well within the time budget, indicating efficient orchestration with minimal overhead.],
  ),
  caption: [Time Efficiency rubric (0--3)],
)

=== Autonomy

Measures the degree of human intervention required for the platform to complete the pipeline. Lower intervention indicates a more autonomous framework.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header([*Score*], [*Criteria*]),
    [*0*], [Required constant intervention. The evaluator had to intervene at nearly every step --- providing additional prompts, manually fixing tool outputs, or restarting failed stages.],
    [*1*], [Frequent intervention. Multiple interventions per stage were needed (e.g. manually providing context the platform should have retrieved, fixing malformed tool arguments).],
    [*2*], [Occasional intervention. One or two interventions across the entire pipeline (e.g. clarifying an ambiguous requirement, providing a missing configuration value).],
    [*3*], [Fully autonomous. The platform completed all stages without any human intervention. The evaluator only initiated the run and reviewed the output.],
  ),
  caption: [Autonomy rubric (0--3)],
)

=== Trace Quality

Measures the completeness and usefulness of the execution trace produced by the framework --- how much visibility the platform provides into its reasoning and decision-making process.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header([*Score*], [*Criteria*]),
    [*0*], [No execution trace. The platform produces only a final output with no record of intermediate steps, tool calls, or reasoning.],
    [*1*], [Partial trace data. Some messages or tool calls are recorded, but the trace is incomplete --- missing tool results, no timing data, or gaps in the reasoning chain.],
    [*2*], [Messages and tool calls traced. The full conversation history (user prompts, assistant responses, tool calls and their results) is captured and available for review.],
    [*3*], [Full trace with tokens, timing, and state. In addition to messages and tool calls, the trace includes per-call token usage, wall-clock timing per step, cost data, and intermediate state (e.g. graph node transitions in LangGraph, step callbacks in CrewAI).],
  ),
  caption: [Trace Quality rubric (0--3)],
)

== Layer 2 Feature Criteria

Layer~2 scores each platform on system-level and interaction-level features (Yes / Partial / No) based on documentation review and hands-on verification. The criteria below extend Broccia et al.'s @broccia2025humainflow visual-platform framework to all nine platforms across the three architectural categories in this evaluation.

#figure(
  table(
    columns: 2,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Criterion*], [*What It Measures*],
    ),
    [MCP Support], [Model Context Protocol integration for interoperability],
    [A2A Support], [Google Agent-to-Agent protocol support],
    [SDK Independence], [Tightly coupled to a specific SDK (e.g., LangChain) or agnostic?],
    [Local LLM Execution], [Can run models locally (e.g., Ollama) for privacy and cost reduction],
    [Remote LLM Providers], [Which commercial APIs are supported (OpenAI, Anthropic, Google, etc.)],
    [Extensibility], [Plugin system? Custom tool registration? Third-party integrations?],
    [Execution Monitoring], [Built-in observability: tracing, logging, node-level inspection],
    [Sandboxing / Safety], [Code execution isolation, permission boundaries],
  ),
  caption: [Layer 2: System-level Feature Criteria],
)

#figure(
  table(
    columns: 2,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Criterion*], [*What It Measures*],
    ),
    [Code Level], [No-code, low-code, or full-code interface accessibility],
    [Team Collaboration], [Shared workflows, version control, multi-user editing],
    [Human-in-the-Loop], [Can humans intervene in workflow execution? First-class or ad-hoc?],
    [Workflow Patterns], [Sequential, parallel, hierarchical, conditional branching support],
    [Memory / State Management], [Conversation memory, persistent state across agent turns],
    [Multi-Agent Coordination], [Can multiple agents collaborate? Role assignment and handoffs?],
  ),
  caption: [Layer 2: Interaction-level Feature Criteria],
)

== Per-Stage Framework Metrics

Every stage records the common resource-consumption metrics (tokens, time, cost, human interventions) defined in the Design chapter. In addition, each stage records stage-specific *framework-centric* metrics---these measure how well the _platform_ orchestrated the task, not the quality of the LLM's output (which is held constant across platforms by using the same model).

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Metric*], [*Type*], [*Measurement*],
    ),
    table.cell(colspan: 3)[_Stage 1: Requirements \& Design_],
    [Stage Completion], [Binary], [Did the platform complete the stage without crashing?],
    [Parseable UML], [Binary], [Does the Mermaid output render via `mmdc`?],
    [Tool Calls], [Quantitative], [Number of tool invocations used],
    [Error Recovery], [Observed], [Did the platform self-correct on tool errors?],

    table.cell(colspan: 3)[_Stage 2: Code Generation_],
    [Stage Completion], [Binary], [Did the platform produce output files?],
    [Files Written], [Quantitative], [Number of files produced via tool use],
    [Tool Reliability], [Observed], [Did write\_file / read\_file tools succeed consistently?],

    table.cell(colspan: 3)[_Stage 3: Test Generation_],
    [Stage Completion], [Binary], [Did the platform produce a test suite?],
    [Test Runner Invocation], [Binary], [Did the platform invoke pytest autonomously?],
    [Coverage Tool Integration], [Binary], [Did the platform produce a coverage report?],
    [Error Recovery], [Observed], [Did the platform fix failing tests and re-run?],

    table.cell(colspan: 3)[_Stage 4: Build \& Deploy_],
    [Build Success], [Binary], [Does the code build without errors?],
    [Deploy Success], [Binary], [Does the health check pass?],
    [Error Recovery], [Observed], [Did the platform resolve dependency/build issues autonomously?],
  ),
  caption: [Per-Stage Framework Metrics (all stages also record tokens, time, cost, interventions)],
)

== Aggregation into Cross-cutting Dimensions

The six rubric dimensions are aggregated into four cross-cutting scores on a 1--5 Likert scale. Automatic metrics (completion ratio, token counts, timing, intervention counts) are captured by the harness during execution; _Auto_ and _Auto-init_ rubric scores are seeded by the trace audit (see @tab-rubric-source), and the evaluator confirms or adjusts _Auto-init_ and _Manual_ scores via the management console's scoring panel after reviewing execution traces and Langfuse observations.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header([*Cross-cutting Dimension (1--5)*], [*Source Rubric Dimensions (0--3)*]),
    [Pipeline Completeness], [Scenario completion ratio (automatic) + pipeline completeness rubric score],
    [Efficiency], [Time ratio and token usage (both automatic) + time efficiency rubric score],
    [Orchestration], [Mean of tool integration, error recovery, and trace quality rubric scores],
    [Autonomy], [Autonomy rubric score (manual 0--3, primary); optionally blended 50/50 with automatic intervention count when the adapter logs interventions],
  ),
  caption: [Mapping from rubric dimensions to cross-cutting scores],
)

Let $R_c$ denote the scenario completion ratio, $overline(P)$ the mean pipeline completeness rubric score (0--3), $overline(T_r)$ the mean time ratio (wall-clock / budget), $overline(K)$ the mean tokens per scenario, $K_B$ the token budget (set to 100,000 based on the longest-running baseline scenario observed during harness calibration), $overline(O)$ the mean orchestration rubric score (average of tool integration, error recovery, and trace quality; 0--3 scale), and $overline(I)$ the mean human interventions per stage. The four cross-cutting scores are computed as:

$ P_"comp" = R_c times 0.5 + overline(P) / 3 times 0.5 quad "(scaled to 1–5)" $

$ E_"eff" = (max(1, 5 - (overline(T_r) - 1) times 2) + max(1, 5 - (overline(K) / K_B - 1) times 2)) / 2 $

$ O = overline(O) times 5 / 3 $

$ A = 5 - min(4, overline(I)) quad "(fewer interventions" arrow.r "higher score)" $
