# Pipeline Restructure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restructure the DESMET evaluation pipeline from requirements-first to stories-first, with an adapter-centric design where each platform is evaluated at every SDLC stage.

**Architecture:** Adapter ABC gains 4 new methods (`generate_requirements`, `generate_code`, `generate_tests`, `build_and_deploy`). Stage modules become thin orchestrators. The runner loops platforms x stories x stages with artifact accumulation. Existing requirements agent/schemas move from stage1 to stage2.

**Tech Stack:** Python 3.10+, async/await, dataclasses, pytest + pytest-asyncio, structlog

**Design doc:** `docs/plans/2026-03-03-pipeline-restructure-design.md`

---

### Task 1: Add StageContext and StageResult Data Models to Harness Base

**Files:**
- Modify: `src/desmet/harness/base.py`
- Create: `tests/test_harness_base.py`

**Step 1: Write failing tests for new data models**

```python
# tests/test_harness_base.py
"""Tests for the harness base data models."""
import pytest
from pathlib import Path
from datetime import datetime

from desmet.harness.base import (
    StageContext,
    StageResult,
    RequirementsResult,
    CodeResult,
    TestResult,
    DeployResult,
    AgentTrace,
    UMLDiagram,
)
from desmet.harness.story import UserStory, DifficultyLevel


@pytest.fixture
def sample_story():
    return UserStory(
        id="US-001",
        title="Test Story",
        description="A test story",
        difficulty=DifficultyLevel.BASIC,
        category="code_generation",
        prompt="Implement a hello world function",
    )


@pytest.fixture
def sample_context(sample_story, tmp_path):
    return StageContext(
        story=sample_story,
        workspace=tmp_path,
        time_budget_seconds=300,
        max_iterations=25,
    )


class TestStageContext:
    def test_create_with_story(self, sample_context, sample_story):
        assert sample_context.story == sample_story
        assert sample_context.artifacts == {}

    def test_add_artifacts(self, sample_context):
        reqs = RequirementsResult(
            platform_id="langgraph",
            stage_name="requirements",
            functional_requirements=[{"id": "FR-1", "title": "Test"}],
        )
        sample_context.add_artifacts("requirements", reqs)
        assert "requirements" in sample_context.artifacts
        assert sample_context.artifacts["requirements"] is reqs

    def test_get_prior_result(self, sample_context):
        reqs = RequirementsResult(
            platform_id="langgraph",
            stage_name="requirements",
            functional_requirements=[{"id": "FR-1", "title": "Test"}],
        )
        sample_context.add_artifacts("requirements", reqs)
        assert sample_context.get_prior_result("requirements") is reqs
        assert sample_context.get_prior_result("codegen") is None


class TestStageResult:
    def test_stage_result_defaults(self):
        result = StageResult(platform_id="langgraph", stage_name="test")
        assert result.success is False
        assert result.wall_clock_seconds == 0.0
        assert result.trace is not None

    def test_stage_result_duration(self):
        result = StageResult(
            platform_id="langgraph",
            stage_name="test",
            wall_clock_seconds=42.5,
        )
        assert result.wall_clock_seconds == 42.5


class TestRequirementsResult:
    def test_create_with_requirements(self):
        result = RequirementsResult(
            platform_id="langgraph",
            stage_name="requirements",
            success=True,
            functional_requirements=[{"id": "FR-1", "title": "Login"}],
            non_functional_requirements=[{"id": "NFR-1", "title": "Performance"}],
            use_cases=[{"id": "UC-1", "name": "User Login"}],
            uml_diagrams=[
                UMLDiagram(diagram_type="class", title="Domain Model", content="@startuml\n@enduml")
            ],
        )
        assert len(result.functional_requirements) == 1
        assert len(result.uml_diagrams) == 1
        assert result.uml_diagrams[0].diagram_type == "class"


class TestCodeResult:
    def test_create_with_output(self):
        result = CodeResult(
            platform_id="langgraph",
            stage_name="codegen",
            success=True,
            output_files=["src/main.py"],
            git_diff="diff --git a/src/main.py",
        )
        assert len(result.output_files) == 1
        assert result.git_diff is not None


class TestTestResult:
    def test_create_with_test_metrics(self):
        result = TestResult(
            platform_id="langgraph",
            stage_name="testing",
            success=True,
            test_files=["tests/test_main.py"],
            tests_run=10,
            tests_passed=9,
            tests_failed=1,
            coverage_percentage=85.0,
        )
        assert result.tests_run == 10
        assert result.test_pass_rate == 90.0


class TestDeployResult:
    def test_create_with_deploy_info(self):
        result = DeployResult(
            platform_id="langgraph",
            stage_name="deploy",
            success=True,
            build_success=True,
            deployment_ready=True,
            build_log="Build completed successfully",
        )
        assert result.build_success is True
        assert result.deployment_ready is True
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_harness_base.py -v`
Expected: FAIL — `ImportError: cannot import name 'StageContext'`

**Step 3: Implement the new data models**

Add to `src/desmet/harness/base.py` (after existing `ExecutionResult` class, before `BasePlatformAdapter`):

```python
@dataclass
class UMLDiagram:
    """A UML diagram produced by a platform."""
    diagram_type: str  # "class", "sequence", "component", "activity", "usecase", "state", "deployment"
    title: str
    content: str  # PlantUML or Mermaid source
    format: str = "plantuml"


@dataclass
class StageContext:
    """
    Context passed through pipeline stages.

    Accumulates artifacts as stages execute — each stage can
    access outputs from prior stages.
    """
    story: 'UserStory'
    workspace: Path
    time_budget_seconds: int = 600
    max_iterations: int = 50
    max_tool_calls: int = 100
    allowed_tools: list[str] = field(
        default_factory=lambda: [
            "read_file", "write_file", "list_directory",
            "execute_shell", "search_code",
        ]
    )
    model: str = "gpt-4.1"
    temperature: float = 0.0
    artifacts: dict[str, 'StageResult'] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_artifacts(self, stage_name: str, result: 'StageResult') -> None:
        """Add a stage result to the accumulated artifacts."""
        self.artifacts[stage_name] = result

    def get_prior_result(self, stage_name: str) -> Optional['StageResult']:
        """Get the result from a prior stage, or None if it doesn't exist."""
        return self.artifacts.get(stage_name)


@dataclass
class StageResult:
    """Base result from any pipeline stage."""
    platform_id: str
    stage_name: str

    success: bool = False
    completed: bool = False
    error_message: Optional[str] = None

    trace: AgentTrace = field(default_factory=AgentTrace)
    wall_clock_seconds: float = 0.0
    iterations: int = 0
    tool_calls_count: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    human_interventions: int = 0

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    raw_output: Any = None


@dataclass
class RequirementsResult(StageResult):
    """Result from Stage 2: Requirements Generation."""
    functional_requirements: list[dict[str, Any]] = field(default_factory=list)
    non_functional_requirements: list[dict[str, Any]] = field(default_factory=list)
    use_cases: list[dict[str, Any]] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    api_endpoints: list[dict[str, Any]] = field(default_factory=list)
    uml_diagrams: list[UMLDiagram] = field(default_factory=list)


@dataclass
class CodeResult(StageResult):
    """Result from Stage 3: Code Generation."""
    output_files: list[str] = field(default_factory=list)
    git_diff: Optional[str] = None


@dataclass
class TestResult(StageResult):
    """Result from Stage 4: Testing."""
    test_files: list[str] = field(default_factory=list)
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    coverage_percentage: float = 0.0

    @property
    def test_pass_rate(self) -> float:
        if self.tests_run == 0:
            return 0.0
        return (self.tests_passed / self.tests_run) * 100


@dataclass
class DeployResult(StageResult):
    """Result from Stage 5: Build & Deploy."""
    build_success: bool = False
    deployment_ready: bool = False
    build_log: str = ""
    dependency_issues: list[str] = field(default_factory=list)
```

Also add the forward-reference import at the top of `base.py`:

```python
from __future__ import annotations
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_harness_base.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add tests/test_harness_base.py src/desmet/harness/base.py
git commit -m "feat: add StageContext and StageResult data models for pipeline restructure"
```

---

### Task 2: Add New Abstract Methods to BasePlatformAdapter

**Files:**
- Modify: `src/desmet/harness/base.py`
- Create: `tests/test_adapter_interface.py`

**Step 1: Write failing tests for new adapter interface**

```python
# tests/test_adapter_interface.py
"""Tests for the adapter interface contract."""
import pytest
from abc import ABC
import inspect

from desmet.harness.base import (
    BasePlatformAdapter,
    VisualPlatformAdapter,
    StageContext,
    RequirementsResult,
    CodeResult,
    TestResult,
    DeployResult,
)


class TestAdapterInterface:
    def test_has_generate_requirements_method(self):
        assert hasattr(BasePlatformAdapter, "generate_requirements")
        sig = inspect.signature(BasePlatformAdapter.generate_requirements)
        params = list(sig.parameters.keys())
        assert "context" in params
        assert sig.return_annotation in (RequirementsResult, "RequirementsResult")

    def test_has_generate_code_method(self):
        assert hasattr(BasePlatformAdapter, "generate_code")
        sig = inspect.signature(BasePlatformAdapter.generate_code)
        params = list(sig.parameters.keys())
        assert "context" in params
        assert sig.return_annotation in (CodeResult, "CodeResult")

    def test_has_generate_tests_method(self):
        assert hasattr(BasePlatformAdapter, "generate_tests")
        sig = inspect.signature(BasePlatformAdapter.generate_tests)
        params = list(sig.parameters.keys())
        assert "context" in params
        assert sig.return_annotation in (TestResult, "TestResult")

    def test_has_build_and_deploy_method(self):
        assert hasattr(BasePlatformAdapter, "build_and_deploy")
        sig = inspect.signature(BasePlatformAdapter.build_and_deploy)
        params = list(sig.parameters.keys())
        assert "context" in params
        assert sig.return_annotation in (DeployResult, "DeployResult")

    def test_all_new_methods_are_abstract(self):
        abstract_methods = BasePlatformAdapter.__abstractmethods__
        assert "generate_requirements" in abstract_methods
        assert "generate_code" in abstract_methods
        assert "generate_tests" in abstract_methods
        assert "build_and_deploy" in abstract_methods

    def test_execute_story_still_exists(self):
        """execute_story is deprecated but still present for backwards compat."""
        assert hasattr(BasePlatformAdapter, "execute_story")
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_adapter_interface.py -v`
Expected: FAIL — `generate_requirements` not found

**Step 3: Add abstract methods to BasePlatformAdapter**

Add to `BasePlatformAdapter` in `src/desmet/harness/base.py`, inside the class after `execute_story`:

```python
    # =========================================================================
    # SDLC Stage Methods (Adapter-Centric Pipeline)
    # =========================================================================

    @abstractmethod
    async def generate_requirements(
        self,
        context: StageContext,
    ) -> RequirementsResult:
        """
        Stage 2: Generate requirements from a user story.

        The platform should analyze the story and produce:
        - Functional and non-functional requirements
        - Use cases
        - Entity models and API specs
        - UML diagrams (class, sequence, component)

        Args:
            context: Stage context containing the story and workspace

        Returns:
            RequirementsResult with all generated requirements artifacts
        """
        pass

    @abstractmethod
    async def generate_code(
        self,
        context: StageContext,
    ) -> CodeResult:
        """
        Stage 3: Generate code implementation from story + requirements.

        The platform should implement the code described by the story,
        using requirements from Stage 2 if available in context.artifacts.

        Args:
            context: Stage context with story + prior stage artifacts

        Returns:
            CodeResult with output files and git diff
        """
        pass

    @abstractmethod
    async def generate_tests(
        self,
        context: StageContext,
    ) -> TestResult:
        """
        Stage 4: Generate and run tests.

        The platform should create tests for the code from Stage 3,
        run them, and report results.

        Args:
            context: Stage context with story + requirements + code artifacts

        Returns:
            TestResult with test files, pass/fail counts, coverage
        """
        pass

    @abstractmethod
    async def build_and_deploy(
        self,
        context: StageContext,
    ) -> DeployResult:
        """
        Stage 5: Build and verify deployment readiness.

        The platform should build the project, resolve dependencies,
        and verify it's deployment-ready.

        Args:
            context: Stage context with all prior stage artifacts

        Returns:
            DeployResult with build status and deployment readiness
        """
        pass
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_adapter_interface.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add tests/test_adapter_interface.py src/desmet/harness/base.py
git commit -m "feat: add SDLC stage abstract methods to BasePlatformAdapter"
```

---

### Task 3: Rename and Move Stage Directories

**Files:**
- Move: `src/desmet/stages/stage1_requirements/` → `src/desmet/stages/stage2_requirements/`
- Rewrite: `src/desmet/stages/stage1_stories/__init__.py`
- Update: all stage `__init__.py` docstrings
- Modify: any imports referencing old stage paths

**Step 1: Verify no imports reference old stage1_requirements path from outside the stage**

Run: `grep -r "stage1_requirements" src/desmet/ --include="*.py" -l` (use Grep tool)
Expected: only files within `stages/stage1_requirements/` itself (internal relative imports)

**Step 2: Move stage1_requirements to stage2_requirements**

```bash
# Rename stage2_stories (stub) out of the way
mv src/desmet/stages/stage2_stories src/desmet/stages/_old_stage2_stories

# Move stage1_requirements to stage2_requirements
mv src/desmet/stages/stage1_requirements src/desmet/stages/stage2_requirements

# Create new stage1_stories
mkdir -p src/desmet/stages/stage1_stories

# Clean up old stub
rm -rf src/desmet/stages/_old_stage2_stories
```

**Step 3: Update stage docstrings**

Write `src/desmet/stages/stage1_stories/__init__.py`:

```python
"""Stage 1: User Stories — Load benchmark user stories and prepare stage context."""
```

Write `src/desmet/stages/stage2_requirements/__init__.py`:

```python
"""Stage 2: Requirements Engineering — Platform generates requirements and UML from user stories."""
```

Update `src/desmet/stages/stage0_setup/__init__.py`:

```python
"""Stage 0: Framework Setup & Onboarding — Evaluate setup friction and time-to-value."""
```

Update `src/desmet/stages/stage3_codegen/__init__.py`:

```python
"""Stage 3: Code Generation — Platform implements code from story and requirements."""
```

Update `src/desmet/stages/stage4_testing/__init__.py`:

```python
"""Stage 4: Testing — Platform generates and runs tests against generated code."""
```

Update `src/desmet/stages/stage5_deploy/__init__.py`:

```python
"""Stage 5: Build & Deploy — Platform builds the project and verifies deployment readiness."""
```

**Step 4: Verify the move preserved all files**

```bash
ls -la src/desmet/stages/stage2_requirements/
ls -la src/desmet/stages/stage2_requirements/agents/
ls -la src/desmet/stages/stage2_requirements/schemas/
ls -la src/desmet/stages/stage2_requirements/templates/
```

Expected: all files from old stage1 present in new stage2 location

**Step 5: Verify no broken imports**

Run: `python -c "from desmet.stages.stage2_requirements.stage_runner import RequirementsStageRunner; print('OK')"`
Expected: `OK`

**Step 6: Commit**

```bash
git add -A src/desmet/stages/
git commit -m "refactor: rename stages — stories first (stage1), requirements second (stage2)"
```

---

### Task 4: Implement Stage 1 Story Loader Module

**Files:**
- Create: `src/desmet/stages/stage1_stories/loader.py`
- Create: `tests/test_stage1_stories.py`

**Step 1: Write failing tests**

```python
# tests/test_stage1_stories.py
"""Tests for Stage 1: Story loading and StageContext preparation."""
import pytest
from pathlib import Path

from desmet.harness.story import UserStory, DifficultyLevel
from desmet.harness.base import StageContext
from desmet.stages.stage1_stories.loader import prepare_stage_context


@pytest.fixture
def sample_story():
    return UserStory(
        id="US-001",
        title="Add Email Validation",
        description="Add a validate_email function",
        difficulty=DifficultyLevel.BASIC,
        category="code_generation",
        prompt="Implement a validate_email function that checks format",
        target_files=["utils/validation.py"],
        time_budget_seconds=300,
        max_iterations=25,
    )


class TestPrepareStageContext:
    def test_creates_stage_context(self, sample_story, tmp_path):
        ctx = prepare_stage_context(sample_story, workspace=tmp_path)
        assert isinstance(ctx, StageContext)
        assert ctx.story is sample_story
        assert ctx.workspace == tmp_path

    def test_inherits_story_constraints(self, sample_story, tmp_path):
        ctx = prepare_stage_context(sample_story, workspace=tmp_path)
        assert ctx.time_budget_seconds == 300
        assert ctx.max_iterations == 25

    def test_overrides_constraints(self, sample_story, tmp_path):
        ctx = prepare_stage_context(
            sample_story,
            workspace=tmp_path,
            time_budget_seconds=600,
            timeout_multiplier=1.5,
        )
        assert ctx.time_budget_seconds == 900  # 600 * 1.5

    def test_artifacts_start_empty(self, sample_story, tmp_path):
        ctx = prepare_stage_context(sample_story, workspace=tmp_path)
        assert ctx.artifacts == {}
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_stage1_stories.py -v`
Expected: FAIL — `ImportError: cannot import name 'prepare_stage_context'`

**Step 3: Implement the loader**

```python
# src/desmet/stages/stage1_stories/loader.py
"""
Stage 1: Story Loading and Context Preparation

Loads user stories from YAML and prepares StageContext for downstream stages.
This is a harness-only stage — no adapter call.
"""
from pathlib import Path
from typing import Optional

from desmet.harness.base import StageContext
from desmet.harness.story import UserStory


def prepare_stage_context(
    story: UserStory,
    workspace: Path,
    time_budget_seconds: Optional[int] = None,
    max_iterations: Optional[int] = None,
    timeout_multiplier: float = 1.0,
    model: str = "gpt-4.1",
) -> StageContext:
    """
    Prepare a StageContext from a UserStory for pipeline execution.

    Args:
        story: The user story to prepare context for
        workspace: Path to the isolated workspace for this execution
        time_budget_seconds: Override story time budget (None = use story's)
        max_iterations: Override story max iterations (None = use story's)
        timeout_multiplier: Multiply the time budget by this factor
        model: LLM model to use

    Returns:
        StageContext ready for pipeline stages 2-5
    """
    budget = time_budget_seconds if time_budget_seconds is not None else story.time_budget_seconds
    budget = int(budget * timeout_multiplier)

    iterations = max_iterations if max_iterations is not None else story.max_iterations

    return StageContext(
        story=story,
        workspace=workspace,
        time_budget_seconds=budget,
        max_iterations=iterations,
        model=model,
    )
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_stage1_stories.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/desmet/stages/stage1_stories/loader.py tests/test_stage1_stories.py
git commit -m "feat: implement Stage 1 story loader with StageContext preparation"
```

---

### Task 5: Migrate LangGraph Adapter to New Interface

**Files:**
- Modify: `src/desmet/adapters/langgraph.py`
- Create: `tests/test_langgraph_adapter.py`

**Step 1: Write failing tests for new interface methods**

```python
# tests/test_langgraph_adapter.py
"""Tests for LangGraph adapter's new SDLC stage methods."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from desmet.adapters.langgraph import LangGraphAdapter
from desmet.harness.base import (
    StageContext,
    RequirementsResult,
    CodeResult,
    TestResult,
    DeployResult,
)
from desmet.harness.story import UserStory, DifficultyLevel


@pytest.fixture
def adapter():
    return LangGraphAdapter(config={"model": "gpt-4.1"})


@pytest.fixture
def sample_story():
    return UserStory(
        id="US-001",
        title="Test Story",
        description="A test story",
        difficulty=DifficultyLevel.BASIC,
        category="code_generation",
        prompt="Implement a hello world function",
    )


@pytest.fixture
def stage_context(sample_story, tmp_path):
    return StageContext(
        story=sample_story,
        workspace=tmp_path,
        time_budget_seconds=300,
        max_iterations=25,
    )


class TestLangGraphAdapterInterface:
    def test_has_generate_requirements(self, adapter):
        assert hasattr(adapter, "generate_requirements")
        assert callable(adapter.generate_requirements)

    def test_has_generate_code(self, adapter):
        assert hasattr(adapter, "generate_code")
        assert callable(adapter.generate_code)

    def test_has_generate_tests(self, adapter):
        assert hasattr(adapter, "generate_tests")
        assert callable(adapter.generate_tests)

    def test_has_build_and_deploy(self, adapter):
        assert hasattr(adapter, "build_and_deploy")
        assert callable(adapter.build_and_deploy)

    def test_generate_requirements_returns_correct_type(self, adapter, stage_context):
        """generate_requirements should return RequirementsResult (tested via type annotation)."""
        import inspect
        sig = inspect.signature(adapter.generate_requirements)
        assert sig.return_annotation in (RequirementsResult, "RequirementsResult")

    def test_generate_code_returns_correct_type(self, adapter, stage_context):
        import inspect
        sig = inspect.signature(adapter.generate_code)
        assert sig.return_annotation in (CodeResult, "CodeResult")

    def test_generate_tests_returns_correct_type(self, adapter, stage_context):
        import inspect
        sig = inspect.signature(adapter.generate_tests)
        assert sig.return_annotation in (TestResult, "TestResult")

    def test_build_and_deploy_returns_correct_type(self, adapter, stage_context):
        import inspect
        sig = inspect.signature(adapter.build_and_deploy)
        assert sig.return_annotation in (DeployResult, "DeployResult")

    def test_execute_story_still_works(self, adapter):
        """Backwards compat: execute_story still exists."""
        assert hasattr(adapter, "execute_story")
        assert callable(adapter.execute_story)
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_langgraph_adapter.py -v`
Expected: FAIL — `LangGraphAdapter` can't be instantiated (missing abstract methods)

**Step 3: Migrate execute_story to generate_code, add stubs for other methods**

In `src/desmet/adapters/langgraph.py`, add the new imports and methods:

Add to imports at top:
```python
from desmet.harness.base import (
    AgentMessage,
    AgentTrace,
    BasePlatformAdapter,
    CodeResult,
    DeployResult,
    EvaluationContext,
    ExecutionResult,
    PlatformCategory,
    PlatformInfo,
    PlatformRuntime,
    RequirementsResult,
    StageContext,
    TestResult,
    ToolCall,
)
```

Rename `execute_story` to `generate_code` with updated signature, and add a backwards-compat `execute_story` wrapper. Add stubs for the other 3 methods:

```python
    async def generate_requirements(
        self,
        context: StageContext,
    ) -> RequirementsResult:
        """Stage 2: Generate requirements from a user story using LangGraph."""
        from langgraph.prebuilt import create_react_agent

        execution_id = self._create_execution_id()
        trace = AgentTrace(start_time=datetime.now())

        try:
            tools = self._create_tools_from_stage_context(context)
            agent = create_react_agent(
                self._llm,
                tools,
                checkpointer=self._checkpointer,
            )

            prompt = (
                f"Analyze the following user story and produce structured requirements.\n\n"
                f"User Story: {context.story.title}\n"
                f"Description: {context.story.description}\n"
                f"Prompt: {context.story.prompt}\n\n"
                f"Generate:\n"
                f"1. Functional requirements (as JSON list)\n"
                f"2. Non-functional requirements (as JSON list)\n"
                f"3. Use cases (as JSON list)\n"
                f"4. PlantUML class diagram\n"
                f"5. PlantUML sequence diagram\n"
            )

            messages = [{"role": "user", "content": prompt}]
            config = {"configurable": {"thread_id": execution_id}}

            final_state = None
            iteration = 0

            async for event in agent.astream(
                {"messages": messages}, config, stream_mode="values",
            ):
                iteration += 1
                trace.total_iterations = iteration
                if "messages" in event:
                    for msg in event["messages"]:
                        trace.messages.append(
                            AgentMessage(
                                role=getattr(msg, "type", "unknown"),
                                content=getattr(msg, "content", str(msg)),
                                timestamp=datetime.now(),
                            )
                        )
                final_state = event
                if iteration >= context.max_iterations:
                    break

            trace.end_time = datetime.now()
            success = iteration < context.max_iterations

            return RequirementsResult(
                platform_id=self.platform_info.id,
                stage_name="requirements",
                success=success,
                completed=success,
                trace=trace,
                wall_clock_seconds=trace.duration_seconds,
                iterations=iteration,
                start_time=trace.start_time,
                end_time=trace.end_time,
                # TODO: parse structured requirements from agent output
                functional_requirements=[],
                non_functional_requirements=[],
                use_cases=[],
                uml_diagrams=[],
            )

        except Exception as e:
            trace.end_time = datetime.now()
            trace.errors.append(str(e))
            return RequirementsResult(
                platform_id=self.platform_info.id,
                stage_name="requirements",
                success=False,
                error_message=str(e),
                trace=trace,
                wall_clock_seconds=trace.duration_seconds,
                start_time=trace.start_time,
                end_time=trace.end_time,
            )

    async def generate_code(
        self,
        context: StageContext,
    ) -> CodeResult:
        """Stage 3: Generate code using LangGraph (migrated from execute_story)."""
        from langgraph.prebuilt import create_react_agent

        execution_id = self._create_execution_id()
        trace = AgentTrace(start_time=datetime.now())

        try:
            tools = self._create_tools_from_stage_context(context)
            agent = create_react_agent(
                self._llm,
                tools,
                checkpointer=self._checkpointer,
            )

            # Build prompt incorporating requirements if available
            prompt = context.story.prompt
            reqs = context.get_prior_result("requirements")
            if reqs and isinstance(reqs, RequirementsResult) and reqs.functional_requirements:
                prompt += "\n\nRequirements from prior analysis:\n"
                for req in reqs.functional_requirements:
                    prompt += f"- {req.get('title', '')}: {req.get('description', '')}\n"

            messages = [{"role": "user", "content": prompt}]
            if context.story.context:
                messages.insert(0, {"role": "system", "content": context.story.context})

            config = {"configurable": {"thread_id": execution_id}}

            final_state = None
            iteration = 0

            async for event in agent.astream(
                {"messages": messages}, config, stream_mode="values",
            ):
                iteration += 1
                trace.total_iterations = iteration
                if "messages" in event:
                    for msg in event["messages"]:
                        trace.messages.append(
                            AgentMessage(
                                role=getattr(msg, "type", "unknown"),
                                content=getattr(msg, "content", str(msg)),
                                timestamp=datetime.now(),
                            )
                        )
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tc in msg.tool_calls:
                                trace.tool_calls.append(
                                    ToolCall(
                                        tool_name=tc.get("name", "unknown"),
                                        arguments=tc.get("args", {}),
                                        result=None,
                                        timestamp=datetime.now(),
                                        duration_ms=0,
                                        success=True,
                                    )
                                )
                final_state = event
                if iteration >= context.max_iterations:
                    break

            trace.end_time = datetime.now()
            success = iteration < context.max_iterations

            return CodeResult(
                platform_id=self.platform_info.id,
                stage_name="codegen",
                success=success,
                completed=success,
                trace=trace,
                wall_clock_seconds=trace.duration_seconds,
                iterations=iteration,
                tool_calls_count=len(trace.tool_calls),
                start_time=trace.start_time,
                end_time=trace.end_time,
                output_files=[],  # TODO: detect created/modified files from workspace
            )

        except Exception as e:
            trace.end_time = datetime.now()
            trace.errors.append(str(e))
            return CodeResult(
                platform_id=self.platform_info.id,
                stage_name="codegen",
                success=False,
                error_message=str(e),
                trace=trace,
                wall_clock_seconds=trace.duration_seconds,
                start_time=trace.start_time,
                end_time=trace.end_time,
            )

    async def generate_tests(
        self,
        context: StageContext,
    ) -> TestResult:
        """Stage 4: Generate and run tests using LangGraph."""
        from langgraph.prebuilt import create_react_agent

        execution_id = self._create_execution_id()
        trace = AgentTrace(start_time=datetime.now())

        try:
            tools = self._create_tools_from_stage_context(context)
            agent = create_react_agent(
                self._llm,
                tools,
                checkpointer=self._checkpointer,
            )

            prompt = (
                f"Generate comprehensive tests for the following user story.\n\n"
                f"Story: {context.story.title}\n"
                f"Description: {context.story.description}\n\n"
                f"Write pytest test files, run them, and report results.\n"
            )

            messages = [{"role": "user", "content": prompt}]
            config = {"configurable": {"thread_id": execution_id}}

            iteration = 0
            async for event in agent.astream(
                {"messages": messages}, config, stream_mode="values",
            ):
                iteration += 1
                trace.total_iterations = iteration
                if iteration >= context.max_iterations:
                    break

            trace.end_time = datetime.now()
            success = iteration < context.max_iterations

            return TestResult(
                platform_id=self.platform_info.id,
                stage_name="testing",
                success=success,
                completed=success,
                trace=trace,
                wall_clock_seconds=trace.duration_seconds,
                iterations=iteration,
                start_time=trace.start_time,
                end_time=trace.end_time,
            )

        except Exception as e:
            trace.end_time = datetime.now()
            trace.errors.append(str(e))
            return TestResult(
                platform_id=self.platform_info.id,
                stage_name="testing",
                success=False,
                error_message=str(e),
                trace=trace,
                start_time=trace.start_time,
                end_time=trace.end_time,
            )

    async def build_and_deploy(
        self,
        context: StageContext,
    ) -> DeployResult:
        """Stage 5: Build and verify deployment using LangGraph."""
        from langgraph.prebuilt import create_react_agent

        execution_id = self._create_execution_id()
        trace = AgentTrace(start_time=datetime.now())

        try:
            tools = self._create_tools_from_stage_context(context)
            agent = create_react_agent(
                self._llm,
                tools,
                checkpointer=self._checkpointer,
            )

            prompt = (
                f"Build and verify the project in the workspace.\n\n"
                f"1. Install dependencies\n"
                f"2. Run the full test suite\n"
                f"3. Verify the build completes without errors\n"
                f"4. Check for any deployment issues\n"
            )

            messages = [{"role": "user", "content": prompt}]
            config = {"configurable": {"thread_id": execution_id}}

            iteration = 0
            async for event in agent.astream(
                {"messages": messages}, config, stream_mode="values",
            ):
                iteration += 1
                trace.total_iterations = iteration
                if iteration >= context.max_iterations:
                    break

            trace.end_time = datetime.now()
            success = iteration < context.max_iterations

            return DeployResult(
                platform_id=self.platform_info.id,
                stage_name="deploy",
                success=success,
                completed=success,
                trace=trace,
                wall_clock_seconds=trace.duration_seconds,
                iterations=iteration,
                start_time=trace.start_time,
                end_time=trace.end_time,
                build_success=success,
                deployment_ready=success,
            )

        except Exception as e:
            trace.end_time = datetime.now()
            trace.errors.append(str(e))
            return DeployResult(
                platform_id=self.platform_info.id,
                stage_name="deploy",
                success=False,
                error_message=str(e),
                trace=trace,
                start_time=trace.start_time,
                end_time=trace.end_time,
            )

    def _create_tools_from_stage_context(self, context: StageContext) -> list:
        """Create LangChain tools from a StageContext (shared across all stages)."""
        import subprocess
        from langchain_core.tools import tool

        repo_path = context.workspace
        tools = []

        @tool
        def read_file(path: str) -> str:
            """Read the contents of a file."""
            full_path = repo_path / path
            if full_path.exists():
                return full_path.read_text()
            return f"File not found: {path}"
        tools.append(read_file)

        @tool
        def write_file(path: str, content: str) -> str:
            """Write content to a file."""
            full_path = repo_path / path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            return f"Successfully wrote to {path}"
        tools.append(write_file)

        @tool
        def list_directory(path: str = ".") -> str:
            """List files in a directory."""
            full_path = repo_path / path
            if full_path.exists():
                files = list(full_path.iterdir())
                return "\n".join(str(f.relative_to(repo_path)) for f in files)
            return f"Directory not found: {path}"
        tools.append(list_directory)

        @tool
        def execute_shell(command: str) -> str:
            """Execute a shell command."""
            try:
                result = subprocess.run(
                    command, shell=True, cwd=repo_path,
                    capture_output=True, text=True, timeout=30,
                )
                output = result.stdout + result.stderr
                return output if output else "(no output)"
            except subprocess.TimeoutExpired:
                return "Command timed out"
            except Exception as e:
                return f"Error: {e}"
        tools.append(execute_shell)

        return tools

    async def execute_story(
        self,
        context: EvaluationContext,
    ) -> ExecutionResult:
        """
        DEPRECATED: Use generate_code() instead.

        Maintained for backwards compatibility. Wraps generate_code().
        """
        # Convert old EvaluationContext to new StageContext
        from desmet.harness.story import UserStory, DifficultyLevel

        story = UserStory(
            id=context.story_id,
            title=context.story_id,
            description=context.story_prompt,
            difficulty=DifficultyLevel.BASIC,
            category="code_generation",
            prompt=context.story_prompt,
            context=context.story_context,
            target_files=context.target_files,
            time_budget_seconds=context.time_budget_seconds,
            max_iterations=context.max_iterations,
        )

        stage_ctx = StageContext(
            story=story,
            workspace=context.repo_path,
            time_budget_seconds=context.time_budget_seconds,
            max_iterations=context.max_iterations,
            model=context.model,
            temperature=context.temperature,
        )

        code_result = await self.generate_code(stage_ctx)

        return ExecutionResult(
            platform_id=code_result.platform_id,
            story_id=context.story_id,
            execution_id=self._create_execution_id(),
            success=code_result.success,
            completed=code_result.completed,
            error_message=code_result.error_message,
            trace=code_result.trace,
            output_files=code_result.output_files,
            git_diff=code_result.git_diff,
            start_time=code_result.start_time or datetime.now(),
            end_time=code_result.end_time,
            wall_clock_seconds=code_result.wall_clock_seconds,
        )
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_langgraph_adapter.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/desmet/adapters/langgraph.py tests/test_langgraph_adapter.py
git commit -m "feat: migrate LangGraph adapter to new SDLC stage interface"
```

---

### Task 6: Migrate CrewAI Adapter to New Interface

**Files:**
- Modify: `src/desmet/adapters/crewai.py`

**Step 1: Read and understand current CrewAI adapter**

Read: `src/desmet/adapters/crewai.py`

**Step 2: Add new method stubs following same pattern as LangGraph**

Follow the same pattern as Task 5: add imports for new types, implement `generate_requirements()`, `generate_code()` (migrated from `execute_story()`), `generate_tests()`, `build_and_deploy()`, and a backwards-compat `execute_story()` wrapper. Add `_create_tools_from_stage_context()` adapted for CrewAI's tool format.

**Step 3: Verify adapter instantiates**

Run: `python -c "from desmet.adapters.crewai import CrewAIAdapter; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add src/desmet/adapters/crewai.py
git commit -m "feat: migrate CrewAI adapter to new SDLC stage interface"
```

---

### Task 7: Update All Stub Adapters with New Abstract Methods

**Files:**
- Modify: `src/desmet/adapters/autogen.py`
- Modify: `src/desmet/adapters/openai_agents.py`
- Modify: `src/desmet/adapters/google_adk.py`
- Modify: `src/desmet/adapters/semantic_kernel.py`
- Modify: `src/desmet/adapters/flowise.py`
- Modify: `src/desmet/adapters/langflow.py`
- Modify: `src/desmet/adapters/dify.py`
- Modify: `src/desmet/adapters/n8n.py`

**Step 1: Create a stub adapter template**

Each stub adapter currently has only a comment placeholder. They need to become proper classes that inherit from `BasePlatformAdapter` (or `VisualPlatformAdapter` for Flowise/LangFlow/Dify/n8n) and raise `NotImplementedError` for all abstract methods.

For each of the 4 SDK/framework adapters (`autogen.py`, `openai_agents.py`, `google_adk.py`, `semantic_kernel.py`), write:

```python
"""
{Platform} Platform Adapter

Stub implementation — not yet functional.
"""
from typing import Any

from desmet.harness.base import (
    BasePlatformAdapter,
    CodeResult,
    DeployResult,
    EvaluationContext,
    ExecutionResult,
    PlatformCategory,
    PlatformInfo,
    PlatformRuntime,
    RequirementsResult,
    StageContext,
    TestResult,
)


class {ClassName}Adapter(BasePlatformAdapter):
    """Stub adapter for {Platform}."""

    @property
    def platform_info(self) -> PlatformInfo:
        return PlatformInfo(
            name="{Platform}",
            id="{platform_id}",
            category=PlatformCategory.{CATEGORY},
            runtime=PlatformRuntime.PYTHON,
            version="stub",
            vendor="{Vendor}",
            description="{Description}",
            documentation_url="{URL}",
            repository_url="{Repo}",
        )

    async def initialize(self) -> None:
        raise NotImplementedError("{Platform} adapter not yet implemented")

    async def shutdown(self) -> None:
        pass

    async def health_check(self) -> bool:
        return False

    async def execute_story(self, context: EvaluationContext) -> ExecutionResult:
        raise NotImplementedError("{Platform} adapter not yet implemented")

    async def generate_requirements(self, context: StageContext) -> RequirementsResult:
        raise NotImplementedError("{Platform} adapter not yet implemented")

    async def generate_code(self, context: StageContext) -> CodeResult:
        raise NotImplementedError("{Platform} adapter not yet implemented")

    async def generate_tests(self, context: StageContext) -> TestResult:
        raise NotImplementedError("{Platform} adapter not yet implemented")

    async def build_and_deploy(self, context: StageContext) -> DeployResult:
        raise NotImplementedError("{Platform} adapter not yet implemented")
```

For the 4 visual platform adapters (`flowise.py`, `langflow.py`, `dify.py`, `n8n.py`), use `VisualPlatformAdapter` as the base class and also include stubs for `create_workflow`, `execute_workflow`, `delete_workflow`.

**Step 2: Update the adapter registry**

In `src/desmet/adapters/registry.py`, update `None` class names to actual class names:

```python
ADAPTER_REGISTRY: dict[str, tuple[str, str | None]] = {
    "langgraph":          ("desmet.adapters.langgraph",        "LangGraphAdapter"),
    "crewai":             ("desmet.adapters.crewai",           "CrewAIAdapter"),
    "microsoft_autogen":  ("desmet.adapters.autogen",          "AutoGenAdapter"),
    "openai_agents_sdk":  ("desmet.adapters.openai_agents",    "OpenAIAgentsAdapter"),
    "google_adk":         ("desmet.adapters.google_adk",       "GoogleADKAdapter"),
    "semantic_kernel":    ("desmet.adapters.semantic_kernel",   "SemanticKernelAdapter"),
    "flowise":            ("desmet.adapters.flowise",          "FlowiseAdapter"),
    "langflow":           ("desmet.adapters.langflow",         "LangFlowAdapter"),
    "dify":               ("desmet.adapters.dify",             "DifyAdapter"),
    "n8n":                ("desmet.adapters.n8n",              "N8nAdapter"),
}
```

**Step 3: Verify all adapters import cleanly**

Run: `python -c "from desmet.adapters.autogen import AutoGenAdapter; print('OK')"`
(Repeat for all 8)

**Step 4: Commit**

```bash
git add src/desmet/adapters/
git commit -m "feat: update all stub adapters with SDLC stage interface methods"
```

---

### Task 8: Rewrite the Evaluation Runner for Stage-by-Stage Execution

**Files:**
- Modify: `src/desmet/harness/runner.py`
- Create: `tests/test_runner.py`

**Step 1: Write failing tests for the new runner flow**

```python
# tests/test_runner.py
"""Tests for the restructured evaluation runner."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from desmet.harness.runner import EvaluationRunner, RunnerConfig
from desmet.harness.base import (
    RequirementsResult,
    CodeResult,
    TestResult,
    DeployResult,
    StageContext,
    AgentTrace,
)
from desmet.harness.story import UserStory, DifficultyLevel


@pytest.fixture
def mock_adapter():
    adapter = AsyncMock()
    adapter.platform_info = MagicMock()
    adapter.platform_info.id = "test_platform"
    adapter.platform_info.name = "Test Platform"

    adapter.generate_requirements.return_value = RequirementsResult(
        platform_id="test_platform", stage_name="requirements", success=True,
    )
    adapter.generate_code.return_value = CodeResult(
        platform_id="test_platform", stage_name="codegen", success=True,
    )
    adapter.generate_tests.return_value = TestResult(
        platform_id="test_platform", stage_name="testing", success=True,
    )
    adapter.build_and_deploy.return_value = DeployResult(
        platform_id="test_platform", stage_name="deploy", success=True,
        build_success=True, deployment_ready=True,
    )
    return adapter


@pytest.fixture
def sample_story():
    return UserStory(
        id="US-001",
        title="Test Story",
        description="A test story",
        difficulty=DifficultyLevel.BASIC,
        category="code_generation",
        prompt="Implement something",
        time_budget_seconds=300,
        max_iterations=25,
    )


@pytest.fixture
def runner(mock_adapter, sample_story, tmp_path):
    config = RunnerConfig(results_dir=tmp_path / "results", logs_dir=tmp_path / "logs")
    return EvaluationRunner(
        config=config,
        platforms={"test_platform": mock_adapter},
        stories=[sample_story],
        baseline_repo=tmp_path / "baseline",
    )


class TestRunnerStageExecution:
    async def test_runs_all_four_stages(self, runner, mock_adapter, tmp_path):
        # Create baseline dir
        baseline = tmp_path / "baseline"
        baseline.mkdir()
        (baseline / "README.md").write_text("baseline")

        await runner.run_full_evaluation()

        mock_adapter.generate_requirements.assert_called_once()
        mock_adapter.generate_code.assert_called_once()
        mock_adapter.generate_tests.assert_called_once()
        mock_adapter.build_and_deploy.assert_called_once()

    async def test_stage_context_accumulates_artifacts(self, runner, mock_adapter, tmp_path):
        baseline = tmp_path / "baseline"
        baseline.mkdir()
        (baseline / "README.md").write_text("baseline")

        await runner.run_full_evaluation()

        # The context passed to generate_code should have requirements in artifacts
        code_call_ctx = mock_adapter.generate_code.call_args[0][0]
        assert isinstance(code_call_ctx, StageContext)
        assert "requirements" in code_call_ctx.artifacts

    async def test_stage_failure_doesnt_block_later_stages(self, runner, mock_adapter, tmp_path):
        baseline = tmp_path / "baseline"
        baseline.mkdir()
        (baseline / "README.md").write_text("baseline")

        # Make requirements fail
        mock_adapter.generate_requirements.return_value = RequirementsResult(
            platform_id="test_platform", stage_name="requirements",
            success=False, error_message="Failed",
        )

        await runner.run_full_evaluation()

        # Code gen should still be called
        mock_adapter.generate_code.assert_called_once()
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_runner.py -v`
Expected: FAIL — runner doesn't call the new stage methods yet

**Step 3: Rewrite the runner's _run_story method**

Replace `_run_story` in `src/desmet/harness/runner.py` with a stage-by-stage implementation. The key changes:

1. Replace the single `adapter.execute_story(context)` call with 4 stage calls
2. Build `StageContext` instead of `EvaluationContext`
3. Accumulate artifacts between stages
4. Store per-stage results in the results directory
5. Continue on stage failure (score 0, but don't block)

Also add a new `_run_stages` method and update `_run_story` to call it.

The `run_full_evaluation` method stays mostly the same — it still loops platforms then stories.

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_runner.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/desmet/harness/runner.py tests/test_runner.py
git commit -m "feat: rewrite evaluation runner for stage-by-stage execution with artifact accumulation"
```

---

### Task 9: Update Metrics for Per-Stage Tracking

**Files:**
- Modify: `src/desmet/harness/metrics.py`
- Create: `tests/test_metrics.py`

**Step 1: Write failing tests for per-stage metrics**

```python
# tests/test_metrics.py
"""Tests for per-stage metrics tracking."""
import pytest
from pathlib import Path

from desmet.harness.metrics import MetricsCollector, StageMetrics


class TestStageMetrics:
    def test_create_stage_metrics(self):
        m = StageMetrics(
            story_id="US-001",
            platform_id="langgraph",
            stage_name="requirements",
            success=True,
            wall_clock_seconds=15.3,
            iterations=5,
        )
        assert m.stage_name == "requirements"
        assert m.success is True

    def test_collector_records_stage_metrics(self, tmp_path):
        collector = MetricsCollector(tmp_path)
        collector.get_or_create_platform_metrics("langgraph", "LangGraph")
        m = StageMetrics(
            story_id="US-001",
            platform_id="langgraph",
            stage_name="requirements",
            success=True,
            wall_clock_seconds=15.3,
            iterations=5,
        )
        collector.record_stage_metrics("langgraph", m)
        platform_metrics = collector.platform_metrics["langgraph"]
        assert len(platform_metrics.stage_metrics) == 1
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_metrics.py -v`
Expected: FAIL — `StageMetrics` not found

**Step 3: Add StageMetrics and update MetricsCollector**

Add `StageMetrics` dataclass to `src/desmet/harness/metrics.py`:

```python
@dataclass
class StageMetrics:
    """Metrics for a single stage execution."""
    story_id: str
    platform_id: str
    stage_name: str  # "requirements", "codegen", "testing", "deploy"

    success: bool = False
    wall_clock_seconds: float = 0.0
    iterations: int = 0
    tool_calls: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    human_interventions: int = 0

    # Stage-specific scores (0-3)
    correctness_score: float = 0.0
    completeness_score: float = 0.0
    quality_score: float = 0.0
```

Add `stage_metrics: list[StageMetrics]` field to `EvaluationMetrics` and a `record_stage_metrics` method to `MetricsCollector`.

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_metrics.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/desmet/harness/metrics.py tests/test_metrics.py
git commit -m "feat: add per-stage metrics tracking to MetricsCollector"
```

---

### Task 10: Update CLI for Stage-Aware Commands

**Files:**
- Modify: `src/desmet/cli.py`

**Step 1: Read current CLI**

Read: `src/desmet/cli.py`

**Step 2: Update CLI to reflect new stage ordering**

Update the `run` command to accept a `--stage` flag for running individual stages. Update help text and list commands to reflect the new pipeline ordering. Update internal wiring to use the new runner flow.

**Step 3: Verify CLI help works**

Run: `python -m desmet.cli --help`
Expected: shows updated stage names

**Step 4: Commit**

```bash
git add src/desmet/cli.py
git commit -m "feat: update CLI for new stage-aware pipeline"
```

---

### Task 11: Update MEMORY.md and Pipeline Specification

**Files:**
- Modify: `docs/spec/PIPELINE_SPECIFICATION.md`
- Modify: memory file

**Step 1: Update pipeline spec to reflect new ordering**

Update the pipeline specification document to reflect:
- Stage 1 = User Stories (input)
- Stage 2 = Requirements (platform evaluated)
- Adapter-centric design
- Per-stage evaluation with artifact accumulation

**Step 2: Update project memory**

Update MEMORY.md to reflect the new stage structure.

**Step 3: Commit**

```bash
git add docs/spec/PIPELINE_SPECIFICATION.md
git commit -m "docs: update pipeline specification for stories-first restructure"
```

---

### Task 12: Run Full Test Suite and Verify

**Step 1: Run all tests**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests PASS

**Step 2: Verify imports work end-to-end**

```bash
python -c "
from desmet.harness.base import StageContext, StageResult, RequirementsResult, CodeResult, TestResult, DeployResult
from desmet.harness.runner import EvaluationRunner
from desmet.stages.stage1_stories.loader import prepare_stage_context
from desmet.adapters.langgraph import LangGraphAdapter
print('All imports OK')
"
```

**Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: resolve any remaining issues from pipeline restructure"
```
