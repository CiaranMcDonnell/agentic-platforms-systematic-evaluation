# DESMET Agentic Platforms Evaluation Pipeline

## Complete Specification Document

**Version:** 1.0
**Author:** Ciaran McDonnell
**Project:** Systematic Evaluation of Agentic Platforms
**Supervisor:** Alessio Ferrari

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Pipeline Overview](#pipeline-overview)
3. [Stage 0: Framework Setup & Onboarding](#stage-0-framework-setup--onboarding)
4. [Stage 1: Requirements Engineering](#stage-1-requirements-engineering)
5. [Stage 2: Requirements User Stories](#stage-2-requirements-user-stories)
6. [Stage 3: Code Generation](#stage-3-code-generation)
7. [Stage 4: Testing Generation](#stage-4-testing-generation)
8. [Stage 5: Building and Deploying](#stage-5-building-and-deploying)
9. [Cross-Cutting Evaluation Dimensions](#cross-cutting-evaluation-dimensions)
10. [Traceability Matrix](#traceability-matrix)
11. [Evaluation Scoring Framework](#evaluation-scoring-framework)

---

## Executive Summary

This document specifies the complete evaluation pipeline for systematically comparing agentic platforms using the DESMET methodology. The pipeline consists of **six sequential stages** that mirror the software development lifecycle, plus **seven cross-cutting evaluation dimensions** that are assessed continuously throughout execution.

### Pipeline at a Glance

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DESMET AGENTIC PLATFORMS EVALUATION PIPELINE             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │   Stage 0    │   │   Stage 1    │   │   Stage 2    │   │   Stage 3    │ │
│  │   Framework  │──►│ Requirements │──►│    User      │──►│     Code     │ │
│  │   Setup &    │   │ Engineering  │   │   Stories    │   │  Generation  │ │
│  │  Onboarding  │   │              │   │              │   │              │ │
│  └──────────────┘   └──────────────┘   └──────────────┘   └──────┬───────┘ │
│                                                                   │         │
│                     ┌─────────────────────────────────────────────┘         │
│                     │                                                       │
│                     ▼                                                       │
│               ┌──────────────┐   ┌──────────────┐                          │
│               │   Stage 4    │   │   Stage 5    │                          │
│               │   Testing    │──►│  Building &  │                          │
│               │  Generation  │   │  Deploying   │                          │
│               └──────────────┘   └──────────────┘                          │
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
| Multi-Agent Frameworks | LangGraph, CrewAI, Microsoft AutoGen |
| Agent SDK Runtimes | OpenAI Agents SDK, Google ADK, Semantic Kernel |
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
│  Framework    ──►  Requirements  ──►  User      ──►  Implementation      │
│  Documentation     Catalogue         Stories        Artifacts            │
│                                                                           │
│  Platform     ──►  Evaluation   ──►  Scoring    ──►  Test Suites         │
│  Capabilities      Plan             Rubrics                              │
│                                                                           │
│  SWE Tasks    ──►  NFR List     ──►  Gherkin    ──►  Build Artifacts     │
│  (Realistic)                        Scenarios                            │
│                                                                           │
│  Stakeholder  ──►  Traceability ──►  Comparison ──►  Deployment          │
│  Context           Matrix           Harness        Evidence              │
│                                                                           │
│                                                     ──►  DESMET Report   │
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

## Stage 1: Requirements Engineering

### Purpose

Define what constitutes a successful evaluation by establishing clear, testable requirements that apply uniformly across all platforms. This stage creates the foundation for fair comparison.

### Rationale

Without explicit requirements:
- Evaluations become subjective and inconsistent
- Platforms may be judged on different criteria
- Results cannot be reproduced or validated
- Gaps in coverage go unnoticed

### What This Stage Covers

#### 1. Evaluation Scope Definition

Define precisely what "agentic framework" means for this study:

| Dimension | Scope |
|-----------|-------|
| **Agent Capabilities** | Reasoning, planning, tool use, memory, multi-agent coordination |
| **Tool Integration** | File I/O, shell execution, API calls, database access |
| **Orchestration** | Sequential, parallel, hierarchical, conversational patterns |
| **Memory Types** | Short-term (context), long-term (persistence), shared (multi-agent) |
| **Observability** | Logging, tracing, debugging, replay |
| **Deployment** | Local, containerized, cloud-hosted options |

#### 2. Stakeholder & Context Identification

| Stakeholder | Role | Key Concerns |
|-------------|------|--------------|
| Evaluator (you) | Developer/researcher | Fair comparison, reproducibility, evidence collection |
| Target Organization | Hypothetical adopter | Capability fit, learning curve, operational cost |
| End Developer | Framework user | Developer experience, documentation, debugging |
| Operations | Deployment/maintenance | Reliability, observability, security |

| Constraint | Description |
|------------|-------------|
| Time | Academic year timeline |
| Budget | Limited API credits |
| Infrastructure | Local development machine + cloud APIs |
| Access | Public/open-source platforms only |

#### 3. Requirements Sources

| Source | What It Provides |
|--------|------------------|
| Academic literature | Established evaluation criteria, DESMET methodology |
| Framework documentation | Claimed capabilities, intended use cases |
| Industry surveys | Real-world usage patterns, pain points |
| SWE workflow analysis | Realistic task scenarios |
| Prior evaluations | Lessons learned, gaps to address |

#### 4. Functional Requirements

Requirements for what the frameworks must be able to **do**:

| Category | Example Requirements |
|----------|---------------------|
| Code Generation | Generate syntactically correct code from specifications |
| Code Modification | Edit existing code while preserving functionality |
| Testing | Generate meaningful tests with assertions |
| Tool Use | Invoke external tools and process results |
| Multi-Step Reasoning | Decompose complex tasks into subtasks |
| Error Handling | Detect failures and attempt recovery |

#### 5. Non-Functional Requirements

Requirements for **how well** the frameworks perform:

| Category | Example Requirements |
|----------|---------------------|
| Performance | Complete tasks within time budgets |
| Reliability | Produce consistent results across runs |
| Usability | Provide clear interfaces and documentation |
| Observability | Enable inspection of agent decisions |
| Security | Respect permission boundaries |
| Maintainability | Support debugging and iteration |

#### 6. Acceptance Criteria & Measurement

For each requirement, define:
- **What counts as success** (binary or graduated)
- **How to score it** (rubric or metric)
- **How to log evidence** (artifacts to collect)

### Requirements

| Req ID | Requirement | Priority | Rationale |
|--------|-------------|----------|-----------|
| S1-R01 | Define evaluation scope document | Critical | Scopes the study |
| S1-R02 | Identify all stakeholders and constraints | Critical | Context for evaluation |
| S1-R03 | Create functional requirements catalogue | Critical | What to test |
| S1-R04 | Create non-functional requirements list | Critical | How to judge quality |
| S1-R05 | Define acceptance criteria per requirement | Critical | Success definition |
| S1-R06 | Define measurement method per requirement | Critical | Evidence collection |
| S1-R07 | Assign priorities to all requirements | High | Focus limited resources |
| S1-R08 | Map requirements to evaluation tasks | Critical | Traceability |

### Outputs

| Output | Description | Format |
|--------|-------------|--------|
| Requirements Catalogue | Complete list of functional requirements with IDs, descriptions, priorities, rationale | Structured document |
| Non-Functional Requirements List | Quality attributes with measurable criteria | Structured document |
| Evaluation Plan | Mapping of requirements → tasks → metrics | Matrix/table |
| Acceptance Criteria Document | Success definitions per requirement | Structured document |
| Measurement Protocol | How each metric will be collected | Procedural document |

### Evidence Artifacts

```
evaluation/
├── requirements/
│   ├── scope_definition.md
│   ├── stakeholder_analysis.md
│   ├── functional_requirements.json
│   ├── non_functional_requirements.json
│   ├── acceptance_criteria.json
│   └── evaluation_plan.md
```

---

## Stage 2: Requirements User Stories

### Purpose

Translate abstract requirements into concrete, executable user stories that each framework will attempt to complete. These stories form the **benchmark tasks** for the evaluation.

### Rationale

User stories provide:
- Realistic, scenario-based evaluation tasks
- Clear success criteria via acceptance tests
- Graduated difficulty for nuanced comparison
- Standardized basis for fair comparison

### What This Stage Covers

#### 1. Story Translation

Convert each functional requirement into one or more user stories:

```
Requirement: "Framework must generate correct code from specifications"
                              ↓
User Story: "As a developer, I want to generate a REST API endpoint
            from a natural language description, so that I can
            quickly scaffold new features"
```

#### 2. Gherkin-Style Acceptance Criteria

Each story includes testable scenarios:

```gherkin
Feature: REST API Endpoint Generation

  Scenario: Generate a simple GET endpoint
    Given a codebase with an existing FastAPI application
    And the specification "Create a GET endpoint at /users that returns a list of users"
    When I invoke the agent with this specification
    Then the agent creates a new route file or modifies existing routes
    And the endpoint responds to GET /users with status 200
    And the response is valid JSON containing a list

  Scenario: Generate endpoint with path parameters
    Given a codebase with an existing FastAPI application
    And the specification "Create a GET endpoint at /users/{id} that returns a single user"
    When I invoke the agent with this specification
    Then the endpoint accepts an id path parameter
    And the endpoint returns a user object when given a valid id
    And the endpoint returns 404 for invalid ids
```

#### 3. Story Difficulty Levels

| Level | Characteristics | Example |
|-------|-----------------|---------|
| **Basic** | Single file, isolated change, clear specification | Add a utility function |
| **Intermediate** | Multi-file, requires understanding context, includes tests | Add a new API endpoint with validation |
| **Advanced** | Cross-cutting concerns, architectural impact, CI/CD implications | Implement authentication system |

#### 4. Standardized Constraints

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

#### 5. Scoring Rubrics

Each story is scored on multiple dimensions:

| Dimension | 0 Points | 1 Point | 2 Points | 3 Points |
|-----------|----------|---------|----------|----------|
| **Correctness** | Does not compile/run | Runs but wrong behavior | Mostly correct, minor issues | Fully correct |
| **Completeness** | No meaningful output | Partial implementation | Most requirements met | All requirements met |
| **Code Quality** | Unreadable/unmaintainable | Poor style, no structure | Acceptable quality | Clean, idiomatic code |
| **Test Quality** | No tests | Tests exist but trivial | Tests cover main paths | Comprehensive tests |
| **Time Efficiency** | Exceeded budget by 2x+ | Exceeded budget | Met budget | Under budget |
| **Autonomy** | Required constant intervention | Frequent intervention | Occasional intervention | Fully autonomous |

### Requirements

| Req ID | Requirement | Priority | Rationale |
|--------|-------------|----------|-----------|
| S2-R01 | Create user stories for all functional requirements | Critical | Test coverage |
| S2-R02 | Add Gherkin acceptance criteria to each story | Critical | Testable success criteria |
| S2-R03 | Categorize stories by difficulty level | High | Graduated evaluation |
| S2-R04 | Define standardized constraints document | Critical | Fair comparison |
| S2-R05 | Create scoring rubric per story | Critical | Consistent scoring |
| S2-R06 | Prepare baseline repository | Critical | Reproducibility |
| S2-R07 | Document exact prompt templates | Critical | Reproducibility |
| S2-R08 | Define intervention protocol | High | Consistent handling |

### Outputs

| Output | Description | Format |
|--------|-------------|--------|
| Story Backlog | Complete list of stories with IDs, descriptions, acceptance criteria | Structured document |
| Gherkin Feature Files | Executable acceptance tests | `.feature` files |
| Comparison Harness Document | Rules of engagement, scoring rubrics, constraints | Markdown |
| Baseline Repository | Clean starting codebase for all evaluations | Git repository |
| Prompt Templates | Standardized prompts for each story | Text files |

### Evidence Artifacts

```
evaluation/
├── stories/
│   ├── backlog.json                  # All stories with metadata
│   ├── features/                     # Gherkin feature files
│   │   ├── US001_simple_endpoint.feature
│   │   ├── US002_crud_operations.feature
│   │   └── ...
│   ├── comparison_harness.md         # Rules and rubrics
│   ├── prompts/                      # Prompt templates
│   │   ├── US001_prompt.txt
│   │   └── ...
│   └── baseline_repo/                # Starting codebase
```

---

## Stage 3: Code Generation

### Purpose

Execute user stories using each agentic framework and collect evidence of their performance. This is the primary **capability evaluation** stage.

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

## Stage 4: Testing Generation

### Purpose

Evaluate each framework's ability to generate meaningful tests for the implementations created in Stage 3. Testing is a critical software engineering activity that validates correctness.

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

## Stage 5: Building and Deploying

### Purpose

Verify that code changes produced by agentic frameworks can actually be built and deployed. This validates **practical shippability** of agent-generated code.

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

---

*This document serves as the authoritative specification for the DESMET Agentic Platforms Evaluation Pipeline. All evaluation activities should reference and comply with this specification.*
