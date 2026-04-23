#import "../template.typ": *

= Design

This chapter presents the evaluation framework design: the methodology, platform selection, benchmark design, evaluation dimensions, and scoring rubrics for the systematic evaluation of agentic platforms.

== Evaluation Methodology Selection

As established in the Related Work chapter, this study adopts a hybrid DESMET approach combining *benchmarking* (standardised pipeline execution across platforms) with *qualitative screening* (feature-based assessment of platform characteristics). This hybrid is necessary because the architectural heterogeneity of multi-agent frameworks, SDK runtimes, and visual workflow builders makes purely quantitative comparison insufficient---qualitative factors like developer experience, extensibility, and onboarding complexity significantly influence platform adoption but resist measurement through benchmarks alone. A 0--3 Likert scale is used for qualitative rubrics rather than the conventional 0--5, following the DESMET principle that coarser scales improve reliability when assessments cannot be cross-validated in a single-evaluator study @kitchenham1997desmet @taherdoost2019likert. Methodological limitations---single-evaluator bias, LLM non-determinism, and the point-in-time snapshot nature of the evaluation---are discussed in @limitations.

== Platform Selection and Categorisation

Nine platforms are evaluated, spanning three architectural categories that reflect distinct approaches to agentic systems: *multi-agent frameworks* (LangGraph, CrewAI) provide programmatic control over agent coordination through explicit orchestration logic; *agent SDK runtimes* (OpenAI Agents SDK, Google ADK, Microsoft Agent Framework) offer vendor-supported development kits optimised for their respective LLM providers; and *visual/workflow platforms* (Flowise, LangFlow, Dify, N8n) prioritise accessibility through no-code or low-code interfaces.

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Category*], [*Platform*], [*Description*],
    ),
    table.cell(rowspan: 2)[Multi-Agent Frameworks],
    [LangGraph], [Graph-based agent orchestration built on LangChain @langchain2024langgraph],
    [CrewAI], [Role-based multi-agent collaboration framework @crewai2024],

    table.cell(rowspan: 3)[Agent SDK Runtimes],
    [OpenAI Agents SDK], [OpenAI's native agent development kit @openai2025agents_sdk],
    [Google ADK], [Google's Agent Development Kit @google2025adk],
    [Microsoft Agent Framework], [Unified agent SDK merging AutoGen and Semantic Kernel @microsoft2025agent_framework],

    table.cell(rowspan: 4)[Visual / Workflow Platforms],
    [Flowise], [Drag-and-drop LLM flow builder],
    [LangFlow], [Visual IDE for LangChain applications],
    [Dify], [LLM application development platform @dify2024],
    [N8n], [Workflow automation with AI capabilities],
  ),
  caption: [Selected Agentic Platforms by Category],
)

Platforms were selected for maturity (stable releases, active maintenance), industry adoption (community size, GitHub activity), category coverage, SDK availability for consistent benchmark execution, accessibility (open-source or free-tier), and relevance to software engineering workflows. Microsoft AutoGen @wu2023autogen and Semantic Kernel, originally considered as separate platforms, were unified by Microsoft in 2025 under the Agent Framework @microsoft2025agent_framework; this evaluation assesses the unified framework. Agent-to-Agent (A2A) interoperability is assessed as a cross-cutting feature in the Layer~2 feature matrix rather than as a standalone category.

== Evaluation Pipeline and Benchmark Design

Rather than evaluating platforms on isolated tasks, each platform is given a scenario and must execute a sequence of pipeline stages---mirroring how practitioners actually use agentic platforms. @fig-pipeline-activity shows the complete pipeline as a UML activity diagram, including the per-platform parallel execution region, output artefacts per stage, and the four cross-cutting evaluation dimensions measured throughout.

#include "../diagrams/implementation/pipeline-activity.typ"

=== Pipeline Stages

Each platform attempts a four-stage software engineering pipeline. Design (UML diagram generation) is folded into the first stage, following the approach in Broccia et al. @broccia2025humainflow where requirements extraction and structural modelling form a single artefact-generation step. The requirements and design stage is informed by established GenAI approaches to requirements engineering @cheng2024genai_re, while the build and deployment stage follows continuous integration and delivery principles @shahin2017cicd.

#figure(
  table(
    columns: 4,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Stage*], [*Input*], [*Output*], [*Key Metrics*],
    ),
    [1. Requirements \& Design],
    [User scenario (YAML)],
    [Structured requirements, acceptance criteria, UML diagrams (Mermaid)],
    [Stage completion, parseable UML, tool calls, tokens, time],

    [2. Code Generation],
    [Requirements + UML design],
    [Source code],
    [Stage completion, files produced, tool reliability, tokens, time],

    [3. Test Generation],
    [Requirements + source code],
    [Test suite],
    [Stage completion, test runner invocation, coverage tool integration, tokens, time],

    [4. Build \& Deploy],
    [Source code + tests],
    [Passing build, deployable artifact],
    [Build success, deploy success, error recovery, tokens, time],
  ),
  caption: [Pipeline Stages Overview],
)

For each stage, two tiers are recorded: a *capability tier* (Supported / Partial / Not Supported) indicating whether the platform can perform the stage at all, and a *performance tier* capturing quantitative and qualitative metrics when the stage completes. Every pipeline stage additionally records four common resource consumption metrics alongside its stage-specific framework metrics: token usage (input, output, total), estimated API cost, wall-clock time, and human intervention count.

=== Scenarios

Four scenarios of increasing complexity are run through the pipeline, providing a range of difficulty levels to differentiate platform capabilities:

#figure(
  placement: auto,
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Scenario*], [*Complexity*], [*Purpose*],
    ),
    [US001 (utility function)], [Basic], [Tests pipeline end-to-end with minimal complexity],
    [US010 (API endpoint)], [Intermediate], [Tests API integration and multi-file generation],
    [US030 (fullstack app)], [Intermediate], [Tests frontend and backend coordination],
    [US020 (auth system)], [Advanced], [Tests complex requirements, security concerns, multi-component coordination],
  ),
  caption: [Scenarios for Pipeline Evaluation],
) <tab-user-scenarios>

The framework is designed for 9 platforms × 4 scenarios × 4 stages = 144 stage-level evaluations. Layer~3 pipeline benchmarking is conducted for the eight platforms with implemented adapters (LangGraph, CrewAI, OpenAI Agents SDK, Google ADK, Microsoft Agent Framework, Flowise, LangFlow, N8n), yielding 8 × 4 × 4 = 128 stage-level evaluations; Dify is assessed at Layers~1--2 only, because its marketplace-only plugin ecosystem (introduced in Dify~v1.0 in February~2025 and retained through v1.13.3) blocks fully automated execution (see @limitations).

== Three-Layer Evaluation Framework

The framework comprises three layers, each answering a distinct practitioner question: viability, capability, and performance. @fig-three-layer provides an overview.

#include "../diagrams/evaluation/three-layer-framework.typ"

=== Layer 1: Industry Readiness

*Purpose:* Establish baseline platform viability. Answers: _"Is this platform mature enough to evaluate seriously?"_

#figure(
  table(
    columns: 2,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Criterion*], [*What It Measures*],
    ),
    [Release Maturity], [Stable release (v1.0+)? Pre-release, alpha, or beta?],
    [Maintenance Activity], [Commits in last 6 months, open issues response time, release cadence],
    [Community Size], [GitHub stars, contributors, Discord/Slack activity, Stack Overflow presence],
    [Documentation Quality], [Official docs exist? Tutorials? API reference? Completeness and accuracy],
    [Industry Adoption], [Evidence of production use: case studies, enterprise mentions, job postings],
    [Licensing], [Open-source (MIT/Apache)? Fair-code? Proprietary? Implications for extensibility],
  ),
  caption: [Layer 1: Industry Readiness Criteria],
)

Layer 1 produces a factual maturity profile per platform rather than a numeric score. This contextualises all subsequent findings: a high-performing but abandoned platform is not useful guidance for practitioners.

=== Layer 2: Platform Characteristics

*Purpose:* Map what each platform _can_ do, independent of how well it performs on benchmarks. Answers: _"What features and architectural properties does this platform have?"_

This layer directly extends the system-level and interaction-level comparison framework from Broccia et al. @broccia2025humainflow, expanding it from eight visual workflow tools to nine platforms spanning three architectural categories. Additional criteria (A2A protocol support, sandboxing, workflow patterns, memory management, multi-agent coordination) reflect the broader scope of this evaluation. The feature selection draws on Derouiche et al.'s analysis of agentic framework architectures @derouiche2025agentic and Duan et al.'s comparative study of LangGraph and CrewAI @duan2024exploration.

System-level criteria assess MCP support, A2A support, SDK independence, local LLM execution, remote LLM provider support, extensibility (plugin systems, custom tool registration), execution monitoring, and sandboxing. Interaction-level criteria assess code level (no-code/low-code/full-code), team collaboration, human-in-the-loop support, workflow patterns (sequential, parallel, hierarchical, conditional), memory/state management, and multi-agent coordination. Each criterion is scored Yes/Partial/No based on documentation review and hands-on verification; the full rubric including score-level criteria and evidence notes is provided in @appendix-scoring-rubric.

=== Layer 3: Pipeline Benchmarking

*Purpose:* Measure how well each platform orchestrates a real software engineering pipeline. Answers: _"Given a scenario, how completely and autonomously can this platform execute the four-stage SE pipeline?"_

Layer~3 is the novel empirical contribution of this study. Each platform is evaluated by running the four-stage pipeline across four scenarios of increasing complexity. Since the same LLM is used across all platforms, variations in stage output quality reflect the underlying model rather than the framework; the metrics therefore focus on framework capability (pipeline completion, tool reliability, error recovery, tracing) rather than output quality. Stage outputs (generated requirements, code, tests, build logs) are retained as artefacts for contextual inspection but are *not* scored, since output quality reflects the underlying LLM rather than the framework under evaluation. Per-stage framework-centric metrics (stage completion, parseable UML, tool calls, error recovery, test runner invocation, coverage tool integration, build success, deploy success) are enumerated in @appendix-scoring-rubric.

=== Framework Scoring Rubric

Six framework-centric dimensions are scored on a 0--3 rubric: *Pipeline Completeness* (stages completed end-to-end), *Tool Integration* (tool-call reliability), *Error Recovery* (detection, diagnosis, retry), *Time Efficiency* (wall-clock relative to budget), *Autonomy* (human interventions), and *Trace Quality* (trace completeness: messages, tool calls, tokens, timing, state). These dimensions measure _platform capability_ for building SE pipelines, not the quality of LLM-generated output (which is held constant by using the same model across all platforms). The complete rubric with detailed criteria at each score level and evaluation guidance is provided in @appendix-scoring-rubric.

=== Cross-cutting Aggregations

Per-stage rubric scores are aggregated into four cross-cutting dimension scores per platform, each normalised to a 1--5 Likert scale. All dimensions measure *framework capability*---how well the platform orchestrates the SE pipeline---not LLM output quality. This multi-dimensional approach is validated by Yin et al. @yin2025comprehensive, whose three-perspective evaluation (effectiveness, efficiency, overhead) demonstrated that no single metric suffices for comparing agent frameworks, and by Mehta @mehta2025clear, whose CLEAR framework shows that multi-dimensional evaluation correlates significantly more strongly with production success than accuracy-only assessment. Ferrari et al. @ferrari2021systematic further support this prioritisation, finding that process integration---not usability or maturity---is the primary barrier to tool adoption in practice.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Dimension*], [*Aggregated From*],
    ),
    [Pipeline Completeness], [Scenario completion rate and pipeline completeness rubric scores],
    [Efficiency], [Token usage and wall-clock time relative to budgets],
    [Orchestration], [Tool integration, error recovery, and trace quality rubric scores],
    [Autonomy], [Human interventions across all stages],
  ),
  caption: [Cross-cutting Evaluation Dimensions (Framework-Centric)],
)

The specific aggregation formulas (normalisation constants, component weights, and 1--5 scaling) are defined in @appendix-scoring-rubric. Equal weighting is applied by default, with sensitivity analysis exploring alternative weightings for different practitioner scenarios (e.g., usability-weighted for rapid prototyping, reliability-weighted for production deployment). These four dimensions provide the basis for radar charts and ranked cross-platform comparisons in the results analysis.
