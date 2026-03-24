# DESMET Agentic Platforms Evaluation Pipeline

## Complete Specification Document

**Version:** 2.0
**Author:** Ciaran McDonnell
**Project:** Systematic Evaluation of Agentic Platforms
**Supervisor:** Alessio Ferrari

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Pipeline Overview](#pipeline-overview)
3. [Stage 0: Framework Setup & Onboarding](#stage-0-framework-setup--onboarding)
4. [Stage 1: User Stories](#stage-1-user-stories)
5. [Stage 2: Requirements Engineering](#stage-2-requirements-engineering)
6. [Stage 3: Code Generation](#stage-3-code-generation)
7. [Stage 4: Testing](#stage-4-testing)
8. [Stage 5: Build & Deploy](#stage-5-build--deploy)
9. [Cross-Cutting Evaluation Dimensions](#cross-cutting-evaluation-dimensions)
10. [Traceability Matrix](#traceability-matrix)
11. [Evaluation Scoring Framework](#evaluation-scoring-framework)

---

## Executive Summary

This document specifies the complete evaluation pipeline for systematically comparing agentic platforms using the DESMET methodology. The pipeline follows a **stories-first, adapter-centric design**: benchmark user stories are the fixed ground-truth inputs, and each platform adapter is evaluated on its ability to generate requirements, code, tests, and deployable artifacts from those stories. The pipeline consists of **six sequential stages** that mirror the software development lifecycle, plus **seven cross-cutting evaluation dimensions** that are assessed continuously throughout execution. Each platform is evaluated at every SDLC stage (Stages 2--5) through a uniform adapter interface.

### Pipeline at a Glance

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DESMET AGENTIC PLATFORMS EVALUATION PIPELINE             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │   Stage 0    │   │   Stage 1    │   │   Stage 2    │   │   Stage 3    │ │
│  │   Framework  │──►│    User      │──►│ Requirements │──►│     Code     │ │
│  │   Setup &    │   │   Stories    │   │ Engineering  │   │  Generation  │ │
│  │  Onboarding  │   │  (fixed)     │   │ (per-platform│   │              │ │
│  └──────────────┘   └──────────────┘   └──────────────┘   └──────┬───────┘ │
│                                                                   │         │
│                     ┌─────────────────────────────────────────────┘         │
│                     │                                                       │
│                     ▼                                                       │
│               ┌──────────────┐   ┌──────────────┐                          │
│               │   Stage 4    │   │   Stage 5    │                          │
│               │   Testing    │──►│   Build &    │                          │
│               │              │   │   Deploy     │                          │
│               └──────────────┘   └──────────────┘                          │
│                                                                             │
│  Stories are fixed benchmark inputs; each platform adapter is evaluated     │
│  at Stages 2-5 on how it processes stories through the SDLC.               │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                     CROSS-CUTTING EVALUATION DIMENSIONS                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │Effectiveness│ │ Efficiency  │ │   Quality   │ │Reproducibil.│           │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                           │
│  │Usability/DX │ │Observability│ │  Failure    │                           │
│  │             │ │& Debugging  │ │  Handling   │                           │
│  └─────────────┘ └─────────────┘ └─────────────┘                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Platforms Under Evaluation

| Category | Platforms |
|----------|-----------|
| Multi-Agent Frameworks | LangGraph, CrewAI, Microsoft Agent Framework |
| Agent SDK Runtimes | OpenAI Agents SDK, Google ADK |
| Visual/Workflow Platforms | Flowise, LangFlow, Dify, N8n |

---

## Pipeline Overview

### Purpose

The evaluation pipeline serves three primary objectives:

1. **Systematic Comparison** - Provide a fair, reproducible method for comparing agentic platforms across identical tasks
2. **Evidence Collection** - Generate quantitative and qualitative data for DESMET analysis
3. **Practical Guidance** - Produce actionable recommendations for practitioners selecting agentic tools

### Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Fairness** | Same tasks, same environment, same constraints for all platforms |
| **Reproducibility** | Standardized inputs, version-controlled artifacts, deterministic where possible |
| **Traceability** | Every requirement links to tasks, metrics, and evidence |
| **Comprehensiveness** | Covers full SDLC from setup through deployment |
| **Practicality** | Tasks represent realistic software engineering work |

### What "Agentic Framework" Means in This Study

For the purposes of this evaluation, an **agentic framework** is defined as a platform that provides:

| Capability | Description |
|------------|-------------|
| **Agent Abstraction** | Ability to define autonomous or semi-autonomous agents with goals |
| **Tool Integration** | Mechanisms for agents to interact with external tools (code execution, APIs, file systems) |
| **Orchestration** | Coordination of agent actions, including multi-step and multi-agent workflows |
| **Memory/State** | Persistence of context across interactions |
| **LLM Integration** | Connection to large language models for reasoning |
| **Observability** | Visibility into agent decisions and actions |

### Pipeline Data Flow

```
                    Inputs                          Outputs
                      │                               │
┌─────────────────────▼───────────────────────────────▼─────────────────────┐
│                                                                           │
│  User Stories  ──►  Requirements  ──►  Implementation ──►  Test Suites   │
│  (fixed YAML)      (per-platform)     Artifacts           (per-platform) │
│                                                                           │
│  Platform      ──►  UML Diagrams ──►  Scoring     ──►  Build Artifacts   │
│  Adapters           (per-platform)    Rubrics                            │
│                                                                           │
│  Framework     ──►  Gherkin      ──►  Comparison  ──►  Deployment        │
│  Documentation      Scenarios         Harness         Evidence           │
│                                                                           │
│  Evaluation    ──►  Traceability ──►  Per-stage   ──►  DESMET Report     │
│  Config             Matrix           Metrics                             │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## Stage 0: Framework Setup & Onboarding

### Purpose

Evaluate the effort, complexity, and friction involved in getting each agentic framework operational. This stage directly measures **fitness for use** - a powerful framework that is painful to set up incurs real adoption costs.

### Rationale

DESMET emphasizes evaluating tools in context. Setup complexity is often overlooked in capability comparisons but significantly impacts:
- Time-to-value for adopting organizations
- Required expertise level
- Hidden infrastructure dependencies
- Ongoing maintenance burden

### What This Stage Covers

#### 1. Installation & Configuration Effort

| Aspect | What to Evaluate |
|--------|------------------|
| Package installation | Single command vs multi-step, dependency conflicts |
| Runtime requirements | Python version, Node.js, Docker, system libraries |
| Configuration files | Amount of boilerplate, clarity of options |
| Service dependencies | Databases, message queues, external services required |

#### 2. Model & Provider Setup

| Aspect | What to Evaluate |
|--------|------------------|
| API key management | How keys are configured, secret handling |
| Model selection | Ease of switching models, multi-provider support |
| Quota/rate limit handling | Built-in handling vs manual implementation |
| Cost visibility | Token counting, cost estimation features |

#### 3. Learning Curve & Documentation Quality

| Aspect | What to Evaluate |
|--------|------------------|
| Getting started guide | Clarity, completeness, time to complete |
| API documentation | Comprehensiveness, accuracy, examples |
| Conceptual documentation | Explanation of core concepts and patterns |
| Community resources | Tutorials, Stack Overflow presence, Discord/Slack |

#### 4. Time-to-First-Agent

| Milestone | What to Measure |
|-----------|-----------------|
| Environment ready | Time from zero to dependencies installed |
| Configuration complete | Time to configure all required settings |
| Hello World agent | Time to first successful agent execution |
| Meaningful agent | Time to first agent that performs a useful task |

### Requirements

| Req ID | Requirement | Priority | Rationale |
|--------|-------------|----------|-----------|
| S0-R01 | Document installation steps for each platform | Critical | Reproducibility |
| S0-R02 | Measure time for each setup phase | Critical | Quantitative comparison |
| S0-R03 | Record all dependencies and versions | Critical | Reproducibility |
| S0-R04 | Document hidden assumptions discovered | High | Usability assessment |
| S0-R05 | Rate documentation quality (1-5 scale) | High | Qualitative comparison |
| S0-R06 | Record errors encountered and resolution time | High | Friction measurement |
| S0-R07 | Verify first agent runs successfully | Critical | Baseline functionality |

### Metrics

| Metric ID | Metric | Unit | Collection Method |
|-----------|--------|------|-------------------|
| S0-M01 | Time to environment ready | Minutes | Stopwatch |
| S0-M02 | Time to first agent | Minutes | Stopwatch |
| S0-M03 | Manual steps required | Count | Documented steps |
| S0-M04 | Documentation clarity score | 1-5 | Evaluator rating |
| S0-M05 | Errors during setup | Count | Log |
| S0-M06 | Dependencies count | Count | Package manifest |
| S0-M07 | Required services | Count | Documentation review |

### Outputs

| Output | Description | Format |
|--------|-------------|--------|
| Setup log | Timestamped record of all setup actions | Markdown |
| Dependency manifest | Complete list of installed packages and versions | JSON |
| Configuration files | Sanitized copies of all configuration | Various |
| First agent code | Minimal working agent for each platform | Source code |
| Setup scorecard | Ratings and measurements | Structured data |

### Evidence Artifacts

```
platforms/{framework}/
├── setup/
│   ├── setup_log.md           # Timestamped setup narrative
│   ├── dependencies.json      # Package versions
│   ├── config/                # Configuration files (sanitized)
│   ├── hello_world_agent/     # First working agent
│   └── setup_scorecard.json   # Metrics and ratings
```

---

## Stage 1: User Stories

### Purpose

Load benchmark user stories that serve as the fixed, ground-truth inputs for the entire evaluation pipeline. Stories are predefined in YAML and are **not generated by the platforms under test** -- they are the standardised tasks that every platform must process.

### Rationale

By making stories the fixed starting point (rather than deriving them from generated requirements), the evaluation achieves:
- **Fairness** -- every platform receives identical inputs
- **Reproducibility** -- stories are version-controlled YAML, not LLM output
- **Traceability** -- all downstream artifacts trace back to a known story ID
- **Graduated difficulty** -- basic / intermediate / advanced tiers are curated upfront

### What This Stage Covers

#### 1. Story Loading & Validation

Load user stories from `data/stories/` YAML files and validate their schema:

| Field | Description |
|-------|-------------|
| `story_id` | Unique identifier (e.g. `US-001`) |
| `title` | Short descriptive title |
| `description` | Full user story text (As a ... I want ... So that ...) |
| `difficulty` | `basic`, `intermediate`, or `advanced` |
| `acceptance_criteria` | List of testable Gherkin-style scenarios |
| `constraints` | Time budget, tool access, model limits |

#### 2. Story Difficulty Levels

| Level | Characteristics | Example |
|-------|-----------------|---------|
| **Basic** | Single file, isolated change, clear specification | Add a utility function |
| **Intermediate** | Multi-file, requires understanding context, includes tests | Add a new API endpoint with validation |
| **Advanced** | Cross-cutting concerns, architectural impact, CI/CD implications | Implement authentication system |

#### 3. Standardized Constraints

To ensure fair comparison, all stories execute under identical conditions:

| Constraint | Specification |
|------------|---------------|
| **Repository** | Same starting codebase for all platforms |
| **Environment** | Identical development environment (Docker/devcontainer) |
| **Starting State** | Clean git state, all tests passing |
| **Instructions** | Identical prompt/specification text |
| **Time Budget** | Maximum wall-clock time per story |
| **Tool Access** | Same tools available (shell, file I/O, package manager) |
| **Model Access** | Same LLM models and API limits |
| **Human Intervention** | Logged but minimized; same intervention protocol |

#### 4. Context Preparation

The story loader prepares a `StageContext` for downstream stages, containing:
- Parsed story data (title, description, acceptance criteria)
- Difficulty tier metadata
- File paths to the YAML source
- Prompt template for the story

### Requirements

| Req ID | Requirement | Priority | Rationale |
|--------|-------------|----------|-----------|
| S1-R01 | Load and validate all benchmark stories from YAML | Critical | Pipeline input |
| S1-R02 | Include Gherkin acceptance criteria per story | Critical | Testable success criteria |
| S1-R03 | Categorize stories by difficulty level | High | Graduated evaluation |
| S1-R04 | Prepare StageContext for each story | Critical | Downstream stage input |
| S1-R05 | Validate story schema on load | High | Fail fast on bad input |
| S1-R06 | Document exact prompt templates per story | Critical | Reproducibility |

### Outputs

| Output | Description | Format |
|--------|-------------|--------|
| Loaded Stories | Validated story objects with metadata | Python dataclass / dict |
| StageContext | Per-story context passed to Stage 2 | `StageContext` object |
| Story Index | Summary of loaded stories by difficulty tier | JSON |

### Evidence Artifacts

```
data/stories/
├── basic/
│   ├── US001_simple_endpoint.yaml
│   ├── US002_utility_function.yaml
│   └── ...
├── intermediate/
│   ├── US010_crud_api.yaml
│   └── ...
└── advanced/
    ├── US020_auth_system.yaml
    └── ...
```

---

## Stage 2: Requirements Engineering

### Purpose

Each platform adapter generates requirements and UML diagrams **from** the user stories loaded in Stage 1. This is the first stage where platforms are actively evaluated -- they must demonstrate their ability to analyse stories, derive functional and non-functional requirements, and produce structured specification artifacts.

### Rationale

Requirements engineering is an early SDLC activity. By asking each platform to generate requirements from the same stories, we evaluate:
- Comprehension of user story intent
- Ability to produce structured, traceable requirements
- Quality of generated UML / architectural diagrams
- Completeness and consistency of the requirements set

### What This Stage Covers

#### 1. Requirements Generation (per-platform)

Each platform adapter receives the story context and must produce:

| Artifact | Description |
|----------|-------------|
| **Functional Requirements** | What the system must do, derived from the story |
| **Non-Functional Requirements** | Quality attributes (performance, security, etc.) |
| **UML Diagrams** | Class diagrams, sequence diagrams, or component diagrams |
| **Acceptance Criteria Mapping** | How requirements map back to story acceptance criteria |

#### 2. Requirements Quality Assessment

| Dimension | What to Evaluate |
|-----------|------------------|
| **Completeness** | Do requirements cover all story acceptance criteria? |
| **Consistency** | Are requirements free of contradictions? |
| **Traceability** | Can each requirement be traced to a story element? |
| **Clarity** | Are requirements unambiguous and testable? |
| **Granularity** | Are requirements at the right level of detail? |

#### 3. UML Quality Assessment

| Dimension | What to Evaluate |
|-----------|------------------|
| **Correctness** | Does the diagram accurately represent the requirements? |
| **Completeness** | Are all key entities and relationships shown? |
| **Notation** | Does the diagram follow standard UML notation? |
| **Readability** | Is the diagram easy to understand? |

### Requirements

| Req ID | Requirement | Priority | Rationale |
|--------|-------------|----------|-----------|
| S2-R01 | Platform generates functional requirements from stories | Critical | Core evaluation |
| S2-R02 | Platform generates non-functional requirements | High | Completeness |
| S2-R03 | Platform produces UML diagrams | High | Architectural thinking |
| S2-R04 | Requirements trace back to story acceptance criteria | Critical | Traceability |
| S2-R05 | Assess requirements quality per rubric | Critical | Consistent scoring |
| S2-R06 | Capture generation time and token usage | High | Efficiency measurement |

### Metrics

| Metric ID | Metric | Unit | Collection |
|-----------|--------|------|------------|
| S2-M01 | Requirements completeness | Percentage | Coverage analysis |
| S2-M02 | Requirements consistency | Pass/Fail | Contradiction check |
| S2-M03 | UML correctness score | 0-3 | Rubric assessment |
| S2-M04 | Generation time | Seconds | Stopwatch |
| S2-M05 | Tokens consumed | Count | API response |

### Outputs

| Output | Description | Format |
|--------|-------------|--------|
| Requirements Catalogue | Generated functional + non-functional requirements | JSON |
| UML Diagrams | Generated architectural diagrams | PNG/SVG/Mermaid |
| Quality Assessment | Rubric scores for requirements quality | JSON |
| Stage Metrics | Time, tokens, iteration count | `StageResult` |

### Evidence Artifacts

```
results/{platform}/{story_id}/
├── stage2_requirements/
│   ├── functional_requirements.json
│   ├── non_functional_requirements.json
│   ├── uml_diagrams/
│   │   ├── class_diagram.png
│   │   └── sequence_diagram.png
│   ├── quality_assessment.json
│   └── stage_metrics.json
```

---

## Stage 3: Code Generation

### Purpose

Each platform adapter implements code from the user story and the requirements generated in Stage 2. This is the primary **capability evaluation** stage.

### Rationale

Code generation is the core task that agentic frameworks claim to assist with. This stage produces:
- Direct comparison of implementation capability
- Quantitative performance data
- Qualitative assessment of output quality
- Evidence of agent behavior patterns

### What This Stage Covers

#### 1. Standardized Interaction Protocol

Every framework receives the same treatment:

| Aspect | Protocol |
|--------|----------|
| **Prompt Template** | Identical specification text, structured consistently |
| **Tool Access** | Same set: file read/write, shell execution, package manager, git |
| **Retry Policy** | Maximum 3 retries on failure, then record as failed |
| **Iteration Limit** | Maximum agent turns/messages before timeout |
| **Time Budget** | Wall-clock limit per story (e.g., 10 minutes basic, 30 minutes advanced) |
| **Human Intervention** | Logged with timestamp, reason, and action taken |

#### 2. Evidence Capture

| Evidence Type | What to Capture |
|---------------|-----------------|
| **Iteration Count** | Number of agent turns/messages to completion |
| **Tool Calls** | Count and types of tool invocations |
| **Time** | Wall-clock total, active human time, LLM response time |
| **Token Usage** | Input and output tokens consumed |
| **Autonomy Indicators** | Did agent plan? Decompose tasks? Ask clarifying questions? |
| **Errors** | Errors encountered, recovery attempts, final state |

#### 3. Output Assessment

| Dimension | Assessment Method |
|-----------|-------------------|
| **Functional Correctness** | Acceptance tests pass/fail |
| **Syntactic Correctness** | Code compiles/parses without errors |
| **Behavioral Correctness** | Manual verification of edge cases |
| **Completeness** | All story requirements addressed |

#### 4. Maintainability Quality

| Aspect | What to Evaluate |
|--------|------------------|
| **Structure** | Appropriate file organization, separation of concerns |
| **Naming** | Clear, consistent, conventional naming |
| **Style** | Adherence to language idioms and project conventions |
| **Documentation** | Comments where needed, README updates |
| **Error Handling** | Appropriate error handling added |

#### 5. Agent Behavior Analysis

| Behavior | Questions to Answer |
|----------|---------------------|
| **Planning** | Did the agent create a plan before acting? |
| **Decomposition** | Did it break complex tasks into subtasks? |
| **Verification** | Did it check its work (run tests, verify changes)? |
| **Recovery** | How did it respond to errors? |
| **Communication** | Were clarifying questions appropriate? |

### Requirements

| Req ID | Requirement | Priority | Rationale |
|--------|-------------|----------|-----------|
| S3-R01 | Execute all stories on all platforms | Critical | Comprehensive evaluation |
| S3-R02 | Use identical prompts across platforms | Critical | Fair comparison |
| S3-R03 | Capture all specified evidence | Critical | Data for analysis |
| S3-R04 | Apply standardized retry/timeout policy | Critical | Consistent handling |
| S3-R05 | Log all human interventions | Critical | Autonomy measurement |
| S3-R06 | Assess functional correctness via tests | Critical | Objective measurement |
| S3-R07 | Evaluate code quality per rubric | High | Qualitative assessment |
| S3-R08 | Produce per-story agent run report | Critical | Documented evidence |

### Metrics

| Metric ID | Metric | Unit | Collection |
|-----------|--------|------|------------|
| S3-M01 | Correctness score | 0-3 | Rubric assessment |
| S3-M02 | Completeness score | 0-3 | Rubric assessment |
| S3-M03 | Code quality score | 0-3 | Rubric assessment |
| S3-M04 | Iterations to completion | Count | Agent log |
| S3-M05 | Tool calls | Count | Agent log |
| S3-M06 | Wall-clock time | Seconds | Stopwatch |
| S3-M07 | Human interventions | Count | Manual log |
| S3-M08 | Tokens consumed | Count | API response |
| S3-M09 | Acceptance tests passed | Percentage | Test runner |

### Outputs

| Output | Description | Format |
|--------|-------------|--------|
| Implementation Branches | Code produced per framework per story | Git branches |
| Execution Logs | Full agent traces and console output | Log files |
| Agent Run Reports | Structured summary per story execution | JSON + Markdown |
| Metrics Dataset | All measurements in analyzable format | CSV/JSON |

### Evidence Artifacts

```
platforms/{framework}/
├── stories/
│   ├── US001/
│   │   ├── implementation/        # Code changes
│   │   ├── execution_log.txt      # Full agent trace
│   │   ├── run_report.json        # Structured metrics
│   │   ├── run_report.md          # Human-readable summary
│   │   └── commits.log            # Git commit history
│   ├── US002/
│   │   └── ...
│   └── metrics_summary.csv        # All story metrics
```

---

## Stage 4: Testing

### Purpose

Evaluate each platform adapter's ability to generate meaningful tests for the implementations created in Stage 3, and verify that those tests pass. Testing is a critical software engineering activity that validates correctness.

### Rationale

Tests serve multiple purposes:
- Verify implementation correctness
- Prevent regressions
- Document intended behavior
- Enable confident refactoring

A framework that generates code but not tests is only partially useful.

### What This Stage Covers

#### 1. Test Generation Task

For each story implementation, the agent must:
- Generate or extend tests (unit/integration/e2e as appropriate)
- Follow project testing conventions
- Integrate with existing test infrastructure

#### 2. Test Validity Assessment

| Check | Description |
|-------|-------------|
| **Fail-Before-Pass** | Tests fail on buggy code, pass on correct code |
| **Meaningful Assertions** | Tests actually check behavior, not just run |
| **Not Tautological** | Tests aren't always-pass or always-fail |
| **Coverage Contribution** | Tests exercise new/changed code |

#### 3. Test Quality Dimensions

| Dimension | What to Evaluate |
|-----------|------------------|
| **Coverage** | Statement and branch coverage contribution |
| **Mutation Resistance** | Would tests catch common wrong implementations? |
| **Determinism** | Tests produce consistent results |
| **Isolation** | Tests don't depend on external state |
| **Readability** | Tests are understandable and maintainable |
| **Performance** | Tests run in reasonable time |

#### 4. CI/CD Compatibility

| Aspect | What to Verify |
|--------|----------------|
| **Runner Integration** | Tests work with project's test runner |
| **CI Configuration** | CI pipeline runs new tests correctly |
| **Reporting** | Test results are properly reported |

### Requirements

| Req ID | Requirement | Priority | Rationale |
|--------|-------------|----------|-----------|
| S4-R01 | Generate tests for all story implementations | Critical | Complete evaluation |
| S4-R02 | Verify tests fail before fix / pass after | Critical | Test validity |
| S4-R03 | Measure coverage contribution | High | Quantitative quality |
| S4-R04 | Assess test quality per rubric | High | Qualitative assessment |
| S4-R05 | Verify CI compatibility | High | Practical usability |
| S4-R06 | Check for flaky tests | High | Reliability |
| S4-R07 | Document test generation evidence | Critical | Reproducibility |

### Metrics

| Metric ID | Metric | Unit | Collection |
|-----------|--------|------|------------|
| S4-M01 | Tests generated | Count | File analysis |
| S4-M02 | Tests passing | Count | Test runner |
| S4-M03 | Coverage delta | Percentage | Coverage tool |
| S4-M04 | Flaky tests | Count | Multiple runs |
| S4-M05 | Test quality score | 0-3 | Rubric |
| S4-M06 | Assertions per test | Average | Static analysis |

### Outputs

| Output | Description | Format |
|--------|-------------|--------|
| Test Suites | Generated tests per framework/story | Source code |
| Test Quality Notes | Assessment of test meaningfulness | Markdown |
| Coverage Reports | Before/after coverage comparison | HTML/JSON |
| CI Logs | Test execution in CI environment | Log files |

### Evidence Artifacts

```
platforms/{framework}/
├── stories/
│   ├── US001/
│   │   ├── tests/                 # Generated test files
│   │   ├── coverage_before.json   # Coverage before changes
│   │   ├── coverage_after.json    # Coverage after tests
│   │   ├── test_results.json      # Test runner output
│   │   └── test_quality.md        # Quality assessment
│   └── ...
```

---

## Stage 5: Build & Deploy

### Purpose

Verify that code changes produced by each platform adapter can actually be built and deployed. This validates **practical shippability** of agent-generated code.

### Rationale

Code that works locally but fails in CI/CD is incomplete. This stage evaluates:
- Build system compatibility
- CI pipeline awareness
- Deployment artifact production
- Operational readiness

### What This Stage Covers

#### 1. Build Verification

| Aspect | What to Verify |
|--------|----------------|
| **Compilation/Bundling** | Code builds without errors |
| **Dependency Resolution** | All dependencies are correctly specified |
| **Build Artifacts** | Expected outputs are produced |
| **Build Time** | Build completes in reasonable time |

#### 2. Packaging & Containerization

| Aspect | What to Evaluate |
|--------|------------------|
| **Docker Builds** | Dockerfiles build successfully |
| **Container Runs** | Containers start and run correctly |
| **Size Efficiency** | Images aren't unnecessarily large |
| **Layer Optimization** | Good layer caching practices |

#### 3. Environment & Secrets Handling

| Aspect | What to Evaluate |
|--------|------------------|
| **Configuration** | Environment variables properly used |
| **Secrets** | No secrets committed, proper handling documented |
| **Environment Parity** | Dev/staging/prod differences addressed |

#### 4. CI/CD Integration

| Aspect | What to Verify |
|--------|----------------|
| **Pipeline Updates** | CI config modified correctly if needed |
| **All Checks Pass** | Linting, tests, build all pass in CI |
| **Release Process** | Versioning/changelog handled appropriately |

#### 5. Operational Readiness

| Aspect | What to Evaluate |
|--------|------------------|
| **Health Checks** | Endpoints for liveness/readiness |
| **Logging** | Appropriate logging for operations |
| **Monitoring** | Metrics exposure if applicable |
| **Rollback** | Clear rollback procedure |

### Requirements

| Req ID | Requirement | Priority | Rationale |
|--------|-------------|----------|-----------|
| S5-R01 | Verify all implementations build successfully | Critical | Basic shippability |
| S5-R02 | Verify CI pipeline passes | Critical | Integration quality |
| S5-R03 | Assess Docker/container builds if applicable | High | Deployment readiness |
| S5-R04 | Check secrets handling | High | Security |
| S5-R05 | Verify deployment artifacts produced | High | Complete delivery |
| S5-R06 | Document operational considerations | Medium | Practical guidance |

### Metrics

| Metric ID | Metric | Unit | Collection |
|-----------|--------|------|------------|
| S5-M01 | Build success rate | Percentage | CI logs |
| S5-M02 | CI pass rate | Percentage | CI logs |
| S5-M03 | Build time | Seconds | CI logs |
| S5-M04 | Container builds | Pass/Fail | Docker build |
| S5-M05 | Secrets exposed | Count | Automated scan |

### Outputs

| Output | Description | Format |
|--------|-------------|--------|
| Build Artifacts | Compiled outputs, packages | Various |
| Container Images | Docker images if applicable | Images |
| CI Logs | Complete CI pipeline logs | Log files |
| Deployment Evidence | Screenshots, URLs, health check results | Various |
| Operational Notes | Post-deploy verification results | Markdown |

### Evidence Artifacts

```
platforms/{framework}/
├── stories/
│   ├── US001/
│   │   ├── build/
│   │   │   ├── build_log.txt
│   │   │   └── artifacts/
│   │   ├── deploy/
│   │   │   ├── ci_log.txt
│   │   │   ├── health_check.json
│   │   │   └── screenshots/
│   │   └── operational_notes.md
│   └── ...
```

---

## Cross-Cutting Evaluation Dimensions

These dimensions are evaluated **continuously throughout all stages**, not just at a single point. They represent the DESMET quality criteria applied to agentic frameworks.

### Dimension 1: Effectiveness

**Definition:** Does the framework successfully accomplish the intended tasks?

| Indicator | Measurement |
|-----------|-------------|
| Task completion rate | Percentage of stories successfully completed |
| Functional correctness | Acceptance test pass rate |
| Requirement coverage | Percentage of requirements addressable |
| Goal achievement | Did the agent achieve the stated objective? |

### Dimension 2: Efficiency

**Definition:** How much resource (time, tokens, human effort) is consumed?

| Indicator | Measurement |
|-----------|-------------|
| Time efficiency | Wall-clock time per task |
| Token efficiency | Tokens consumed per successful task |
| Iteration efficiency | Agent turns per successful task |
| Human effort | Intervention count and duration |
| Cost efficiency | API cost per successful task |

### Dimension 3: Quality

**Definition:** How good is the output beyond mere correctness?

| Indicator | Measurement |
|-----------|-------------|
| Code quality | Rubric scores for structure, naming, style |
| Test quality | Coverage, meaningfulness, reliability |
| Documentation | README updates, comments, clarity |
| Maintainability | Would a human want to maintain this code? |

### Dimension 4: Reproducibility

**Definition:** Can results be replicated consistently?

| Indicator | Measurement |
|-----------|-------------|
| Determinism | Same input produces same output? |
| Consistency | Variance across multiple runs |
| Version stability | Behavior across framework versions |
| Environment independence | Works across different machines |

### Dimension 5: Usability / Developer Experience

**Definition:** How pleasant and productive is the framework to use?

| Indicator | Measurement |
|-----------|-------------|
| Learning curve | Time to productivity (Stage 0) |
| Documentation quality | Clarity, completeness, accuracy |
| Error messages | Helpfulness when things go wrong |
| IDE integration | Editor support, autocomplete |
| API design | Intuitiveness, consistency |

### Dimension 6: Observability & Debugging

**Definition:** Can you understand what the agent is doing and why?

| Indicator | Measurement |
|-----------|-------------|
| State visibility | Can you inspect agent state? |
| Decision transparency | Are agent decisions explainable? |
| Tool call visibility | Can you see what tools were called and why? |
| Memory inspection | Can you examine agent memory? |
| Step-through debugging | Can you pause and step through execution? |
| Replay capability | Can you replay a previous execution? |
| Failure diagnosis | Can you determine why something failed? |

**Critical for DESMET because:**
- Agentic systems fail in non-obvious ways
- Debugging is essential for production use
- Trust requires transparency
- Maps to maintainability and operational risk

### Dimension 7: Failure Handling & Recovery

**Definition:** How gracefully does the framework handle and recover from failures?

| Indicator | Measurement |
|-----------|-------------|
| Failure detection | Does the agent know when it failed? |
| Self-correction | Can it fix its own mistakes? |
| Graceful degradation | Does it fail safely vs catastrophically? |
| Human handoff | Can a human intervene cleanly? |
| State recovery | Can you resume from a checkpoint? |
| Idempotency | Is it safe to retry? |
| Error surfacing | Are errors clearly communicated? |
| Partial completion | Is partial work preserved on failure? |

**Critical for DESMET because:**
- Real-world use involves failures
- Recovery capability determines reliability
- Silent failures are dangerous
- Maps directly to reliability and trust

### Optional: Security & Safety Boundaries

**Definition:** Does the framework respect safety constraints?

| Indicator | Measurement |
|-----------|-------------|
| Permission boundaries | File system, network, shell restrictions |
| Prompt injection resistance | Resilience to malicious inputs |
| Secrets handling | Proper credential management |
| Unsafe action prevention | Block destructive operations |
| Audit trail | Actions are logged for review |

---

## Traceability Matrix

The traceability matrix links requirements through stories to metrics and evidence, ensuring complete coverage.

### Structure

```
Requirement ──► User Story ──► Task ──► Metrics ──► Evidence Artifacts
```

### Example Traceability

| Req ID | Requirement | Story IDs | Metrics | Evidence |
|--------|-------------|-----------|---------|----------|
| FR-01 | Generate correct code from specs | US-001, US-002 | S3-M01, S3-M02 | implementation/, run_report.json |
| FR-02 | Modify existing code safely | US-003, US-004 | S3-M01, S3-M09 | implementation/, test_results.json |
| NFR-01 | Complete tasks within time budget | All | S3-M06 | execution_log.txt |
| NFR-02 | Produce maintainable code | All | S3-M03 | run_report.json, code review notes |
| NFR-03 | Enable debugging of agent behavior | All | Observability dimension | agent traces |

### Full Matrix Template

```
evaluation/
├── traceability/
│   ├── requirements_to_stories.json
│   ├── stories_to_metrics.json
│   ├── metrics_to_evidence.json
│   └── full_traceability_matrix.xlsx
```

---

## Evaluation Scoring Framework

### Overall Scoring Approach

Each platform receives scores across all dimensions, which are aggregated into an overall assessment.

### Scoring Scales

**Quantitative Metrics:** Normalized to 0-100 scale for comparison

**Qualitative Ratings:** 5-point Likert scale

| Score | Label | Description |
|-------|-------|-------------|
| 1 | Poor | Feature absent or severely deficient |
| 2 | Below Average | Feature present but with significant issues |
| 3 | Adequate | Feature functional with minor limitations |
| 4 | Good | Feature well-implemented with few limitations |
| 5 | Excellent | Feature exemplary, best-in-class |

### Dimension Weighting

Default equal weighting with sensitivity analysis for different use case priorities:

| Scenario | Effectiveness | Efficiency | Quality | Reproducibility | Usability | Observability | Failure Handling |
|----------|--------------|------------|---------|-----------------|-----------|---------------|------------------|
| Default | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| Rapid Prototyping | 1.5 | 1.5 | 0.5 | 0.5 | 1.5 | 0.5 | 0.5 |
| Production Deployment | 1.0 | 0.5 | 1.5 | 1.5 | 0.5 | 1.5 | 1.5 |
| Research/Experimentation | 1.5 | 0.5 | 0.5 | 1.5 | 1.0 | 1.5 | 0.5 |

### Aggregation Formula

```
Overall Score = Σ (Dimension Score × Weight) / Σ Weights
```

### Reporting Format

```
Platform: LangGraph
═══════════════════════════════════════════════════════════

Dimension Scores:
├── Effectiveness:      ████████░░ 4.2/5
├── Efficiency:         ███████░░░ 3.5/5
├── Quality:            ████████░░ 4.0/5
├── Reproducibility:    ███████░░░ 3.8/5
├── Usability:          ██████░░░░ 3.0/5
├── Observability:      █████████░ 4.5/5
└── Failure Handling:   ███████░░░ 3.5/5

Overall Score:          ███████░░░ 3.79/5

Key Strengths:
• Excellent agent state visibility and debugging
• Strong task completion rate
• Good code quality outputs

Key Weaknesses:
• Steeper learning curve
• Moderate efficiency on complex tasks
• Limited self-recovery capability
```

---

## Appendices

### Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Agent** | Autonomous software entity that perceives, reasons, and acts |
| **Agentic Framework** | Platform for building and orchestrating agents |
| **DESMET** | Methodology for evaluating software engineering tools |
| **Gherkin** | Language for writing acceptance test scenarios |
| **NFR** | Non-Functional Requirement (quality attribute) |
| **Story Points** | Relative effort estimation for user stories |
| **Traceability** | Ability to link requirements to implementation and tests |

### Appendix B: Tool Versions

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.13+ | SDK platforms |
| Node.js | 22+ LTS | Workflow platforms |
| Docker | 24+ | Containerization |
| Git | 2.40+ | Version control |

### Appendix C: Evidence Checklist

For each platform and story, collect:

- [ ] Execution log (full agent trace)
- [ ] Implementation code (git branch/tag)
- [ ] Run report (metrics JSON)
- [ ] Test results (pass/fail, coverage)
- [ ] Build log (CI output)
- [ ] Screenshots (if applicable)
- [ ] Human intervention log
- [ ] Quality assessment notes

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01 | Ciaran McDonnell | Initial specification |
| 2.0 | 2026-03 | Ciaran McDonnell | Stories-first restructure: stories are now Stage 1 (fixed inputs), requirements engineering is Stage 2 (per-platform generation). Adapter-centric design throughout. |

---

*This document serves as the authoritative specification for the DESMET Agentic Platforms Evaluation Pipeline. All evaluation activities should reference and comply with this specification.*
