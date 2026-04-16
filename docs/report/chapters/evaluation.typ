#import "../template.typ": *

= Results

This chapter presents the evaluation results across all three layers of the framework and discusses findings and cross-platform patterns.

== Layer 1 Results: Industry Readiness

// TODO: Present the maturity profile for each of the 9 platforms.
// Use a summary table followed by brief narrative per platform.

#figure(
  table(
    columns: 7,
    stroke: 0.5pt,
    inset: 6pt,
    align: left,
    table.header(
      [*Platform*], [*Release Maturity*], [*Maintenance*], [*Community*], [*Docs*], [*Adoption*], [*Licensing*],
    ),
    [LangGraph], [], [], [], [], [], [],
    [CrewAI], [], [], [], [], [], [],
    [OpenAI Agents SDK], [], [], [], [], [], [],
    [Google ADK], [], [], [], [], [], [],
    [Microsoft Agent Framework], [], [], [], [], [], [],
    [Flowise], [], [], [], [], [], [],
    [LangFlow], [], [], [], [], [], [],
    [Dify], [], [], [], [], [], [],
    [N8n], [], [], [], [], [], [],
  ),
  caption: [Layer 1: Industry Readiness Profiles (Yes / Partial / No)],
)

// TODO: Narrative summaries highlighting key differentiators —
// which platforms are production-grade vs. experimental, notable gaps.

== Layer 2 Results: Platform Characteristics

=== System-level Feature Matrix

#figure(
  table(
    columns: 9,
    stroke: 0.5pt,
    inset: 5pt,
    align: left,
    table.header(
      [*Platform*], [*MCP*], [*A2A*], [*SDK Indep.*], [*Local LLM*], [*Remote LLM*], [*Extensibility*], [*Monitoring*], [*Sandboxing*],
    ),
    [LangGraph], [], [], [], [], [], [], [], [],
    [CrewAI], [], [], [], [], [], [], [], [],
    [OpenAI Agents SDK], [], [], [], [], [], [], [], [],
    [Google ADK], [], [], [], [], [], [], [], [],
    [Microsoft Agent Framework], [], [], [], [], [], [], [], [],
    [Flowise], [], [], [], [], [], [], [], [],
    [LangFlow], [], [], [], [], [], [], [], [],
    [Dify], [], [], [], [], [], [], [], [],
    [N8n], [], [], [], [], [], [], [], [],
  ),
  caption: [Layer 2: System-level Feature Matrix],
)

=== Interaction-level Feature Matrix

#figure(
  table(
    columns: 7,
    stroke: 0.5pt,
    inset: 5pt,
    align: left,
    table.header(
      [*Platform*], [*Code Level*], [*Collaboration*], [*HITL*], [*Workflow Patterns*], [*Memory*], [*Multi-Agent*],
    ),
    [LangGraph], [], [], [], [], [], [],
    [CrewAI], [], [], [], [], [], [],
    [OpenAI Agents SDK], [], [], [], [], [], [],
    [Google ADK], [], [], [], [], [], [],
    [Microsoft Agent Framework], [], [], [], [], [], [],
    [Flowise], [], [], [], [], [], [],
    [LangFlow], [], [], [], [], [], [],
    [Dify], [], [], [], [], [], [],
    [N8n], [], [], [], [], [], [],
  ),
  caption: [Layer 2: Interaction-level Feature Matrix],
)

// TODO: Narrative analysis of Layer 2 findings — patterns across categories,
// key differentiators, gaps relative to Broccia et al. framework.

== Layer 3 Results: Pipeline Benchmarking

// Tables in this section are generated from the DuckDB result store
// by `desmet export-typst`. Regenerate after each evaluation run or
// after bulk rubric edits — do not hand-edit the files under
// `docs/report/generated/`.

=== Capability Overview

// Tier per (platform, stage): Supported = every story completed the
// stage; Partial = at least one but not all; Not Supported = zero.
#include "../generated/capability-tiers.typ"

=== Per-Story Results

==== US001: Add Utility Function (Basic)

#include "../generated/per-story-US-001.typ"

// TODO: Narrative for US001 across all platforms.

==== US010: Add API Endpoint (Intermediate)

// #include "../generated/per-story-US-010.typ"  // uncomment once US-010 is run

// TODO: Results table and narrative for US010 across all platforms.

==== US030: Design Fullstack App (Intermediate)

// #include "../generated/per-story-US-030.typ"  // uncomment once US-030 is run

// TODO: Results table and narrative for US030 across all platforms.

==== US020: Implement Auth System (Advanced)

// #include "../generated/per-story-US-020.typ"  // uncomment once US-020 is run

// TODO: Results table and narrative for US020 across all platforms.

=== Cross-cutting Dimension Scores

#include "../generated/cross-cutting.typ"

// TODO: Radar chart figure showing all 9 platforms on the 4 dimensions.

=== Resource Consumption Analysis

#include "../generated/resource.typ"

// TODO: Narrative on efficiency patterns across complexity levels.

== Discussion

=== Key Findings

// TODO: Summarise the most significant findings from the evaluation.
// What patterns emerged? Which platforms excelled and where?
// Cite: @yin2025comprehensive @mehta2025clear @derouiche2025agentic to compare findings with prior framework evaluations

=== Cross-Category Patterns

// TODO: Analyse how the three platform categories (multi-agent frameworks,
// SDK runtimes, visual platforms) performed relative to each other.
// Did category predict performance?

=== Complexity Scaling

// TODO: How did platform performance change as story complexity increased
// from US001 (basic) to US020 (advanced)?

