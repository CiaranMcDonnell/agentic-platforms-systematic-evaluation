# Pipeline Restructure: Adapter-Centric SDLC Pipeline

**Date:** 2026-03-03
**Status:** Approved

## Problem

The current pipeline ordering (Stage 0: Setup → Stage 1: Requirements → Stage 2: Stories → ...) has requirements before stories. In practice, user stories are the ground truth and the real entry point. The pipeline should follow an agile SDLC flow where stories drive everything.

Additionally, the current adapter interface has a single `execute_story()` method, but each platform should be evaluated at every SDLC stage — not just code generation.

## Decision

Restructure to an adapter-centric pipeline where:
- User stories are the fixed benchmark input (Stage 1)
- Each subsequent stage evaluates the platform under test
- The adapter ABC gets one method per evaluated stage
- Stage modules become thin orchestrators; adapters own platform-specific logic

## New Pipeline Flow

```
Stage 0: Setup & Onboarding (pre-step, per-platform, run once)
    |
For each story:
    Stage 1: User Stories (harness loads YAML, prepares StageContext)
        | StoryContext
    Stage 2: Requirements (platform generates reqs + UML from story)
        | RequirementsResult
    Stage 3: Code Generation (platform implements code)
        | CodeResult
    Stage 4: Testing (platform generates & runs tests)
        | TestResult
    Stage 5: Build & Deploy (platform builds & verifies)
        | DeployResult
```

### Stage Responsibilities

**Stage 0 — Setup & Onboarding**: Runs once per platform. Measures installation friction, time-to-first-agent, documentation quality. Not story-driven.

**Stage 1 — User Stories**: Harness-only stage (no adapter call). Loads static YAML story, prepares `StageContext` with prompt, acceptance criteria, target files, and baseline workspace.

**Stage 2 — Requirements**: Platform under test receives the user story and must produce:
- Structured requirements (functional, non-functional, use cases)
- UML diagrams (class, sequence, component)
- Entity models, API specs

**Stage 3 — Code Generation**: Platform receives story + generated requirements and must implement the code. Migrated from current `execute_story()`.

**Stage 4 — Testing**: Platform receives story + requirements + code and must generate tests, run them, and report coverage.

**Stage 5 — Build & Deploy**: Platform must build the project and verify deployment readiness.

### Evaluation Scope

Each platform is evaluated at every SDLC stage (Stages 2-5). The 7 DESMET dimensions are scored per stage independently. Aggregate platform score is a weighted combination across all stages and stories.

## Adapter ABC Changes

```python
class BasePlatformAdapter(ABC):
    # Existing (unchanged)
    async def initialize() -> None
    async def shutdown() -> None
    async def health_check() -> bool
    async def reset_state() -> None

    # NEW — one method per evaluated stage
    async def generate_requirements(context: StageContext) -> RequirementsResult
    async def generate_code(context: StageContext) -> CodeResult
    async def generate_tests(context: StageContext) -> TestResult
    async def build_and_deploy(context: StageContext) -> DeployResult

    # DEPRECATED — wrapper that calls generate_code() for backwards compat
    async def execute_story(context: EvaluationContext) -> ExecutionResult
```

### StageContext

Replaces `EvaluationContext`. Carries:
- The original story (always present)
- Accumulated artifacts from prior stages
- Stage-specific constraints (time budget, iteration limits)

### Result Types

All inherit from `StageResult` base with common fields: trace, wall_clock_seconds, iterations, tool_calls, tokens, human_interventions, errors.

| Stage | Method | Returns | Key Fields |
|-------|--------|---------|------------|
| 2 | `generate_requirements()` | `RequirementsResult` | functional_reqs, non_functional_reqs, use_cases, uml_diagrams, entities |
| 3 | `generate_code()` | `CodeResult` | output_files, git_diff |
| 4 | `generate_tests()` | `TestResult` | test_files, tests_run, tests_passed, coverage |
| 5 | `build_and_deploy()` | `DeployResult` | build_success, deployment_ready, build_log |

## Runner Changes

The runner loops `platforms x stories x stages`:

```python
for platform in platforms:
    await adapter.initialize()          # Stage 0 metrics captured here

    for story in stories:
        stage_ctx = load_story(story)   # Stage 1

        reqs = await adapter.generate_requirements(stage_ctx)   # Stage 2
        score(reqs, dimensions)
        stage_ctx.add_artifacts(reqs)

        code = await adapter.generate_code(stage_ctx)           # Stage 3
        score(code, dimensions)
        stage_ctx.add_artifacts(code)

        tests = await adapter.generate_tests(stage_ctx)         # Stage 4
        score(tests, dimensions)
        stage_ctx.add_artifacts(tests)

        deploy = await adapter.build_and_deploy(stage_ctx)      # Stage 5
        score(deploy, dimensions)
```

### Stage Failure Handling

If a platform fails at Stage N, the runner still attempts Stage N+1 by falling back to the original story prompt without the failed stage's artifacts. The failure scores 0 for that stage but doesn't block later stages.

### Results Directory Structure

```
results/{platform}/{story_id}/
    stage2_requirements/    # RequirementsResult artifacts + UML diagrams
    stage3_codegen/         # CodeResult artifacts + workspace
    stage4_testing/         # TestResult artifacts + coverage
    stage5_deploy/          # DeployResult artifacts + build logs
    metrics.json            # Per-stage + aggregate scores
```

## File Structure Changes

### Stage Directories

| Old | New | Change |
|-----|-----|--------|
| `stages/stage0_setup/` | `stages/stage0_setup/` | Unchanged |
| `stages/stage1_requirements/` | `stages/stage1_stories/` | Repurpose: story loading, context prep |
| `stages/stage2_stories/` | `stages/stage2_requirements/` | Existing requirements agent/schemas move here |
| `stages/stage3_codegen/` | `stages/stage3_codegen/` | Thin orchestrator for adapter.generate_code() |
| `stages/stage4_testing/` | `stages/stage4_testing/` | Thin orchestrator for adapter.generate_tests() |
| `stages/stage5_deploy/` | `stages/stage5_deploy/` | Thin orchestrator for adapter.build_and_deploy() |

### Harness Files

| File | Change |
|------|--------|
| `harness/base.py` | Add StageContext, StageResult base, RequirementsResult, CodeResult, TestResult, DeployResult. Add 4 new abstract methods. Deprecate EvaluationContext + execute_story(). |
| `harness/runner.py` | Rewrite loop for stage-by-stage execution with artifact accumulation. |
| `harness/story.py` | Keep as-is — UserStory remains the input model. |
| `harness/metrics.py` | Extend to track per-stage metrics. |

### Adapter Files

| File | Change |
|------|--------|
| `adapters/langgraph.py` | Migrate execute_story() -> generate_code(). Add stubs for 3 new methods. |
| `adapters/crewai.py` | Same migration pattern. |
| 8 stub adapters | Add the 4 new abstract method stubs. |

### Preserved

- `stage1_requirements/schemas/` → moves to `stage2_requirements/schemas/`
- `stage1_requirements/agents/` → moves to `stage2_requirements/agents/`
- `stage1_requirements/templates/` → moves to `stage2_requirements/templates/`
- `data/stories/*.yaml` — untouched
- `config/platforms.yaml` — untouched

### Nothing Deleted

`execute_story()` gets deprecated with a wrapper that calls `generate_code()` for backwards compatibility.
