#import "../template.typ": *

= Background and Related Work

This chapter surveys the DESMET evaluation methodology, comparative analyses of GenAI-enabled workflow platforms, recent work on LLM-based agent architectures, and identifies the research gap this study addresses. The review follows the guidelines for systematic literature reviews in software engineering established by Kitchenham and Charters @kitchenham2007systematic.

== The DESMET Methodology

The DESMET (Determining an Evaluation Method for Software Engineering Methods and Tools) methodology was developed by Kitchenham et al. as a DTI-backed project to provide a scientifically-based and practical approach to evaluation in software engineering @kitchenham1997desmet. DESMET addresses a fundamental challenge: how to rigorously compare tools and methods when controlled experiments are difficult to conduct and context varies widely across organisations. A subsequent self-evaluation of the methodology identified practical barriers to adoption and refined guidance for method selection @kitchenham1998desmet_eval. The methodology has been successfully applied in subsequent studies, including Ferrari et al.'s systematic evaluation and usability analysis of formal methods tools for railway signaling system design @ferrari2021systematic, which demonstrated the value of combining quantitative benchmarking with qualitative usability assessments when evaluating specialised software engineering tools.

=== Evaluation Types

DESMET separates evaluation exercises into two main types:

- *Quantitative (objective) evaluations*: Aimed at establishing measurable effects of using a method or tool, typically based on observed changes in production time, rework costs, or maintenance effort. These evaluations identify expected benefits in measurable terms and collect data to determine whether benefits are actually delivered.
- *Qualitative (subjective) evaluations*: Aimed at establishing method/tool appropriateness---how well a method or tool fits the needs and culture of an organisation. This is typically assessed through _feature analysis_, examining the features provided, supplier characteristics, and training requirements.
- *Hybrid methods*: Combine both subjective and objective elements, including qualitative effects analysis (expert opinion on quantitative effects) and benchmarking (standard tests comparing tools).

=== Evaluation Methods

DESMET identifies nine evaluation methods spanning quantitative (experiments, case studies, surveys), qualitative (screening, experiments, case studies, surveys), and hybrid approaches (effects analysis, benchmarking). Of these, two are directly applicable to this study:

- *Qualitative screening*: Feature-based evaluation by an individual who determines features, rating scales, and performs assessment---typically based on literature and hands-on use rather than controlled experiments.
- *Benchmarking*: Running standard tests using alternative tools and assessing relative performance against those tests.

=== Evaluation Method Selection

DESMET provides criteria to help evaluators select an appropriate method based on their specific circumstances. Key selection factors include:

- Whether benefits are clearly quantifiable
- Availability of staff for experiments
- Stability of development procedures
- Timescales available for evaluation
- Size of the tool/method user population
- Whether benefits are observable from task output

@fig-desmet-selection illustrates how these criteria applied to this study led to the hybrid approach of Qualitative Screening combined with Benchmarking. Following the decision path: the expected benefits of agentic tools resist precise quantification, eliminating purely quantitative methods; the absence of a large accessible user population rules out survey-based approaches; the architectural heterogeneity of the nine platforms favours qualitative feature screening; and the availability of standardised software engineering tasks enables objective benchmarking. The resulting approach combines Qualitative Screening (Layers 1--2) with Hybrid Benchmarking (Layer 3).

#include "../diagrams/methodology/desmet-method-selection.typ"

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

This comparative framework informs the evaluation dimensions used in the present study, particularly the emphasis on SDK independence, extensibility, and collaboration support alongside traditional functionality metrics. However, Broccia et al.'s analysis is limited to visual workflow platforms and excludes multi-agent frameworks (LangGraph, CrewAI) and SDK runtimes (OpenAI Agents SDK, Google ADK, Microsoft Agent Framework), which represent fundamentally different architectural paradigms. Their feature analysis also omits pipeline-based benchmarking---platforms are compared on what they _offer_, not how they _perform_ on real tasks. The present study extends their framework to all three categories and adds empirical benchmarking as a third evaluation layer.

== LLM-Based Agent Architectures and Benchmarking

Recent work has surveyed the rapidly expanding landscape of LLM-based code generation agents and autonomous agent architectures @wang2024survey @bandi2025rise @nguyenduc2024genai_se. Dong et al. @dong2025survey provide a comprehensive taxonomy of single-agent and multi-agent architectures for software development, cataloguing evaluation benchmarks such as SWE-bench, HumanEval, and MBPP. Their survey highlights a key gap: while individual agent capabilities are increasingly well-benchmarked, comparative evaluation of the _platforms_ and _frameworks_ used to build and orchestrate these agents remains largely unaddressed.

Several studies address specific aspects of agentic system design relevant to this evaluation. Yang et al. @yang2025bamas introduce BAMAS, a framework for structuring budget-aware multi-agent systems that uses integer linear programming for LLM provisioning and offline reinforcement learning for topology selection. Benchmarking against AutoGen, MetaGPT, and ChatDev, BAMAS achieves comparable accuracy at up to 86% lower cost—for example, matching AutoGen's 95.4% on GSM8K while reducing expenditure by 62%. Their four collaboration topologies (Linear, Star, Feedback, and Planner-Driven) provide a useful vocabulary for characterising the architectural approaches of the platforms evaluated in this study, and their finding that no current framework incorporates budget-awareness underscores a gap in production-readiness that ecosystem-level evaluation can help surface.

Derouiche et al. @derouiche2025agentic provide the most directly comparable architectural analysis, comparing six frameworks that overlap with this study's platform set—CrewAI, LangGraph, AutoGen, Semantic Kernel, Google ADK, and MetaGPT—across communication patterns, memory management, orchestration, modularity, and guardrails. Their analysis confirms that frameworks differ significantly in orchestration architecture (graph-based vs. role-based vs. conversation-driven), but does not extend to visual/workflow platforms or empirical pipeline benchmarking. Adimulam et al. @adimulam2026orchestration complement this with a unified orchestration framework covering emerging interoperability protocols such as MCP and A2A, arguing that "value emerges less from individual capabilities and more from orchestrated interactions within a collective"—a finding that directly supports the present study's framework-centric evaluation approach. Shu et al. @shu2024towards propose assertion-based benchmarking for multi-agent collaboration in enterprise settings, avoiding dependency on ground-truth output trajectories and finding that multi-agent collaboration improves goal success rates by up to 70% over single-agent baselines.

These studies share a common limitation: each evaluates a single system or architectural approach in isolation, without systematic cross-platform comparison using consistent evaluation criteria. The present study addresses this by applying a unified DESMET-based framework across nine platforms spanning all three architectural categories.

== Research Gap

Neither the DESMET-based evaluation literature @kitchenham1997desmet @ferrari2021systematic, the GenAI workflow comparison work @broccia2025humainflow, nor the LLM agent surveys @dong2025survey @jin2024llmagents_se address the systematic comparison of platforms that integrate autonomous agents into the full software development lifecycle. Existing evaluations either target a single platform category @broccia2025humainflow, benchmark narrow capabilities in isolation @dong2025survey, or compare frameworks only along a single axis such as cost @yang2025bamas. The two most directly related studies are Yin et al. @yin2025comprehensive, who demonstrate through three-perspective evaluation (effectiveness, efficiency, overhead) that no single framework dominates across all dimensions—reinforcing the need for multi-dimensional assessment—and Derouiche et al. @derouiche2025agentic, who compare six of the nine platforms evaluated in this study across architectural dimensions but without empirical benchmarking or visual/workflow platform coverage. Wang et al. @wang2024survey note that existing benchmarks focus on task completion but lack standardised metrics for orchestration quality and multi-stage pipeline coherence. No systematic evaluation currently spans the heterogeneous landscape of multi-agent frameworks, agent SDK runtimes, and visual workflow builders using evaluation criteria that encompass both technical performance and platform maturity.

This project addresses this gap by applying a DESMET-based three-layer framework to nine agentic platforms—covering a different and broader set of frameworks than prior work—combining pipeline benchmarking with qualitative feature assessment across consistent evaluation criteria. Where Yin et al. evaluate what frameworks _can do_, this study additionally evaluates what practitioners _need to know_ to adopt them: release maturity, documentation quality, community support, extensibility, and licensing. The following chapter presents the design of the evaluation framework.
