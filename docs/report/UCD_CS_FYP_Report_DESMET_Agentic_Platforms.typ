// =============================================================================
// UCD CS FYP Report — Typst Conversion
// Systematic Evaluation of Agentic Platforms
// =============================================================================

// ---------------------------------------------------------------------------
// Document metadata & page setup (mirrors UCD_CS_FYP_Report.cls)
// ---------------------------------------------------------------------------

#set document(
  title: "Systematic Evaluation of Agentic Platforms",
  author: "Ciaran McDonnell",
)

#set page(
  paper: "a4",
  margin: (left: 3cm, right: 2.5cm, top: 2.5cm, bottom: 2cm),
  header: [],
  footer: context [
    #set align(center)
    #set text(size: 9pt)
    Page #counter(page).display() of #counter(page).final().first()
  ],
)

#set text(font: "Arial", size: 11pt)
#set par(leading: 0.6em * 1.2, spacing: 1em, first-line-indent: 0cm)

#set heading(numbering: "1.1.1")
#show heading.where(level: 1): it => {
  pagebreak(weak: true)
  v(0.5cm)
  text(size: 20pt, weight: "bold")[Chapter #counter(heading).display(): #it.body]
  v(0.2cm)
  line(length: 5cm, stroke: 0.5pt)
  v(0.8cm)
}
#show heading.where(level: 2): it => {
  v(0.4cm)
  text(size: 16pt, weight: "bold")[#counter(heading).display() #it.body]
  v(0.2cm)
}
#show heading.where(level: 3): it => {
  v(0.3cm)
  text(size: 13pt, weight: "bold")[#counter(heading).display() #it.body]
  v(0.1cm)
}
#show heading.where(level: 4): it => {
  v(0.2cm)
  text(size: 11pt, weight: "bold")[#counter(heading).display() #it.body]
  v(0.1cm)
}

// Hyperlink styling
#show link: set text(fill: blue)

// ---------------------------------------------------------------------------
// Project details
// ---------------------------------------------------------------------------

#let student-name = "Ciaran McDonnell"
#let student-id = "21320201"
#let project-title = "Systematic Evaluation of Agentic Platforms"
#let supervisor-name = "Alessio Ferrari"

// ---------------------------------------------------------------------------
// Title page
// ---------------------------------------------------------------------------

#page(header: [], footer: [])[
  #set align(center)
  #v(1fr)

  #text(size: 24pt)[Final Year Project]
  #v(0.5cm)
  #line(length: 4cm, stroke: 1pt)
  #v(0.7cm)
  #text(size: 24pt, weight: "bold")[#project-title]
  #v(1cm)

  #text(size: 18pt)[#student-name]
  #v(0.5cm)
  #line(length: 4cm, stroke: 1pt)
  #v(0.5cm)
  #text(size: 16pt)[Student ID: #student-id]
  #v(0.5cm)
  #line(length: 4cm, stroke: 1pt)
  #v(0.5cm)

  #text(size: 16pt)[
    A thesis submitted in part fulfilment of the degree of \
    #text(weight: "bold")[BSc. (Hons.) in Computer Science]
  ]
  #v(0.5cm)
  #text(size: 16pt)[#text(weight: "bold")[Supervisor:] #supervisor-name]
  #v(1.8cm)

  #image("UCD_Logo.pdf", height: 6cm)
  #v(1cm)

  #text(size: 16pt)[
    UCD School of Computer Science \
    University College Dublin
  ]
  #v(1fr)
  #text(size: 12pt)[#datetime.today().display("[month repr:long] [day], [year]")]
  #v(1fr)
]

// ---------------------------------------------------------------------------
// Table of Contents
// ---------------------------------------------------------------------------

#outline(title: "Table of Contents", depth: 3, indent: auto)

// ---------------------------------------------------------------------------
// Abstract
// ---------------------------------------------------------------------------

#heading(level: 1, numbering: none)[Abstract]

Agentic platforms are emerging as transformative tools in software engineering, integrating autonomous or semi-autonomous agents into the development lifecycle to enhance productivity and code quality. However, existing literature provides limited comparative evaluation across heterogeneous agentic frameworks, multi-agent systems, and workflow-based LLM platforms, leaving practitioners without clear guidance for tool selection. This study applies a systematic DESMET-based evaluation framework to compare agentic platforms across dimensions such as functionality, usability, collaboration support, scalability, and reliability. The evaluation covers ten platforms representing three architectural categories: multi-agent frameworks (LangGraph, CrewAI, Microsoft Autogen), agent SDK runtimes (OpenAI Agents SDK, Google ADK, Semantic Kernel), and visual workflow platforms (Flowise, LangFlow, Dify, N8n). Each platform is assessed using representative software engineering tasks, including code generation, debugging, refactoring, tool-use workflows, and agent coordination. The results aim to provide practical guidance for practitioners, highlight capability gaps across different tool categories, and offer a structured methodology for evaluating emerging agentic technologies.

// =========================================================================
// Chapter 1 — Project Description
// =========================================================================

= Project Description

== Core Goals

+ Define sources for the initial search of agentic platforms (Google, Reddit, specialised forums, X, LinkedIn, academic papers)
+ Define selection criteria for identifying the most mature or promising platforms (approximately 10)
+ Apply search and selection criteria to identify the platforms for evaluation
+ Define analysis criteria following DESMET guidelines, informed by stakeholder consultation
+ Define representative software engineering problems to exercise and compare the tools
+ Conduct systematic evaluation of selected platforms across defined dimensions (functionality, usability, extensibility, collaboration support, scalability, reliability)
+ Produce comparative analysis and evidence-based recommendations for practitioners

== Advanced Goals

+ Develop a reusable evaluation framework that can be applied to future agentic platforms
+ Create a taxonomy of agentic platforms categorising architectural approaches
+ Extend evaluation to include emerging platforms or protocols not in the initial selection
+ Conduct user studies or expert interviews to validate evaluation criteria and findings
+ Publish findings as a contribution to the software engineering research community

== Selected Platforms

#figure(
  table(
    columns: 2,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Category*], [*Platforms*],
    ),
    [Multi-Agent Frameworks], [LangGraph, CrewAI, Microsoft Autogen],
    [Agent SDK Runtimes], [OpenAI Agents SDK, Google ADK, Semantic Kernel],
    [Visual / Workflow Platforms], [Flowise, LangFlow, Dify, N8n],
  ),
  caption: [Selected Agentic Platforms by Category],
)

*Link to Repository:*
#link("https://csgitlab.ucd.ie/cmd/agentic-platforms-systematic-evaluation")[Agentic Platforms Systematic Evaluation]

// =========================================================================
// Chapter 2 — Introduction
// =========================================================================

= Introduction

== Background & Motivation

Agentic platforms represent a new paradigm in software engineering tooling, integrating autonomous or semi-autonomous agents capable of performing complex development tasks with minimal human intervention. These platforms leverage advances in large language models and artificial intelligence to assist with code generation, debugging, refactoring, testing, and documentation. As organisations increasingly adopt these tools to enhance developer productivity and code quality, understanding their capabilities and limitations becomes critical.

== Problem Statement

Despite the growing adoption of agentic platforms, there is a lack of systematic comparisons to guide practitioners in selecting appropriate tools for their specific needs. The relative capabilities of different platforms remain unclear, and practitioners lack evidence-based guidance for making informed adoption decisions. This gap presents challenges for organisations seeking to integrate agentic tools into their development workflows.

== Aims & Objectives

This project aims to:

+ Construct a systematic evaluation framework for comparing agentic platforms
+ Evaluate multiple platforms across dimensions of functionality, usability, extensibility, collaboration support, scalability, and reliability
+ Identify the comparative strengths and weaknesses of each platform
+ Provide actionable guidance for practitioners selecting agentic tools

== Scope

*In Scope:*
- Comparative evaluation of ten selected agentic platforms representing multi-agent systems, SDK runtimes, and workflow builders
- Assessment across defined dimensions using DESMET methodology
- Testing against representative software engineering tasks: code generation, debugging, refactoring, tool-use workflows, and multi-agent coordination
- Stakeholder consultation to inform evaluation criteria

*Out of Scope:*
- Exhaustive evaluation of all available agentic platforms
- Long-term longitudinal studies of platform evolution
- Economic cost-benefit analysis of platform adoption
- Proprietary internal tools with restricted access (e.g., Devin internal architecture)

*Constraints:*
- Timeline limited to the academic year
- Platform availability and access restrictions
- Rapidly evolving landscape of agentic tools may cause changes post-evaluation

== Methodological Overview

The DESMET (Determining an Evaluation Method for Software Engineering Methods and Tools) methodology provides the foundation for this evaluation. DESMET offers a structured approach to systematically assess software engineering tools, ensuring rigorous and reproducible evaluation. The methodology guides the selection of evaluation criteria, the design of assessment procedures, and the analysis of results. This approach is well-suited to comparing agentic platforms as it accommodates both quantitative metrics and qualitative assessments of usability and collaboration support.

// =========================================================================
// Chapter 3 — Related Work and Ideas
// =========================================================================

= Related Work and Ideas

This chapter surveys prior research relevant to the systematic evaluation of agentic platforms. The review is organised into three thematic areas. First, it presents established methodologies for evaluating software engineering tools, focusing on the DESMET framework and subsequent systematic evaluation practices that form the methodological foundation of this study. Second, it examines comparative analyses of GenAI-enabled workflow platforms, highlighting system-level and interaction-level evaluation dimensions identified in recent literature. Third, it reviews emerging research on agentic orchestration, multi-agent system architectures, and interoperability protocols, encompassing workflow generation, model and tool routing, cross-agent communication standards, and multi-agent coordination approaches that inform the design of the evaluation framework used in this project.

== The DESMET Methodology

The DESMET (Determining an Evaluation Method for Software Engineering Methods and Tools) methodology was developed by Kitchenham et al. as a DTI-backed project to provide a scientifically-based and practical approach to evaluation in software engineering @kitchenham1997desmet. DESMET addresses a fundamental challenge: how to rigorously compare tools and methods when controlled experiments are difficult to conduct and context varies widely across organisations. The methodology has been successfully applied in subsequent studies, including Ferrari et al.'s systematic evaluation and usability analysis of formal methods tools for railway signaling system design @ferrari2021systematic, which demonstrated the value of combining quantitative benchmarking with qualitative usability assessments when evaluating specialised software engineering tools.

=== Evaluation Types

DESMET separates evaluation exercises into two main types:

- *Quantitative (objective) evaluations*: Aimed at establishing measurable effects of using a method or tool, typically based on observed changes in production time, rework costs, or maintenance effort. These evaluations identify expected benefits in measurable terms and collect data to determine whether benefits are actually delivered.
- *Qualitative (subjective) evaluations*: Aimed at establishing method/tool appropriateness---how well a method or tool fits the needs and culture of an organisation. This is typically assessed through _feature analysis_, examining the features provided, supplier characteristics, and training requirements.
- *Hybrid methods*: Combine both subjective and objective elements, including qualitative effects analysis (expert opinion on quantitative effects) and benchmarking (standard tests comparing tools).

=== Nine Evaluation Methods

DESMET identifies nine distinct evaluation methods organised by type and approach:

*Quantitative methods:*

+ _Quantitative experiment_: Investigation of quantitative impact organised as a formal experiment with subjects assigned to methods/tools using statistical techniques.
+ _Quantitative case study_: Investigation of quantitative impact on a real project using standard development procedures.
+ _Quantitative survey_: Investigation of quantitative impact through data collection from staff/organisations with past project experience.

*Qualitative methods:*

#set enum(start: 4)
4. _Qualitative screening_: Feature-based evaluation by a single individual who determines features, rating scales, and performs assessment---typically based on literature rather than actual use.
5. _Qualitative experiment_: Feature-based evaluation by potential users who try out methods/tools on typical tasks before evaluation.
6. _Qualitative case study_: Feature-based evaluation by staff who have used the method/tool on a real project.
7. _Qualitative survey_: Feature-based evaluation by people with experience using or studying the method/tool, where participation is at the subject's discretion.

*Hybrid methods:*

#set enum(start: 8)
8. _Qualitative effects analysis_: Subjective assessment of quantitative effects based on expert opinion.
9. _Benchmarking_: Running standard tests using alternative tools and assessing relative performance against those tests.
#set enum(start: 1)

=== Evaluation Method Selection

DESMET provides criteria to help evaluators select an appropriate method based on their specific circumstances. Key selection factors include:

- Whether benefits are clearly quantifiable
- Availability of staff for experiments
- Stability of development procedures
- Timescales available for evaluation
- Size of the tool/method user population
- Whether benefits are observable from task output

=== Challenges in Software Engineering Evaluation

The DESMET project identified several persistent challenges in evaluation exercises:

- *Defining appropriate controls*: The 'control' situation is often undefined or context-dependent, making results difficult to generalise.
- *Scaling problems*: Formal experiments typically use small applications, while case studies on real projects are too costly to replicate adequately.
- *Evaluation costs*: No mandatory requirements exist for method/tool developers to validate their products.
- *Immature measures*: Few universally agreed measures of software quality and productivity exist, making replication difficult.
- *Confounding factors*: Variability in staff capability, learning-curve effects, and expectation effects complicate evaluation.

The most significant insight from DESMET is that no single evaluation method is always best---different methods are appropriate in different circumstances, necessitating a taxonomy of approaches and guidance for selection.

== Comparative Analysis of Agentic Workflow Platforms

Broccia et al. @broccia2025humainflow provide a systematic comparison of GenAI-enabled workflow platforms, analysing tools across system-level and interaction-level features. Their study examines eight platforms: Langflow, Flowise AI, n8n, Dive, Dify, Haystack UI, AgenticFlow, and AutoGen Studio---several of which overlap with the platforms selected for this evaluation.

*System-level features* examined include:
- MCP (Model Context Protocol) support for interoperability
- Local versus remote LLM execution capabilities
- SDK dependence and its implications for extensibility
- Licensing models (MIT, Apache 2.0, Fair-code, proprietary)
- Execution monitoring and observability

*Interaction-level features* examined include:
- No-code versus low-code interface accessibility
- Team collaboration support (shared workflows, version control)
- Human-in-the-loop modelling as first-class workflow elements
- Human role simulation via LLMs for prototyping

The analysis reveals several gaps in the current landscape. While many platforms offer no-code interfaces and remote LLM integration, few combine interoperability, extensibility, and explicit human-in-the-loop modelling. Most tools remain tightly coupled to specific SDKs such as LangChain, limiting long-term adaptability. Execution monitoring remains limited across most platforms, with only basic logging available rather than full observability. Critically, human-in-the-loop functionality is restricted in most tools---while some allow pausing for manual input, these capabilities are not modelled as first-class workflow elements.

This comparative framework informs the evaluation dimensions used in the present study, particularly the emphasis on SDK independence, extensibility, and collaboration support alongside traditional functionality metrics.

// TODO: Add additional comparative studies as they are found

== Summary and Research Gap

The literature reviewed establishes two complementary foundations for this study. First, the DESMET methodology provides a rigorous, taxonomy-based approach to evaluating software engineering tools, offering nine distinct evaluation methods spanning quantitative, qualitative, and hybrid approaches @kitchenham1997desmet. Ferrari et al. @ferrari2021systematic demonstrated the practical application of systematic evaluation combining benchmarking with usability analysis for specialised tools, validating that such hybrid approaches yield actionable insights for practitioners. Second, recent comparative analyses of GenAI-enabled workflow platforms @broccia2025humainflow have identified critical evaluation dimensions---including SDK independence, interoperability, extensibility, and human-in-the-loop support---that extend beyond traditional functionality metrics.

However, gaps remain in the current body of research. While Ferrari et al. and Broccia et al. provide valuable systematic evaluation frameworks, neither addresses tools that integrate autonomous or semi-autonomous agents into the software development lifecycle. No systematic evaluation currently spans the heterogeneous landscape of agentic platforms, which encompasses architecturally distinct categories including multi-agent frameworks, agent SDK runtimes, and visual workflow builders. Practitioners seeking to adopt agentic tools lack evidence-based guidance for comparing platforms across these categories, as existing evaluations do not address the cross-category trade-offs between programmatic control, ease of use, and collaboration support.

This project addresses these gaps by applying a DESMET-based evaluation framework to ten agentic platforms spanning three architectural categories. The evaluation combines benchmarking against representative software engineering tasks with qualitative assessment of usability, extensibility, and collaboration features. By systematically comparing multi-agent frameworks, SDK runtimes, and visual platforms using consistent evaluation criteria, this study aims to provide practitioners with actionable guidance for tool selection and to contribute a reusable methodology for evaluating emerging agentic technologies.

// =========================================================================
// Chapter 4 — Data Considerations
// =========================================================================

= Data Considerations

// =========================================================================
// Chapter 5 — Project Approach and Design
// =========================================================================

= Project Approach and Design

This chapter presents the methodology, platform selection, benchmark design, evaluation dimensions, and implementation plan for the systematic evaluation of agentic platforms.

== Evaluation Methodology Selection (DESMET Application)

This study adopts a hybrid evaluation approach combining benchmarking with qualitative screening, following DESMET guidelines for selecting appropriate evaluation methods based on context and constraints.

=== Chosen Evaluation Type

The evaluation employs two complementary DESMET methods:

- *Benchmarking*: Running standardised software engineering tasks across all platforms and measuring performance against consistent criteria. This provides objective, comparable data on platform capabilities.
- *Qualitative Screening*: Feature-based evaluation examining platform characteristics, documentation quality, extensibility, and developer experience. This captures aspects that quantitative benchmarks cannot fully address.

=== Justification for Hybrid Approach

A purely quantitative evaluation is unsuitable for comparing agentic platforms for several reasons:

- *Architectural heterogeneity*: Multi-agent frameworks, SDK runtimes, and visual workflow builders differ fundamentally in their design paradigms, making direct quantitative comparison across categories challenging.
- *Task variability*: Software engineering tasks vary in complexity and structure; some platforms excel at specific task types while underperforming on others.
- *Qualitative factors*: Developer experience, onboarding complexity, and extensibility significantly influence platform adoption but resist purely quantitative measurement.
- *Rapidly evolving landscape*: Agentic platforms are under active development; qualitative assessment captures maturity and stability factors that benchmarks alone may miss.

=== DESMET Guidance in This Study

DESMET principles guide four aspects of this evaluation:

+ *Feature identification*: Evaluation dimensions are derived from DESMET's emphasis on both objective capabilities and subjective appropriateness, ensuring comprehensive coverage of functionality, usability, scalability, and reliability.
+ *Test design*: Benchmark tasks are designed as standardised tests that can be consistently applied across platforms, following DESMET's benchmarking method requirements.
+ *Platform inclusion*: Selection criteria ensure sufficient diversity for meaningful comparison while maintaining practical scope, addressing DESMET's guidance on evaluation feasibility.
+ *Hybrid evaluation framing*: The combination of quantitative benchmarks with qualitative screening aligns with DESMET's recognition that different evaluation methods suit different circumstances and can be combined for comprehensive assessment.

== Platform Selection and Categorisation

This section presents the platforms selected for evaluation and the criteria guiding their selection.

=== Selected Platforms

Eleven platforms are included in this evaluation, spanning four architectural categories:

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Category*], [*Platform*], [*Description*],
    ),
    table.cell(rowspan: 3)[Multi-Agent Frameworks],
    [LangGraph], [Graph-based agent orchestration built on LangChain],
    [CrewAI], [Role-based multi-agent collaboration framework],
    [Microsoft Autogen], [Conversational multi-agent framework],

    table.cell(rowspan: 3)[Agent SDK Runtimes],
    [OpenAI Agents SDK], [OpenAI's native agent development kit],
    [Google ADK], [Google's Agent Development Kit],
    [Semantic Kernel], [Microsoft's AI orchestration SDK],

    table.cell(rowspan: 4)[Visual / Workflow Platforms],
    [Flowise], [Drag-and-drop LLM flow builder],
    [LangFlow], [Visual IDE for LangChain applications],
    [Dify], [LLM application development platform],
    [N8n], [Workflow automation with AI capabilities],

    [Interoperability Protocol], [A2A (Agent-to-Agent)], [Google's agent interoperability protocol],
  ),
  caption: [Selected Agentic Platforms by Category],
)

=== Selection Criteria

Platforms were selected based on the following criteria:

- *Maturity*: Preference for platforms with stable releases, active maintenance, and established documentation.
- *Industry adoption*: Consideration of community size, GitHub activity, and real-world usage evidence.
- *Category coverage*: Ensuring representation across multi-agent frameworks, SDK runtimes, workflow builders, and interoperability protocols.
- *SDK availability*: Platforms must provide programmatic access for consistent benchmark execution.
- *Accessibility*: Preference for open-source tools or those with accessible free tiers for evaluation purposes.
- *Relevance to software engineering*: Platforms must support tasks representative of software development workflows.

=== Category Rationale

The four-category taxonomy reflects distinct architectural approaches to agentic systems:

- *Multi-Agent Frameworks* provide programmatic control over agent coordination, enabling complex multi-agent workflows with explicit orchestration logic.
- *Agent SDK Runtimes* offer vendor-supported development kits optimised for their respective LLM providers, emphasising integration and developer experience.
- *Visual / Workflow Platforms* prioritise accessibility through no-code or low-code interfaces, enabling rapid prototyping and non-developer usage.
- *Interoperability Protocols* address cross-platform agent communication, enabling agents built on different frameworks to collaborate.

== Evaluation Pipeline and Benchmark Design

This section specifies the software engineering pipeline used to evaluate platform capabilities and the user stories that exercise it. Rather than evaluating platforms on isolated tasks (code generation, debugging, refactoring), this study adopts a pipeline-based approach: each platform is given a user story and must produce working software through a sequence of stages. This design mirrors how practitioners actually use agentic platforms and provides a more holistic assessment of end-to-end capability.

=== Pipeline Stages

Each platform attempts a four-stage software engineering pipeline. Design (UML diagram generation) is folded into the first stage, following the approach in Broccia et al. @broccia2025humainflow where requirements extraction and structural modelling form a single artefact-generation step.

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
    [Completeness, quality, traceability, parseable UML],

    [2. Code Generation],
    [Requirements + UML design],
    [Source code],
    [Functional correctness, completeness, code quality, design adherence],

    [3. Test Generation],
    [Requirements + source code],
    [Test suite],
    [Test pass rate, coverage, test quality],

    [4. Build \& Deploy],
    [Source code + tests],
    [Passing build, deployable artifact],
    [Build success, deploy success, configuration effort],
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
    [Supported], [Stage completes autonomously or with minimal prompting. Output is usable without manual rewriting.],
    [Partial], [Stage produces output but requires significant human intervention (more than two corrections) or output is only partially usable.],
    [Not Supported], [Platform cannot attempt this stage, or output is unusable or empty despite attempts.],
  ),
  caption: [Capability Tier Definitions],
)

=== Common Per-Stage Metrics

Every pipeline stage records the following resource consumption metrics alongside its stage-specific quality metrics:

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

This yields a total of 10 platforms × 4 stories × 4 stages = 160 stage-level evaluations.

== Three-Layer Evaluation Framework

This section defines the evaluation framework used to assess platforms. The framework comprises three complementary layers, each answering a distinct practitioner question. Together, they cover platform viability, capability, and performance---providing a complete evaluation from initial consideration through empirical benchmarking.

=== Layer 1: Industry Readiness

*Purpose:* Establish baseline platform viability. Answers: _"Is this platform mature enough to evaluate seriously?"_

Agentic platforms are a rapidly evolving space where some tools are production-grade while others remain experimental. This layer establishes a factual maturity profile for each platform before investing effort in deeper evaluation.

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

This layer directly extends the system-level and interaction-level comparison framework from Broccia et al. @broccia2025humainflow, expanding it from eight visual workflow tools to ten platforms spanning three architectural categories. Additional criteria (A2A protocol support, sandboxing, workflow patterns, memory management, multi-agent coordination) reflect the broader scope of this evaluation.

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

*Purpose:* Measure how well each platform performs on real software engineering tasks. Answers: _"Given a user story, how effectively can this platform produce working software?"_

Layer 3 is the novel empirical contribution of this study. Each platform is evaluated by running the four-stage pipeline described in Section 5.3 across four user stories of increasing complexity. Stage-specific quality metrics are defined in the subsections below.

==== Requirements \& Design Metrics

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Metric*], [*Type*], [*Measurement*],
    ),
    [Requirement Completeness], [Quantitative], [Percentage of expected requirements captured (ground truth: acceptance criteria from user story)],
    [Requirement Quality], [Qualitative], [Free of smells: ambiguity, vagueness, incompleteness (rubric 0--3)],
    [Traceability], [Qualitative], [Requirements traceable back to user story (rubric 0--3)],
    [Design Completeness], [Qualitative], [All key entities and relationships captured in UML (rubric 0--3)],
    [Design Correctness], [Qualitative], [Diagrams consistent with requirements (rubric 0--3)],
    [Parseable UML], [Quantitative], [Does the PlantUML output compile? (binary)],
  ),
  caption: [Stage 1 Metrics: Requirements \& Design],
)

==== Code Generation Metrics

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Metric*], [*Type*], [*Measurement*],
    ),
    [Functional Correctness], [Quantitative], [Does the code run and produce expected output?],
    [Completeness], [Quantitative], [Percentage of requirements with corresponding implementation],
    [Code Quality], [Qualitative], [Structure, naming, style, maintainability (rubric 0--3)],
    [Adherence to Design], [Qualitative], [Code reflects the UML structure (rubric 0--3)],
  ),
  caption: [Stage 2 Metrics: Code Generation],
)

==== Test Generation Metrics

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Metric*], [*Type*], [*Measurement*],
    ),
    [Test Pass Rate], [Quantitative], [Percentage of generated tests that pass against generated code],
    [Test Coverage], [Quantitative], [Statement and branch coverage of generated tests],
    [Test Quality], [Qualitative], [Meaningful assertions and edge cases (rubric 0--3)],
  ),
  caption: [Stage 3 Metrics: Test Generation],
)

==== Build \& Deploy Metrics

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Metric*], [*Type*], [*Measurement*],
    ),
    [Build Success], [Quantitative], [Does the code build without errors? (binary)],
    [Deploy Success], [Quantitative], [Does the health check pass? (binary)],
    [Configuration Effort], [Qualitative], [How much manual setup was needed (rubric 0--3)],
  ),
  caption: [Stage 4 Metrics: Build \& Deploy],
)

=== Qualitative Scoring Rubric

All qualitative metrics use a consistent four-point rubric:

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Score*], [*Label*], [*Definition*],
    ),
    [0], [Absent], [No meaningful output, or output is completely wrong or unusable],
    [1], [Poor], [Output exists but has major deficiencies; requires substantial rework],
    [2], [Adequate], [Output is functional with minor issues; usable with light corrections],
    [3], [Good], [Output is correct, complete, and well-structured; no corrections needed],
  ),
  caption: [Qualitative Scoring Rubric (0--3 Scale)],
)

=== Cross-cutting Aggregations

Per-stage metrics are aggregated into four cross-cutting scores per platform, each normalised to a 1--5 Likert scale:

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Dimension*], [*Aggregated From*], [*Formula*],
    ),
    [Effectiveness],
    [Capability tier across all stages, correctness, and completeness scores],
    [$(S_"supported" / S_"total") times 0.4 + overline(C_"correctness") times 0.3 + overline(C_"completeness") times 0.3$, scaled to 1--5],

    [Efficiency],
    [Total token usage, wall-clock time, and API cost],
    [Rank-normalised across platforms: lowest resource consumption = 5, highest = 1],

    [Quality],
    [All qualitative rubric scores across stages],
    [$overline(R_"all") times 5 / 3$, where $R$ is the average of all 0--3 rubric scores],

    [Autonomy],
    [Human interventions across all stages],
    [$5 - min(4, overline(I_"per-stage"))$; fewer interventions yields a higher score],
  ),
  caption: [Cross-cutting Evaluation Dimensions],
)

These four dimensions provide the basis for radar charts and ranked cross-platform comparisons in the results analysis. Equal weighting is applied by default, with sensitivity analysis exploring alternative weightings for different practitioner scenarios (e.g., usability-weighted for rapid prototyping, reliability-weighted for production deployment).

=== Data Collection Methods

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

== Implementation Plan and Tooling Setup

This section describes the technical environment, repository structure, and execution methodology for conducting the evaluation.

=== Runtime Environment

The evaluation environment comprises:

- *Python*: Version 3.13 for SDK-based platforms (LangGraph, CrewAI, Autogen, OpenAI Agents SDK, Google ADK, Semantic Kernel)
- *Node.js*: Latest LTS version for JavaScript-based workflow platforms (N8n, Flowise, LangFlow)
- *Docker*: Containerised deployments for platforms requiring isolated environments
- *LLM Access*: API keys for OpenAI, Anthropic, and Google models as required by platforms

=== Development Environment

- *Hardware*: Local development machine with sufficient resources for concurrent platform execution
- *Operating System*: Cross-platform compatibility (macOS, Windows, Linux)
- *Version Control*: Git repository with structured organisation for reproducibility
- *Package Management*: UV for Python dependencies, PNPM for Node.js dependencies

=== Repository Structure

```
DESMET_Agentic_Platforms/
├── analysis/           # Evaluation analysis scripts
├── config/             # Platform configurations
├── data/               # Input data for benchmarks
├── docker/             # Docker configurations
├── documentation/      # Project report and documentation
├── platforms/          # Platform-specific implementations
│   ├── langgraph/
│   ├── crewai/
│   ├── autogen/
│   ├── openai-agents/
│   ├── google-adk/
│   ├── semantic-kernel/
│   ├── flowise/
│   ├── langflow/
│   ├── dify/
│   ├── n8n/
│   └── a2a/
├── results/            # Benchmark results and metrics
└── Resources/          # Additional resources
```

=== Execution Methodology

Each platform undergoes the following evaluation process:

+ *Layer 1 Assessment*: Platform maturity profile compiled from GitHub data, documentation review, and industry adoption evidence.
+ *Layer 2 Assessment*: Feature matrices populated through documentation review and hands-on verification of each criterion.
+ *Layer 3 Benchmarking*: Four user stories executed through the four-stage pipeline using the `desmet-eval` CLI harness. Quantitative metrics (token usage, timing, costs) captured automatically; qualitative rubric scores assigned post-execution.
+ *Result recording*: All results logged to structured JSON output in `results/{platform}/{story_id}/` for analysis.

=== Automation and Reproducibility

To ensure reproducibility and reduce evaluator bias:

- Standardised prompt templates are used across all platforms where applicable
- The evaluation harness automates pipeline execution, metric collection, and result storage
- Token usage and API costs are recorded programmatically at each pipeline stage
- All configurations, prompts, and results are version-controlled
- Qualitative rubric scores are assigned against the defined 0--3 scale to minimise subjectivity

// =========================================================================
// Chapter 6 — Implementation
// =========================================================================

= Implementation

// =========================================================================
// Chapter 7 — Evaluation
// =========================================================================

= Evaluation

== Goals Completed

// =========================================================================
// Chapter 8 — Conclusions
// =========================================================================

= Conclusions

// =========================================================================
// Acknowledgements
// =========================================================================

#heading(level: 1, numbering: none)[Acknowledgements]

// =========================================================================
// Bibliography
// =========================================================================

#bibliography("references.bib", style: "springer-mathphys")
