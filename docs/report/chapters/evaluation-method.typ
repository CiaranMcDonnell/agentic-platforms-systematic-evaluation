#import "../template.typ": *

= Evaluation Method

== DESMET Method Selection

DESMET identifies nine evaluation methods and provides selection criteria based on quantifiability of benefits, availability of staff and users, stability of procedures, and observability of outcomes @kitchenham1997desmet. A single method is insufficient for the nine platforms covered here, because the three architectural categories---multi-agent frameworks, SDK runtimes, and visual workflow builders---differ in what can be measured and how. The evaluation therefore selects a distinct DESMET variant at each of the three layers.

Layer~1 applies *qualitative screening through feature analysis*. Six criteria (release maturity, maintenance activity, community size, documentation quality, industry adoption, licensing) are scored Yes/Partial/No from desk research against publicly available evidence---GitHub metadata, release notes, published case studies, and documentation sites.

Layer~2 applies *feature analysis with hands-on verification*. System-level and interaction-level criteria extend Broccia et~al. @broccia2025humainflow to the three architectural categories. Each criterion is scored Yes/Partial/No based on documentation review supplemented by hands-on exercise of each feature in the platform's own runtime, because vendor documentation routinely overstates support.

Layer~3 applies *benchmarking with hybrid subjective--objective scoring*. The four-stage pipeline is executed on every platform for which an adapter is available, with quantitative metrics (wall-clock, tokens, cost, tool calls, iterations) captured automatically and a 0--3 rubric applied to six framework-capability dimensions. The empirical pass reported in this study covers the basic scenario (US001) on the five programmatic platforms; higher-complexity scenarios and visual-platform runs remain outstanding and are discussed in @limitations. The hybrid approach is required where identical cost numbers can reflect very different orchestration strategies.

== Scenario Design

The evaluation pipeline is driven by four scenarios of increasing complexity (defined in the Design chapter, @tab-user-scenarios), each representing a realistic software engineering task.

*US001 (basic).* Tests the pipeline end-to-end with a single-file utility function, minimising task complexity so pipeline failures can be attributed to framework issues rather than task difficulty.

*US010 and US030 (intermediate).* Introduce multi-file generation with API integration or frontend--backend coordination, requiring the agent to manage cross-file dependencies.

*US020 (advanced).* Demands multi-component coordination with security requirements (authentication), exercising the full range of planning, generation, testing, and deployment capabilities.

Scenarios are scoped to fit within a single LLM context window to avoid conflating framework orchestration capability with context-length limitations; the most complex (US020) requires approximately 15 files.

Each scenario is defined in YAML with metadata fields consumed by the harness: `id`, `title`, `description`, `category`, `difficulty`, `acceptance_criteria` (a list of criterion objects with verification methods), `time_budget_seconds`, `max_iterations`, and references to associated prompt and Gherkin files. Acceptance criteria coverage serves as a _control variable_ rather than a scoring input: since the same LLM is used across all platforms, similar coverage is expected, and significant divergence would indicate a framework-level issue. A complete worked YAML example and acceptance criteria breakdown per scenario is provided in @appendix-getting-started.

== Data Formats and Artefacts

The evaluation uses three input formats per scenario: *YAML scenario definitions* (`data/stories/`) provide structured scenario metadata, acceptance criteria, and expected outputs used by the harness to drive pipeline execution; *Gherkin feature files* (`data/gherkin/`) express acceptance criteria in Given/When/Then syntax, used as ground truth for acceptance criteria coverage assessment; and *prompt templates* (`data/prompts/`) are standardised prompts provided to each platform, ensuring consistent task framing.

Each pipeline stage produces a `StageResult` object (defined in `harness/results.py`) serialised to JSON in the results directory. Stage-specific result types extend the base: `RequirementsResult` stores structured requirements JSON and `UMLDiagram` entries carrying Mermaid source; `CodeResult` records files written and tool call metadata; `TestResult` captures test pass/fail counts, coverage data, and test runner output; `DeployResult` records push, restart, and health check outcomes.

All result types include common fields: `platform_id`, `stage_name`, `success`, `iterations`, `tool_calls`, `tokens_input`, `tokens_output`, `wall_clock_seconds`, and `langfuse_trace_id` for trace cross-referencing. Generated artefacts (source code, test files, build logs) are retained in the workspace directory for manual inspection.

== Scoring Instrument

Layer~3 scoring rests on six 0--3 rubric dimensions applied per (platform, scenario) pair and aggregated into four cross-cutting 1--5 Likert scores per platform. The rubric is summarised in @tab-rubric-summary; full criterion text at each score level is provided in @appendix-scoring-rubric.

#figure(
  placement: auto,
  table(
    columns: (auto, 1fr, auto),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    table.header([*Dimension (0--3)*], [*What It Measures*], [*Source*]),
    [Pipeline Completeness], [Stages completed end-to-end without manual bridging], [Auto],
    [Tool Integration], [Tool-call reliability and argument-schema correctness], [Auto-init],
    [Error Recovery], [Detection, diagnosis, and retry on tool or build failures], [Auto-init],
    [Time Efficiency], [Wall-clock and token cost relative to budgeted values], [Auto],
    [Autonomy], [Inverse of human interventions required to complete the run], [Manual],
    [Trace Quality], [Completeness of execution trace: messages, tool calls, tokens, timing, state], [Auto-init],
  ),
  caption: [Six rubric dimensions scored per (platform, scenario) on a 0--3 scale. _Source_: _Auto_ dimensions are fully auto-derived from harness signals; _Auto-init_ dimensions are seeded from trace signals and the evaluator confirms or adjusts the score in the management console; _Manual_ dimensions are assigned directly by the evaluator.],
) <tab-rubric-summary>

The six rubric dimensions are aggregated into four cross-cutting 1--5 Likert scores that correspond to the evaluation's headline reporting dimensions. The mapping is defined in @tab-rubric-aggregation; the exact normalisation constants and scaling formulas are given in @appendix-scoring-rubric.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    table.header([*Cross-cutting Dimension (1--5)*], [*Source Rubric Dimensions (0--3)*]),
    [Pipeline Completeness], [Scenario completion ratio (auto) + pipeline completeness rubric score],
    [Efficiency], [Time ratio and token usage (both auto) + time efficiency rubric score],
    [Orchestration], [Mean of tool integration, error recovery, and trace quality rubric scores],
    [Autonomy], [Autonomy rubric score (manual 0--3), optionally 50/50 blended with logged human interventions],
  ),
  caption: [Aggregation of six rubric dimensions into four cross-cutting Likert scores.],
) <tab-rubric-aggregation>

*Pipeline Completeness* captures whether the framework can drive the four-stage pipeline from scenario to deployed artefact without manual stage bridging; it collapses to a binary signal on a single-scenario dataset but widens across the full four-scenario matrix.

*Efficiency* captures framework orchestration overhead relative to per-scenario time, token, and cost budgets; it is the dimension on which history-strategy differences between programmatic platforms become visible.

*Orchestration* captures the three rubric dimensions that describe how well the framework manages tool calls, recovers from errors, and produces a usable execution trace.

*Autonomy* captures the degree of human intervention required, and is the dimension least exercised by basic tasks; US-010, US-030, and US-020 are designed to stress it.

The four cross-cutting dimensions are populated via an auto/manual split defined in `src/desmet/harness/metrics.py`. Pipeline Completeness is auto-derived from `StageResult.success` on every stage; Efficiency is auto-derived from wall-clock, token, and API-cost ratios against documented budgets (600~seconds, 100,000~tokens, \$0.50 per scenario); and Orchestration is auto-derived as the mean of the tool_integration, error_recovery, and trace_quality rubric fields, initialised from trace-level signals (tool-call success ratio, retry-after-error evidence, and Langfuse span completeness). Autonomy is manual: the rubric score reflects the evaluator's judgement of _why_ a stage required intervention, with an optional 50/50 blend against the logged `human_interventions` counter when the adapter records interventions. The auto-safe dimensions reduce to unambiguous counters, while Autonomy's judgement content requires the evaluator to read the trace.

== Execution Setup

The evaluation runs on Python 3.11+ (SDK-based platforms), Node.js LTS (n8n, Flowise), and Docker for isolated deployments. LLM access uses OpenAI, Anthropic, Google, and OpenRouter API keys; dependencies are managed with `uv` (Python) and `bun` (JavaScript/TypeScript). Full environment setup is described in @appendix-getting-started.

Each platform undergoes the three-layer evaluation in sequence: Layer~1 (maturity profile from GitHub data, documentation review, and industry adoption evidence); Layer~2 (feature matrices from documentation review and hands-on verification); and Layer~3 (four scenarios executed through the four-stage pipeline). The management console (@sec-webui) serves as the primary execution instrument: the evaluator uses the _New Run_ page to select platforms, scenarios, and model configuration; monitors execution via the WebSocket log stream in _Run Detail_; and assigns qualitative rubric scores via the _Scoring_ page with Langfuse traces, LangSmith run trees, and the agent communication graph visible alongside the form.

Reproducibility controls are embedded in the instrument: standardised prompt templates, harness-automated execution and metric collection, programmatic token/cost recording, and version-controlled configurations, prompts, and results. Every qualitative score in the management console is accompanied by a free-text justification note referencing specific trace evidence.

== Statistical Treatment

Each (platform, scenario) cell in the present evaluation is n=1: the design is descriptive and comparative rather than inferential. No hypothesis tests or confidence intervals are reported. The harness supports repeated runs---`compute_variance_metrics` in `src/desmet/harness/metrics.py` returns coefficient-of-variation statistics on wall-clock, tokens, cost, tool calls, and iterations across repeats---but this facility has not been exercised systematically in the present dataset.

The primary claims are framework-capability claims: architectural differences produce token-cost spreads substantially larger than expected within-platform LLM variance, and the qualitative replay-strategy taxonomy (bounded checkpoints / trimmed history / full-cycle accumulation) is robust to adapter version in a way the precise ratio is not. Where a claim depends on a difference smaller than expected within-platform variance, it is flagged as a conjecture in @evaluation. Repeated runs and formal variance reporting are listed as future work in @limitations.

== Ethical Considerations

*Data privacy:* all scenarios are synthetic software engineering tasks containing no personal, sensitive, or proprietary data. *API cost transparency:* each pipeline stage records estimated API costs based on token usage and provider pricing; total evaluation cost is reported to enable informed replication decisions. *Open-source licensing:* all nine platforms are open-source (MIT, Apache~2.0, or fair-code licensed); the harness itself is open-source. *Reproducibility:* all prompts, model configurations, scenario definitions, and results are version-controlled; the harness records the exact model identifier and temperature used for each run. Single-evaluator bias is treated as an internal-validity threat in @limitations.
