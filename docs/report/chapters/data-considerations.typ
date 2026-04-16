#import "../template.typ": *

= Data Considerations

This chapter describes the data artefacts used throughout the evaluation: the user stories that drive the pipeline, the formats and schemas employed, the ground truth against which outputs are assessed, and ethical considerations.

== User Story Design

The evaluation pipeline is driven by four user stories of increasing complexity, each representing a realistic software engineering task. Stories are authored to exercise different platform capabilities and to differentiate performance across complexity tiers.

=== Story Selection Rationale

// TODO: Explain why these 4 stories were chosen — coverage of complexity tiers,
// relevance to real SE workflows, ability to exercise all 4 pipeline stages.

=== Story Definitions

Each story is defined in YAML with the following structure: a title, description, complexity tier, acceptance criteria, and expected artefacts per pipeline stage.

// TODO: Include a representative example (e.g., US001) showing the YAML schema.
// Consider a figure showing the YAML structure with annotations.

#figure(
  table(
    columns: 4,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Story ID*], [*Title*], [*Complexity*], [*Acceptance Criteria Count*],
    ),
    [US001], [Add utility function], [Basic], [--],
    [US010], [Add API endpoint], [Intermediate], [--],
    [US030], [Design fullstack app], [Intermediate], [--],
    [US020], [Implement auth system], [Advanced], [--],
  ),
  caption: [User Story Summary],
)

== Data Formats and Artefacts

=== Input Artefacts

The evaluation uses three input formats per story:

- *YAML story definitions* (`data/stories/`): Structured story metadata, acceptance criteria, and expected outputs used by the harness to drive pipeline execution.
- *Gherkin feature files* (`data/gherkin/`): Behaviour-driven specifications expressing acceptance criteria in Given/When/Then syntax, used as ground truth for acceptance criteria coverage assessment.
- *Prompt templates* (`data/prompts/`): Standardised prompts provided to each platform, ensuring consistent task framing across the evaluation.

// TODO: Briefly describe how these three formats relate to each other and
// how they flow into the pipeline stages.

=== Output Artefacts

Each pipeline stage produces structured output stored in `results/{platform}/{story_id}/`:

// TODO: Describe the per-stage output format (JSON artefacts, generated code,
// test results, build logs). Reference the StageResult model from the harness.

== Ground Truth and Baselines

=== Acceptance Criteria as Ground Truth

Acceptance criteria coverage is measured against the criteria defined in each user story's YAML definition. This serves as a _control variable_ rather than a scoring input: since the same LLM is used across all platforms, similar acceptance criteria coverage is expected, and significant divergence would indicate a framework-level issue (e.g., the platform failing to pass the full story context to the model). The framework-centric scoring dimensions (pipeline completeness, tool integration, error recovery, etc.) are assessed independently of output content quality.

// TODO: Describe how ground truth differs per stage — acceptance criteria
// for Stage 1, requirements document for Stage 2, generated code for Stage 3,
// test suite for Stage 4.

=== Baseline Expectations

// TODO: Describe any baseline expectations or reference implementations used
// to calibrate the qualitative rubric scoring (0–3 scale).

== Ethical Considerations

// TODO: Cover the following:
// - No personal or sensitive data is used in user stories
// - API cost implications of running 144 stage-level evaluations
// - Open-source licensing of platforms under evaluation
// - Reproducibility: all prompts, configurations, and results are version-controlled
// - Single-evaluator bias mitigation through structured rubrics
