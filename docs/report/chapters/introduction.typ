#import "../template.typ": *

= Introduction

== Background & Motivation

Agentic platforms integrate autonomous or semi-autonomous agents into the software development lifecycle, assisting with code generation, testing, debugging, and documentation @dong2025survey. As organisations increasingly adopt these tools, understanding their capabilities and limitations becomes critical for informed tool selection. Recent surveys highlight a rapidly expanding landscape of LLM-based agent architectures @dong2025survey, cost-aware multi-agent systems @yang2025bamas, comprehensive reviews of autonomous agent architectures @wang2024survey @bandi2025rise, and surveys of LLM-based agents for the software engineering lifecycle @jin2024llmagents_se, yet no structured comparison helps practitioners navigate these options.

Despite growing adoption, there is no systematic comparison across the heterogeneous landscape of agentic frameworks, SDK runtimes, and workflow-based LLM platforms. Existing evaluations either focus on a single platform category—such as visual workflow tools @broccia2025humainflow—or benchmark narrow capabilities like code generation in isolation @dong2025survey. The closest prior work is Yin et al. @yin2025comprehensive, who provide a rigorous empirical evaluation of seven agent frameworks across three code-centric SE tasks (software development, vulnerability detection, and program repair), finding that no single framework dominates across all dimensions. However, their evaluation focuses exclusively on technical performance metrics and covers a different set of frameworks (OpenHands, SWE-Agent, GPTswarm, among others), without addressing the ecosystem maturity, practitioner-readiness, and architectural diversity that influence real-world adoption decisions. Recent multi-dimensional evaluation frameworks such as CLEAR @mehta2025clear have begun to address evaluation methodology for agentic systems. Mehta demonstrates that accuracy-only evaluation of agentic systems correlates poorly with production success ($rho = 0.41$), while multi-dimensional evaluation achieves significantly stronger correlation ($rho = 0.83$)—validating the multi-dimensional approach adopted by the present study. However, CLEAR's specific dimensions (Cost, Latency, Efficacy, Assurance, Reliability) target enterprise deployment rather than software engineering pipeline performance. Practitioners lack evidence-based guidance for making informed adoption decisions that account for both technical capability and platform ecosystem factors.

== Research Questions

To address this gap, the study is guided by three research questions:

+ *RQ1 — Platform Landscape:* How do agentic platforms compare in terms of industry readiness and architectural characteristics across multi-agent frameworks, SDK runtimes, and visual workflow platforms?

+ *RQ2 — Pipeline Performance:* How completely, efficiently, and autonomously can agentic platforms orchestrate a four-stage software engineering pipeline (requirements and design, code generation, test generation, build and deployment)?

+ *RQ3 — Cross-Category Patterns:* What patterns in capability and limitation emerge across the three architectural categories, and what practical guidance can be derived for practitioner platform selection?

== Aims, Objectives & Scope

This project aims to:

+ Construct a systematic evaluation framework for comparing agentic platforms, following DESMET methodology @kitchenham1997desmet
+ Evaluate nine platforms across three layers: industry readiness (Layer 1), platform characteristics (Layer 2), and pipeline benchmarking (Layer 3) measuring pipeline completeness, efficiency, orchestration, and autonomy
+ Identify comparative strengths and weaknesses across three architectural categories
+ Provide actionable guidance for practitioners selecting agentic tools
+ Deliver a reusable evaluation harness and taxonomy applicable to future platforms

The evaluation covers nine agentic platforms representing multi-agent frameworks (LangGraph, CrewAI), agent SDK runtimes (OpenAI Agents SDK, Google ADK, Microsoft Agent Framework), and visual workflow platforms (Flowise, LangFlow, Dify, N8n). All nine platforms are assessed at Layers 1 and 2 through desk research and hands-on feature verification. Layer 3 pipeline benchmarking is conducted for five platforms---LangGraph, CrewAI, OpenAI Agents SDK, Google ADK, and Microsoft Agent Framework---using purpose-built adapters; the remaining four platforms are assessed at Layers 1--2 only, with the evaluation harness designed for straightforward adapter extension. Exhaustive platform coverage, longitudinal studies, economic cost-benefit analysis, and proprietary tools (e.g., Devin) are out of scope.

*Repository:* #link("https://csgitlab.ucd.ie/cmd/agentic-platforms-systematic-evaluation")[Agentic Platforms Systematic Evaluation]. Installation and configuration instructions are provided in @appendix-getting-started.

== Summary of Approach and Contributions

This study applies a DESMET-based three-layer evaluation framework that combines qualitative screening with pipeline benchmarking @kitchenham1997desmet. Layer 1 establishes industry readiness through desk research on release maturity, community size, documentation quality, and adoption evidence. Layer 2 maps platform characteristics across system-level features (MCP support, SDK independence, observability, sandboxing) and interaction-level features (human-in-the-loop, workflow patterns, multi-agent coordination), extending the comparative framework of Broccia et al. @broccia2025humainflow from visual workflow tools to all three architectural categories. Layer 3 benchmarks each platform by executing user stories of increasing complexity through a four-stage software engineering pipeline, scoring six framework-centric rubric dimensions that aggregate into four cross-cutting scores: Pipeline Completeness, Efficiency, Orchestration, and Autonomy. Since the same LLM is used across all platforms, the metrics isolate framework capability from model capability.

To operationalise this framework, the study contributes a purpose-built evaluation harness (`desmet`) comprising a platform-agnostic pipeline runner, a shared adapter infrastructure with a template-method pattern requiring implementors to define only a single method, automated metrics collection with structured result export, and a web-based management console (FastAPI backend, Svelte frontend) for pipeline execution, scoring, and visualisation. Four platform adapters implement idiomatic multi-agent architectures: LangGraph (graph-based checkpointing), CrewAI (role-based sequential crews), OpenAI Agents SDK (structured output with handoff chains), and Microsoft Agent Framework (MagenticOne manager-driven teams). All adapters share a common tool set and prompt structure while preserving framework-specific orchestration patterns, enabling controlled cross-platform comparison.

// TODO: Add 1 paragraph previewing key findings once results are complete.
// Structure: "The evaluation reveals that [category differences]. Across the
// four benchmarked platforms, [finding about completeness/autonomy]. [Finding
// about orchestration patterns]. These findings suggest [practical implication]."

== Report Overview

The remainder of this report is structured as follows. Chapter 2 provides the background necessary to understand the evaluation approach, surveying the DESMET methodology, comparative analyses of GenAI workflow platforms, and LLM-based agent benchmarking, before identifying the research gap in cross-category platform comparison. Chapter 3 presents the design of the three-layer evaluation framework, including the platform selection criteria and category taxonomy, four-stage pipeline and benchmark design, the 0--3 scoring rubric, and the cross-cutting dimension aggregation formulas. Chapter 4 describes the technical implementation of the evaluation harness: the adapter architecture with its template-method pattern, pipeline stage modules, metrics collection, deploy infrastructure, and the web-based management console. Chapter 5 details the evaluation method---user story design and selection rationale, data formats and ground truth definitions, data collection procedures per layer, and execution setup for reproducibility. Chapter 6 presents the results across all three evaluation layers, including industry readiness profiles, system-level and interaction-level feature matrices, per-story pipeline benchmarking results, cross-cutting dimension scores, and a discussion of cross-category patterns in relation to the research questions. Chapter 7 examines limitations of the proposed approach and threats to the validity of the evaluation across internal, external, construct, and statistical dimensions. Chapter 8 concludes with a summary of contributions, an assessment of goals achieved against the original objectives, and directions for future work including multi-evaluator studies and adapter coverage extension.
