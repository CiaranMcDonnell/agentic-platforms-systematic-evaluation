#import "../template.typ": *

= Conclusions

== Summary of Contributions

This project makes three contributions to the evaluation of agentic platforms for software engineering:

+ *Evaluation framework.* A DESMET-based three-layer evaluation methodology combining qualitative screening (industry readiness, platform characteristics) with pipeline benchmarking. The framework extends Broccia et al.'s @broccia2025humainflow visual-platform-only comparison to all three architectural categories (multi-agent frameworks, SDK runtimes, visual workflow platforms) and adds empirical benchmarking as a third evaluation layer. The framework's design---separating industry readiness (Layer~1), platform capabilities (Layer~2), and pipeline performance (Layer~3)---enables practitioners to evaluate platforms at the depth appropriate to their decision-making stage.

+ *Empirical comparison.* A cross-platform evaluation of nine agentic platforms, covering a different and broader set of frameworks than prior work. Where Yin et al. @yin2025comprehensive evaluate seven code-centric frameworks and Derouiche et al. @derouiche2025agentic compare six frameworks architecturally, this study spans nine platforms across three architectural categories using a unified evaluation methodology with four cross-cutting dimensions: Pipeline Completeness, Efficiency, Orchestration, and Autonomy.

+ *Evaluation tooling.* The `desmet` evaluation harness and web-based management console, designed as a reusable evaluation instrument rather than a single-use research artefact. The harness's template-method adapter pattern requires implementors to define a single method (`_run_agent`), with prompt construction, tool creation, trace lifecycle, retry orchestration, and result building provided by the base class. The management console operationalises the scoring rubric through an interactive scoring panel with integrated trace evidence (Langfuse span trees, LangSmith run trees) and a novel agent communication graph visualisation that makes multi-agent orchestration patterns directly observable. The framework is extensible to future platforms without changes to the runner, metrics, or console (see @appendix-adding-adapter).

== Key Findings

// RESULTS-DEPENDENT: fill after evaluations are complete.
// Structure: "The evaluation reveals that [cross-category patterns]. Across the
// benchmarked platforms, [completeness/autonomy finding]. [Orchestration finding].
// [Efficiency finding]. These findings suggest [practical implication]."

== Goals Achieved

The project's five aims, as defined in the Introduction, are assessed below:

+ *Construct a systematic evaluation framework*: Achieved. The three-layer DESMET-based framework is fully designed, documented, and operationalised through the evaluation harness and management console.

+ *Evaluate nine platforms across three layers*: // RESULTS-DEPENDENT: state extent of completion once evaluations are done.

+ *Identify comparative strengths and weaknesses across categories*: // RESULTS-DEPENDENT: summarise whether cross-category patterns emerged.

+ *Provide actionable guidance for practitioners*: // RESULTS-DEPENDENT: summarise whether the findings support practical recommendations.

+ *Deliver a reusable evaluation harness and taxonomy*: Achieved. The `desmet` harness with its template-method adapter pattern, management console, and scoring infrastructure is designed for extension. The platform taxonomy (multi-agent frameworks, SDK runtimes, visual platforms) provides a vocabulary for categorising future platforms.

== Future Work

Several directions for future research emerge from this study:

- *Multi-evaluator validation.* The most significant methodological improvement would be repeating the qualitative scoring with multiple independent evaluators to compute inter-rater reliability (Cohen's $kappa$). The management console's scoring infrastructure---with its trace-evidence integration and per-dimension notes---is designed to support this: additional evaluators can score the same platform--story combinations independently, and the stored justification notes enable disagreement analysis.

- *Full Dify Layer~3 integration.* Three of the four visual/workflow platforms (Flowise, LangFlow, N8n) are now benchmarked at Layer~3 alongside the five SDK-based platforms. Extending Layer~3 coverage to Dify~1.13 would require programmatic plugin install via the Dify marketplace (`POST /console/api/workspaces/current/plugin/install/marketplace`) and a rewrite of the app `model_config` shape to reference plugin-scoped provider names (e.g., `langgenius/openrouter/openrouter`). The current harness already automates Dify init, authentication, and app creation, so the remaining work is well-defined but tied to an evolving marketplace API.

- *Longitudinal evaluation.* Agentic platforms evolve rapidly---CrewAI's breaking changes between minor versions illustrate this. A longitudinal study repeating the evaluation across platform versions would reveal whether capability gaps are narrowing and whether relative rankings are stable over time.

- *Extended pipeline stages.* The four-stage pipeline could be expanded with additional software engineering tasks: debugging (given a failing test, locate and fix the bug), refactoring (improve code quality without changing behaviour), and code review (assess a pull request for correctness and style). Each additional stage would exercise different framework capabilities.

- *Alternative LLM models.* Repeating the evaluation with different LLM models (e.g., Claude, Gemini, open-source models via Ollama) would test the assumption that framework-centric metrics are model-independent and reveal whether some platforms are better optimised for specific model families.

- *Community-contributed adapters.* The template-method adapter pattern (see @appendix-adding-adapter) is designed for community extension. Publishing the harness as a standalone package with adapter contribution guidelines would enable the research community to expand platform coverage beyond the nine platforms evaluated in this study.
