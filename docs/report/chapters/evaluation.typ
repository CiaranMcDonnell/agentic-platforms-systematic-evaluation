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

Google ADK and Microsoft Agent Framework completed the first three stages but failed Deploy, and are therefore excluded from the per-platform narrative above. ADK aborted immediately after planning with a swallowed `KeyError` reporting that the context variable `PORT` was not found; the exception originates from ADK's instruction templater matching the literal `\${PORT}` placeholder in the prompt as a session-state lookup. The stage recorded one iteration, zero tool calls, and zero tokens. Microsoft Agent Framework reached the 50-iteration cap without producing the deployment artefacts: mid-run the executor reported that `write_file` was no longer available and the orchestrator replanned onto unrelated edits (for example, modifying a hallucinated `SECRET_KEY` constant in a non-existent `utils.py`), indicating a transient tool-binding loss after a replanning event. Both failures are adapter-level rather than task-level; both have since been fixed (ADK via a brace-escape applied to every agent instruction before it reaches the ADK templater; MAF via a re-ordered deploy prompt that surfaces the required artefacts before the task list, so a replanning orchestrator cannot drop them). The tables above continue to reflect the original Gemini Flash run so the evaluation remains on a single dataset; the fixed behaviour is observed consistently in the subsequent cross-model run described in the next subsection.

==== US001 Cross-Model Observations

The five platforms were re-run on US-001 with `anthropic/claude-sonnet-4.6` to verify that the framework-level patterns observed under Gemini Flash persisted under a stronger model and a different provider. Results below summarise the observed behaviour; the primary tables above are not regenerated because the Sonnet run exposed four adapter-level or provider-level issues that bias the comparison, and the Gemini Flash dataset remains the only self-consistent five-platform baseline currently available.

*Confirmed patterns.* LangGraph retained the tightest profile on the new model, finishing all four stages in three supervisor iterations each (49 tool calls, 209,130 tokens, \$0.821) with a redundant-tool-call rate of zero on every stage. OpenAI Agents SDK remained low-token (111,442 tokens, \$0.442 total) with zero redundancy across Code Gen, Testing, and Deploy. CrewAI continued to dominate the cost profile (538,715 tokens, \$1.856 across three completed stages), with Deploy redundancy at 0.29 after a fix---still the highest on any platform but reduced from 0.50 under Gemini Flash. The relative platform ranking---LangGraph $<$ OpenAI SDK $<$ CrewAI on cost per completed story---held under model swap.

*Four new issues were surfaced by the model swap* and are worth reporting as methodological findings in their own right:

1. *CrewAI internal task timeout* (Requirements stage). CrewAI enforces a default 45-second `max_execution_time` per task that Sonnet could not meet on the Requirements prompt; under Gemini Flash the same stage completed in 30 seconds and the limit was never approached. The symptom is stage-level failure with no diagnostic beyond the CrewAI error. The cap is a framework-configuration issue rather than a capability issue.

2. *Google ADK directory-argument handling* (Requirements stage). The stage aborted with `[Errno 21] Is a directory: '/workspace/app/schemas'` during a routine `list_directory` call. The fault is an adapter wrapper issue, not an ADK or Sonnet behaviour; it went undetected under Gemini Flash because the baseline workspace navigation under that model did not touch the affected path.

3. *Microsoft Agent Framework via AWS Bedrock* (all stages). Every stage failed with a Claude `tool_use_id`/`tool_result` message-ordering error originating from MAF's Magentic orchestrator stitching sub-agent histories for Bedrock's strict message format. Zero tool calls executed in any stage, making the Sonnet MAF row unreportable until the provider routing is switched from Bedrock to direct Anthropic.

4. *False-positive success under zero work*. A separate harness guard was added during the run analysis to flip stages to FAIL when the orchestration error was accompanied by zero tool calls; without it, MAF's codegen and testing stages reported PASS purely because earlier stages' baseline artefacts satisfied the file-presence validator.

*Methodological conclusion.* Three of the four issues---the CrewAI task timeout, the ADK `list_directory` error, and the MAF Bedrock incompatibility---were not visible under single-model evaluation on Gemini Flash. This is direct evidence for a claim the evaluation framework can now make explicitly: even on a task as simple as US-001, a cross-model run surfaces framework and adapter fragilities that a single-model baseline hides. The Sonnet dataset is therefore treated as a validation pass for the Gemini Flash findings rather than a replacement for them, and the tables and numbers elsewhere in this chapter continue to refer to the Gemini Flash run.

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

Five findings emerge from the US-001 evaluation and its cross-model repeat; each is grounded in specific observed behaviour rather than theoretical expectation.

*Token cost on an identical task spans more than an order of magnitude across platforms.* OpenAI Agents SDK completed US-001 end-to-end in 52,652 tokens under Gemini Flash; CrewAI required 1,251,528 tokens on the same task and the same model---a 24× spread attributable entirely to orchestration overhead. No platform produced meaningfully different source artefacts. This is the single most decisive signal in the dataset: framework choice dominates model choice in shaping inference economics for short development tasks.

*Redundant-tool-call rate (rtc) is a reliable early indicator of orchestration pathology.* Stages with rtc $\geq$ 0.5 in this run correspond one-to-one with stages that triggered loop-defence and burned disproportionate tokens (CrewAI Code Gen and Deploy, ADK Testing). The metric distinguishes between platforms that converge cleanly (rtc = 0 on every LangGraph and OpenAI SDK stage) and platforms whose retry policies absorb loop-defence warnings without changing behaviour (CrewAI's internal retry on Testing and Deploy). This differs from the prior-framework evaluations surveyed in @yin2025comprehensive and @mehta2025clear, which report raw task success without instrumenting intra-stage retry loops.

*Framework replay strategy predicts cost scaling.* Three distinct history-management strategies were observed: LangGraph's bounded supervisor checkpoints (iteration cost is roughly constant across the stage), OpenAI SDK's trimmed conversation history (2:1 input/output token ratio throughout), and CrewAI's full inter-agent log preservation (31:1 input/output ratio on Deploy). Only the third pattern is super-linear in stage length, which is why CrewAI accounts for nearly 70% of the entire Gemini Flash run's token consumption despite completing the same work as the others.

*Adapter-level fragilities hide under single-model evaluation.* Cross-model repeat under Sonnet 4.6 surfaced three issues---a CrewAI 45-second task timeout, an ADK `list_directory` directory-argument error, and a Microsoft Agent Framework incompatibility with Anthropic via AWS Bedrock---none of which was visible on Gemini Flash. On a task as simple as US-001 this is a meaningful methodological result: the framework comparison reported in @derouiche2025agentic, which evaluates visual platforms on a single LLM backend, would not detect these classes of fault.

*File-presence validation is insufficient as a stage success signal.* The MAF Sonnet run demonstrates a degenerate case: four stages reported PASS with zero tool calls and a visible orchestration error, purely because baseline files produced in earlier stages satisfied the validator's file-existence check. Without a harness guard that demotes stages to FAIL when agent work is zero and errors are non-empty, evaluation reports would silently include non-runs as successes. The harness-level fix---demoting any stage with zero tool calls and a non-empty error list to FAIL regardless of the validator verdict---is described in the Implementation chapter alongside the other defence-in-depth mitigations.

=== Cross-Category Patterns

Of the three platform categories defined in the framework (multi-agent orchestrators, SDK runtimes, visual platforms), only the first two are represented in the current benchmarking dataset; the four visual platforms (Flowise, LangFlow, Dify, n8n) have not yet been run on US-001 and are therefore excluded from category-level analysis.

Within the evaluated set, a consistent separation is visible between *multi-agent orchestrators* (LangGraph, CrewAI, Microsoft Agent Framework) and *SDK runtimes* (OpenAI Agents SDK, Google ADK). SDK runtimes averaged roughly 60,000 tokens and \$0.06 per completed US-001 run; multi-agent orchestrators ranged from LangGraph's 131,727 tokens / \$0.053 to CrewAI's 1,251,528 tokens / \$0.448. The separation is not driven by agent count (LangGraph and CrewAI both run multi-agent graphs) but by conversation-history policy, as described under _Framework replay strategy_ above.

LangGraph occupies the lowest-cost position in its category because its supervisor checkpoints effectively bound history replay; this converges the multi-agent orchestrator profile onto the SDK-runtime profile on simple tasks. The hypothesis that category alone predicts performance is therefore not supported by the current data---orchestration strategy is the finer-grained predictor. A full cross-category claim requires the visual-platform Stage 3 data, which is noted as outstanding in the Limitations chapter.

=== Complexity Scaling

US-001 is the only pipeline-benchmarking story completed at the time of writing; complexity scaling across US-010, US-030, and US-020 is outstanding. A single-story dataset cannot distinguish a platform whose overhead is constant from one whose overhead scales with task length---the CrewAI token profile in particular is plausibly either (1) a fixed per-turn surcharge that stays constant as tasks grow or (2) a compounding history-replay cost that would widen the gap on more complex stories. The planned intermediate and advanced stories are specifically designed to discriminate between these hypotheses, and results against them are the highest-priority outstanding item for the evaluation.

