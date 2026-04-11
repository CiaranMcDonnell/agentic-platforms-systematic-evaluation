#import "../template.typ": *

= Evaluation Method

This chapter describes the evaluation procedure: the data artefacts driving the pipeline, the execution setup, data collection methods, and ethical considerations. It complements the framework design presented in the preceding chapters by detailing _how_ the evaluation was conducted.

== User Story Design

The evaluation pipeline is driven by four user stories of increasing complexity, each representing a realistic software engineering task. Stories are authored to exercise different platform capabilities and to differentiate performance across complexity tiers.

=== Story Selection Rationale

The four user stories were selected to satisfy three criteria: coverage of complexity tiers, exercise of all pipeline stages, and differentiation of platform capabilities.

Complexity coverage is achieved through three tiers: US001 (basic) tests the pipeline end-to-end with a single-file utility function, minimising task complexity so that pipeline failures can be attributed to framework issues rather than task difficulty. US010 and US030 (intermediate) introduce multi-file generation and API integration (US010) or frontend--backend coordination (US030), requiring the agent to manage cross-file dependencies and produce multiple artefacts. US020 (advanced) demands multi-component coordination with security requirements (authentication), exercising the full range of planning, generation, testing, and deployment capabilities.

Each story is designed to exercise all four pipeline stages: every story has acceptance criteria suitable for requirements extraction (Stage~1), produces source code (Stage~2), supports automated testing (Stage~3), and can be packaged and deployed as a runnable service (Stage~4). This ensures that per-stage metrics are available for every platform--story combination, enabling the cross-cutting dimension aggregations defined in the Design chapter.

The stories are deliberately scoped to be achievable within a single LLM context window to avoid conflating framework orchestration capability with context-length limitations. The most complex story (US020) requires approximately 15 files across authentication, routing, and testing modules---substantial enough to differentiate platforms but not so large that token budget exhaustion becomes the dominant failure mode.

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

#figure(
  table(
    columns: 4,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Story ID*], [*Title*], [*Complexity*], [*Acceptance Criteria Count*],
    ),
    [US001], [Add utility function], [Basic], [4],
    [US010], [Add API endpoint], [Intermediate], [4],
    [US030], [Design fullstack app], [Intermediate], [9],
    [US020], [Implement auth system], [Advanced], [7],
  ),
  caption: [User Story Summary],
)

== Data Formats and Artefacts

=== Input Artefacts

The evaluation uses three input formats per story:

- *YAML story definitions* (`data/stories/`): Structured story metadata, acceptance criteria, and expected outputs used by the harness to drive pipeline execution.
- *Gherkin feature files* (`data/gherkin/`): Behaviour-driven specifications expressing acceptance criteria in Given/When/Then syntax, used as ground truth for acceptance criteria coverage assessment.
- *Prompt templates* (`data/prompts/`): Standardised prompts provided to each platform, ensuring consistent task framing across the evaluation.

These three formats form a pipeline: YAML story definitions provide the structured metadata that the harness uses to configure each run (time budgets, iteration limits, expected files). The harness constructs stage-specific prompts from the standardised prompt templates, injecting story-specific context (description, acceptance criteria, prior stage outputs) into each template. Gherkin feature files serve as ground truth for acceptance criteria coverage assessment---the harness can compare the agent's generated requirements against the Gherkin specifications to identify coverage gaps, though this comparison serves as a control variable rather than a scoring input (see §5.3 below).

=== Output Artefacts

Each pipeline stage produces a `StageResult` object (defined in `harness/results.py`) serialised to JSON in the results directory. Stage-specific result types extend the base: `RequirementsResult` stores structured requirements JSON and PlantUML source; `CodeResult` records files written and tool call metadata; `TestResult` captures test pass/fail counts, coverage data, and test runner output; `DeployResult` records push, restart, and health check outcomes. All result types include common fields: `platform_id`, `stage_name`, `success`, `iterations`, `tool_calls`, `tokens_input`, `tokens_output`, `wall_clock_seconds`, and `langfuse_trace_id` for trace cross-referencing. Generated artefacts (source code, test files, build logs) are retained in the workspace directory for manual inspection.

== Ground Truth and Baselines

=== Acceptance Criteria as Ground Truth

Acceptance criteria coverage is measured against the criteria defined in each user story's YAML definition. This serves as a _control variable_ rather than a scoring input: since the same LLM is used across all platforms, similar acceptance criteria coverage is expected, and significant divergence would indicate a framework-level issue (e.g., the platform failing to pass the full story context to the model). The framework-centric scoring dimensions (pipeline completeness, tool integration, error recovery, etc.) are assessed independently of output content quality.

// TODO: Describe how ground truth differs per stage — acceptance criteria
// for Stage 1, requirements document for Stage 2, generated code for Stage 3,
// test suite for Stage 4.

=== Baseline Expectations

// TODO: Describe any baseline expectations or reference implementations used
// to calibrate the qualitative rubric scoring (0–3 scale).

== Data Collection Methods

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Layer*], [*Method*], [*Tooling*],
    ),
    [Layer 1], [Desk research: GitHub API for repository statistics, manual review of documentation and adoption evidence], [Standardised template per platform],
    [Layer 2], [Documentation review and hands-on verification: install each platform, attempt feature use, record Yes/Partial/No], [Feature matrix with evidence notes per cell],
    [Layer 3], [Automated pipeline execution via the evaluation harness; manual scoring for qualitative rubrics post-execution], [Per-stage JSON artifacts stored in results directory],
  ),
  caption: [Data Collection Methods by Layer],
)

== Execution Setup

=== Environment and Repository Structure

The evaluation runs on Python 3.11+ (SDK-based platforms), Node.js LTS (N8n, Flowise), and Docker for isolated deployments. LLM access uses OpenAI, Anthropic, Google, and OpenRouter API keys. Dependencies are managed with uv (Python) and Bun (JavaScript/TypeScript). Full environment setup is described in @appendix-getting-started.

=== Execution Methodology

Each platform undergoes the following evaluation process:

+ *Layer 1 Assessment*: Platform maturity profile compiled from GitHub data, documentation review, and industry adoption evidence.
+ *Layer 2 Assessment*: Feature matrices populated through documentation review and hands-on verification of each criterion.
+ *Layer 3 Benchmarking*: Four user stories executed through the four-stage pipeline using the management console. Quantitative metrics (token usage, timing, costs) captured automatically; qualitative rubric scores assigned post-execution via the scoring panel.
+ *Result recording*: All results logged to structured JSON output in `results/{platform}/{story_id}/` for analysis.

In practice, the management console (described in @sec-webui) serves as the primary execution instrument. The evaluator uses the _New Run_ page to select platforms, stories, and model configuration; monitors execution progress via the live WebSocket log stream in the _Run Detail_ page (@fig-webui-run-detail); and assigns qualitative rubric scores via the _Scoring_ page with Langfuse trace evidence, LangSmith run trees, and the agent communication graph visible alongside the scoring form. This workflow ensures that qualitative scoring decisions are grounded in trace-level evidence rather than post-hoc recollection.

#figure(
  image("../figures/webui/run-detail.png", width: 95%),
  caption: [Run Detail page showing live log stream during pipeline execution with stage progress and status tracking],
) <fig-webui-run-detail>

=== Automation and Reproducibility

To ensure reproducibility and reduce evaluator bias:

- Standardised prompt templates are used across all platforms where applicable
- The evaluation harness automates pipeline execution, metric collection, and result storage
- Token usage and API costs are recorded programmatically at each pipeline stage
- All configurations, prompts, and results are version-controlled
- Qualitative rubric scores are assigned against the defined 0--3 scale to minimise subjectivity

== Ethical Considerations

The evaluation was designed with the following ethical considerations:

- *Data privacy*: All user stories are synthetic software engineering tasks containing no personal, sensitive, or proprietary data. No real user data is processed at any stage of the pipeline.
- *API cost transparency*: Each pipeline stage records estimated API costs based on token usage and provider pricing. The total evaluation cost across all platform--story combinations is reported in the results to enable informed replication decisions by future researchers.
- *Open-source licensing*: All nine platforms under evaluation are open-source (MIT, Apache~2.0, or fair-code licensed). The evaluation harness itself is developed as an open-source project, enabling independent verification of results.
- *Reproducibility*: All prompts, model configurations, story definitions, and evaluation results are version-controlled in the project repository. The harness records the exact model identifier and temperature used for each run, enabling precise replication of the evaluation conditions.
- *Single-evaluator bias*: The qualitative rubric scores reflect a single evaluator's judgement. This limitation is mitigated through structured rubrics with explicit criteria at each score level (0--3), reducing but not eliminating subjectivity. The scoring panel in the management console records free-text justification notes for each dimension score, providing an audit trail for future multi-evaluator validation studies.
