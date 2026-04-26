#import "../template.typ": *

= Conclusions

== Summary of Contributions

This project makes three contributions to the evaluation of agentic platforms for software engineering:

+ *Evaluation framework.* A DESMET-based three-layer evaluation methodology combining qualitative screening (industry readiness, platform characteristics) with pipeline benchmarking. The framework extends Broccia et al.'s @broccia2025humainflow visual-platform-only comparison to all three architectural categories (multi-agent frameworks, SDK runtimes, visual workflow platforms) and adds empirical benchmarking as a third evaluation layer. Separating industry readiness (Layer~1), platform capabilities (Layer~2), and pipeline performance (Layer~3) enables practitioners to evaluate platforms at the depth appropriate to their decision-making stage.

+ *Empirical comparison.* A cross-platform evaluation of nine agentic platforms, covering a different and broader set of frameworks than prior work. Where Yin et al. @yin2025comprehensive evaluate seven code-centric frameworks and Derouiche et al. @derouiche2025agentic compare six frameworks architecturally, this study spans nine platforms across three architectural categories using a unified evaluation methodology with four cross-cutting dimensions: Pipeline Completeness, Efficiency, Orchestration, and Autonomy.

+ *Evaluation tooling.* The `desmet` evaluation harness and web-based management console, designed as a reusable evaluation instrument rather than a single-use research artefact. The harness's template-method adapter pattern requires implementors to define a single method, with shared infrastructure handling prompt construction, tool creation, trace lifecycle, and result building. The management console operationalises the scoring rubric through an interactive scoring panel with integrated trace evidence and a novel agent communication graph visualisation. The framework is extensible to future platforms without changes to the runner, metrics, or console (see @appendix-adding-adapter).

The methodological stance is to isolate framework contribution from model capability: the same model and temperature across every platform make observed differences---the ~2.4× token-cost spread between OpenAI Agents SDK and Microsoft Agent Framework on US-001, the rtc separation between CrewAI's full-history replay and the zero-rtc converging platforms, the orchestration fragilities exposed by the Sonnet cross-model repeat---attributable to framework behaviour. Prior benchmarks (SWE-bench, HumanEval, the surveys of @dong2025survey and @wang2024survey) quantify model capability; architectural analyses (@broccia2025humainflow, @derouiche2025agentic) describe framework structure without measuring orchestration cost. The framework-centric metric set---pipeline completeness, tool integration, error recovery, trace quality, redundant-tool-call rate, and replay strategy---measures what a platform adds _on top of_ any given LLM, letting model and framework choice be made on independent evidence.

== Key Findings

Findings are scoped to the current Layer~3 dataset (five programmatic platforms on US-001); visual-platform Layer~3 and the three remaining scenarios are specified future work (see @limitations). Full evidence is in @evaluation.

- *Conversation-history policy, not architectural category or agent count, is the finer-grained predictor of orchestration cost.* Three replay strategies (bounded checkpoints, trimmed history, full-cycle accumulation) produce three distinct cost profiles; CrewAI sits near the SDK-runtime cost floor despite being a multi-agent framework.

- *Redundant-tool-call rate (rtc) is the stage-level early indicator of orchestration pathology contributed by this evaluation.* It separates converging platforms (rtc = 0) from those whose retry policies absorb loop-defence signals (CrewAI at rtc = 0.33 on US-001).

- *Token cost on an identical task spans ~2.4× across platforms.* OpenAI Agents SDK at 100,383 tokens vs. MAF at 239,801 on the same task and model.

- *No single (model, provider) run surfaces all framework fragilities.* The Sonnet 4.6 pass exposed a CrewAI task timeout, an ADK provider rate-limit regression, and an MAF provider-routing failure, none of which are visible on the `gpt-4.1-mini` baseline.

- *Frameworks differ in how much they amplify model-level variance.* Token amplification between `gpt-4.1-mini` and Sonnet 4.6 is ~1.1× for LangGraph and OpenAI SDK but ~5.2× for CrewAI---the Crew pattern's full-history replay compounds per-turn verbosity non-linearly.

- *File-presence validation alone is insufficient as a stage success signal.* The productive-tool-call harness guard correctly demotes MAF's zero-work Sonnet stages and intermittent ADK Testing-stage read-only aborts that would otherwise satisfy a naive file-existence check using baseline workspace artefacts.

At Layers~1 and~2 across all nine platforms, two further patterns hold. The feature gap between the three architectural categories is narrower in 2026 than 2023--2024 surveys reported: every platform supports MCP, local and remote LLMs, extensibility, memory, and multi-agent coordination, with differentiation now on A2A adoption, runtime sandboxing, and workflow-pattern coverage. Licensing rather than maturity separates platforms for commercial embedding---seven ship permissive MIT/Apache-2.0, while n8n's Sustainable Use License and Dify's modified Apache-2.0 restrict multi-tenant resale.

== Answers to the Research Questions

Scoped to the empirical coverage of the present study:

*RQ1 --- Platform Landscape.* The Layer~1 and Layer~2 results cover all nine platforms and answer RQ1 in full. Industry readiness is broadly strong across the field: seven of nine platforms have crossed a stable 1.0 release, maintenance cadence is uniform, and documentation is the one criterion on which no platform falls short. Release maturity and licensing are the cleanest differentiators for commercial embedding. Architecturally, the three categories have converged on MCP, memory, multi-agent coordination, and local- and remote-LLM support; the remaining differentiation sits on A2A breadth, runtime sandboxing, and workflow-pattern coverage. This narrows the architectural gap relative to the state described by @broccia2025humainflow and @derouiche2025agentic and shifts the locus of platform comparison from feature presence to orchestration behaviour.

*RQ2 --- Pipeline Performance.* Layer~3 results answer RQ2 partially. All five programmatic platforms completed all four stages of US-001, and token cost spanned a roughly 2.4× range between Microsoft Agent Framework (239,801 tokens) and OpenAI Agents SDK (100,383 tokens)---with Google~ADK below the SDK-runtime floor at 56,764 tokens---on an identical task driven by the same model. Efficiency and orchestration therefore differentiate the programmatic platforms meaningfully; pipeline completeness saturates on a basic task and autonomy does not differentiate---every run logged zero human interventions and the aggregator falls back to that signal when the manual rubric is unscored---so both require more complex scenarios to exercise. Pipeline performance across the visual category and across the complexity tiers captured by US-010, US-030, and US-020 is held as specified future work (@conclusions-future-work).

*RQ3 --- Cross-Category Patterns.* RQ3 is the RQ most blocked by outstanding work: the cross-category comparison the framework is designed to enable requires Layer~3 runs against the visual-platform category, which are scaffolded but not yet executed. Within the two categories currently represented (multi-agent frameworks and SDK runtimes), the data supports one load-bearing finding: conversation-history policy, not architectural category or agent count, is the finer-grained predictor of pipeline cost. Google~ADK and OpenAI Agents SDK (SDK runtimes) sit at the low end at 57k and 100k tokens; CrewAI (a multi-agent framework) clusters with them at 104k after the native-function-calling and termination-tool fixes, while LangGraph and Microsoft Agent Framework (both multi-agent frameworks) sit higher at 190k and 240k because of heavier test-fixture generation and Magentic history accumulation respectively. The internal spread within the multi-agent-framework category (CrewAI 104k to MAF 240k) is as wide as the gap between the two SDK-runtime points---direct evidence that category-level guidance is weaker than strategy-level guidance, a methodologically useful contrast with the category-based framing of prior comparative analyses. A full three-category answer covering all architectural families requires the visual-platform Layer~3 runs noted in @conclusions-future-work.

== Goals Achieved

*Aims~1 and~5 --- Framework and harness.* Fully delivered. The evaluation framework has been applied end-to-end across all three layers, and the harness accepts new platforms through a single adapter method without changes to the runner, metrics, rubric engine, or web console (see @appendix-adding-adapter).

*Aim~2 --- Three-layer evaluation.* Complete at Layers~1 and~2 for all nine platforms; complete at Layer~3 for the five programmatic platforms on US-001. Visual-platform Layer~3 runs and the three remaining scenarios (US-010, US-030, US-020) are scaffolded but outstanding (@conclusions-future-work).

*Aim~3 --- Cross-category strengths and weaknesses.* Partially delivered: Layer~1 and Layer~2 matrices establish category-level patterns across all nine platforms; the Layer~3 cross-category claim awaits visual-platform Stage~3 data.

*Aim~4 --- Practitioner guidance.* Delivered for the programmatic-subset, basic-task slice: framework-centric metrics, orchestration-pathology indicators, conversation-history-policy implications, and licensing-for-commercial-embedding guidance. Broader guidance awaits the outstanding runs.

== Platform Selection Guidance

#block(
  fill: rgb("#F5F7FA"),
  stroke: 0.5pt + rgb("#B0B8C4"),
  radius: 4pt,
  inset: 12pt,
  width: 100%,
)[
*Is there an overall best platform?* No single platform dominates across cost, orchestration quality, sandboxing, observability, and authoring ergonomics simultaneously. However, if forced to a single recommendation for _software engineering practitioners_ evaluated on the dimensions measured in this study, the strongest default choice within the benchmarked set is *OpenAI Agents SDK*: it set the tightest cost profile on US-001 (≈100k tokens, zero redundant tool calls), carries built-in tracing and sandboxed code execution, and amplified model-level variance by only ~1.1× on the cross-model pass. Its principal caveats---pre-1.0 API and OpenAI-centric ergonomics---are ecosystem rather than capability issues. *LangGraph* is the strongest alternative when deep observability and bounded per-iteration cost matter more than absolute token usage.

#v(0.3em)

*Major strength of each platform (all dimensions considered).*

- *LangGraph* --- _Deepest observability and architectural rigour._ Native LangSmith plus OpenTelemetry tracing, and supervisor checkpoints that keep per-iteration cost constant regardless of tool-call volume. Best choice when debuggability and orchestration control outweigh token-count concerns.
- *CrewAI* --- _Fastest path to a working role-based crew._ Sits within 4% of the SDK-runtime cost floor on US-001 after native-function-calling and `check_completion` fixes, with the richest ecosystem of community crews. Best choice for rapid prototyping of role-based patterns.
- *OpenAI Agents SDK* --- _Lowest-cost basic-task orchestration and built-in sandboxing._ Cleanest trimmed-history cost profile in the benchmarked set, model-swap stable, production-grade Sandbox Agents out of the box.
- *Google~ADK* --- _Lowest absolute cost on the basic task, strongest out-of-the-box runtime isolation._ 57k tokens / \$0.026 on US-001; gVisor-sandboxed `GkeCodeExecutor` and GCP-native observability. Intermittent Testing-stage regressions in repeat passes are tracked as a run-variance characterisation item.
- *Microsoft Agent Framework* --- _Unified enterprise successor to AutoGen and Semantic Kernel._ Native OTLP emission, DevUI debugger, first-party connectors for every major provider, and full A2A support at 1.0.
- *Flowise* --- _Fastest no-code agent prototyping._ Broadest component catalogue with Custom MCP node; the right choice for rapid UI-driven experimentation, subject to its in-process sandbox CVE history for production use.
- *LangFlow* --- _Genuine low-code bridge._ Python-editable visual components are the distinguishing feature; the right choice when a team wants a visual authoring surface without giving up access to component code.
- *Dify* --- _Turnkey no-code enterprise apps._ RBAC, model routing, and Seccomp-sandboxed code out of the box; the plugin-only provider ecosystem blocks full automation today and modified-Apache licensing restricts multi-tenant resale.
- *n8n* --- _Workflow automation at scale._ Rich per-node execution logs, 400+ integrations, custom-node extensibility; the Sustainable Use licence restricts re-hosting as a commercial service.
]

@tab-platform-selection summarises each platform's headline strength and principal caveat. Layer~3-derived claims are scoped to the five programmatic platforms on US-001; visual-platform rows rely on Layers~1 and~2.

#figure(
  placement: none,
  table(
    columns: (auto, 1.6fr, 1.6fr),
    stroke: 0.5pt,
    inset: 5pt,
    align: (left, left, left),
    table.header([*Platform*], [*Headline strength*], [*Principal caveat*]),
    [LangGraph],
      [Deep observability (LangSmith + OpenTelemetry); supervisor checkpoints keep per-iteration cost constant within a stage],
      [Testing-stage test-fixture generation drove ~151k of its 190k US-001 tokens; no built-in sandboxing, so code execution must be isolated externally],
    [CrewAI],
      [Rapid role-based crew construction with minimal orchestration code; strong ecosystem; on US-001 sits within 4\% of the SDK-runtime cost floor (104k tokens) after native-function-calling and `check_completion` termination fixes landed],
      [Highest redundant-tool-call rate in the dataset (rtc = 0.33) because the Crew pattern preserves the full inter-agent log; cost behaviour on longer, multi-turn tasks remains an open question pending the intermediate and advanced scenario runs],
    [OpenAI Agents SDK],
      [Lowest-cost basic-task orchestration observed in this study; built-in tracing and sandboxed code execution],
      [Pre-1.0 API and OpenAI-centric ergonomics; A2A only via community adapters],
    [Google ADK],
      [Lowest absolute token and cost on US-001 (57k tokens, \$0.026); gVisor-sandboxed `GkeCodeExecutor`---strongest out-of-the-box isolation; GCP-native observability],
      [Intermittent Testing-stage regressions observed in repeated passes; run-variance characterisation listed as specified future work],
    [Microsoft Agent Framework],
      [Unified successor to AutoGen + Semantic Kernel; native OTLP, DevUI debugger, enterprise backing],
      [Magentic manager can accumulate full-cycle histories on completion-detection misfires---largest token cost on US-001 (~240k)],
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

The first two items are specified extensions---scaffolded in the harness, scenario artefacts, and rubric but not yet executed---and are the highest-priority outstanding work.

- *Visual-platform Layer~3 benchmarking.* Completing the three-category comparison requires running the US-001 pipeline end-to-end against the four visual platforms. Flowise, LangFlow, and n8n have adapters that reach platform initialisation and authentication; end-to-end execution is the remaining work. Once these runs complete, every Layer~3 finding above can be tested for cross-category generalisation.

- *Complexity-scaling runs on US-010, US-030, and US-020.* The three remaining scenarios are fully defined (YAML, prompts, Gherkin acceptance criteria) and the harness supports their execution; what is outstanding is the runs themselves. Running them is the only way to discriminate between the two live hypotheses for CrewAI's cost profile---fixed per-turn surcharge versus super-linear history-replay compounding---and to convert the present basic-task baseline into a complexity-scaling result.

- *Multi-evaluator validation and repeated-runs variance characterisation.* The most significant methodological improvement would be repeating the qualitative scoring with multiple independent evaluators to compute inter-rater reliability (Cohen's $kappa$), and repeating the pipeline runs themselves (`repeats > 1`) to report coefficient-of-variation statistics on tokens, wall-clock, and cost per platform. The management console's scoring infrastructure and the harness's `VarianceMetrics` summary are already designed to support both workflows.

- *Full Dify Layer~3 integration.* Extending Layer~3 coverage to Dify would require programmatic plugin install via the Dify marketplace and a rewrite of the app `model_config` shape to reference plugin-scoped provider names; the harness already automates init, authentication, and app creation (see @limitations).

- *Longitudinal evaluation.* Agentic platforms evolve rapidly---CrewAI's breaking changes between minor versions illustrate this. A longitudinal study repeating the evaluation across platform versions would reveal whether capability gaps are narrowing and whether relative rankings are stable over time.

- *Extended pipeline stages.* The four-stage pipeline could be expanded with debugging (locate and fix bugs from failing tests), refactoring (improve code quality without changing behaviour), and code review (assess a pull request for correctness and style), each exercising different framework capabilities.

- *Alternative LLM models.* Repeating the evaluation with different models (Claude, Gemini, open-source via Ollama) would test the assumption that framework-centric metrics are model-independent and reveal whether some platforms are better optimised for specific model families.

- *Formal Model Robustness cross-cutting dimension.* The two-model pass reported in @tab-model-sensitivity gives a descriptive observation of how much each framework amplifies model-level token variance (~1.1× for LangGraph and OpenAI SDK, ~5.2× for CrewAI). Promoting this to a rubric-scored fifth cross-cutting dimension (1--5 Likert, anchored in stage-completion delta, token-amplification ratio, and distinct error classes across models) requires at least three model conditions to calibrate the scoring thresholds, plus a new manual rubric dimension in the Scoring page. The scaffolding is a natural extension of the existing four-dimension aggregation formula in @appendix-scoring-rubric and would convert the present descriptive observation into an inferential claim.

- *Community-contributed adapters.* Publishing the harness as a standalone package with adapter contribution guidelines would enable the research community to expand platform coverage beyond the nine platforms evaluated in this study.
