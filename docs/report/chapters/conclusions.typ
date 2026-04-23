#import "../template.typ": *

= Conclusions

== Summary of Contributions

This project makes three contributions to the evaluation of agentic platforms for software engineering:

+ *Evaluation framework.* A DESMET-based three-layer evaluation methodology combining qualitative screening (industry readiness, platform characteristics) with pipeline benchmarking. The framework extends Broccia et al.'s @broccia2025humainflow visual-platform-only comparison to all three architectural categories (multi-agent frameworks, SDK runtimes, visual workflow platforms) and adds empirical benchmarking as a third evaluation layer. Separating industry readiness (Layer~1), platform capabilities (Layer~2), and pipeline performance (Layer~3) enables practitioners to evaluate platforms at the depth appropriate to their decision-making stage.

+ *Empirical comparison.* A cross-platform evaluation of nine agentic platforms, covering a different and broader set of frameworks than prior work. Where Yin et al. @yin2025comprehensive evaluate seven code-centric frameworks and Derouiche et al. @derouiche2025agentic compare six frameworks architecturally, this study spans nine platforms across three architectural categories using a unified evaluation methodology with four cross-cutting dimensions: Pipeline Completeness, Efficiency, Orchestration, and Autonomy.

+ *Evaluation tooling.* The `desmet` evaluation harness and web-based management console, designed as a reusable evaluation instrument rather than a single-use research artefact. The harness's template-method adapter pattern requires implementors to define a single method, with shared infrastructure handling prompt construction, tool creation, trace lifecycle, and result building. The management console operationalises the scoring rubric through an interactive scoring panel with integrated trace evidence and a novel agent communication graph visualisation. The framework is extensible to future platforms without changes to the runner, metrics, or console (see @appendix-adding-adapter).

Taken together, these contributions embody a distinct methodological stance on how agentic platforms should be compared: by isolating and measuring the contribution of the _framework_ itself, independent of the large language model it runs on. Because the same model and temperature are used across every platform, every observed difference---the roughly 14× token-cost spread between OpenAI Agents SDK and Microsoft Agent Framework on US-001, the redundant-tool-call rate that distinguishes LangGraph's supervisor checkpoints from CrewAI's full history replay, and the orchestration fragilities exposed only by the cross-model repeat---is attributable to framework behaviour rather than to the model's raw generative capability.

Prior benchmarks for code-generation agents (SWE-bench, HumanEval, and the multi-agent surveys reviewed by @dong2025survey and @wang2024survey) quantify what models can do; architectural analyses (@broccia2025humainflow, @derouiche2025agentic) describe how frameworks are structured but do not empirically measure their orchestration cost. The framework-centric metric set proposed here---pipeline completeness, tool integration, error recovery, trace quality, redundant-tool-call rate, and framework replay strategy---fills the gap between these two bodies of work by measuring what a platform adds _on top of_ any given LLM.

The practical value of this separation is that a practitioner's model choice and framework choice can be made on independent evidence, and framework-selection guidance remains meaningful as models evolve underneath it. This architectural-rather-than-LLM-capability orientation is, in the author's view, the most distinctive aspect of the methodology developed here and the aspect most likely to retain value as the underlying models continue to improve.

== Key Findings

The evaluation produced a concise set of empirical findings; full evidence and methodology are presented in @evaluation. Findings below are scoped to the current Layer~3 dataset (the five programmatic platforms on US-001), with visual-platform Layer~3 coverage and the three remaining scenarios held as specified future work (see @limitations).

- *Framework choice dominates model choice for short development tasks.* On an identical basic task executed with the same model, token cost spans more than an order of magnitude across platforms: OpenAI Agents SDK completed US-001 in 46,758~tokens (\$0.023); Microsoft Agent Framework required 646,588~tokens (\$0.271) for the same task---a roughly 14× spread attributable entirely to orchestration overhead, as no platform produced meaningfully different source artefacts.

- *Redundant-tool-call rate is a reliable early indicator of orchestration pathology.* Stages with rtc~$\geq$~0.5 correspond one-to-one with stages that triggered loop-defence and burned disproportionate tokens. The metric cleanly distinguishes platforms that converge (LangGraph and OpenAI~SDK at rtc~=~0 across every stage) from platforms whose internal retry policies absorb loop-defence warnings (CrewAI on Testing and Deploy).

- *Conversation-history policy, not agent count, predicts cost scaling.* Three replay strategies produced three distinct cost profiles: LangGraph's bounded supervisor checkpoints (constant per-iteration cost), OpenAI~SDK's trimmed history, and Microsoft Agent Framework's Magentic-orchestrator accumulation (the manager resubmits the full cycle history on each round when completion detection misfires). This explains why MAF accounts for roughly 73\% of the entire Gemini~Flash token consumption despite completing identical work. CrewAI's full inter-agent log preservation is architecturally in the same family and a prime candidate to exhibit the same profile on longer tasks, a hypothesis the outstanding US-010 and US-020 runs are designed to test.

- *Single-model evaluation hides adapter-level fragilities.* The cross-model repeat under `anthropic/claude-sonnet-4.6` surfaced three framework and provider-level issues invisible on Gemini~Flash---a CrewAI 45-second task timeout, a Google~ADK `list_directory` directory-argument error, and a Microsoft Agent Framework incompatibility with Anthropic via AWS Bedrock. None affected LLM output quality; all affected framework execution. The framework-centric methodology developed here surfaces exactly the class of fault that single-model LLM-centric benchmarks cannot.

- *File-presence validation alone is insufficient as a stage success signal.* The MAF Sonnet run demonstrated a degenerate case in which four stages reported PASS with zero productive tool calls, purely because baseline files produced by earlier stages satisfied file-existence checks. The harness guard was strengthened to demote any stage lacking a productive tool call (`write_file`, `execute_shell`, or `deploy_remote`) to FAIL, independent of the validator verdict.

Across Layers~1 and~2 (which cover all nine platforms), two further patterns are significant. First, the feature gap between the three architectural categories is narrower in 2026 than prior-art surveys reported in 2023--2024: every platform now supports MCP, local and remote LLMs, extensibility, memory, and multi-agent coordination; meaningful differentiation has moved to A2A adoption, runtime sandboxing, and workflow-pattern coverage. Second, licensing rather than maturity separates the platforms cleanly for commercial embedding---seven platforms ship permissive MIT/Apache-2.0 licences, while n8n's Sustainable Use License and Dify's modified Apache-2.0 restrict multi-tenant resale in ways practitioners must explicitly consider.

== Answers to the Research Questions

The three research questions defined in @aims are answered as follows, scoped to the empirical coverage of the present study.

*RQ1 --- Platform Landscape.* The Layer~1 and Layer~2 results cover all nine platforms and answer RQ1 in full. Industry readiness is broadly strong across the field: seven of nine platforms have crossed a stable 1.0 release, maintenance cadence is uniform, and documentation is the one criterion on which no platform falls short. Release maturity and licensing are the cleanest differentiators for commercial embedding. Architecturally, the three categories have converged on MCP, memory, multi-agent coordination, and local- and remote-LLM support; the remaining differentiation sits on A2A breadth, runtime sandboxing, and workflow-pattern coverage. This narrows the architectural gap relative to the state described by @broccia2025humainflow and @derouiche2025agentic and shifts the locus of platform comparison from feature presence to orchestration behaviour.

*RQ2 --- Pipeline Performance.* Layer~3 results answer RQ2 partially. For the five programmatic platforms on US-001, four of five completed all four stages (CrewAI failed the Testing stage), and token cost spanned a roughly 14× range between Microsoft Agent Framework (646,588 tokens) and OpenAI Agents SDK (46,758 tokens) on an identical task driven by the same model. Pipeline completeness, efficiency, and orchestration therefore all differentiate the programmatic platforms meaningfully; autonomy does not on a basic task and requires more complex scenarios to exercise. Pipeline performance across all nine platforms---specifically the visual category---and across the complexity tiers captured by US-010, US-030, and US-020 cannot be claimed from the current dataset and is held as specified future work (@conclusions-future-work).

*RQ3 --- Cross-Category Patterns.* Cross-category claims can be made within the programmatic subset. The data shows that conversation-history policy, not architectural category or agent count, is the finer-grained predictor of pipeline cost: LangGraph (a multi-agent framework) clusters with OpenAI Agents SDK and Google ADK (SDK runtimes) in the 45--60k-token band because its supervisor checkpoints bound history replay, while Microsoft Agent Framework (same category as LangGraph) is the token-cost outlier because its Magentic orchestrator accumulates full cycle histories on completion-detection failure.

This is direct evidence that category-level guidance is weaker than strategy-level guidance---a methodologically useful finding that contrasts with the category-based framing of prior comparative analyses. A full cross-category answer covering all three architectural families requires the visual-platform Layer~3 runs noted in @conclusions-future-work.

== Goals Achieved

The five aims defined in @aims are assessed as follows.

*Aims~1 and~5 --- Framework and harness.* The systematic evaluation framework (Aim~1) and the reusable evaluation harness with its platform taxonomy and management console (Aim~5) are fully designed, documented, and operationalised. The framework has been applied end-to-end across all three layers, and the harness accepts new platforms through a single adapter method without changes to the runner, metrics, rubric engine, or web console (see @appendix-adding-adapter).

*Aim~2 --- Three-layer evaluation.* Complete at Layers~1 and~2 for all nine platforms, and complete at Layer~3 for the five programmatic platforms on US-001. Visual-platform Layer~3 runs and the three remaining scenarios (US-010, US-030, US-020) are scaffolded but outstanding, and are the two largest items in @conclusions-future-work.

*Aim~3 --- Cross-category strengths and weaknesses.* Partially delivered: the Layer~1 and Layer~2 matrices establish category-level patterns across all nine platforms, but the Layer~3 cross-category claim cannot be made in full until visual-platform Stage~3 data exists.

*Aim~4 --- Practitioner guidance.* Delivered for the programmatic-subset, basic-task slice: framework-centric metrics, orchestration-pathology indicators, conversation-history-policy implications, and licensing-for-commercial-embedding guidance are all concrete and actionable. Broader guidance covering the visual-platform category and the full complexity range awaits the outstanding runs.

== Platform Selection Guidance

#block(
  fill: rgb("#F5F7FA"),
  stroke: 0.5pt + rgb("#B0B8C4"),
  radius: 4pt,
  inset: 12pt,
  width: 100%,
)[
*Verdict.* No single platform dominates across cost, orchestration quality, sandboxing, observability, and authoring ergonomics simultaneously, so the selection reduces to which trade-off is least acceptable for the intended use.

#v(0.2em)

Within the scope of this study:
- *Cheapest orchestration on short tasks:* *OpenAI Agents SDK* (≈47k tokens on US-001) or *Google ADK* (≈57k)---the latter additionally ships production-grade gVisor sandboxing.
- *Deepest observability, bounded cost on longer tasks:* *LangGraph* (native LangSmith + OTel, supervisor checkpoints prevent history-replay blow-up).
- *Unified enterprise stack:* *Microsoft Agent Framework* (consolidates AutoGen + Semantic Kernel, native OTLP, strong SDK independence), at the cost of being the most expensive on US-001.
- *No-code authoring:* *Flowise* for prototyping, *n8n* for large-scale workflow automation, *Dify* for turnkey enterprise apps---subject to sandboxing and licence constraints below.
]

The table below summarises each platform's headline strength and principal caveat from the three-layer evaluation. Layer~3-derived claims are scoped to the five programmatic platforms on US-001; visual-platform rows rely on Layers~1 and~2 and are marked where Layer~3 data is still outstanding.

#figure(
  table(
    columns: (auto, 1.6fr, 1.6fr),
    stroke: 0.5pt,
    inset: 6pt,
    align: (left, left, left),
    table.header([*Platform*], [*Headline strength*], [*Principal caveat*]),
    [LangGraph],
      [Deep observability (LangSmith + OpenTelemetry); supervisor checkpoints keep token cost flat across iterations],
      [No built-in sandboxing---code execution must be isolated externally],
    [CrewAI],
      [Rapid role-based crew construction with minimal orchestration code; strong ecosystem],
      [Full history preserved across agents; possible super-linear cost on longer tasks (hypothesis pending complexity runs)],
    [OpenAI Agents SDK],
      [Lowest-cost basic-task orchestration observed in this study; built-in tracing and sandboxed code execution],
      [Pre-1.0 API and OpenAI-centric ergonomics; A2A only via community adapters],
    [Google ADK],
      [gVisor-sandboxed `GkeCodeExecutor`---strongest out-of-the-box isolation; GCP-native observability],
      [Smaller community than LangGraph/CrewAI; best-fit when targeting GCP],
    [Microsoft Agent Framework],
      [Unified successor to AutoGen + Semantic Kernel; native OTLP, DevUI debugger, enterprise backing],
      [Magentic manager can accumulate full-cycle histories on completion-detection misfires---largest token cost on US-001],
    [Flowise],
      [Fast no-code agent prototyping; broad component catalogue with Custom MCP node],
      [In-process sandbox with multiple 2025--2026 CVEs; Layer~3 run outstanding],
    [LangFlow],
      [Python-editable visual components---genuine low-code bridge between SDK and no-code],
      [No native multi-user support; weak sandboxing (CVE-2026-33017, CVSS~9.3); Layer~3 run outstanding],
    [Dify],
      [Turnkey no-code enterprise apps with RBAC, model routing, and Seccomp-sandboxed code],
      [Plugin-only LLM provider ecosystem blocks full automation; modified-Apache licence restricts multi-tenant SaaS resale],
    [n8n],
      [Workflow automation at scale; rich per-node execution logs; custom-node extensibility],
      [Sustainable Use licence restricts re-hosting as a commercial service; Layer~3 run outstanding],
  ),
  caption: [Platform-by-platform summary of headline strengths and principal caveats.],
) <tab-platform-selection>

== Future Work <conclusions-future-work>

Several directions for future research emerge from this study. The first two are specified extensions of the current evaluation---scaffolded in the harness, scenario artefacts, and rubric but not yet executed---and are the highest-priority outstanding items.

- *Visual-platform Layer~3 benchmarking.* Completing the three-category comparison requires running the US-001 pipeline end-to-end against the four visual platforms. Flowise, LangFlow, and n8n have adapters that reach platform initialisation and authentication; end-to-end execution is the remaining work. Once these runs complete, every Layer~3 finding above can be tested for cross-category generalisation.

- *Complexity-scaling runs on US-010, US-030, and US-020.* The three remaining scenarios are fully defined (YAML, prompts, Gherkin acceptance criteria) and the harness supports their execution; what is outstanding is the runs themselves. Running them is the only way to discriminate between the two live hypotheses for CrewAI's cost profile---fixed per-turn surcharge versus super-linear history-replay compounding---and to convert the present basic-task baseline into a complexity-scaling result.

- *Multi-evaluator validation.* The most significant methodological improvement would be repeating the qualitative scoring with multiple independent evaluators to compute inter-rater reliability (Cohen's $kappa$). The management console's scoring infrastructure, with its trace-evidence integration and per-dimension notes, is designed to support this workflow.

- *Full Dify Layer~3 integration.* Extending Layer~3 coverage to Dify would require programmatic plugin install via the Dify marketplace and a rewrite of the app `model_config` shape to reference plugin-scoped provider names; the harness already automates init, authentication, and app creation (see @limitations).

- *Longitudinal evaluation.* Agentic platforms evolve rapidly---CrewAI's breaking changes between minor versions illustrate this. A longitudinal study repeating the evaluation across platform versions would reveal whether capability gaps are narrowing and whether relative rankings are stable over time.

- *Extended pipeline stages.* The four-stage pipeline could be expanded with debugging (locate and fix bugs from failing tests), refactoring (improve code quality without changing behaviour), and code review (assess a pull request for correctness and style), each exercising different framework capabilities.

- *Alternative LLM models.* Repeating the evaluation with different models (Claude, Gemini, open-source via Ollama) would test the assumption that framework-centric metrics are model-independent and reveal whether some platforms are better optimised for specific model families.

- *Community-contributed adapters.* Publishing the harness as a standalone package with adapter contribution guidelines would enable the research community to expand platform coverage beyond the nine platforms evaluated in this study.
