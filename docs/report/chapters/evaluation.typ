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

All five evaluated platforms reached a passing workspace on US-001, but they did so at token and iteration costs that span more than an order of magnitude: OpenAI Agents SDK completed the full four-stage pipeline in 52,652 tokens for \$0.025, while CrewAI required 1,251,528 tokens for \$0.448---a 24× spread on an identical task driven by the same model (`google/gemini-2.5-flash`). Neither platform produced meaningfully different source artefacts; the divergence is attributable to framework-level orchestration behaviour rather than task-related work.

*OpenAI Agents SDK* exhibited the tightest profile. Each stage converged in a single planning cycle followed by a small number of tool calls (7, 2, 3, and 9 across Requirements, Code Gen, Testing, and Deploy respectively), with a zero redundant-tool-call rate at every stage. Native function calling and a trimmed conversation history kept the input--output token ratio near 2:1, so accumulated context did not dominate later turns. One transient `max turns exceeded` event was recorded in Testing, after which the agent recovered without intervention and passed validation. This is the efficiency baseline against which the other platforms are compared.

*LangGraph* completed all four stages in three supervisor iterations each, with a total wall-clock of 2.6~minutes and \$0.053 in API spend. The first three stages were unremarkable---five, three, and three tool calls respectively---but Deploy triggered a redundant-tool-call rate of 0.50 as the agent entered a short `write\_file`~→~`pytest`~→~`write\_file` cycle when the initial test run failed. The harness's loop-defence guard fired on the fourth identical `write\_file`, and LangGraph's checkpointing made the subsequent iteration converge on a passing test run within a further two cycles. The outcome illustrates LangGraph's graceful degradation under early failure: iteration overhead is bounded by the supervisor budget, and the redundant tokens paid for Deploy (116k) remain within a single order of magnitude of the baseline.

*CrewAI* completed all stages but at a cost that warrants closer inspection. Requirements and Code Gen were comparable in shape to LangGraph, but Testing entered a 34-call `uv run pytest` loop---each invocation failing with an identical import error and the QA agent retrying without modifying the test file---and Deploy then repeated the pattern with 33 `write\_file` calls of which only 9 had unique content (10 byte-identical writes to `utils/validation.py` and 9 to `tests/test\_validation.py`). The iteration ratio on Deploy reached 1.60, meaning the stage exceeded its nominal iteration budget. The root cause of the token volume is compounding rather than additive: CrewAI falls back to ReAct text-mode prompting on non-OpenAI providers (the native function-calling path is currently unavailable for Gemini via OpenRouter), so the full tool catalogue and few-shot parser hints are embedded in every prompt; and the Crew pattern preserves the full inter-agent message log across Technical~Lead~→~Developer~→~QA~→~Reviewer handoffs, producing an input/output token ratio of 31:1 on Deploy. The loop-defence guard fired on both Testing and Deploy but did not force termination because CrewAI's internal retry policy absorbs the signal; an 11,290-token average input per tool call across 75 calls accounts for the bulk of the 874k Deploy total.

Google ADK and Microsoft Agent Framework completed the first three stages but failed Deploy, and are therefore excluded from the per-platform narrative above. ADK aborted immediately after planning with a swallowed `KeyError` reporting that the context variable `PORT` was not found; the exception originates from ADK's instruction templater matching the literal `\${PORT}` placeholder in the prompt as a session-state lookup. The stage recorded one iteration, zero tool calls, and zero tokens. Microsoft Agent Framework reached the 50-iteration cap without producing the deployment artefacts: mid-run the executor reported that `write_file` was no longer available and the orchestrator replanned onto unrelated edits (for example, modifying a hallucinated `SECRET_KEY` constant in a non-existent `utils.py`), indicating a transient tool-binding loss after a replanning event. Both failures are adapter-level rather than task-level and are scheduled for re-run after the corresponding adapter fixes land.

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

