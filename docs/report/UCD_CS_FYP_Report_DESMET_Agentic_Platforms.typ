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

== Test Tasks and Benchmark Design

This section specifies the software engineering tasks used to evaluate platform capabilities. Tasks are designed to be realistic, consistently executable across platforms, and diagnostic of agent orchestration strengths and weaknesses.

=== Task Overview

Six benchmark tasks are defined, each targeting different aspects of agentic platform capability:

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Task*], [*Purpose*], [*Key Metrics*],
    ),
    [Code Generation], [Generate functional code from natural language specification], [Correctness, completeness, code quality],
    [Bug Fixing / Debugging], [Identify and fix bugs in provided code], [Accuracy, fix correctness, explanation quality],
    [Refactoring], [Improve code structure while preserving behaviour], [Behavioural preservation, improvement quality],
    [Tool-use Workflow], [Execute API calls and transform results], [Tool invocation success, data transformation accuracy],
    [Multi-agent Coordination], [Coordinate multiple agents on a collaborative task], [Coordination effectiveness, task completion],
    [Memory and Context Handling], [Maintain context across extended interactions], [Context retention, retrieval accuracy],
  ),
  caption: [Benchmark Tasks Overview],
)

=== Task Specifications

==== Code Generation Task

- *Input*: Natural language description of a function or module to implement (e.g., "Implement a function that validates email addresses using regex").
- *Expected Output*: Syntactically correct, functional code that satisfies the specification.
- *Metrics*: Syntactic correctness, test pass rate, adherence to specification, code style quality.

==== Bug Fixing / Debugging Task

- *Input*: Code containing one or more bugs, with a description of expected versus actual behaviour.
- *Expected Output*: Corrected code with explanation of the bug(s) identified and fixes applied.
- *Metrics*: Bug identification accuracy, fix correctness, explanation clarity.

==== Refactoring Task

- *Input*: Functional but poorly structured code with refactoring goals (e.g., "Extract repeated logic into helper functions").
- *Expected Output*: Refactored code that preserves original behaviour while improving structure.
- *Metrics*: Behavioural equivalence, structural improvement, maintainability gain.

==== Tool-use Workflow Task

- *Input*: A multi-step task requiring external tool invocation (e.g., "Fetch weather data from API, parse the response, and format a summary").
- *Expected Output*: Correctly executed workflow with accurate data transformation.
- *Metrics*: Tool invocation success rate, data transformation accuracy, workflow completion.

==== Multi-agent Coordination Task

- *Input*: A task requiring collaboration between multiple agents with distinct roles (e.g., researcher agent gathers information, writer agent drafts content, reviewer agent provides feedback).
- *Expected Output*: Completed collaborative output demonstrating effective agent coordination.
- *Metrics*: Role adherence, handoff effectiveness, final output quality, coordination overhead.

==== Memory and Context Handling Task

- *Input*: Extended multi-turn interaction requiring recall of earlier context (e.g., referencing variables or decisions from previous exchanges).
- *Expected Output*: Responses demonstrating accurate context retention and retrieval.
- *Metrics*: Context retention accuracy, retrieval precision, graceful degradation over extended sessions.

== Evaluation Dimensions and Metrics

This section defines the evaluation dimensions and scoring methodology used to assess platforms across both quantitative and qualitative axes.

=== Evaluation Dimensions

Four core dimensions structure the evaluation:

==== Functionality

Assessment of platform capabilities for software engineering tasks:

- Tool support and integration capabilities
- Agent orchestration features (sequential, parallel, hierarchical)
- Supported workflow patterns
- External API and service integration
- Code execution and sandboxing capabilities

==== Usability

Assessment of developer experience and accessibility:

- Onboarding complexity and time-to-first-workflow
- Documentation quality and completeness
- Required code versus configuration balance
- Debugging and error message clarity
- IDE integration and developer tooling

==== Scalability and Performance

Assessment of platform behaviour under load and resource constraints:

- Execution time for benchmark tasks
- Resource consumption (memory, compute)
- Architecture suitability for production deployment
- Model routing and load balancing capabilities
- Concurrent agent execution support

==== Reliability

Assessment of platform robustness and consistency:

- Error tolerance and recovery mechanisms
- Output reproducibility across runs
- Determinism in agent behaviour
- Observability, logging, and tracing capabilities
- Graceful degradation under adverse conditions

=== Scoring Methodology

Each evaluation criterion is scored using a five-point Likert scale:

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Score*], [*Rating*], [*Description*],
    ),
    [1], [Poor], [Feature absent or non-functional; significant limitations],
    [2], [Below Average], [Feature present but with notable deficiencies],
    [3], [Adequate], [Feature functional with minor limitations],
    [4], [Good], [Feature well-implemented with few limitations],
    [5], [Excellent], [Feature exemplary; best-in-class implementation],
  ),
  caption: [Likert Scale Scoring Rubric],
)

Quantitative metrics from benchmark tasks (execution time, success rate, accuracy) are normalised and converted to this scale for integration with qualitative assessments.

=== Aggregation and Weighting

Dimension scores are aggregated to produce overall platform assessments. Equal weighting is applied by default, with sensitivity analysis exploring alternative weightings based on practitioner priorities (e.g., usability-weighted for rapid prototyping scenarios, reliability-weighted for production deployment scenarios).

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

+ *Installation*: Platform installed following official documentation; installation complexity noted.
+ *Configuration*: Platform configured with required API keys, models, and settings; configuration complexity noted.
+ *Benchmark execution*: Standardised benchmark tasks executed using automation scripts to ensure consistency.
+ *Metric collection*: Quantitative metrics (timing, success rates) automatically captured; qualitative observations documented.
+ *Result recording*: All results logged to structured output format for analysis.

=== Automation and Reproducibility

To ensure reproducibility and reduce evaluator bias:

- Standardised prompt templates are used across all platforms where applicable
- Benchmark execution scripts automate task submission and result collection
- Random seeds are fixed where platforms support deterministic execution
- All configurations, prompts, and results are version-controlled

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
