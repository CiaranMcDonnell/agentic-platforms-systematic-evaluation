#import "../template.typ": *

= Limitations and Threats to Validity <limitations>

This chapter consolidates the limitations of the proposed approach and the threats to validity of the evaluation.

== Limitations

Several limitations of the proposed approach should be acknowledged. First, the evaluation uses four scenarios spanning three complexity tiers. While designed to exercise all pipeline stages and differentiate platform capabilities, four scenarios cannot represent the full diversity of software engineering tasks---results may not generalise to domains such as data engineering, mobile development, or systems programming.

Second, Layer~3 pipeline benchmarking in the present evaluation is restricted to the five programmatic platforms (LangGraph, CrewAI, Microsoft Agent Framework, OpenAI Agents SDK, Google~ADK) and to the basic scenario US-001. The four visual platforms (Flowise, LangFlow, Dify, n8n) are fully covered at Layers~1 and~2, and adapters for Flowise, LangFlow, and n8n are implemented to the point of platform initialisation and authentication, but a complete end-to-end US-001 pipeline run has not been executed against any of the four. Likewise, the three remaining scenarios (US-010, US-030, US-020) are fully defined and harness-executable but have not been run. Both gaps are specified future work rather than open research questions---the framework, harness, rubric, and data artefacts are designed to absorb these extensions without architectural change---but the current benchmarking findings should be interpreted as a programmatic-subset, basic-task baseline rather than a full-matrix comparison.

Third, Dify in particular is covered at Layers~1 and~2 only as a partial integration. Dify's v1.0 release (February~2025) moved its entire LLM provider and tool ecosystem into a marketplace-only plugin system: no model provider ships in-box, and each must be fetched and installed per-workspace before any agent app can select a model. This evaluation targets v1.13.3, which retains the same plugin-first architecture. The harness automates Dify's initialisation, admin setup, authentication, and app creation cleanly, but end-to-end agent execution would require programmatic plugin install and adoption of a provider-scoped `model_config` shape that is still evolving. This gap is itself a finding rather than a missing feature: plugin-only ecosystems exhibit weaker automation affinity than component-catalogue ecosystems, where every provider ships in-box (cf. the Flowise and LangFlow adapters, which build agent flows entirely from live component catalogues).

Fourth, all evaluations use a single LLM model to isolate framework capability from model capability. While this is a deliberate methodological choice, it means results may not transfer to other models---a framework that performs well with one model's function-calling behaviour may struggle with another's.

Fifth, qualitative rubric scores are assigned by a single evaluator. Despite structured criteria at each score level, borderline cases (e.g. distinguishing a score of~2 from~3 on error recovery) involve subjective judgement. The management console records free-text justification notes to support future multi-evaluator validation.

Finally, agentic platforms evolve rapidly. The evaluation represents a point-in-time snapshot; findings may not generalise to future platform versions. All platform versions are recorded in the results metadata to enable temporal context when interpreting findings.

== Threats to Validity

=== Internal Validity

Internal validity concerns whether the evaluation outcomes could have been influenced by uncontrolled factors. All qualitative rubric scores reflect a single evaluator's judgement (also noted above); this is mitigated by structured rubrics with explicit criteria at each score level @kitchenham1997desmet and by the management console's scoring workflow, which presents trace evidence alongside the rubric to ground judgements in observable data rather than recollection. Free-text notes per dimension provide an audit trail for borderline cases.

*Prompt sensitivity.* A single evaluator authored the standardised prompt templates, and all platforms receive them via the same shared template layer. See *Prompt-injection heterogeneity* under Construct Validity for adapter-level drift in how those templates reach the LLM.

*Order effects.* Platforms are evaluated sequentially, and later evaluations may benefit from the evaluator's accumulated familiarity with the scoring rubric. This is partially mitigated by the structured rubric, which anchors scores to specific observable criteria rather than relative comparison.

*LLM non-determinism.* Language model outputs are inherently stochastic. All prompts, configurations, and outputs are recorded for reproducibility, and the harness supports repeated runs with variance metrics computation @taherdoost2019likert.

*Adapter-level measurement fidelity.* Measurement-fidelity concerns about how iterations, retries, and reviewer tool calls are counted across adapters are cross-adapter comparability issues and are discussed under Construct Validity below.

=== External Validity

External validity concerns the generalisability of the conclusions beyond the specific evaluation context.

*Scenario representativeness.* Four scenarios cannot represent the full population of software engineering tasks. Results should be interpreted as indicative of relative platform capability within the evaluated task types rather than as absolute performance predictions.

*Platform version sensitivity.* Agentic platforms are under active development, with breaking changes occurring between minor versions. Findings are tied to the specific platform versions recorded in the evaluation metadata and may not generalise to future releases.

*LLM model dependency.* Using a single LLM model controls for model capability but limits generalisability. A platform's orchestration effectiveness may vary with different models---for example, a framework that relies heavily on structured output may perform differently with models that have weaker JSON generation capabilities.

*Category representativeness.* Nine platforms across three categories provide reasonable but not exhaustive coverage. Proprietary tools (e.g. Devin, Cursor Agent) and domain-specific platforms are excluded; the three-category taxonomy captures the major architectural paradigms but may not account for emerging hybrid approaches.

=== Construct Validity

Construct validity concerns whether the metrics and rubrics adequately capture the concepts they claim to measure.

*Framework-centric vs. output quality metrics.* The evaluation's central design choice is to measure framework capability rather than LLM output quality, since the same model is used across all platforms. This separation is imperfect: platforms differ in how they construct system prompts, structure conversation history, and handle tool results, all of which can influence output quality through the framework's interaction with the model. The framework-centric metrics capture orchestration behaviour (tool reliability, error recovery, trace fidelity) but may not fully account for framework-induced output quality differences.

*Adapter-level measurement fidelity.* A structured review of all five SDK and multi-agent adapters identified and fixed several classes of bug (silent event-drop, cumulative iteration counters, guardrail-only validation, missing asymmetric-tool distribution, silently-swallowed planner fallbacks, over-defensive regex escapes, and token/duration double-counting); the complete audit with fixes and investigated-but-ruled-out concerns is documented in @appendix-adding-adapter. Three cross-adapter concerns remain as documented comparability gaps rather than bug fixes: iteration-count semantics differ across adapters (LangGraph counts graph-node steps, CrewAI counts LLM calls, MAF counts executor turns, OpenAI SDK counts `new_items`, and ADK counts events with author, inflating 3--5× relative to peers); CrewAI's outer-retry loop multiplies effective iteration budget by up to 3× versus peers; and LangGraph's reviewer subgraph is given tools via `bind_tools` but has no tool-execution node so those calls are silently dropped. Per-platform absolute numbers remain interpretable, but relative rankings on Efficiency, Autonomy, and Orchestration should be read with the qualification that measurement units are not uniform across adapter families.

*Prompt-injection heterogeneity.* Although the harness holds the logical prompt templates constant, each adapter wraps them differently before the LLM sees them: LangGraph prepends supervisor role framings on top of persona backstories, CrewAI injects role/goal/backstory triples into every agent turn, and Google~ADK applies a brace-escape pass and routes non-Gemini models via LiteLLM wrappers. Inter-platform comparisons therefore reflect both framework orchestration and framework-level prompt construction; the two cannot be fully separated with the present design.

*Rubric scale granularity.* The 0--3 rubric scale was chosen to reduce inter-rater ambiguity in a single-evaluator context @kitchenham1997desmet @taherdoost2019likert. This coarser scale trades measurement precision for scoring reliability---meaningful differences between closely-performing platforms may be obscured when both map to the same integer score. The cross-cutting dimension aggregation (averaging across scenarios) partially mitigates this by producing continuous scores on a 1--5 scale.

*Aggregation formula design.* The cross-cutting dimension formulas involve design choices: equal weighting across scenarios, specific normalisation constants (100,000-token budget, \$0.50-per-scenario cost budget), and equal weighting across dimension components. Alternative weighting schemes could yield different platform rankings. The formulas are documented explicitly to enable sensitivity analysis, and the raw per-stage metrics are retained to support alternative aggregation approaches @kitchenham1998desmet_eval.

=== Statistical Power

This evaluation does not employ statistical hypothesis testing. The harness supports repeated runs with `repeats > 1` and computes a `VarianceMetrics` summary (see Implementation chapter), but the US-001 Gemini Flash baseline and the Sonnet cross-model pass reported in @evaluation were each executed at `repeats = 1`. Variance characterisation is therefore a harness capability exercised only on pilot stages, and is reported as specified future work alongside the outstanding US-010, US-030, and US-020 runs in @conclusions-future-work.
