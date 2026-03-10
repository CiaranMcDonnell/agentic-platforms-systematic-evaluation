# Evaluation Criteria Design — Systematic Evaluation of Agentic Platforms

**Date**: 2026-03-10
**Status**: Approved
**Scope**: Defines the three-layer evaluation framework for comparing 10 agentic platforms

---

## Overview

The evaluation uses a **three-layer hybrid framework** combining qualitative screening with quantitative benchmarking, following DESMET methodology (Benchmarking + Qualitative Screening).

- **Layer 1 — Industry Readiness**: Establishes baseline platform viability
- **Layer 2 — Platform Characteristics**: Maps features (extends Broccia et al. ISTI-TR-2025/011)
- **Layer 3 — Pipeline Benchmarking**: Measures performance on real SE tasks (novel contribution)

Together these answer three practitioner questions: *"Should I consider it?"* → *"What can it do?"* → *"How well does it do it?"*

### Platforms Under Evaluation

| Category | Platforms |
|----------|----------|
| Multi-Agent Frameworks | LangGraph, CrewAI, Microsoft Autogen |
| Agent SDK Runtimes | OpenAI Agents SDK, Google ADK, Semantic Kernel |
| Visual / Workflow Platforms | Flowise, LangFlow, Dify, N8n |

---

## Layer 1 — Industry Readiness (Qualitative Screening)

**Purpose**: Establish baseline viability. Answers: *"Is this platform mature enough to evaluate seriously?"*

**Justification**: Agentic platforms are a fast-moving space. Some are production-grade, others are experimental. Evaluating a dead or unmaintained project wastes effort and produces misleading results. This layer filters for seriousness before investing in deep evaluation.

**Criteria** (all scored Yes / Partial / No, with supporting evidence):

| Criterion | What it measures |
|-----------|-----------------|
| Release Maturity | Stable release (v1.0+)? Pre-release / alpha / beta? |
| Maintenance Activity | Commits in last 6 months, open issues response time, release cadence |
| Community Size | GitHub stars, contributors, Discord/Slack activity, Stack Overflow presence |
| Documentation Quality | Official docs exist? Tutorials? API reference? Completeness and accuracy |
| Industry Adoption | Evidence of production use (case studies, enterprise mentions, job postings) |
| Licensing | Open-source (MIT/Apache)? Fair-code? Proprietary? Implications for extensibility |

**Output**: A maturity profile per platform. Not a score — a factual summary that contextualises everything in Layers 2 and 3.

---

## Layer 2 — Platform Characteristics (Qualitative Screening, extending Broccia et al.)

**Purpose**: Map what each platform *can* do, independent of how well it does it. Answers: *"What features and architectural properties does this platform have?"*

**Justification**: Directly extends the system-level / interaction-level comparison framework from Broccia et al. (ISTI-TR-2025/011). This provides academic grounding and lets the evaluation cite the framework while expanding it to cover a broader platform set (10 platforms across 3 categories vs. their 8 visual/workflow tools).

### System-level Features (Yes / Partial / No)

| Criterion | What it measures |
|-----------|-----------------|
| MCP Support | Model Context Protocol integration for interoperability |
| A2A Support | Google Agent-to-Agent protocol support |
| SDK Independence | Tightly coupled to a specific SDK (e.g., LangChain) or agnostic? |
| Local LLM Execution | Can run models locally (e.g., Ollama) for privacy/cost |
| Remote LLM Providers | Which commercial APIs supported (OpenAI, Anthropic, Google, etc.) |
| Extensibility | Plugin system? Custom tool registration? Third-party integrations? |
| Execution Monitoring | Built-in observability — tracing, logging, node-level inspection |
| Sandboxing / Safety | Code execution isolation, permission boundaries |

### Interaction-level Features (Yes / Partial / No)

| Criterion | What it measures |
|-----------|-----------------|
| Code Level | No-code / Low-code / Full-code — interface accessibility |
| Team Collaboration | Shared workflows, version control, multi-user editing |
| Human-in-the-Loop | Can humans intervene in workflow execution? First-class or ad-hoc? |
| Workflow Patterns | Sequential, parallel, hierarchical, conditional branching support |
| Memory / State Management | Conversation memory, persistent state across agent turns |
| Multi-Agent Coordination | Can multiple agents collaborate? Role assignment, handoffs? |

**Extensions beyond Broccia et al.**: A2A support, sandboxing/safety, workflow patterns, memory/state management, multi-agent coordination. These reflect the broader scope (multi-agent frameworks and SDK runtimes, not just visual tools).

**Output**: Two feature matrices (system-level, interaction-level) — one row per platform, one column per criterion. Plus a short narrative per platform summarising key strengths and gaps.

---

## Layer 3 — Pipeline Benchmarking (Quantitative + Qualitative)

**Purpose**: Measure how well each platform performs on real software engineering tasks. Answers: *"Given a user story, how effectively can this platform produce working software?"*

**Justification**: Novel contribution. No existing study evaluates agentic platforms by running them through a full SE pipeline. The pipeline mirrors what a practitioner actually needs: take a requirement, produce code, test it, deploy it. Broccia et al.'s example scenario (interview → requirements → UML → code) provides direct precedent — this scales it to a systematic cross-platform comparison.

### Pipeline Stages

Each platform attempts all 4 stages. Design (UML diagram generation) is folded into the Requirements & Design stage, following Broccia et al.'s approach where requirements and structural modelling form a single artefact-generation step.

**Codebase mapping**: The evaluation stages correspond to codebase directories as follows:

| Spec Stage | Codebase Directory | Adapter Method |
|------------|--------------------|----------------|
| Stage 1 — Requirements & Design | `stage2_requirements/` | `generate_requirements()` |
| Stage 2 — Code Generation | `stage3_codegen/` | `generate_code()` |
| Stage 3 — Test Generation | `stage4_testing/` | `generate_tests()` |
| Stage 4 — Build & Deploy | `stage5_deploy/` | `build_and_deploy()` |

*Note*: Codebase `stage0_setup/` (framework onboarding) and `stage1_stories/` (YAML story loading) are harness infrastructure, not evaluation stages.

Per stage, two tiers are recorded:

- **Capability Tier**: Supported / Partial / Not Supported (see definitions below)
- **Performance Tier** (only for stages completed): quantitative + qualitative metrics

#### Capability Tier Definitions

| Rating | Criteria |
|--------|----------|
| **Supported** | Stage completes autonomously or with minimal prompting. Output is usable without manual rewriting. |
| **Partial** | Stage produces output but requires significant human intervention (>2 corrections) or output is only partially usable. |
| **Not Supported** | Platform cannot attempt this stage, or output is unusable/empty despite attempts. |

#### Stage 1 — Requirements & Design

*Input*: User story (YAML) | *Output*: Structured requirements, acceptance criteria, UML diagrams (class + sequence in PlantUML)

| Metric | Type | Measurement |
|--------|------|-------------|
| Requirement Completeness | Quantitative | % of expected requirements captured (ground truth: acceptance criteria from user story YAML) |
| Requirement Quality | Qualitative | Free of smells — ambiguity, vagueness, incompleteness (rubric 0-3) |
| Traceability | Qualitative | Requirements traceable back to story? (rubric 0-3) |
| Design Completeness | Qualitative | All key entities and relationships captured in UML? (rubric 0-3) |
| Design Correctness | Qualitative | Diagrams consistent with requirements? (rubric 0-3) |
| Parseable UML | Quantitative | Does the PlantUML compile? (binary) |
| Token Usage | Quantitative | Input / output / total tokens |
| API Cost | Quantitative | Estimated cost based on provider pricing (USD) |
| Wall-clock Time | Quantitative | Seconds to completion |
| Human Interventions | Quantitative | Count of manual corrections needed |

#### Stage 2 — Code Generation

*Input*: Requirements + UML Design | *Output*: Source code

| Metric | Type | Measurement |
|--------|------|-------------|
| Functional Correctness | Quantitative | Does it run? Does it produce expected output? |
| Completeness | Quantitative | % of requirements with corresponding implementation |
| Code Quality | Qualitative | Structure, naming, style, maintainability (rubric 0-3) |
| Adherence to Design | Qualitative | Code reflects the UML structure? (rubric 0-3) |
| Token Usage | Quantitative | Input / output / total tokens |
| API Cost | Quantitative | Estimated cost based on provider pricing (USD) |
| Wall-clock Time | Quantitative | Seconds to completion |
| Human Interventions | Quantitative | Count of manual corrections needed |

#### Stage 3 — Test Generation

*Input*: Requirements + Source code | *Output*: Test suite

| Metric | Type | Measurement |
|--------|------|-------------|
| Test Pass Rate | Quantitative | % of generated tests that pass against generated code |
| Test Coverage | Quantitative | Statement/branch coverage of generated tests |
| Test Quality | Qualitative | Meaningful assertions? Edge cases? (rubric 0-3) |
| Token Usage | Quantitative | Input / output / total tokens |
| API Cost | Quantitative | Estimated cost based on provider pricing (USD) |
| Wall-clock Time | Quantitative | Seconds to completion |
| Human Interventions | Quantitative | Count of manual corrections needed |

#### Stage 4 — Build & Deploy

*Input*: Source code + Tests | *Output*: Passing build, deployable artifact

| Metric | Type | Measurement |
|--------|------|-------------|
| Build Success | Quantitative | Does it build without errors? (binary) |
| Deploy Success | Quantitative | Health check passes? (binary) |
| Configuration Effort | Qualitative | How much manual setup was needed? (rubric 0-3) |
| Token Usage | Quantitative | Input / output / total tokens |
| API Cost | Quantitative | Estimated cost based on provider pricing (USD) |
| Wall-clock Time | Quantitative | Seconds to completion |
| Human Interventions | Quantitative | Count of manual corrections needed |

### Qualitative Rubric Definitions (0-3 Scale)

All qualitative metrics use a consistent 0-3 rubric:

| Score | Label | Definition |
|-------|-------|------------|
| 0 | Absent | No meaningful output, or output is completely wrong/unusable |
| 1 | Poor | Output exists but has major deficiencies; requires substantial rework |
| 2 | Adequate | Output is functional with minor issues; usable with light corrections |
| 3 | Good | Output is correct, complete, and well-structured; no corrections needed |

### Cross-cutting Aggregations

Per-stage metrics roll up into 4 cross-cutting scores per platform, each on a 1-5 Likert scale:

| Dimension | Aggregated from | Formula |
|-----------|----------------|---------|
| Effectiveness | Capability tier across all stages, correctness, completeness | `(stages_supported / total_stages) × 0.4 + avg(correctness_scores) × 0.3 + avg(completeness_scores) × 0.3`, scaled to 1-5 |
| Efficiency | Total token usage, total wall-clock time, total API cost | Rank-normalized across platforms: lowest resource consumption = 5, highest = 1 |
| Quality | Code quality + test quality + requirement quality + design quality rubrics | `avg(all 0-3 rubric scores)` scaled to 1-5 |
| Autonomy | Human interventions across all stages | `5 - min(4, avg(interventions_per_stage))` — fewer interventions = higher score |

**Relationship to codebase dimensions**: The codebase's `EvaluationDimension` enum defines 7 dimensions (Effectiveness, Efficiency, Quality, Reproducibility, Usability, Observability, Failure Handling). These 4 cross-cutting aggregations are the Layer 3 benchmarking scores; Usability and Observability are captured in Layer 2 (Platform Characteristics); Reproducibility and Failure Handling are observable from the benchmarking runs but not scored as separate aggregated dimensions.

### Test Tasks

4 user stories of increasing complexity, each run through the full pipeline:

| Story | Complexity | Purpose |
|-------|-----------|---------|
| US001 (utility function) | Basic | Tests pipeline end-to-end with minimal complexity |
| US010 (API endpoint) | Intermediate | Tests API integration, multi-file generation |
| US030 (fullstack app) | Intermediate | Tests frontend + backend coordination |
| US020 (auth system) | Advanced | Tests complex requirements, security, multi-component coordination |

**Scale**: 10 platforms × 4 stories × 4 stages = 160 stage-level evaluations.

### Data Collection Methods

| Layer | Method | Tooling |
|-------|--------|---------|
| Layer 1 | Desk research: GitHub API for stars/commits/releases, manual review of docs and adoption evidence | Standardised template per platform, populated manually |
| Layer 2 | Documentation review + hands-on verification: install each platform, attempt feature use, record Yes/Partial/No | Feature matrix spreadsheet with evidence notes per cell |
| Layer 3 | Automated pipeline execution via `desmet-eval` CLI harness; manual scoring for qualitative rubrics post-execution | Per-stage JSON artifacts in `results/{platform}/{story_id}/` |

---

## Scoring Summary

| Layer | Scale | Method |
|-------|-------|--------|
| Layer 1 | Factual profile (no numeric score) | Desk research, GitHub data |
| Layer 2 | Yes / Partial / No per feature | Documentation review + hands-on verification |
| Layer 3 per-stage | Capability tier + performance metrics | Automated pipeline execution |
| Layer 3 cross-cutting | 1-5 Likert (aggregated) | Computed from per-stage metrics using formulas above |

---

## Completeness Mapping

Every dimension from the original project notes maps to a specific layer:

| Original Note | Layer |
|---------------|-------|
| Industry readiness | Layer 1 |
| Set of functionalities (yes/no/partial) | Layer 2 |
| Characterizing features | Layer 2 |
| A2A, MCP, Openness | Layer 2 (system-level) |
| Requirements engineering | Layer 3 Stage 1 |
| Design (UML) | Layer 3 Stage 1 (folded into Requirements & Design) |
| Code generation | Layer 3 Stage 2 |
| Test generation | Layer 3 Stage 3 |
| Building and deploying | Layer 3 Stage 4 |
| Token usage | Layer 3 (per-stage + aggregated into Efficiency) |

---

## Academic Grounding

- **DESMET methodology** (Kitchenham et al.): Hybrid evaluation = Benchmarking + Qualitative Screening
- **Broccia et al. (ISTI-TR-2025/011)**: System-level + Interaction-level feature comparison framework, extended in Layer 2
- **Ferrari et al.**: Precedent for combining benchmarking with usability analysis in systematic tool evaluation
- **Pipeline approach**: Extends Broccia et al.'s example scenario (interview → requirements → UML → code) to a full systematic cross-platform comparison
