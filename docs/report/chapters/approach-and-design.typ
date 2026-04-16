#import "../template.typ": *

= Design

This chapter presents the evaluation framework design: the methodology, platform selection, benchmark design, evaluation dimensions, and scoring rubrics for the systematic evaluation of agentic platforms.

== Evaluation Methodology Selection

As established in the Related Work chapter, this study adopts a hybrid DESMET approach combining *benchmarking* (standardised pipeline execution across platforms) with *qualitative screening* (feature-based assessment of platform characteristics). This hybrid is necessary because the architectural heterogeneity of multi-agent frameworks, SDK runtimes, and visual workflow builders makes purely quantitative comparison insufficient---qualitative factors like developer experience, extensibility, and onboarding complexity significantly influence platform adoption but resist measurement through benchmarks alone. A 0--5 Likert scale was considered for qualitative rubrics but rejected in favour of a 0--3 scale to reduce inter-rater ambiguity in a single-evaluator study, following the DESMET principle that coarser scales improve reliability when assessments cannot be cross-validated @kitchenham1997desmet. This scale length falls within the range of response formats reviewed by Taherdoost @taherdoost2019likert, who notes that shorter scales reduce cognitive burden at the cost of measurement granularity---a trade-off appropriate for the present single-evaluator context. The overall study design follows the PICOC framework for structuring empirical software engineering research @kitchenham2007systematic: the _Population_ is the nine agentic platforms, the _Intervention_ is the DESMET-based three-layer evaluation, the _Comparison_ is across platforms against consistent criteria, the _Outcomes_ are the four cross-cutting dimensions (Pipeline Completeness, Efficiency, Orchestration, Autonomy) alongside Layer 1 and Layer 2 profiles, and the _Context_ is the four-stage software engineering pipeline.

This methodology carries inherent limitations that should be acknowledged upfront. The evaluation is conducted by a single evaluator, introducing potential subjective bias in qualitative scoring; this is mitigated through structured rubrics with explicit criteria at each score level. LLM outputs are non-deterministic, meaning repeated runs may yield different results; the study addresses this by recording all prompts, configurations, and outputs for reproducibility. The evaluation represents a point-in-time snapshot---platforms evolve rapidly, and findings may not generalise to future versions. These limitations are discussed further in the Limitations and Threats to Validity chapter.

== Platform Selection and Categorisation

This section presents the platforms selected for evaluation and the criteria guiding their selection.

=== Selected Platforms

Nine platforms are included in this evaluation, spanning three architectural categories:

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

Microsoft AutoGen @wu2023autogen and Semantic Kernel were originally considered as separate platforms. However, Microsoft unified these under the Microsoft Agent Framework in 2025 @microsoft2025agent_framework, consolidating AutoGen's multi-agent conversation capabilities with Semantic Kernel's orchestration SDK into a single framework with shared abstractions and migration paths. This evaluation therefore assesses the unified framework rather than its legacy components, reflecting the platform landscape as it stands at the time of writing.

=== Selection Criteria

Platforms were selected based on the following criteria:

- *Maturity*: Preference for platforms with stable releases, active maintenance, and established documentation.
- *Industry adoption*: Consideration of community size, GitHub activity, and real-world usage evidence.
- *Category coverage*: Ensuring representation across multi-agent frameworks, SDK runtimes, and workflow builders.
- *SDK availability*: Platforms must provide programmatic access for consistent benchmark execution.
- *Accessibility*: Preference for open-source tools or those with accessible free tiers for evaluation purposes.
- *Relevance to software engineering*: Platforms must support tasks representative of software development workflows.

=== Category Rationale

The three-category taxonomy reflects distinct architectural approaches to agentic systems:

- *Multi-Agent Frameworks* provide programmatic control over agent coordination, enabling complex multi-agent workflows with explicit orchestration logic.
- *Agent SDK Runtimes* offer vendor-supported development kits optimised for their respective LLM providers, emphasising integration and developer experience.
- *Visual / Workflow Platforms* prioritise accessibility through no-code or low-code interfaces, enabling rapid prototyping and non-developer usage.

Agent-to-Agent (A2A) interoperability is assessed as a cross-cutting feature in the Layer 2 feature matrix rather than as a standalone platform category, alongside Model Context Protocol (MCP) support.

== Evaluation Pipeline and Benchmark Design

Rather than evaluating platforms on isolated tasks, each platform is given a user story and must execute a sequence of pipeline stages---mirroring how practitioners actually use agentic platforms.

@fig-pipeline-activity shows the complete pipeline as a UML activity diagram, including the per-platform parallel execution region, output artefacts per stage, and the four cross-cutting evaluation dimensions measured throughout.

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
    [User story (YAML)],
    [Structured requirements, acceptance criteria, UML diagrams (PlantUML)],
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

For each stage, two tiers are recorded:

- *Capability Tier*: Whether the platform can perform the stage at all (Supported / Partial / Not Supported).
- *Performance Tier*: For stages the platform completes, quantitative and qualitative metrics are recorded.

#figure(
  table(
    columns: 2,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Rating*], [*Criteria*],
    ),
    [Supported], [Stage completes autonomously or with minimal prompting; structured output is produced without manual rewriting.],
    [Partial], [Stage executes but requires significant human intervention (more than two corrections) or produces incomplete structured output.],
    [Not Supported], [Platform cannot attempt this stage, or stage crashes and produces no output despite attempts.],
  ),
  caption: [Capability Tier Definitions],
)

=== Common Per-Stage Metrics

Every pipeline stage records the following resource consumption metrics alongside its stage-specific framework metrics:

- *Token Usage*: Input, output, and total tokens consumed
- *API Cost*: Estimated cost in USD based on provider pricing
- *Wall-clock Time*: Seconds from stage invocation to completion
- *Human Interventions*: Count of manual corrections required during execution

=== User Stories

Four user stories of increasing complexity are run through the pipeline, providing a range of difficulty levels to differentiate platform capabilities:

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Story*], [*Complexity*], [*Purpose*],
    ),
    [US001 (utility function)], [Basic], [Tests pipeline end-to-end with minimal complexity],
    [US010 (API endpoint)], [Intermediate], [Tests API integration and multi-file generation],
    [US030 (fullstack app)], [Intermediate], [Tests frontend and backend coordination],
    [US020 (auth system)], [Advanced], [Tests complex requirements, security concerns, multi-component coordination],
  ),
  caption: [User Stories for Pipeline Evaluation],
)

The framework is designed for 9 platforms × 4 stories × 4 stages = 144 stage-level evaluations. Layer 3 pipeline benchmarking is conducted for the eight platforms with implemented adapters (LangGraph, CrewAI, OpenAI Agents SDK, Google ADK, Microsoft Agent Framework, Flowise, LangFlow, N8n), yielding 8 × 4 × 4 = 128 stage-level evaluations; Dify is assessed at Layers 1--2 only as a partial integration, because its marketplace-only plugin ecosystem (new in Dify~1.13) blocks fully automated execution (see @limitations).

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

==== System-level Features

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

==== Interaction-level Features

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

Each criterion is scored as Yes, Partial, or No based on documentation review and hands-on verification. The output is two feature matrices (one per feature category) with one row per platform and one column per criterion.

=== Layer 3: Pipeline Benchmarking

*Purpose:* Measure how well each platform orchestrates a real software engineering pipeline. Answers: _"Given a user story, how completely and autonomously can this platform execute the four-stage SE pipeline?"_

Layer 3 is the novel empirical contribution of this study. Each platform is evaluated by running the four-stage pipeline described in the Pipeline and Benchmark Design section across four user stories of increasing complexity. Since the same LLM is used across all platforms, variations in stage output quality reflect the underlying model rather than the framework; the metrics therefore focus on framework capability (pipeline completion, tool reliability, error recovery, tracing) rather than output quality. Stage-specific framework metrics are defined in the subsections below.

==== Per-Stage Framework Metrics

Every stage records the common resource-consumption metrics (tokens, time, cost, human interventions) defined above. In addition, each stage records stage-specific *framework-centric* metrics---these measure how well the _platform_ orchestrated the task, not the quality of the LLM's output (which is held constant across platforms by using the same model). Stage outputs (generated requirements, code, tests, build logs) are retained as artefacts for contextual inspection but are *not* scored, since output quality reflects the underlying LLM rather than the framework under evaluation.

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
    [Parseable UML], [Binary], [Does the PlantUML output compile?],
    [Tool Calls], [Quantitative], [Number of tool invocations used],
    [Error Recovery], [Observed], [Did the platform self-correct on tool errors?],

    table.cell(colspan: 3)[_Stage 2: Code Generation_],
    [Stage Completion], [Binary], [Did the platform produce output files?],
    [Files Written], [Quantitative], [Number of files produced via tool use],
    [Tool Reliability], [Observed], [Did write\_file / read\_file tools succeed consistently?],

    table.cell(colspan: 3)[_Stage 3: Test Generation_],
    [Stage Completion], [Binary], [Did the platform produce a test suite?],
    [Test Runner Invocation], [Binary], [Did the platform invoke pytest / jest autonomously?],
    [Coverage Tool Integration], [Binary], [Did the platform produce a coverage report?],
    [Error Recovery], [Observed], [Did the platform fix failing tests and re-run?],

    table.cell(colspan: 3)[_Stage 4: Build \& Deploy_],
    [Build Success], [Binary], [Does the code build without errors?],
    [Deploy Success], [Binary], [Does the health check pass?],
    [Error Recovery], [Observed], [Did the platform resolve dependency/build issues autonomously?],
  ),
  caption: [Per-Stage Framework Metrics (all stages also record tokens, time, cost, interventions)],
)

=== Framework Scoring Rubric

Six framework-centric dimensions are scored on a 0--3 rubric. These dimensions measure _platform capability_ for building SE pipelines, not the quality of LLM-generated output (which is held constant by using the same model across all platforms). The complete rubric with detailed criteria at each score level and evaluation guidance is provided in @appendix-scoring-rubric.

#figure(
  table(
    columns: 4,
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    table.header(
      [*Dimension*], [*0*], [*1*], [*2--3*],
    ),
    [Pipeline Completeness], [Cannot run any stage], [Runs 1--2 stages], [Runs 3 (2) / all 4 stages end-to-end (3)],
    [Tool Integration], [No tool use], [Tools defined but frequently fail], [Tools work with workarounds (2) / clean, reliable execution (3)],
    [Error Recovery], [Crashes on first error], [Errors halt pipeline], [Logs errors, continues partially (2) / self-corrects and retries (3)],
    [Time Efficiency], [Exceeded budget by 2x+], [Exceeded budget], [Met budget (2) / under budget (3)],
    [Autonomy], [Required constant intervention], [Frequent intervention], [Occasional intervention (2) / fully autonomous (3)],
    [Trace Quality], [No execution trace], [Partial trace data], [Messages + tool calls traced (2) / full trace with tokens, timing, state (3)],
  ),
  caption: [Framework Scoring Rubric (0--3 Scale)],
)

=== Cross-cutting Aggregations

Per-stage metrics are aggregated into four cross-cutting dimension scores per platform, each normalised to a 1--5 Likert scale. All dimensions measure *framework capability*---how well the platform orchestrates the SE pipeline---not LLM output quality (which is held constant across platforms). This multi-dimensional approach is validated by Yin et al. @yin2025comprehensive, whose three-perspective evaluation (effectiveness, efficiency, overhead) demonstrated that no single metric suffices for comparing agent frameworks, and by Mehta @mehta2025clear, whose CLEAR framework shows that multi-dimensional evaluation correlates significantly more strongly with production success than accuracy-only assessment. Ferrari et al. @ferrari2021systematic further support this prioritisation, finding that process integration---not usability or maturity---is the primary barrier to tool adoption in practice.

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Dimension*], [*Aggregated From*],
    ),
    [Pipeline Completeness], [Story completion rate and pipeline completeness rubric scores],
    [Efficiency], [Token usage and wall-clock time relative to budgets],
    [Orchestration], [Tool integration, error recovery, and trace quality rubric scores],
    [Autonomy], [Human interventions across all stages],
  ),
  caption: [Cross-cutting Evaluation Dimensions (Framework-Centric)],
)

Each dimension is normalised to a 1--5 Likert scale. Let $R_c$ denote the story completion ratio, $overline(P)$ the mean pipeline completeness rubric score (0--3), $overline(T_r)$ the mean time ratio (wall-clock / budget), $overline(K)$ the mean tokens per story, $K_B$ the token budget (100,000), $overline(O)$ the mean orchestration rubric score (average of tool integration, error recovery, and trace quality; 0--3 scale), and $overline(I)$ the mean human interventions per stage.

$ P_"comp" = R_c times 0.5 + overline(P) / 3 times 0.5 quad "(scaled to 1–5)" $

$ E_"eff" = (max(1, 5 - (overline(T_r) - 1) times 2) + max(1, 5 - (overline(K) / K_B - 1) times 2)) / 2 $

$ O = overline(O) times 5 / 3 $

$ A = 5 - min(4, overline(I)) quad "(fewer interventions" arrow.r "higher score)" $

These four dimensions provide the basis for radar charts and ranked cross-platform comparisons in the results analysis. Equal weighting is applied by default, with sensitivity analysis exploring alternative weightings for different practitioner scenarios (e.g., usability-weighted for rapid prototyping, reliability-weighted for production deployment).

