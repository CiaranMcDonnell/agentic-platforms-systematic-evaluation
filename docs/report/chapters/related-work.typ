#import "../template.typ": *

= Background and Related Work

This chapter surveys the DESMET evaluation methodology, comparative analyses of GenAI-enabled workflow platforms, recent work on LLM-based agent architectures, evaluation-harness prior art for LLM and agent benchmarking, and identifies the research gap this study addresses. The review follows the guidelines for systematic literature reviews in software engineering established by Kitchenham and Charters @kitchenham2007systematic.

== The DESMET Methodology

The DESMET (Determining an Evaluation Method for Software Engineering Methods and Tools) methodology was developed by Kitchenham et al. as a DTI-backed project to provide a scientifically-based and practical approach to evaluation in software engineering @kitchenham1997desmet. DESMET addresses a fundamental challenge: how to rigorously compare tools and methods when controlled experiments are difficult to conduct and context varies widely across organisations. A subsequent self-evaluation of the methodology identified practical barriers to adoption and refined guidance for method selection @kitchenham1998desmet_eval. The methodology has been successfully applied in subsequent studies, including Ferrari et al.'s systematic evaluation and usability analysis of formal methods tools for railway signaling system design @ferrari2021systematic, which demonstrated the value of combining quantitative benchmarking with qualitative usability assessments when evaluating specialised software engineering tools.

DESMET separates evaluation exercises into quantitative (objective) evaluations aimed at measurable effects, qualitative (subjective) evaluations aimed at method/tool appropriateness through feature analysis, and hybrid methods combining both. Within these types, DESMET identifies nine evaluation methods spanning experiments, case studies, surveys, screening, and benchmarking. Two are directly applicable to this study: *Qualitative screening* (feature-based evaluation by an individual who determines features, rating scales, and performs assessment) and *Benchmarking* (running standard tests using alternative tools and assessing relative performance).

=== Evaluation Method Selection

DESMET provides criteria to help evaluators select an appropriate method based on specific circumstances, including whether benefits are clearly quantifiable, availability of staff for experiments, stability of development procedures, timescales available, user population size, and whether benefits are observable from task output. @fig-desmet-selection illustrates how these criteria applied to this study led to the hybrid approach of Qualitative Screening combined with Benchmarking. Following the decision path: the expected benefits of agentic tools resist precise quantification, eliminating purely quantitative methods; the absence of a large accessible user population rules out survey-based approaches; the architectural heterogeneity of the nine platforms favours qualitative feature screening; and the availability of standardised software engineering tasks enables objective benchmarking. The resulting approach combines Qualitative Screening (Layers~1--2) with Hybrid Benchmarking (Layer~3). The most significant insight from DESMET is that no single evaluation method is always best---different methods are appropriate in different circumstances, necessitating a taxonomy of approaches and guidance for selection.

#include "../diagrams/methodology/desmet-method-selection.typ"

== Comparative Analysis of Agentic Workflow Platforms

Broccia et al. @broccia2025humainflow provide a systematic comparison of GenAI-enabled workflow platforms, analysing tools across system-level features (MCP support, local versus remote LLM execution, SDK dependence, licensing, execution monitoring) and interaction-level features (no-code versus low-code accessibility, team collaboration, human-in-the-loop modelling, human role simulation). Their study examines eight platforms: Langflow, Flowise AI, n8n, Dive, Dify, Haystack UI, AgenticFlow, and AutoGen Studio---several of which overlap with the platforms selected for this evaluation.

The analysis reveals that while many platforms offer no-code interfaces and remote LLM integration, few combine interoperability, extensibility, and explicit human-in-the-loop modelling. Most tools remain tightly coupled to specific SDKs such as LangChain, limiting long-term adaptability. Execution monitoring remains limited, with only basic logging rather than full observability. Critically, human-in-the-loop functionality is restricted in most tools---while some allow pausing for manual input, these capabilities are not modelled as first-class workflow elements. This comparative framework informs the evaluation dimensions used in the present study. However, Broccia et al.'s analysis is limited to visual workflow platforms and excludes multi-agent frameworks (LangGraph, CrewAI) and SDK runtimes (OpenAI Agents SDK, Google ADK, Microsoft Agent Framework), which represent fundamentally different architectural paradigms. Their feature analysis also omits pipeline-based benchmarking---platforms are compared on what they _offer_, not how they _perform_ on real tasks. The present study extends their framework to all three categories and adds empirical benchmarking as a third evaluation layer.

== LLM-Based Agent Architectures and Benchmarking

Recent work has surveyed the rapidly expanding landscape of LLM-based code generation agents and autonomous agent architectures @wang2024survey @bandi2025rise @nguyenduc2024genai_se. Dong et al. @dong2025survey provide a comprehensive taxonomy of single-agent and multi-agent architectures for software development, cataloguing evaluation benchmarks such as SWE-bench, HumanEval, and MBPP. Their survey highlights a key gap: while individual agent capabilities are increasingly well-benchmarked, comparative evaluation of the _platforms_ and _frameworks_ used to build and orchestrate these agents remains largely unaddressed.

Beyond surveys, several studies address specific aspects of agentic system design relevant to this evaluation.

*Budget-aware orchestration.* Yang et al. @yang2025bamas introduce BAMAS, a framework for structuring budget-aware multi-agent systems using integer linear programming for LLM provisioning and offline reinforcement learning for topology selection. Their four collaboration topologies (Linear, Star, Feedback, Planner-Driven) provide a useful vocabulary for characterising platform architectures, and their finding that no current framework incorporates budget-awareness underscores a gap in production-readiness.

*Architectural comparison.* Derouiche et al. @derouiche2025agentic provide the most directly comparable architectural analysis, comparing six frameworks that overlap with this study's platform set---CrewAI, LangGraph, AutoGen, Semantic Kernel, Google ADK, and MetaGPT---across communication patterns, memory management, orchestration, modularity, and guardrails. Their analysis confirms that frameworks differ significantly in orchestration architecture (graph-based vs. role-based vs. conversation-driven), but does not extend to visual/workflow platforms or empirical pipeline benchmarking.

*Interoperability protocols.* Adimulam et al. @adimulam2026orchestration complement this with a unified orchestration framework covering emerging interoperability protocols such as MCP and A2A, arguing that "value emerges less from individual capabilities and more from orchestrated interactions within a collective"---a finding that directly supports the present study's framework-centric evaluation approach.

*Assertion-based benchmarking.* Shu et al. @shu2024towards propose assertion-based benchmarking for multi-agent collaboration in enterprise settings, avoiding dependency on ground-truth output trajectories.

These studies share a common limitation: each evaluates a single system or architectural approach in isolation, without systematic cross-platform comparison using consistent evaluation criteria. The present study addresses this by applying a unified DESMET-based framework across nine platforms spanning all three architectural categories.

== Evaluation Harnesses and SE-Pipeline Benchmarking

A parallel line of work has focused on _what_ LLMs and LLM-based agents can produce on code-centric tasks. SWE-bench @jimenez2024swebench frames software engineering as resolving real-world GitHub issues against test suites drawn from popular Python repositories, and has become the de-facto reference for end-to-end patch-generation capability. HumanEval @chen2021humaneval and MBPP @austin2021mbpp, both introduced as function-level code-generation suites, remain widely used for docstring-to-code and short-program synthesis and are frequently reported alongside newer, harder benchmarks. AgentBench @liu2023agentbench generalises this evaluation style to interactive agents, assessing LLMs across eight environments ranging from operating-system shells to web browsing. These benchmarks measure production capability of an LLM (or an agent built around one) on fixed tasks, but they do not isolate the contribution of the surrounding framework.

A second strand of prior art focuses on _how_ evaluation itself is structured. EleutherAI's lm-evaluation-harness @gao2024lmevalharness provides a standardised, reproducible runner for hundreds of few-shot tasks and underpins much of the public LLM-leaderboard ecosystem. HELM @liang2023helm extends this toward multi-metric, multi-scenario coverage---accuracy, calibration, robustness, fairness, bias, toxicity, and efficiency reported as a matrix rather than a single number---making explicit the argument that a single accuracy score is an insufficient basis for model selection. CLEAR @mehta2025clear carries this multi-dimensional philosophy into the enterprise-agent setting, and Shu et al.'s assertion-based benchmarking for multi-agent collaboration @shu2024towards provides a bridge to rubric-style scoring by decoupling evaluation from ground-truth output trajectories. Together these works standardise how LLM-layer evaluations are specified and executed, but stop at the model boundary and do not extend to multi-stage SE pipelines built on top of an LLM.

The three-layer DESMET framework developed in this study sits at the intersection of three orthogonal bodies of prior art: task-level benchmarks measure _LLM production capability_ on fixed problems, standardised harnesses govern _how LLM evaluations are executed and reported_, and platform surveys @broccia2025humainflow @derouiche2025agentic describe _what agentic frameworks look like_ architecturally. None of these axes addresses the question of what a framework adds _on top of_ a fixed LLM when that framework is exercised across a multi-stage software-engineering pipeline, which is the question the present evaluation harness is designed to answer.

== Research Gap

@tab-related-work summarises how the most directly related prior work maps onto the architectural categories and evaluation methods this study applies, making the gap explicit: no existing study combines coverage of all three architectural categories with both feature analysis and empirical pipeline benchmarking, and none incorporates industry-readiness criteria alongside technical evaluation. The first three columns indicate whether a study covers each architectural category (multi-agent frameworks, SDK runtimes, visual workflow platforms); the last three indicate which evaluation methods it employs (qualitative feature analysis, empirical pipeline benchmarking, and industry-readiness assessment covering release maturity, documentation, community, and licensing). _Partial_ indicates coverage of a subset of that category's typical features or a restricted scope; _Cost only_ indicates empirical measurement confined to a single dimension.

#figure(
  table(
    columns: (2.1fr, 0.85fr, 0.85fr, 0.85fr, 0.85fr, 0.85fr, 0.85fr),
    stroke: 0.5pt,
    inset: 5pt,
    align: (left, center, center, center, center, center, center),
    table.header(
      [*Study*],
      [*Multi-\ agent \ Fwks.*],
      [*SDK \ Runtimes*],
      [*Visual \ Platforms*],
      [*Feature \ Analysis*],
      [*Empirical \ Bench.*],
      [*Industry \ Ready.*],
    ),
    [*This study*], yes-cell, yes-cell, yes-cell, yes-cell, yes-cell, yes-cell,
    [Broccia et al. @broccia2025humainflow], no-cell, no-cell, yes-cell, yes-cell, no-cell, partial-cell,
    [Derouiche et al. @derouiche2025agentic], yes-cell, yes-cell, no-cell, yes-cell, no-cell, no-cell,
    [Yin et al. @yin2025comprehensive], yes-cell, partial-cell, no-cell, no-cell, yes-cell, no-cell,
    [Dong et al. @dong2025survey (survey)], yes-cell, yes-cell, no-cell, yes-cell, no-cell, no-cell,
    [Yang et al. @yang2025bamas (BAMAS)], yes-cell, no-cell, no-cell, no-cell, cost-only-cell, no-cell,
    [Adimulam et al. @adimulam2026orchestration], yes-cell, yes-cell, partial-cell, yes-cell, no-cell, no-cell,
    [Shu et al. @shu2024towards], yes-cell, no-cell, no-cell, no-cell, yes-cell, no-cell,
  ),
  caption: [Coverage comparison across the most directly related prior work.],
) <tab-related-work>

Neither the DESMET-based evaluation literature @kitchenham1997desmet @ferrari2021systematic, the GenAI workflow comparison work @broccia2025humainflow, nor the LLM agent surveys @dong2025survey @jin2024llmagents_se address the systematic comparison of platforms that integrate autonomous agents into the full software development lifecycle. Existing evaluations either target a single platform category @broccia2025humainflow, benchmark narrow capabilities in isolation @dong2025survey, or compare frameworks only along a single axis such as cost @yang2025bamas.

The two most directly related studies are Yin et al. @yin2025comprehensive, who demonstrate through three-perspective evaluation (effectiveness, efficiency, overhead) that no single framework dominates across all dimensions---reinforcing the need for multi-dimensional assessment---and Derouiche et al. @derouiche2025agentic, who compare six of the nine platforms evaluated in this study across architectural dimensions but without empirical benchmarking or visual/workflow platform coverage.

Wang et al. @wang2024survey note that existing benchmarks focus on task completion but lack standardised metrics for orchestration quality and multi-stage pipeline coherence, and task-level code benchmarks such as SWE-bench @jimenez2024swebench measure end-to-end LLM production capability rather than the contribution of the framework layered on top of the model. No systematic evaluation currently spans the heterogeneous landscape of multi-agent frameworks, agent SDK runtimes, and visual workflow builders using evaluation criteria that encompass both technical performance and platform maturity.

This project addresses this gap by applying a DESMET-based three-layer framework to nine agentic platforms---covering a different and broader set of frameworks than prior work---combining pipeline benchmarking with qualitative feature assessment across consistent evaluation criteria. Where Yin et al. evaluate what frameworks _can do_, this study additionally evaluates what practitioners _need to know_ to adopt them: release maturity, documentation quality, community support, extensibility, and licensing. The following chapter presents the design of the evaluation framework.
