# Evaluation Criteria Report Update — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite Chapter 5 sections 5.3 and 5.4 of the Typst FYP report to reflect the approved three-layer evaluation framework.

**Architecture:** Single-file edit of the Typst report. Replace the old 6-task benchmark design and 4-dimension evaluation structure with the pipeline-based benchmarking approach (4 stages × 4 user stories) and three-layer evaluation framework (Industry Readiness, Platform Characteristics, Pipeline Benchmarking).

**Tech Stack:** Typst markup language

**Spec:** `docs/superpowers/specs/2026-03-10-evaluation-criteria-design.md`

---

## File Structure

- Modify: `docs/report/UCD_CS_FYP_Report_DESMET_Agentic_Platforms.typ:415-555`
  - Section 5.3 "Test Tasks and Benchmark Design" (lines 415-478) → rewrite as "Evaluation Pipeline and Benchmark Design"
  - Section 5.4 "Evaluation Dimensions and Metrics" (lines 480-555) → rewrite as "Three-Layer Evaluation Framework"

No new files created. No tests required (this is documentation).

---

## Chunk 1: Rewrite Section 5.3 — Evaluation Pipeline and Benchmark Design

### Task 1: Replace the 6-task benchmark section with the pipeline-based approach

**Files:**
- Modify: `docs/report/UCD_CS_FYP_Report_DESMET_Agentic_Platforms.typ:415-478`

- [ ] **Step 1: Replace section 5.3 content**

Replace lines 415-478 (from `== Test Tasks and Benchmark Design` through the Memory and Context Handling task spec) with the following Typst content:

```typst
== Evaluation Pipeline and Benchmark Design

This section specifies the software engineering pipeline used to evaluate platform capabilities and the user stories that exercise it. Rather than evaluating platforms on isolated tasks (code generation, debugging, refactoring), this study adopts a pipeline-based approach: each platform is given a user story and must produce working software through a sequence of stages. This design mirrors how practitioners actually use agentic platforms and provides a more holistic assessment of end-to-end capability.

=== Pipeline Stages

Each platform attempts a four-stage software engineering pipeline. Design (UML diagram generation) is folded into the first stage, following the approach in Broccia et al. @broccia2025humainflow where requirements extraction and structural modelling form a single artefact-generation step.

#figure(
  table(
    columns: 4,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Stage*], [*Input*], [*Output*], [*Key Metrics*],
    ),
    [1. Requirements \& Design],
    [User story (YAML)],
    [Structured requirements, acceptance criteria, UML diagrams (PlantUML)],
    [Completeness, quality, traceability, parseable UML],

    [2. Code Generation],
    [Requirements + UML design],
    [Source code],
    [Functional correctness, completeness, code quality, design adherence],

    [3. Test Generation],
    [Requirements + source code],
    [Test suite],
    [Test pass rate, coverage, test quality],

    [4. Build \& Deploy],
    [Source code + tests],
    [Passing build, deployable artifact],
    [Build success, deploy success, configuration effort],
  ),
  caption: [Pipeline Stages Overview],
)

For each stage, two tiers are recorded:

- *Capability Tier*: Whether the platform can perform the stage at all (Supported / Partial / Not Supported).
- *Performance Tier*: For stages the platform completes, quantitative and qualitative metrics are recorded.

#figure(
  table(
    columns: 2,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Rating*], [*Criteria*],
    ),
    [Supported], [Stage completes autonomously or with minimal prompting. Output is usable without manual rewriting.],
    [Partial], [Stage produces output but requires significant human intervention (more than two corrections) or output is only partially usable.],
    [Not Supported], [Platform cannot attempt this stage, or output is unusable or empty despite attempts.],
  ),
  caption: [Capability Tier Definitions],
)

=== Common Per-Stage Metrics

Every pipeline stage records the following resource consumption metrics alongside its stage-specific quality metrics:

- *Token Usage*: Input, output, and total tokens consumed
- *API Cost*: Estimated cost in USD based on provider pricing
- *Wall-clock Time*: Seconds from stage invocation to completion
- *Human Interventions*: Count of manual corrections required during execution

=== User Stories

Four user stories of increasing complexity are run through the pipeline, providing a range of difficulty levels to differentiate platform capabilities:

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Story*], [*Complexity*], [*Purpose*],
    ),
    [US001 (utility function)], [Basic], [Tests pipeline end-to-end with minimal complexity],
    [US010 (API endpoint)], [Intermediate], [Tests API integration and multi-file generation],
    [US030 (fullstack app)], [Intermediate], [Tests frontend and backend coordination],
    [US020 (auth system)], [Advanced], [Tests complex requirements, security concerns, multi-component coordination],
  ),
  caption: [User Stories for Pipeline Evaluation],
)

This yields a total of 10 platforms × 4 stories × 4 stages = 160 stage-level evaluations.
```

- [ ] **Step 2: Verify the edit compiles**

If Typst is available, run: `typst compile docs/report/UCD_CS_FYP_Report_DESMET_Agentic_Platforms.typ`

Otherwise, visually verify Typst syntax is correct (matching brackets, proper `#figure` / `table` nesting).

- [ ] **Step 3: Commit**

```bash
git add docs/report/UCD_CS_FYP_Report_DESMET_Agentic_Platforms.typ
git commit -m "docs(report): rewrite section 5.3 with pipeline-based benchmark design"
```

---

## Chunk 2: Rewrite Section 5.4 — Three-Layer Evaluation Framework

### Task 2: Replace the 4-dimension evaluation section with the three-layer framework

**Files:**
- Modify: `docs/report/UCD_CS_FYP_Report_DESMET_Agentic_Platforms.typ:480-555`

- [ ] **Step 1: Replace section 5.4 content**

Replace lines 480-555 (from `== Evaluation Dimensions and Metrics` through the Aggregation and Weighting paragraph) with the following Typst content:

```typst
== Three-Layer Evaluation Framework

This section defines the evaluation framework used to assess platforms. The framework comprises three complementary layers, each answering a distinct practitioner question. Together, they cover platform viability, capability, and performance---providing a complete evaluation from initial consideration through empirical benchmarking.

=== Layer 1: Industry Readiness

*Purpose:* Establish baseline platform viability. Answers: _"Is this platform mature enough to evaluate seriously?"_

Agentic platforms are a rapidly evolving space where some tools are production-grade while others remain experimental. This layer establishes a factual maturity profile for each platform before investing effort in deeper evaluation.

#figure(
  table(
    columns: 2,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Criterion*], [*What It Measures*],
    ),
    [Release Maturity], [Stable release (v1.0+)? Pre-release, alpha, or beta?],
    [Maintenance Activity], [Commits in last 6 months, open issues response time, release cadence],
    [Community Size], [GitHub stars, contributors, Discord/Slack activity, Stack Overflow presence],
    [Documentation Quality], [Official docs exist? Tutorials? API reference? Completeness and accuracy],
    [Industry Adoption], [Evidence of production use: case studies, enterprise mentions, job postings],
    [Licensing], [Open-source (MIT/Apache)? Fair-code? Proprietary? Implications for extensibility],
  ),
  caption: [Layer 1: Industry Readiness Criteria],
)

Layer 1 produces a factual maturity profile per platform rather than a numeric score. This contextualises all subsequent findings: a high-performing but abandoned platform is not useful guidance for practitioners.

=== Layer 2: Platform Characteristics

*Purpose:* Map what each platform _can_ do, independent of how well it performs on benchmarks. Answers: _"What features and architectural properties does this platform have?"_

This layer directly extends the system-level and interaction-level comparison framework from Broccia et al. @broccia2025humainflow, expanding it from eight visual workflow tools to ten platforms spanning three architectural categories. Additional criteria (A2A protocol support, sandboxing, workflow patterns, memory management, multi-agent coordination) reflect the broader scope of this evaluation.

==== System-level Features

#figure(
  table(
    columns: 2,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Criterion*], [*What It Measures*],
    ),
    [MCP Support], [Model Context Protocol integration for interoperability],
    [A2A Support], [Google Agent-to-Agent protocol support],
    [SDK Independence], [Tightly coupled to a specific SDK (e.g., LangChain) or agnostic?],
    [Local LLM Execution], [Can run models locally (e.g., Ollama) for privacy and cost reduction],
    [Remote LLM Providers], [Which commercial APIs are supported (OpenAI, Anthropic, Google, etc.)],
    [Extensibility], [Plugin system? Custom tool registration? Third-party integrations?],
    [Execution Monitoring], [Built-in observability: tracing, logging, node-level inspection],
    [Sandboxing / Safety], [Code execution isolation, permission boundaries],
  ),
  caption: [Layer 2: System-level Feature Criteria],
)

==== Interaction-level Features

#figure(
  table(
    columns: 2,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Criterion*], [*What It Measures*],
    ),
    [Code Level], [No-code, low-code, or full-code interface accessibility],
    [Team Collaboration], [Shared workflows, version control, multi-user editing],
    [Human-in-the-Loop], [Can humans intervene in workflow execution? First-class or ad-hoc?],
    [Workflow Patterns], [Sequential, parallel, hierarchical, conditional branching support],
    [Memory / State Management], [Conversation memory, persistent state across agent turns],
    [Multi-Agent Coordination], [Can multiple agents collaborate? Role assignment and handoffs?],
  ),
  caption: [Layer 2: Interaction-level Feature Criteria],
)

Each criterion is scored as Yes, Partial, or No based on documentation review and hands-on verification. The output is two feature matrices (one per feature category) with one row per platform and one column per criterion.

=== Layer 3: Pipeline Benchmarking

*Purpose:* Measure how well each platform performs on real software engineering tasks. Answers: _"Given a user story, how effectively can this platform produce working software?"_

Layer 3 is the novel empirical contribution of this study. Each platform is evaluated by running the four-stage pipeline described in Section 5.3 across four user stories of increasing complexity. Stage-specific quality metrics are defined in the subsections below.

==== Requirements \& Design Metrics

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Metric*], [*Type*], [*Measurement*],
    ),
    [Requirement Completeness], [Quantitative], [Percentage of expected requirements captured (ground truth: acceptance criteria from user story)],
    [Requirement Quality], [Qualitative], [Free of smells: ambiguity, vagueness, incompleteness (rubric 0--3)],
    [Traceability], [Qualitative], [Requirements traceable back to user story (rubric 0--3)],
    [Design Completeness], [Qualitative], [All key entities and relationships captured in UML (rubric 0--3)],
    [Design Correctness], [Qualitative], [Diagrams consistent with requirements (rubric 0--3)],
    [Parseable UML], [Quantitative], [Does the PlantUML output compile? (binary)],
  ),
  caption: [Stage 1 Metrics: Requirements \& Design],
)

==== Code Generation Metrics

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Metric*], [*Type*], [*Measurement*],
    ),
    [Functional Correctness], [Quantitative], [Does the code run and produce expected output?],
    [Completeness], [Quantitative], [Percentage of requirements with corresponding implementation],
    [Code Quality], [Qualitative], [Structure, naming, style, maintainability (rubric 0--3)],
    [Adherence to Design], [Qualitative], [Code reflects the UML structure (rubric 0--3)],
  ),
  caption: [Stage 2 Metrics: Code Generation],
)

==== Test Generation Metrics

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Metric*], [*Type*], [*Measurement*],
    ),
    [Test Pass Rate], [Quantitative], [Percentage of generated tests that pass against generated code],
    [Test Coverage], [Quantitative], [Statement and branch coverage of generated tests],
    [Test Quality], [Qualitative], [Meaningful assertions and edge cases (rubric 0--3)],
  ),
  caption: [Stage 3 Metrics: Test Generation],
)

==== Build \& Deploy Metrics

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Metric*], [*Type*], [*Measurement*],
    ),
    [Build Success], [Quantitative], [Does the code build without errors? (binary)],
    [Deploy Success], [Quantitative], [Does the health check pass? (binary)],
    [Configuration Effort], [Qualitative], [How much manual setup was needed (rubric 0--3)],
  ),
  caption: [Stage 4 Metrics: Build \& Deploy],
)

=== Qualitative Scoring Rubric

All qualitative metrics use a consistent four-point rubric:

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Score*], [*Label*], [*Definition*],
    ),
    [0], [Absent], [No meaningful output, or output is completely wrong or unusable],
    [1], [Poor], [Output exists but has major deficiencies; requires substantial rework],
    [2], [Adequate], [Output is functional with minor issues; usable with light corrections],
    [3], [Good], [Output is correct, complete, and well-structured; no corrections needed],
  ),
  caption: [Qualitative Scoring Rubric (0--3 Scale)],
)

=== Cross-cutting Aggregations

Per-stage metrics are aggregated into four cross-cutting scores per platform, each normalised to a 1--5 Likert scale:

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Dimension*], [*Aggregated From*], [*Formula*],
    ),
    [Effectiveness],
    [Capability tier across all stages, correctness, and completeness scores],
    [$(S_"supported" / S_"total") times 0.4 + overline(C_"correctness") times 0.3 + overline(C_"completeness") times 0.3$, scaled to 1--5],

    [Efficiency],
    [Total token usage, wall-clock time, and API cost],
    [Rank-normalised across platforms: lowest resource consumption = 5, highest = 1],

    [Quality],
    [All qualitative rubric scores across stages],
    [$overline(R_"all") times 5 / 3$, where $R$ is the average of all 0--3 rubric scores],

    [Autonomy],
    [Human interventions across all stages],
    [$5 - min(4, overline(I_"per-stage"))$; fewer interventions yields a higher score],
  ),
  caption: [Cross-cutting Evaluation Dimensions],
)

These four dimensions provide the basis for radar charts and ranked cross-platform comparisons in the results analysis. Equal weighting is applied by default, with sensitivity analysis exploring alternative weightings for different practitioner scenarios (e.g., usability-weighted for rapid prototyping, reliability-weighted for production deployment).

=== Data Collection Methods

#figure(
  table(
    columns: 3,
    stroke: 0.5pt,
    inset: 8pt,
    align: left,
    table.header(
      [*Layer*], [*Method*], [*Tooling*],
    ),
    [Layer 1], [Desk research: GitHub API for repository statistics, manual review of documentation and adoption evidence], [Standardised template per platform],
    [Layer 2], [Documentation review and hands-on verification: install each platform, attempt feature use, record Yes/Partial/No], [Feature matrix with evidence notes per cell],
    [Layer 3], [Automated pipeline execution via the evaluation harness; manual scoring for qualitative rubrics post-execution], [Per-stage JSON artifacts stored in results directory],
  ),
  caption: [Data Collection Methods by Layer],
)
```

- [ ] **Step 2: Verify the edit compiles**

If Typst is available, run: `typst compile docs/report/UCD_CS_FYP_Report_DESMET_Agentic_Platforms.typ`

Otherwise, visually verify Typst syntax is correct.

- [ ] **Step 3: Commit**

```bash
git add docs/report/UCD_CS_FYP_Report_DESMET_Agentic_Platforms.typ
git commit -m "docs(report): rewrite section 5.4 with three-layer evaluation framework"
```

---

## Chunk 3: Update Section 5.5 — Execution Methodology alignment

### Task 3: Update the execution methodology to reference the pipeline

**Files:**
- Modify: `docs/report/UCD_CS_FYP_Report_DESMET_Agentic_Platforms.typ:601-618`

- [ ] **Step 1: Update execution methodology**

Replace lines 601-618 (from `=== Execution Methodology` through the end of `=== Automation and Reproducibility`) with:

```typst
=== Execution Methodology

Each platform undergoes the following evaluation process:

+ *Layer 1 Assessment*: Platform maturity profile compiled from GitHub data, documentation review, and industry adoption evidence.
+ *Layer 2 Assessment*: Feature matrices populated through documentation review and hands-on verification of each criterion.
+ *Layer 3 Benchmarking*: Four user stories executed through the four-stage pipeline using the `desmet-eval` CLI harness. Quantitative metrics (token usage, timing, costs) captured automatically; qualitative rubric scores assigned post-execution.
+ *Result recording*: All results logged to structured JSON output in `results/{platform}/{story_id}/` for analysis.

=== Automation and Reproducibility

To ensure reproducibility and reduce evaluator bias:

- Standardised prompt templates are used across all platforms where applicable
- The evaluation harness automates pipeline execution, metric collection, and result storage
- Token usage and API costs are recorded programmatically at each pipeline stage
- All configurations, prompts, and results are version-controlled
- Qualitative rubric scores are assigned against the defined 0--3 scale to minimise subjectivity
```

- [ ] **Step 2: Commit**

```bash
git add docs/report/UCD_CS_FYP_Report_DESMET_Agentic_Platforms.typ
git commit -m "docs(report): update execution methodology for pipeline-based evaluation"
```

---

## Chunk 4: Final verification

### Task 4: Verify consistency across the full chapter

**Files:**
- Read: `docs/report/UCD_CS_FYP_Report_DESMET_Agentic_Platforms.typ:324-650`

- [ ] **Step 1: Read the full Chapter 5 and verify**

Check that:
1. Section 5.1 (Evaluation Methodology Selection) still correctly describes "Benchmarking + Qualitative Screening" — it should, since the three-layer framework is exactly this.
2. Section 5.2 (Platform Selection) is unchanged and consistent.
3. Section 5.3 (new pipeline design) flows logically into Section 5.4 (new three-layer framework).
4. Section 5.4 references back to Section 5.3 for the pipeline stages.
5. Section 5.5 (Implementation Plan) references the correct methodology.
6. The `@broccia2025humainflow` citation resolves (already in references.bib).
7. No orphaned references to the old 6-task or 4-dimension structures remain.

- [ ] **Step 2: Fix any inconsistencies found**

- [ ] **Step 3: Final commit if fixes were needed**

```bash
git add docs/report/UCD_CS_FYP_Report_DESMET_Agentic_Platforms.typ
git commit -m "docs(report): fix consistency issues in Chapter 5"
```
