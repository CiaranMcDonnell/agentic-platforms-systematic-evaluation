#import "../template.typ": *

= Evaluation Method

This chapter describes how the evaluation was conducted: the DESMET method selected at each layer, the data artefacts driving the pipeline, the scoring instrument, the execution setup, and the statistical treatment of the resulting data. It complements the framework design presented in the preceding chapters by detailing the procedure rather than the instrument itself. Limitations and threats to validity are consolidated in @limitations, after the results are presented.

== DESMET Method Selection

DESMET identifies nine evaluation methods and provides selection criteria based on quantifiability of benefits, availability of staff and users, stability of procedures, and observability of outcomes @kitchenham1997desmet. A single method is insufficient for the nine platforms covered here, because the three architectural categories---multi-agent frameworks, SDK runtimes, and visual workflow builders---differ in what can be measured and how. The evaluation therefore selects a distinct DESMET variant at each of the three layers described in the preceding chapter.

Layer~1 applies *qualitative screening through feature analysis*. Six criteria (release maturity, maintenance activity, community size, documentation quality, industry adoption, licensing) are scored Yes/Partial/No from desk research against publicly available evidence---GitHub metadata, release notes, published case studies, and documentation sites. Screening is the appropriate DESMET method where benefits resist numerical quantification and where no benchmark execution is yet required to separate viable from abandoned platforms.

Layer~2 applies *feature analysis with hands-on verification*. System-level and interaction-level criteria extend Broccia et~al. @broccia2025humainflow to the three architectural categories. Each criterion is scored Yes/Partial/No based on documentation review supplemented by hands-on exercise of each feature in the platform's own runtime. Hands-on verification distinguishes Layer~2 from the pure desk research of Layer~1 and is necessary because vendor documentation routinely overstates support.

Layer~3 applies *benchmarking with hybrid subjective--objective scoring*. The same four scenarios are executed through the same four-stage pipeline on every platform, with quantitative metrics (wall-clock, tokens, cost, tool calls, iterations) captured automatically and a 0--3 rubric applied to six framework-capability dimensions. DESMET permits this hybrid explicitly where architectural heterogeneity makes purely quantitative comparison brittle: identical cost numbers can reflect very different orchestration strategies, and a rubric is required to characterise the difference.

== Scenario Design

The evaluation pipeline is driven by four scenarios of increasing complexity (defined in the Design chapter, @tab-user-scenarios), each representing a realistic software engineering task. Scenarios satisfy three criteria: coverage of complexity tiers, exercise of all four pipeline stages, and differentiation of platform capabilities.

*US001 (basic).* Tests the pipeline end-to-end with a single-file utility function, minimising task complexity so pipeline failures can be attributed to framework issues rather than task difficulty.

*US010 and US030 (intermediate).* Introduce multi-file generation with API integration or frontend--backend coordination, requiring the agent to manage cross-file dependencies.

*US020 (advanced).* Demands multi-component coordination with security requirements (authentication), exercising the full range of planning, generation, testing, and deployment capabilities.

Scenarios are deliberately scoped to be achievable within a single LLM context window to avoid conflating framework orchestration capability with context-length limitations; the most complex (US020) requires approximately 15 files---substantial enough to differentiate platforms but not so large that token budget exhaustion becomes the dominant failure mode.

Each scenario is defined in YAML with metadata fields consumed by the harness: `id`, `title`, `description`, `category`, `difficulty`, `acceptance_criteria` (a list of criterion objects with verification methods), `time_budget_seconds`, `max_iterations`, and references to associated prompt and Gherkin files. Acceptance criteria coverage is measured against the criteria defined in each scenario's YAML definition---this serves as a _control variable_ rather than a scoring input: since the same LLM is used across all platforms, similar coverage is expected, and significant divergence would indicate a framework-level issue (e.g. the platform failing to pass full scenario context to the model). Full scenario definitions and prompt templates are available in the project repository; a complete worked YAML example and acceptance criteria breakdown per scenario is provided in @appendix-getting-started.

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
    [Tool Integration], [Tool-call reliability and argument-schema correctness], [Manual],
    [Error Recovery], [Detection, diagnosis, and retry on tool or build failures], [Manual],
    [Time Efficiency], [Wall-clock and token cost relative to budgeted values], [Auto],
    [Autonomy], [Inverse of human interventions required to complete the run], [Manual],
    [Trace Quality], [Completeness of execution trace: messages, tool calls, tokens, timing, state], [Manual],
  ),
  caption: [Six rubric dimensions scored per (platform, scenario) on a 0--3 scale. _Source_ indicates whether the score is auto-derived from harness signals or assigned manually in the management console.],
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

*Pipeline Completeness* captures whether the framework can drive the four-stage software engineering pipeline from a scenario through to a deployed artefact without manual stage bridging; it collapses to a binary signal on a single-scenario dataset but widens meaningfully across the full four-scenario matrix.

*Efficiency* captures framework orchestration overhead relative to per-scenario time, token, and cost budgets---the dimension on which the 14× cost spread between OpenAI SDK and Microsoft Agent Framework on US-001 is visible.

*Orchestration* captures the three rubric dimensions that describe how well the framework manages its tool calls, recovers from errors, and produces a usable execution trace; these are the dimensions that differentiate platforms of similar cost profile.

*Autonomy* captures the degree of human intervention required, and is the dimension least exercised by basic tasks; US-010, US-030, and US-020 are designed to stress it.

The four cross-cutting dimensions are populated via a deliberate auto/manual split, documented in @tab-rubric-summary and defined in `src/desmet/harness/metrics.py`. Pipeline Completeness is auto-derived from `StageResult.success` on every stage; Efficiency is auto-derived from wall-clock, token, and API-cost ratios against documented budgets (600~seconds, 100,000~tokens, \$0.50 per scenario); and Orchestration is auto-derived as the mean of the tool_integration, error_recovery, and trace_quality rubric fields, which themselves are initialised from trace-level signals (tool-call success ratio, retry-after-error evidence, and Langfuse span completeness). Autonomy is manual: the rubric score reflects the evaluator's judgement of _why_ a stage required intervention, with an optional 50/50 blend against the logged `human_interventions` counter when the adapter records interventions. The justification for the split is that the auto-safe dimensions reduce to unambiguous counters---a stage either succeeded or it did not, a tool call either parsed or it did not---while Autonomy's judgement content (distinguishing a genuine platform-level intervention from an infrastructure-level one, for example) requires the evaluator to read the trace rather than read a counter.

== Execution Setup

The evaluation runs on Python 3.11+ (SDK-based platforms), Node.js LTS (N8n, Flowise), and Docker for isolated deployments. LLM access uses OpenAI, Anthropic, Google, and OpenRouter API keys; dependencies are managed with `uv` (Python) and `bun` (JavaScript/TypeScript). Full environment setup is described in @appendix-getting-started.

Each platform undergoes the three-layer evaluation process in sequence: Layer~1 assessment (platform maturity profile compiled from GitHub data, documentation review, and industry adoption evidence); Layer~2 assessment (feature matrices populated through documentation review and hands-on verification of each criterion); and Layer~3 benchmarking (four scenarios executed through the four-stage pipeline using the management console, with quantitative metrics captured automatically and qualitative rubric scores assigned post-execution via the scoring panel). In practice, the management console (described in @sec-webui) serves as the primary execution instrument: the evaluator uses the _New Run_ page to select platforms, scenarios, and model configuration; monitors execution progress via the live WebSocket log stream in _Run Detail_; and assigns qualitative rubric scores via the _Scoring_ page with Langfuse trace evidence, LangSmith run trees, and the agent communication graph visible alongside the scoring form. This workflow ensures qualitative scoring decisions are grounded in trace-level evidence rather than post-hoc recollection.

Reproducibility controls are embedded in the instrument rather than in ad-hoc run procedure: standardised prompt templates are used across all platforms, the harness automates pipeline execution and metric collection, token usage and API costs are recorded programmatically at each stage, and all configurations, prompts, and results are version-controlled. Rubric scores are assigned against the defined 0--3 scale to minimise subjectivity, and every qualitative score in the management console is accompanied by a free-text justification note that references specific trace evidence.

== Statistical Treatment

Each (platform, scenario) cell in the present evaluation is n=1: the evaluation is a descriptive and comparative design rather than an inferential one. No hypothesis tests are reported, and no confidence intervals are placed on cross-platform differences. The harness is designed to support repeated runs---`compute_variance_metrics` in `src/desmet/harness/metrics.py` returns coefficient-of-variation statistics on wall-clock, tokens, cost, tool calls, and iterations along with a success rate across an arbitrary number of repeats of the same scenario---and this facility is available for any future inferential extension, but has not been exercised systematically in the present dataset.

Treating n=1 as acceptable at this stage is defensible because the evaluation's primary claims are framework-capability claims: architectural differences between platforms (such as Microsoft Agent Framework's Magentic-orchestrator history accumulation versus OpenAI SDK's trimmed conversation history) produce roughly 14× spreads on identical work, which dominates any plausible run-to-run noise within a single platform. Where a claim depends on a difference smaller than the expected within-platform variance, the claim is flagged as a conjecture rather than a conclusion in @evaluation. The shift to repeated runs and formal variance reporting is listed as specified future work in @limitations.

== Ethical Considerations

The evaluation was designed with the following ethical considerations. *Data privacy:* all scenarios are synthetic software engineering tasks containing no personal, sensitive, or proprietary data. *API cost transparency:* each pipeline stage records estimated API costs based on token usage and provider pricing; total evaluation cost is reported to enable informed replication decisions. *Open-source licensing:* all nine platforms are open-source (MIT, Apache~2.0, or fair-code licensed); the evaluation harness itself is developed as an open-source project. *Reproducibility:* all prompts, model configurations, scenario definitions, and evaluation results are version-controlled; the harness records the exact model identifier and temperature used for each run. The single-evaluator bias is treated as an internal-validity threat and discussed in @limitations.
