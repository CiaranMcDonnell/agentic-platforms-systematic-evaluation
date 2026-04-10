#import "../template.typ": *

= Limitations and Threats to Validity

This chapter consolidates the limitations of the proposed approach and the threats to validity of the evaluation.

== Limitations

Several limitations of the proposed approach should be acknowledged. First, the evaluation uses four user stories spanning three complexity tiers. While these stories were designed to exercise all pipeline stages and differentiate platform capabilities, four stories cannot represent the full diversity of software engineering tasks---results may not generalise to domains such as data engineering, mobile development, or systems programming.

Second, Layer~3 pipeline benchmarking is conducted for five of the nine platforms (LangGraph, CrewAI, OpenAI Agents SDK, Google ADK, Microsoft Agent Framework). The remaining four visual/workflow platforms (Flowise, LangFlow, Dify, N8n) are assessed at Layers~1 and~2 only, as their REST API interfaces require a fundamentally different adapter architecture. The framework is designed for straightforward adapter extension (see @appendix-adding-adapter), but the current results provide limited Layer~3 insight into the visual platform category.

Third, all evaluations use a single LLM model to isolate framework capability from model capability. While this is a deliberate methodological choice, it means results may not transfer to other models---a framework that performs well with one model's function-calling behaviour may struggle with another's.

Fourth, qualitative rubric scores are assigned by a single evaluator. Despite structured criteria at each score level, borderline cases (e.g., distinguishing a score of~2 from~3 on error recovery) involve subjective judgement. The management console records free-text justification notes to support future multi-evaluator validation.

Finally, agentic platforms evolve rapidly. The evaluation represents a point-in-time snapshot; findings may not generalise to future platform versions. All platform versions are recorded in the results metadata to enable temporal context when interpreting findings.

== Threats to Validity

=== Internal Validity

Internal validity concerns whether the evaluation outcomes could have been influenced by uncontrolled factors, compromising objectivity. Key threats include:

*Single-evaluator bias.* All qualitative rubric scores reflect one person's judgement. This is mitigated by structured rubrics with explicit criteria at each score level @kitchenham1997desmet and by the management console's scoring workflow, which presents trace evidence alongside the rubric to ground judgements in observable data rather than recollection.

*Rubric subjectivity.* Despite structured criteria, borderline cases require judgement calls---for example, whether a platform that recovers from one error but not another warrants a score of~2 or~3 on error recovery. The free-text notes field in the scoring panel provides an audit trail for such decisions.

*Prompt sensitivity.* All platforms receive the same standardised prompts via shared prompt templates. However, platforms process prompts differently---some inject additional system instructions, others restructure the conversation history---which may affect LLM behaviour in ways not captured by the framework-centric metrics.

*Order effects.* Platforms are evaluated sequentially, and later evaluations may benefit from the evaluator's accumulated familiarity with the scoring rubric and common failure modes. This is partially mitigated by the structured rubric, which anchors scores to specific observable criteria rather than relative comparison.

*LLM non-determinism.* Language model outputs are inherently stochastic. Repeated runs of the same platform--story combination may yield different results. All prompts, configurations, and outputs are recorded for reproducibility, and the harness supports repeated runs with variance metrics computation @taherdoost2019likert.

=== External Validity

External validity concerns the generalisability of the conclusions beyond the specific evaluation context.

*Story representativeness.* Four user stories cannot represent the full population of software engineering tasks. The stories were selected for complexity-tier coverage and pipeline-stage exercise (see §5.1.1), but results should be interpreted as indicative of relative platform capability within the evaluated task types rather than as absolute performance predictions.

*Platform version sensitivity.* Agentic platforms are under active development, with breaking changes occurring between minor versions---as evidenced by the CrewAI token tracking breakage documented in the Technical Challenges section. Findings are tied to the specific platform versions recorded in the evaluation metadata and may not generalise to future releases.

*LLM model dependency.* Using a single LLM model controls for model capability but limits generalisability. A platform's orchestration effectiveness may vary with different models---for example, a framework that relies heavily on structured output may perform differently with models that have weaker JSON generation capabilities.

*Category representativeness.* Nine platforms across three categories provide reasonable but not exhaustive coverage of the agentic platform landscape. Notably, proprietary tools (e.g., Devin, Cursor Agent) and domain-specific platforms (e.g., biomedical agent frameworks) are excluded. The three-category taxonomy (multi-agent frameworks, SDK runtimes, visual platforms) captures the major architectural paradigms but may not account for emerging hybrid approaches.

=== Construct Validity

Construct validity concerns whether the metrics and rubrics adequately capture the concepts they claim to measure.

*Framework-centric vs.\ output quality metrics.* The evaluation's central design choice is to measure framework capability rather than LLM output quality, since the same model is used across all platforms. However, this separation is imperfect: platforms differ in how they construct system prompts, structure conversation history, and handle tool results, all of which can influence output quality through the framework's interaction with the model. The framework-centric metrics capture orchestration behaviour (tool reliability, error recovery, trace fidelity) but may not fully account for framework-induced output quality differences.

*Rubric scale granularity.* The 0--3 rubric scale was chosen to reduce inter-rater ambiguity in a single-evaluator context @kitchenham1997desmet @taherdoost2019likert. This coarser scale trades measurement precision for scoring reliability---meaningful differences between closely-performing platforms may be obscured when both map to the same integer score. The cross-cutting dimension aggregation (averaging across stories) partially mitigates this by producing continuous scores on a 1--5 scale.

*Aggregation formula design.* The cross-cutting dimension formulas involve design choices: equal weighting across stories, specific normalisation constants (100,000-token budget, \$0.50-per-story cost budget), and equal weighting across dimension components. Alternative weighting schemes could yield different platform rankings. The formulas are documented explicitly to enable sensitivity analysis, and the raw per-stage metrics are retained to support alternative aggregation approaches @kitchenham1998desmet_eval.

=== Statistical Power

This evaluation does not employ statistical hypothesis testing, as each platform--story combination produces a single observation rather than a sample from which statistical inferences can be drawn. The evaluation is therefore descriptive and comparative rather than inferential. Future work with multiple evaluators or repeated runs could enable statistical analysis of inter-rater reliability and result stability.
