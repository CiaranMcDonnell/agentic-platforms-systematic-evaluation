#import "../template.typ": *

= Introduction

== Background & Motivation

This project evaluates agentic platforms *as software engineering tools*---that is, for their ability to help a practitioner execute the main stages of a software engineering pipeline (requirements and design, code generation, test generation, and build and deployment) rather than for their capabilities as general-purpose agent runtimes. The software engineering setting imposes concrete task shapes (structured specifications, code artefacts, runnable tests, deployable services) that differ from the conversational or data-analysis workloads on which most agent-platform literature has focused to date.

Agentic platforms integrate autonomous or semi-autonomous agents into the software development lifecycle, assisting with code generation, testing, debugging, and documentation @dong2025survey. Recent surveys highlight a rapidly expanding landscape of LLM-based agent architectures @wang2024survey @bandi2025rise @jin2024llmagents_se @yang2025bamas, yet no structured comparison helps software engineering practitioners navigate the options.

There is no systematic comparison of how agentic frameworks, SDK runtimes, and workflow-based LLM platforms perform specifically as software engineering tools. Existing evaluations either focus on a single platform category @broccia2025humainflow or benchmark narrow capabilities like code generation in isolation @dong2025survey. Yin et al. @yin2025comprehensive provide a rigorous empirical evaluation of seven agent frameworks across three code-centric SE tasks but address a different set of frameworks and focus exclusively on technical performance, without ecosystem maturity, practitioner-readiness, or architectural diversity. Multi-dimensional evaluation frameworks such as CLEAR @mehta2025clear target enterprise deployment rather than SE pipeline performance. Practitioners therefore lack evidence-based guidance for adoption decisions that account for both technical capability and platform ecosystem factors in an SE context.

== Research Questions

To address this gap, the study is guided by three research questions:

+ *RQ1 — Platform Landscape:* For software engineering applications, how do agentic platforms compare in terms of industry readiness and architectural characteristics across multi-agent frameworks, SDK runtimes, and visual workflow platforms?

+ *RQ2 — Pipeline Performance:* How completely, efficiently, autonomously, and with what orchestration quality can agentic platforms execute a four-stage software engineering pipeline (requirements and design, code generation, test generation, build and deployment)?

+ *RQ3 — Cross-Category Patterns:* What patterns in capability and limitation emerge across the three architectural categories, and what practical guidance can be derived for practitioners selecting an agentic platform for software engineering?

== Aims, Objectives & Scope <aims>

This project aims to:

+ Construct a systematic evaluation framework for comparing agentic platforms as software engineering tools, following DESMET methodology @kitchenham1997desmet
+ Evaluate nine platforms across three layers: industry readiness (Layer~1), platform characteristics (Layer~2), and pipeline benchmarking (Layer~3) measuring pipeline completeness, efficiency, orchestration, and autonomy
+ Identify comparative strengths and weaknesses across three architectural categories
+ Provide actionable guidance for practitioners selecting agentic tools
+ Deliver a reusable evaluation harness and taxonomy applicable to future platforms

The evaluation covers nine agentic platforms representing multi-agent frameworks (LangGraph, CrewAI, Microsoft Agent Framework), agent SDK runtimes (OpenAI Agents SDK, Google ADK), and visual workflow platforms (Flowise, LangFlow, Dify, n8n). All nine platforms are assessed at Layers~1 and~2. Layer~3 benchmarking is scoped in this report to the five programmatic platforms on the basic scenario; visual-platform Layer~3 runs and higher-complexity scenarios are scaffolded but outstanding, and are discussed as a scoping finding in @limitations. Exhaustive platform coverage, longitudinal studies, economic cost-benefit analysis, and proprietary tools (e.g. Devin) are out of scope.

*Repository:* #link("https://csgitlab.ucd.ie/cmd/agentic-platforms-systematic-evaluation")[Agentic Platforms Systematic Evaluation]. Installation and configuration instructions are provided in @appendix-getting-started.

== Summary of Approach and Contributions

This study applies a DESMET-based three-layer evaluation framework combining qualitative screening with pipeline benchmarking @kitchenham1997desmet.

*Layer~1 --- Industry readiness.* Established through desk research on release maturity, community size, documentation, and adoption evidence.

*Layer~2 --- Platform characteristics.* Maps system-level and interaction-level features, extending the comparative framework of Broccia et al. @broccia2025humainflow to all three architectural categories.

*Layer~3 --- Pipeline benchmarking.* Benchmarks each platform by running a sample software engineering pipeline that encompasses the main SE stages---requirements and design (including UML diagrams), code generation, test generation, and build and deployment---with scenarios of increasing complexity supplied as input to the pipeline. Each run scores six framework-centric rubric dimensions that aggregate into four cross-cutting scores: Pipeline Completeness, Efficiency, Orchestration, and Autonomy. Because the same LLM is used across all platforms, the metrics isolate framework capability from model capability.

To operationalise the framework, the study contributes a purpose-built evaluation harness (`desmet`) comprising a platform-agnostic pipeline runner, a shared adapter infrastructure, automated metrics collection, and a web-based management console for pipeline execution, scoring, and visualisation.

On the Layers that cover all nine platforms, the feature gap between multi-agent, SDK-runtime, and visual categories is narrower in 2026 than 2023--2024 surveys reported: MCP, memory, multi-agent coordination, and local- and remote-LLM support are now universal. Meaningful differentiation has shifted to protocol breadth (A2A), runtime sandboxing, and workflow-pattern coverage, and licensing separates the platforms cleanly for commercial embedding.

On Layer~3, three distinct conversation-history strategies produce three distinct cost profiles: LangGraph's bounded supervisor checkpoints, OpenAI Agents SDK's trimmed history, and Microsoft Agent Framework's full cycle-history accumulation. This taxonomy, not architectural category or agent count, is the finer-grained predictor of orchestration cost. The report introduces the *redundant-tool-call rate* as a stage-level early indicator of orchestration pathology, cleanly separating platforms that converge on a stage from those whose retry policies absorb loop-defence warnings.

The five programmatic platforms span a roughly 2.4× token-cost range on an identical basic task with the same model, evidence that framework choice materially affects inference cost independently of model choice. A Sonnet cross-model repeat exposes provider- and framework-level fragilities not visible on the primary baseline (CrewAI task timeout, Google~ADK provider rate-limit, Microsoft Agent Framework provider-routing failure), establishing that no single (model, provider) run is sufficient to surface all framework fragilities. It also exposes a further signal not available from either run alone: frameworks differ markedly in how much they amplify model-level token variance (~1.1× for LangGraph and OpenAI Agents SDK, ~5.2× for CrewAI on identical work).

Visual-platform Layer~3 runs and the three higher-complexity scenarios are scaffolded but not yet executed; the cross-category comparison the framework is designed to enable is therefore scoped to the programmatic subset in this report (see @limitations).

== Report Overview

The remainder of this report is structured as follows:

- *Chapter 2* surveys the DESMET methodology, comparative analyses of GenAI workflow platforms, and LLM-based agent benchmarking, identifying the research gap in cross-category platform comparison.
- *Chapter 3* presents the three-layer evaluation framework: platform selection, the four-stage pipeline, the 0--3 scoring rubric, and cross-cutting dimension aggregation.
- *Chapter 4* describes the technical implementation: adapter architecture, pipeline stage modules, metrics collection, deploy infrastructure, and the web-based management console.
- *Chapter 5* details the evaluation method: scenarios, data formats, execution setup, and ethical considerations.
- *Chapter 6* presents the results across all three layers: industry readiness profiles, feature matrices, pipeline benchmarking, cross-cutting scores, and cross-category patterns in relation to the research questions.
- *Chapter 7* analyses threats to validity across internal, external, construct, and conclusion dimensions.
- *Chapter 8* concludes with contributions, goals achieved, and directions for future work.
