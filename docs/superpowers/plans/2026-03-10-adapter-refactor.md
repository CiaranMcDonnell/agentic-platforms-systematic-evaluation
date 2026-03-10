# Adapter Refactor Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract shared adapter boilerplate into `_tracing.py`, `_prompts.py`, and `_tools.py` modules, then refactor the LangGraph and CrewAI adapters to use them, reducing duplication and enabling consistent implementation of the remaining 8 adapters.

**Architecture:** Three new internal modules (`_tracing.py`, `_prompts.py`, `_tools.py`) provide shared helpers for trace lifecycle, prompt construction, and sandboxed tool creation. LangGraph and CrewAI adapters shrink from ~870 lines each to ~180 lines by delegating to these modules. The `execute_story()` backwards-compat wrapper moves to `BasePlatformAdapter`.

**Tech Stack:** Python 3.10+, dataclasses, structlog, LangChain tools (`@tool`), CrewAI `BaseTool`/Pydantic, async/await

**Spec:** `docs/superpowers/specs/2026-03-10-adapter-refactor-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|----------------|
| `src/desmet/adapters/_tracing.py` | AgentTrace lifecycle (start, record, finish) + `build_stage_result()` constructor |
| `src/desmet/adapters/_prompts.py` | Stage prompt builders + `AgentPersona` + `build_system_message()` |
| `src/desmet/adapters/_tools.py` | Sandboxed tool factory with format adapters (LangChain, CrewAI, OpenAI, callable) |
| `tests/test_adapter_tracing.py` | Tests for `_tracing.py` |
| `tests/test_adapter_prompts.py` | Tests for `_prompts.py` |
| `tests/test_adapter_tools.py` | Tests for `_tools.py` |

### Modified Files

| File | Change |
|------|--------|
| `src/desmet/adapters/langgraph.py` | Replace inline prompts/tools/tracing with shared module calls (880 → ~180 lines) |
| `src/desmet/adapters/crewai.py` | Same refactor, keep `_create_trace_callbacks()` (873 → ~180 lines) |
| `src/desmet/harness/base.py` | Add default `execute_story()` implementation on `BasePlatformAdapter` |
| `tests/test_langgraph_adapter.py` | Update to test refactored interface |
| `tests/test_crewai_adapter.py` | Update to test refactored interface |

---

## Chunk 1: Shared Modules

### Task 1: Create `_tracing.py`

**Files:**
- Create: `src/desmet/adapters/_tracing.py`
- Test: `tests/test_adapter_tracing.py`
- Reference: `src/desmet/harness/base.py:79-102` (AgentTrace), `src/desmet/harness/base.py:195-325` (StageResult subclasses)

- [ ] **Step 1: Write failing tests for `start_trace()`**

```python
# tests/test_adapter_tracing.py
"""Tests for the shared tracing module."""

from datetime import datetime, timezone

from desmet.adapters._tracing import (
    build_stage_result,
    finish_trace,
    record_message,
    record_tool_call,
    record_usage,
    start_trace,
)
from desmet.harness.base import AgentTrace, RequirementsResult, DeployResult


class TestStartTrace:
    def test_returns_agent_trace(self):
        trace = start_trace()
        assert isinstance(trace, AgentTrace)

    def test_sets_start_time(self):
        before = datetime.now(timezone.utc)
        trace = start_trace()
        after = datetime.now(timezone.utc)
        assert trace.start_time is not None
        assert before <= trace.start_time <= after

    def test_empty_collections(self):
        trace = start_trace()
        assert trace.messages == []
        assert trace.tool_calls == []
        assert trace.errors == []
        assert trace.total_iterations == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_adapter_tracing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'desmet.adapters._tracing'`

- [ ] **Step 3: Implement `start_trace()`**

```python
# src/desmet/adapters/_tracing.py
"""Shared trace lifecycle and result construction helpers.

Used by all 10 platform adapters to manage AgentTrace objects and
build StageResult subclasses from trace data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from desmet.harness.base import (
    AgentMessage,
    AgentTrace,
    StageResult,
    ToolCall,
)


def start_trace() -> AgentTrace:
    """Create a new AgentTrace with start_time set to now (UTC)."""
    return AgentTrace(start_time=datetime.now(timezone.utc))
```

- [ ] **Step 4: Run tests to verify `start_trace` passes**

Run: `uv run pytest tests/test_adapter_tracing.py::TestStartTrace -v`
Expected: 3 PASSED

- [ ] **Step 5: Write failing tests for `record_message`, `record_tool_call`, `record_usage`**

Append to `tests/test_adapter_tracing.py`:

```python
class TestRecordMessage:
    def test_appends_message(self):
        trace = start_trace()
        record_message(trace, "assistant", "Hello")
        assert len(trace.messages) == 1
        msg = trace.messages[0]
        assert msg.role == "assistant"
        assert msg.content == "Hello"
        assert isinstance(msg.timestamp, datetime)

    def test_metadata_kwargs(self):
        trace = start_trace()
        record_message(trace, "assistant", "Hi", metadata={"step": 1})
        assert trace.messages[0].metadata == {"step": 1}


class TestRecordToolCall:
    def test_appends_tool_call(self):
        trace = start_trace()
        record_tool_call(trace, "read_file", {"path": "a.py"}, "contents")
        assert len(trace.tool_calls) == 1
        tc = trace.tool_calls[0]
        assert tc.tool_name == "read_file"
        assert tc.arguments == {"path": "a.py"}
        assert tc.result == "contents"
        assert tc.success is True

    def test_failed_tool_call(self):
        trace = start_trace()
        record_tool_call(trace, "write_file", {}, "err", success=False)
        assert trace.tool_calls[0].success is False

    def test_duration_ms(self):
        trace = start_trace()
        record_tool_call(trace, "read_file", {}, "", duration_ms=42.5)
        assert trace.tool_calls[0].duration_ms == 42.5


class TestRecordUsage:
    def test_accumulates_tokens(self):
        trace = start_trace()
        record_usage(trace, input_tokens=100, output_tokens=50)
        record_usage(trace, input_tokens=200, output_tokens=75)
        assert trace.total_tokens_input == 300
        assert trace.total_tokens_output == 125
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `uv run pytest tests/test_adapter_tracing.py -v -k "RecordMessage or RecordToolCall or RecordUsage"`
Expected: FAIL with `ImportError`

- [ ] **Step 7: Implement `record_message`, `record_tool_call`, `record_usage`**

Append to `src/desmet/adapters/_tracing.py`:

```python
def record_message(
    trace: AgentTrace,
    role: str,
    content: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append an AgentMessage to trace.messages."""
    trace.messages.append(
        AgentMessage(
            role=role,
            content=content,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
    )


def record_tool_call(
    trace: AgentTrace,
    name: str,
    args: dict,
    result: Any,
    *,
    duration_ms: float = 0.0,
    success: bool = True,
) -> None:
    """Append a ToolCall to trace.tool_calls."""
    trace.tool_calls.append(
        ToolCall(
            tool_name=name,
            arguments=args,
            result=result,
            timestamp=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            success=success,
        )
    )


def record_usage(
    trace: AgentTrace,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """Accumulate token usage into the trace."""
    trace.total_tokens_input += input_tokens
    trace.total_tokens_output += output_tokens
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/test_adapter_tracing.py -v -k "RecordMessage or RecordToolCall or RecordUsage"`
Expected: 7 PASSED

- [ ] **Step 9: Write failing tests for `finish_trace`**

Append to `tests/test_adapter_tracing.py`:

```python
class TestFinishTrace:
    def test_sets_end_time(self):
        trace = start_trace()
        finish_trace(trace)
        assert trace.end_time is not None
        assert trace.end_time >= trace.start_time

    def test_sets_final_state(self):
        trace = start_trace()
        finish_trace(trace, final_state={"done": True})
        assert trace.final_state == {"done": True}

    def test_appends_error(self):
        trace = start_trace()
        finish_trace(trace, error="something broke")
        assert "something broke" in trace.errors

    def test_no_error_no_append(self):
        trace = start_trace()
        finish_trace(trace)
        assert trace.errors == []

    def test_idempotent_end_time(self):
        """finish_trace should not overwrite end_time if already set."""
        trace = start_trace()
        finish_trace(trace)
        first_end = trace.end_time
        finish_trace(trace)
        assert trace.end_time == first_end
```

- [ ] **Step 10: Implement `finish_trace`**

Append to `src/desmet/adapters/_tracing.py`:

```python
def finish_trace(
    trace: AgentTrace,
    final_state: dict | None = None,
    error: str | None = None,
) -> None:
    """Set end_time, final_state, and optionally append error to trace.errors."""
    if trace.end_time is None:
        trace.end_time = datetime.now(timezone.utc)
    if final_state is not None:
        trace.final_state = final_state
    if error is not None:
        trace.errors.append(error)
```

- [ ] **Step 11: Run tests to verify they pass**

Run: `uv run pytest tests/test_adapter_tracing.py::TestFinishTrace -v`
Expected: 5 PASSED

- [ ] **Step 12: Write failing tests for `build_stage_result`**

Append to `tests/test_adapter_tracing.py`:

```python
class TestBuildStageResult:
    def test_basic_requirements_result(self):
        trace = start_trace()
        record_tool_call(trace, "read_file", {}, "ok")
        record_tool_call(trace, "write_file", {}, "ok")
        finish_trace(trace)

        result = build_stage_result(
            RequirementsResult,
            platform_id="langgraph",
            stage_name="requirements",
            trace=trace,
            success=True,
            iterations=5,
        )
        assert isinstance(result, RequirementsResult)
        assert result.platform_id == "langgraph"
        assert result.stage_name == "requirements"
        assert result.success is True
        assert result.completed is True
        assert result.iterations == 5
        assert result.tool_calls_count == 2
        assert result.start_time == trace.start_time
        assert result.end_time == trace.end_time
        assert result.wall_clock_seconds == trace.duration_seconds
        assert result.trace is trace

    def test_failed_result_with_error(self):
        trace = start_trace()
        finish_trace(trace)

        result = build_stage_result(
            RequirementsResult,
            platform_id="crewai",
            stage_name="requirements",
            trace=trace,
            success=False,
            iterations=0,
            error_message="API timeout",
        )
        assert result.success is False
        assert result.completed is False
        assert result.error_message == "API timeout"

    def test_auto_finishes_trace(self):
        """build_stage_result should call finish_trace if end_time not set."""
        trace = start_trace()
        result = build_stage_result(
            RequirementsResult,
            platform_id="test",
            stage_name="requirements",
            trace=trace,
            success=True,
            iterations=1,
        )
        assert trace.end_time is not None
        assert result.end_time is not None

    def test_extra_fields_passed_through(self):
        trace = start_trace()
        finish_trace(trace)

        result = build_stage_result(
            DeployResult,
            platform_id="test",
            stage_name="deploy",
            trace=trace,
            success=True,
            iterations=3,
            build_success=True,
            deployment_ready=True,
        )
        assert isinstance(result, DeployResult)
        assert result.build_success is True
        assert result.deployment_ready is True

    def test_token_counts_from_trace(self):
        trace = start_trace()
        record_usage(trace, input_tokens=500, output_tokens=200)
        finish_trace(trace)

        result = build_stage_result(
            RequirementsResult,
            platform_id="test",
            stage_name="requirements",
            trace=trace,
            success=True,
            iterations=1,
        )
        assert result.tokens_input == 500
        assert result.tokens_output == 200
```

- [ ] **Step 13: Implement `build_stage_result`**

Append to `src/desmet/adapters/_tracing.py`:

```python
def build_stage_result(
    result_cls: type[StageResult],
    platform_id: str,
    stage_name: str,
    trace: AgentTrace,
    success: bool,
    iterations: int,
    error_message: str | None = None,
    **extra_fields: Any,
) -> StageResult:
    """Construct a StageResult subclass from trace data.

    Automatically derives timing, token, and tool-call fields from the
    trace.  Calls finish_trace() if end_time is not yet set.
    """
    if trace.end_time is None:
        finish_trace(trace)

    completed = extra_fields.pop("completed", success)

    return result_cls(
        platform_id=platform_id,
        stage_name=stage_name,
        success=success,
        completed=completed,
        error_message=error_message,
        trace=trace,
        wall_clock_seconds=trace.duration_seconds,
        iterations=iterations,
        tool_calls_count=len(trace.tool_calls),
        tokens_input=trace.total_tokens_input,
        tokens_output=trace.total_tokens_output,
        start_time=trace.start_time,
        end_time=trace.end_time,
        **extra_fields,
    )
```

- [ ] **Step 14: Run all tracing tests**

Run: `uv run pytest tests/test_adapter_tracing.py -v`
Expected: All PASSED

- [ ] **Step 15: Commit**

```bash
git add src/desmet/adapters/_tracing.py tests/test_adapter_tracing.py
git commit -m "feat(adapters): add shared _tracing module with trace lifecycle + result builder"
```

---

### Task 2: Create `_prompts.py`

**Files:**
- Create: `src/desmet/adapters/_prompts.py`
- Test: `tests/test_adapter_prompts.py`
- Reference: `src/desmet/adapters/langgraph.py:160-173` (requirements prompt), `src/desmet/adapters/langgraph.py:537-549` (deploy prompt), `src/desmet/adapters/crewai.py:128-143` (CrewAI personas), `src/desmet/harness/story.py:42-75` (UserStory)

To extract the correct prompt text, read the prompt-building blocks from both existing adapters. The prompts in LangGraph and CrewAI are nearly identical — use them as the canonical source.

- [ ] **Step 1: Write failing tests for prompt builders**

```python
# tests/test_adapter_prompts.py
"""Tests for the shared prompts module."""

from dataclasses import dataclass, field

from desmet.adapters._prompts import (
    AgentPersona,
    build_codegen_prompt,
    build_deploy_prompt,
    build_requirements_prompt,
    build_system_message,
    build_testing_prompt,
    get_stage_persona,
)
from desmet.harness.base import RequirementsResult
from desmet.harness.story import DifficultyLevel, UserStory


def _make_story(**overrides) -> UserStory:
    """Create a minimal UserStory for testing."""
    defaults = dict(
        id="US-TEST",
        title="Test Story",
        description="A test story description.",
        difficulty=DifficultyLevel.BASIC,
        category="code_generation",
        prompt="Implement a hello world function.",
        context="",
        system_prompt=None,
    )
    defaults.update(overrides)
    return UserStory(**defaults)


class TestBuildRequirementsPrompt:
    def test_includes_title(self):
        story = _make_story(title="Email Validator")
        prompt = build_requirements_prompt(story)
        assert "Email Validator" in prompt

    def test_includes_description(self):
        story = _make_story(description="Validate email addresses")
        prompt = build_requirements_prompt(story)
        assert "Validate email addresses" in prompt

    def test_includes_story_prompt(self):
        story = _make_story(prompt="Write a function that validates emails")
        prompt = build_requirements_prompt(story)
        assert "Write a function that validates emails" in prompt

    def test_does_not_include_acceptance_criteria(self):
        """Acceptance criteria are for scoring, not agent input."""
        from desmet.harness.story import AcceptanceCriterion
        story = _make_story()
        story.acceptance_criteria = [
            AcceptanceCriterion(id="AC-1", description="Must pass tests")
        ]
        prompt = build_requirements_prompt(story)
        assert "AC-1" not in prompt
        assert "Must pass tests" not in prompt


class TestBuildCodegenPrompt:
    def test_includes_story_prompt(self):
        story = _make_story(prompt="Build the widget")
        prompt = build_codegen_prompt(story, prior_requirements=None)
        assert "Build the widget" in prompt

    def test_no_prior_requirements(self):
        story = _make_story()
        prompt = build_codegen_prompt(story, prior_requirements=None)
        assert "Prior Requirements" not in prompt

    def test_appends_prior_requirements_fields(self):
        story = _make_story()
        prior = RequirementsResult(
            platform_id="test",
            stage_name="requirements",
            success=True,
            functional_requirements=[{"id": "FR-1", "desc": "Must validate"}],
            entities=[{"name": "User"}],
        )
        prompt = build_codegen_prompt(story, prior_requirements=prior)
        assert "Prior Requirements" in prompt
        assert "FR-1" in prompt
        assert "User" in prompt


class TestBuildDeployPrompt:
    def test_includes_title_and_description(self):
        story = _make_story(title="Deploy Test", description="Deploy desc")
        prompt = build_deploy_prompt(story)
        assert "Deploy Test" in prompt
        assert "Deploy desc" in prompt

    def test_excludes_story_prompt(self):
        story = _make_story(prompt="UNIQUE_PROMPT_TEXT_NOT_IN_DEPLOY")
        prompt = build_deploy_prompt(story)
        assert "UNIQUE_PROMPT_TEXT_NOT_IN_DEPLOY" not in prompt

    def test_includes_build_instructions(self):
        story = _make_story()
        prompt = build_deploy_prompt(story)
        assert "build" in prompt.lower() or "deploy" in prompt.lower()


class TestBuildTestingPrompt:
    def test_includes_story_prompt(self):
        story = _make_story(prompt="Test the widget")
        prompt = build_testing_prompt(story)
        assert "Test the widget" in prompt


class TestBuildSystemMessage:
    def test_returns_none_when_no_context(self):
        story = _make_story(context="", system_prompt=None)
        assert build_system_message(story) is None

    def test_prefers_system_prompt(self):
        story = _make_story(
            context="fallback context",
            system_prompt="explicit system prompt",
        )
        assert build_system_message(story) == "explicit system prompt"

    def test_falls_back_to_context(self):
        story = _make_story(context="some context", system_prompt=None)
        assert build_system_message(story) == "some context"


class TestGetStagePersona:
    def test_requirements_analyst(self):
        p = get_stage_persona("requirements")
        assert isinstance(p, AgentPersona)
        assert "Requirements Analyst" in p.role

    def test_software_developer(self):
        p = get_stage_persona("codegen")
        assert "Software Developer" in p.role or "Developer" in p.role

    def test_qa_engineer(self):
        p = get_stage_persona("testing")
        assert "QA" in p.role

    def test_devops_engineer(self):
        p = get_stage_persona("deploy")
        assert "DevOps" in p.role

    def test_unknown_stage_raises(self):
        import pytest
        with pytest.raises(KeyError):
            get_stage_persona("unknown_stage")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_adapter_prompts.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `_prompts.py`**

Read the exact prompt text from `src/desmet/adapters/langgraph.py` lines 160-173 (requirements), 275-304 (codegen), 405-425 (testing), 537-549 (deploy) to extract the canonical prompts. Then implement:

```python
# src/desmet/adapters/_prompts.py
"""Shared stage prompt builders and agent persona definitions.

Pure functions with no framework dependencies. Used by all 10 platform
adapters to construct consistent prompts for each pipeline stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from desmet.harness.story import UserStory

from desmet.harness.base import RequirementsResult


@dataclass(frozen=True)
class AgentPersona:
    """Role definition for agent-based frameworks (CrewAI, AutoGen)."""
    role: str
    goal: str
    backstory: str


_PERSONAS: dict[str, AgentPersona] = {
    "requirements": AgentPersona(
        role="Requirements Analyst",
        goal="Analyse the user story and produce a structured requirements specification",
        backstory=(
            "You are an experienced software architect and business analyst. "
            "You always write artefacts to disk using the provided tools. "
            "You decompose user stories into clear, actionable requirements."
        ),
    ),
    "codegen": AgentPersona(
        role="Software Developer",
        goal="Complete the assigned programming task by writing all required files",
        backstory=(
            "You are an experienced software developer and architect. "
            "You always write files to disk using the provided tools. "
            "You create complete, well-structured documents and code."
        ),
    ),
    "testing": AgentPersona(
        role="QA Engineer",
        goal="Write comprehensive tests, execute them, and report results",
        backstory=(
            "You are an experienced QA engineer and test automation specialist. "
            "You write thorough unit and integration tests, execute them, "
            "and report precise pass/fail counts."
        ),
    ),
    "deploy": AgentPersona(
        role="DevOps Engineer",
        goal="Build the project and verify it is deployment-ready",
        backstory=(
            "You are an experienced DevOps engineer. "
            "You build projects, resolve dependency issues, "
            "and verify deployment readiness."
        ),
    ),
}


def get_stage_persona(stage_name: str) -> AgentPersona:
    """Return the agent persona for a given stage.

    Raises KeyError if stage_name is not recognised.
    """
    return _PERSONAS[stage_name]


# Stage-specific expected_output strings for CrewAI Task objects.
STAGE_EXPECTED_OUTPUTS: dict[str, str] = {
    "requirements": "All requirements documents and UML diagrams written to disk",
    "codegen": "All required files written to disk using the write_file tool",
    "testing": "Test files written, test suite executed, and results reported",
    "deploy": "Build completed, deployment readiness verified, and any issues reported",
}


def build_requirements_prompt(story: UserStory) -> str:
    """Build the prompt for the requirements analysis stage."""
    # Matches langgraph.py lines 160-173 and crewai.py lines 145-158 exactly.
    # Acceptance criteria are NOT included (used for scoring, not agent input).
    return (
        f"Analyse the following user story and produce a structured "
        f"requirements specification.\n\n"
        f"## User Story\n"
        f"**{story.title}**\n"
        f"{story.description}\n\n"
        f"## Prompt\n{story.prompt}\n\n"
        f"You must:\n"
        f"1. Decompose the story into functional and non-functional requirements.\n"
        f"2. Identify domain entities, relationships and API endpoints.\n"
        f"3. Identify use cases.\n"
        f"4. Produce UML diagrams (class, sequence, use-case) in PlantUML format.\n"
        f"5. Write all artefacts as files in the workspace.\n"
    )


def build_codegen_prompt(
    story: UserStory,
    prior_requirements: RequirementsResult | None = None,
) -> str:
    """Build the prompt for code generation."""
    # Matches langgraph.py lines 284-304 — uses story.prompt as the base,
    # then appends structured prior-requirements fields inline.
    prompt = story.prompt

    if prior_requirements is not None:
        prompt += (
            "\n\n## Prior Requirements Analysis\n"
            "The following requirements were produced in the previous stage. "
            "Use them to guide your implementation.\n"
        )
        if isinstance(prior_requirements, RequirementsResult):
            if prior_requirements.functional_requirements:
                prompt += f"\nFunctional requirements: {prior_requirements.functional_requirements}"
            if prior_requirements.non_functional_requirements:
                prompt += f"\nNon-functional requirements: {prior_requirements.non_functional_requirements}"
            if prior_requirements.use_cases:
                prompt += f"\nUse cases: {prior_requirements.use_cases}"
            if prior_requirements.entities:
                prompt += f"\nEntities: {prior_requirements.entities}"
            if prior_requirements.api_endpoints:
                prompt += f"\nAPI endpoints: {prior_requirements.api_endpoints}"

    return prompt


def build_testing_prompt(story: UserStory) -> str:
    """Build the prompt for test generation and execution."""
    # Matches langgraph.py lines 414-427 exactly.
    return (
        f"Write tests for the following user story, execute them, and "
        f"report the results.\n\n"
        f"## User Story\n"
        f"**{story.title}**\n"
        f"{story.description}\n\n"
        f"## Prompt\n{story.prompt}\n\n"
        f"You must:\n"
        f"1. Read the existing code in the workspace.\n"
        f"2. Write comprehensive unit and integration tests.\n"
        f"3. Run the test suite.\n"
        f"4. Report the number of tests run, passed, and failed.\n"
        f"5. If tests fail, attempt to fix the code and re-run.\n"
    )


def build_deploy_prompt(story: UserStory) -> str:
    """Build the prompt for build and deployment verification.

    Includes story.title and story.description only — NOT story.prompt.
    """
    return (
        f"Build the project and verify it is deployment-ready.\n\n"
        f"## User Story\n"
        f"**{story.title}**\n"
        f"{story.description}\n\n"
        f"You must:\n"
        f"1. Install all dependencies.\n"
        f"2. Run the build step (compilation, bundling, etc.).\n"
        f"3. Run the test suite to verify the build.\n"
        f"4. Verify the build artefact starts or passes a smoke test.\n"
        f"5. Report whether the project is deployment-ready and list any "
        f"dependency or build issues encountered.\n"
    )


def build_system_message(story: UserStory) -> str | None:
    """Return the system message, or None.

    Prefers story.system_prompt if set; falls back to story.context if
    non-empty.
    """
    if story.system_prompt:
        return story.system_prompt
    if story.context:
        return story.context
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_adapter_prompts.py -v`
Expected: All PASSED

- [ ] **Step 5: Commit**

```bash
git add src/desmet/adapters/_prompts.py tests/test_adapter_prompts.py
git commit -m "feat(adapters): add shared _prompts module with stage prompt builders + personas"
```

---

### Task 3: Create `_tools.py`

**Files:**
- Create: `src/desmet/adapters/_tools.py`
- Test: `tests/test_adapter_tools.py`
- Reference: `src/desmet/adapters/langgraph.py:700-847` (LangChain tools), `src/desmet/adapters/crewai.py:654-850` (CrewAI tools), `src/desmet/harness/base.py:232-258` (StageContext.allowed_tools)

- [ ] **Step 1: Write failing tests for core tool functions**

```python
# tests/test_adapter_tools.py
"""Tests for the shared tools module."""

import os
from pathlib import Path

import pytest

from desmet.adapters._tools import (
    AVAILABLE_TOOLS,
    ToolFormat,
    create_tools,
    _safe_resolve,
)


@pytest.fixture
def workspace(tmp_path):
    """Create a workspace directory with some test files."""
    (tmp_path / "hello.py").write_text("print('hello')")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "data.txt").write_text("some data")
    return tmp_path


class TestAvailableTools:
    def test_all_tool_names(self):
        assert "read_file" in AVAILABLE_TOOLS
        assert "write_file" in AVAILABLE_TOOLS
        assert "list_directory" in AVAILABLE_TOOLS
        assert "execute_shell" in AVAILABLE_TOOLS
        assert "search_code" in AVAILABLE_TOOLS


class TestSafeResolve:
    def test_valid_relative_path(self, workspace):
        resolved = _safe_resolve(workspace, "hello.py")
        assert resolved == workspace / "hello.py"

    def test_rejects_path_traversal(self, workspace):
        with pytest.raises(ValueError, match="outside workspace"):
            _safe_resolve(workspace, "../etc/passwd")

    def test_rejects_absolute_path(self, workspace):
        # Use a path guaranteed to be outside workspace on any OS
        with pytest.raises(ValueError, match="outside workspace"):
            _safe_resolve(workspace, "../../../../../../tmp/evil")

    def test_subdirectory_allowed(self, workspace):
        resolved = _safe_resolve(workspace, "subdir/data.txt")
        assert resolved == workspace / "subdir" / "data.txt"


class TestCreateToolsCallable:
    def test_returns_correct_count(self, workspace):
        tools = create_tools(
            workspace,
            ["read_file", "write_file"],
            fmt=ToolFormat.CALLABLE,
        )
        assert len(tools) == 2

    def test_all_tools(self, workspace):
        tools = create_tools(
            workspace,
            list(AVAILABLE_TOOLS),
            fmt=ToolFormat.CALLABLE,
        )
        assert len(tools) == 5

    def test_read_file(self, workspace):
        tools = create_tools(workspace, ["read_file"], fmt=ToolFormat.CALLABLE)
        read_fn = tools[0]
        result = read_fn(path="hello.py")
        assert "print('hello')" in result

    def test_write_file(self, workspace):
        tools = create_tools(workspace, ["write_file"], fmt=ToolFormat.CALLABLE)
        write_fn = tools[0]
        write_fn(path="new.py", content="x = 1")
        assert (workspace / "new.py").read_text() == "x = 1"

    def test_list_directory(self, workspace):
        tools = create_tools(workspace, ["list_directory"], fmt=ToolFormat.CALLABLE)
        list_fn = tools[0]
        result = list_fn(path=".")
        assert "hello.py" in result
        assert "subdir" in result

    def test_search_code(self, workspace):
        tools = create_tools(workspace, ["search_code"], fmt=ToolFormat.CALLABLE)
        search_fn = tools[0]
        result = search_fn(pattern="hello")
        assert "hello.py" in result

    def test_skips_unknown_tool(self, workspace):
        tools = create_tools(workspace, ["nonexistent"], fmt=ToolFormat.CALLABLE)
        assert len(tools) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_adapter_tools.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `_tools.py` — core functions and callable format**

```python
# src/desmet/adapters/_tools.py
"""Sandboxed tool factory for Python SDK platform adapters.

Creates workspace-scoped tools in the format required by each framework.
All file operations are restricted to the workspace directory.
"""

from __future__ import annotations

import os
import subprocess
from enum import Enum
from pathlib import Path
from typing import Any


class ToolFormat(Enum):
    """Output format for tools."""
    LANGCHAIN = "langchain"
    CREWAI = "crewai"
    OPENAI_FUNCTION = "openai"
    CALLABLE = "callable"


AVAILABLE_TOOLS = ("read_file", "write_file", "list_directory", "execute_shell", "search_code")


def _safe_resolve(workspace: Path, path: str) -> Path:
    """Resolve *path* relative to *workspace*, rejecting escapes."""
    resolved = (workspace / path).resolve()
    workspace_resolved = workspace.resolve()
    try:
        resolved.relative_to(workspace_resolved)
    except ValueError:
        raise ValueError(
            f"Path {path!r} resolves outside workspace: {resolved}"
        ) from None
    return resolved


# ---- Core tool implementations (format-agnostic) ----

def _read_file(workspace: Path, path: str) -> str:
    target = _safe_resolve(workspace, path)
    if not target.is_file():
        return f"Error: File not found: {path}"
    return target.read_text(encoding="utf-8", errors="replace")


def _write_file(workspace: Path, path: str, content: str) -> str:
    target = _safe_resolve(workspace, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Written {len(content)} bytes to {path}"


def _list_directory(workspace: Path, path: str = ".") -> str:
    target = _safe_resolve(workspace, path)
    if not target.is_dir():
        return f"Error: Not a directory: {path}"
    entries = sorted(os.listdir(target))
    return "\n".join(entries) if entries else "(empty directory)"


def _execute_shell(workspace: Path, command: str) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(workspace.resolve()),
            capture_output=True,
            text=True,
            timeout=30,  # matches current adapter timeout
        )
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n(exit code {result.returncode})"
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds"
    except Exception as e:
        return f"Error: {e}"


def _search_code(workspace: Path, pattern: str, path: str = ".") -> str:
    """Search file contents for a pattern (simple grep-like)."""
    target = _safe_resolve(workspace, path)
    matches: list[str] = []
    search_root = target if target.is_dir() else target.parent

    for root, _dirs, files in os.walk(search_root):
        for fname in sorted(files):
            fpath = Path(root) / fname
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(text.splitlines(), 1):
                    if pattern in line:
                        rel = fpath.relative_to(workspace.resolve())
                        matches.append(f"{rel}:{i}: {line.strip()}")
            except (OSError, UnicodeDecodeError):
                continue

    if not matches:
        return f"No matches for pattern: {pattern!r}"
    return "\n".join(matches[:100])  # cap output


# ---- Format adapters ----

def _build_callable_tools(workspace: Path, names: list[str]) -> list:
    """Return plain Python callables."""
    registry = {
        "read_file": lambda path: _read_file(workspace, path),
        "write_file": lambda path, content: _write_file(workspace, path, content),
        "list_directory": lambda path=".": _list_directory(workspace, path),
        "execute_shell": lambda command: _execute_shell(workspace, command),
        "search_code": lambda pattern, path=".": _search_code(workspace, pattern, path),
    }
    return [registry[n] for n in names if n in registry]


def create_tools(
    workspace: Path,
    allowed_tools: list[str],
    fmt: ToolFormat = ToolFormat.CALLABLE,
) -> list:
    """Create sandbox tools scoped to the given workspace.

    Returns tools in the format expected by the target framework.
    Only tools listed in *allowed_tools* are created.
    """
    # Filter to known tools, preserving order
    names = [t for t in allowed_tools if t in AVAILABLE_TOOLS]

    if fmt == ToolFormat.CALLABLE:
        return _build_callable_tools(workspace, names)
    elif fmt == ToolFormat.LANGCHAIN:
        return _build_langchain_tools(workspace, names)
    elif fmt == ToolFormat.CREWAI:
        return _build_crewai_tools(workspace, names)
    elif fmt == ToolFormat.OPENAI_FUNCTION:
        return _build_openai_tools(workspace, names)
    else:
        raise ValueError(f"Unknown tool format: {fmt}")


def _build_langchain_tools(workspace: Path, names: list[str]) -> list:
    """Return LangChain @tool decorated functions."""
    from langchain_core.tools import tool as lc_tool

    tools = []

    if "read_file" in names:
        @lc_tool
        def read_file(path: str) -> str:
            """Read the contents of a file at the given relative path."""
            return _read_file(workspace, path)
        tools.append(read_file)

    if "write_file" in names:
        @lc_tool
        def write_file(path: str, content: str) -> str:
            """Write content to a file at the given relative path."""
            return _write_file(workspace, path, content)
        tools.append(write_file)

    if "list_directory" in names:
        @lc_tool
        def list_directory(path: str = ".") -> str:
            """List files and directories at the given relative path."""
            return _list_directory(workspace, path)
        tools.append(list_directory)

    if "execute_shell" in names:
        @lc_tool
        def execute_shell(command: str) -> str:
            """Execute a shell command in the workspace directory."""
            return _execute_shell(workspace, command)
        tools.append(execute_shell)

    if "search_code" in names:
        @lc_tool
        def search_code(pattern: str, path: str = ".") -> str:
            """Search file contents for a pattern (grep-like)."""
            return _search_code(workspace, pattern, path)
        tools.append(search_code)

    return tools


def _build_crewai_tools(workspace: Path, names: list[str]) -> list:
    """Return CrewAI BaseTool subclasses."""
    from crewai.tools import BaseTool as CrewAIBaseTool
    from pydantic import BaseModel, Field

    tools = []

    if "read_file" in names:
        class ReadFileInput(BaseModel):
            path: str = Field(description="Relative path to the file")

        class ReadFileTool(CrewAIBaseTool):
            name: str = "read_file"
            description: str = "Read the contents of a file at the given relative path"
            args_schema: type[BaseModel] = ReadFileInput

            def _run(self, path: str) -> str:
                return _read_file(workspace, path)

        tools.append(ReadFileTool())

    if "write_file" in names:
        class WriteFileInput(BaseModel):
            path: str = Field(description="Relative path to the file")
            content: str = Field(description="Content to write")

        class WriteFileTool(CrewAIBaseTool):
            name: str = "write_file"
            description: str = "Write content to a file at the given relative path"
            args_schema: type[BaseModel] = WriteFileInput

            def _run(self, path: str, content: str) -> str:
                return _write_file(workspace, path, content)

        tools.append(WriteFileTool())

    if "list_directory" in names:
        class ListDirInput(BaseModel):
            path: str = Field(default=".", description="Relative directory path")

        class ListDirectoryTool(CrewAIBaseTool):
            name: str = "list_directory"
            description: str = "List files and directories at the given relative path"
            args_schema: type[BaseModel] = ListDirInput

            def _run(self, path: str = ".") -> str:
                return _list_directory(workspace, path)

        tools.append(ListDirectoryTool())

    if "execute_shell" in names:
        class ShellInput(BaseModel):
            command: str = Field(description="Shell command to execute")

        class ExecuteShellTool(CrewAIBaseTool):
            name: str = "execute_shell"
            description: str = "Execute a shell command in the workspace directory"
            args_schema: type[BaseModel] = ShellInput

            def _run(self, command: str) -> str:
                return _execute_shell(workspace, command)

        tools.append(ExecuteShellTool())

    if "search_code" in names:
        class SearchInput(BaseModel):
            pattern: str = Field(description="Pattern to search for")
            path: str = Field(default=".", description="Relative path to search in")

        class SearchCodeTool(CrewAIBaseTool):
            name: str = "search_code"
            description: str = "Search file contents for a pattern (grep-like)"
            args_schema: type[BaseModel] = SearchInput

            def _run(self, pattern: str, path: str = ".") -> str:
                return _search_code(workspace, pattern, path)

        tools.append(SearchCodeTool())

    return tools


def _build_openai_tools(workspace: Path, names: list[str]) -> list:
    """Return OpenAI function-calling format dicts + callables.

    Returns a list of (schema_dict, callable) tuples that adapters
    can register with their framework.
    """
    registry: dict[str, tuple[dict, Any]] = {
        "read_file": (
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read the contents of a file at the given relative path",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string", "description": "Relative path"}},
                        "required": ["path"],
                    },
                },
            },
            lambda path: _read_file(workspace, path),
        ),
        "write_file": (
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write content to a file at the given relative path",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative path"},
                            "content": {"type": "string", "description": "Content to write"},
                        },
                        "required": ["path", "content"],
                    },
                },
            },
            lambda path, content: _write_file(workspace, path, content),
        ),
        "list_directory": (
            {
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "description": "List files and directories at the given relative path",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string", "description": "Relative path"}},
                        "required": [],
                    },
                },
            },
            lambda path=".": _list_directory(workspace, path),
        ),
        "execute_shell": (
            {
                "type": "function",
                "function": {
                    "name": "execute_shell",
                    "description": "Execute a shell command in the workspace directory",
                    "parameters": {
                        "type": "object",
                        "properties": {"command": {"type": "string", "description": "Shell command"}},
                        "required": ["command"],
                    },
                },
            },
            lambda command: _execute_shell(workspace, command),
        ),
        "search_code": (
            {
                "type": "function",
                "function": {
                    "name": "search_code",
                    "description": "Search file contents for a pattern (grep-like)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string", "description": "Pattern to search for"},
                            "path": {"type": "string", "description": "Relative path to search in"},
                        },
                        "required": ["pattern"],
                    },
                },
            },
            lambda pattern, path=".": _search_code(workspace, pattern, path),
        ),
    }
    return [registry[n] for n in names if n in registry]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_adapter_tools.py -v`
Expected: All PASSED

- [ ] **Step 5: Commit**

```bash
git add src/desmet/adapters/_tools.py tests/test_adapter_tools.py
git commit -m "feat(adapters): add shared _tools module with sandboxed tool factory"
```

---

## Chunk 2: Refactor Existing Adapters

### Task 4: Move `execute_story()` to `BasePlatformAdapter`

**Files:**
- Modify: `src/desmet/harness/base.py:376-396` (change from abstractmethod to default impl)
- Reference: `src/desmet/adapters/langgraph.py:639-694` (current execute_story impl)

- [ ] **Step 1: Write a test for the default `execute_story()` wrapper**

```python
# Append to tests/test_harness_base.py or create tests/test_execute_story_compat.py
"""Test that BasePlatformAdapter provides a default execute_story()."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from desmet.harness.base import (
    BasePlatformAdapter,
    CodeResult,
    EvaluationContext,
    ExecutionResult,
    PlatformCategory,
    PlatformInfo,
    PlatformRuntime,
    StageContext,
)
from desmet.harness.story import DifficultyLevel, UserStory


class ConcreteAdapter(BasePlatformAdapter):
    """Minimal concrete adapter for testing."""

    @property
    def platform_info(self):
        return PlatformInfo(
            name="Test", id="test", category=PlatformCategory.AGENT_SDK_RUNTIME,
            runtime=PlatformRuntime.PYTHON, version="0.1",
            vendor="test", description="test", documentation_url="",
            repository_url="",
        )

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    async def generate_requirements(self, context):
        raise NotImplementedError

    async def generate_code(self, context):
        return CodeResult(
            platform_id="test", stage_name="codegen", success=True,
            completed=True, output_files=["main.py"],
        )

    async def generate_tests(self, context):
        raise NotImplementedError

    async def build_and_deploy(self, context):
        raise NotImplementedError

    async def health_check(self):
        return True


class TestExecuteStoryDefault:
    def test_delegates_to_generate_code(self, tmp_path):
        adapter = ConcreteAdapter()
        ctx = EvaluationContext(
            story_id="US-001",
            story_prompt="Build a thing",
            story_context="",
            repo_path=tmp_path,
        )
        result = asyncio.run(adapter.execute_story(ctx))
        assert isinstance(result, ExecutionResult)
        assert result.success is True
        assert result.platform_id == "test"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_execute_story_compat.py -v`
Expected: FAIL (execute_story is abstract, ConcreteAdapter doesn't implement it)

- [ ] **Step 3: Modify `BasePlatformAdapter.execute_story()` to provide default implementation**

In `src/desmet/harness/base.py`, change `execute_story` from `@abstractmethod` to a concrete default that converts `EvaluationContext` → `StageContext`, calls `generate_code()`, and converts `CodeResult` → `ExecutionResult`. Copy the logic from `langgraph.py:639-694`.

The key change: remove `@abstractmethod` and add the implementation body.

```python
async def execute_story(self, context: EvaluationContext) -> ExecutionResult:
    """Backwards-compatible wrapper: convert legacy context to StageContext
    and delegate to generate_code()."""
    # Deferred import to avoid circular dependency (base.py ↔ story.py)
    from desmet.harness.story import DifficultyLevel, UserStory

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
        max_tool_calls=context.max_tool_calls,
        allowed_tools=context.allowed_tools,
        model=context.model,
        temperature=context.temperature,
    )
    code_result = await self.generate_code(stage_ctx)
    return ExecutionResult(
        platform_id=self.platform_info.id,
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

No top-level import needed — uses deferred import inside the method body to avoid circular dependency.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_execute_story_compat.py -v`
Expected: PASS

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `uv run pytest tests/ -v`
Expected: All existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add src/desmet/harness/base.py tests/test_execute_story_compat.py
git commit -m "refactor(harness): move execute_story() default impl to BasePlatformAdapter"
```

---

### Task 5: Refactor LangGraph Adapter

**Files:**
- Modify: `src/desmet/adapters/langgraph.py` (880 → ~180 lines)
- Test: `tests/test_langgraph_adapter.py`

This is the largest single task. The approach:
1. Replace all prompt-building inline code with `_prompts` calls
2. Replace `_create_tools_from_stage_context` with `_tools.create_tools`
3. Replace all trace setup/recording with `_tracing` calls
4. Replace all result construction with `build_stage_result`
5. Delete `execute_story()` (now inherited from base)
6. Delete `_create_tools()` legacy method
7. Keep these methods unchanged: `_create_chat_model` (static), `initialize`, `shutdown`, `health_check`, `reset_state`, `get_observability_info`, `get_failure_handling_info`
8. Extract `_run_agent()` as the single platform-specific method

- [ ] **Step 1: Read the current langgraph.py thoroughly**

Read: `src/desmet/adapters/langgraph.py` (all 880 lines)
Note the exact structure of each stage method so nothing is lost.

- [ ] **Step 2: Refactor `generate_requirements`**

Replace the inline prompt, tool creation, trace setup, and result construction in `generate_requirements()` (lines 135-257) with shared module calls. The method should shrink to ~20 lines:

```python
async def generate_requirements(self, context: StageContext) -> RequirementsResult:
    trace = start_trace()
    try:
        prompt = build_requirements_prompt(context.story)
        system_msg = build_system_message(context.story)
        tools = create_tools(context.workspace, context.allowed_tools, fmt=ToolFormat.LANGCHAIN)
        iterations, hit_limit = await self._run_agent(prompt, system_msg, tools, trace, context)
        return build_stage_result(
            RequirementsResult, self.platform_info.id, "requirements",
            trace, success=not hit_limit, iterations=iterations,
        )
    except Exception as e:
        finish_trace(trace, error=str(e))
        return build_stage_result(
            RequirementsResult, self.platform_info.id, "requirements",
            trace, success=False, iterations=0, error_message=str(e),
        )
```

- [ ] **Step 3: Refactor `generate_code`, `generate_tests`, `build_and_deploy`**

Apply the same pattern. Each becomes ~20 lines using the shared module calls. For `generate_code`, pass `context.get_prior_result("requirements")` to `build_codegen_prompt`.

- [ ] **Step 4: Extract `_run_agent()` method**

This is the core LangGraph-specific method. It:
1. Creates a `create_react_agent` with the checkpointer
2. Builds config dict with thread_id and optional Langfuse callback
3. Streams events via `agent.astream()`, recording messages and tool calls to trace
4. Returns `(iterations, hit_limit)` tuple

```python
async def _run_agent(
    self,
    prompt: str,
    system_msg: str | None,
    tools: list,
    trace: AgentTrace,
    context: StageContext,
) -> tuple[int, bool]:
    """Run a LangGraph ReAct agent and record trace data.

    Returns (iteration_count, hit_iteration_limit).
    """
    from langgraph.prebuilt import create_react_agent
    from langchain_core.messages import HumanMessage, SystemMessage

    agent = create_react_agent(self._llm, tools, checkpointer=self._checkpointer)
    execution_id = self._create_execution_id()

    messages = []
    if system_msg:
        messages.append(SystemMessage(content=system_msg))
    messages.append(HumanMessage(content=prompt))

    record_message(trace, "user", prompt)

    config: dict[str, Any] = {"configurable": {"thread_id": execution_id}}
    lf_cb = get_langchain_callback()
    if lf_cb is not None:
        config["callbacks"] = [lf_cb]

    final_state = None
    iteration = 0
    hit_limit = False

    async for event in agent.astream(
        {"messages": messages}, config=config, stream_mode="values",
    ):
        iteration += 1
        final_state = event  # track last event for finish_trace

        if "messages" in event and event["messages"]:
            # stream_mode="values" yields the FULL accumulated message list
            # each time, so we only process the last (newest) message to
            # avoid recording duplicates.
            last_msg = event["messages"][-1]
            content = getattr(last_msg, "content", "")
            role = getattr(last_msg, "type", "assistant")
            if content:
                record_message(trace, role, str(content))
            # Extract token usage if available (handles both Anthropic
            # and OpenAI key formats)
            usage = getattr(last_msg, "response_metadata", {}).get("usage", {})
            if usage:
                record_usage(
                    trace,
                    input_tokens=usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0) or usage.get("completion_tokens", 0),
                )
            # Record tool calls from the message
            tool_calls = getattr(last_msg, "tool_calls", [])
            for tc in tool_calls:
                record_tool_call(
                    trace,
                    tc.get("name", "unknown"),
                    tc.get("args", {}),
                    "",  # result comes in next event
                )

        if iteration >= context.max_iterations:
            hit_limit = True
            break

    trace.total_iterations = iteration
    finish_trace(trace, final_state=final_state)
    return iteration, hit_limit
```

- [ ] **Step 5: Delete inline `_create_tools_from_stage_context`, `_create_tools`, and `execute_story`**

These are fully replaced by `_tools.create_tools()` and the base class `execute_story()`.

- [ ] **Step 6: Add imports at top of langgraph.py**

```python
from desmet.adapters._prompts import (
    build_codegen_prompt,
    build_deploy_prompt,
    build_requirements_prompt,
    build_system_message,
    build_testing_prompt,
)
from desmet.adapters._tools import ToolFormat, create_tools
from desmet.adapters._tracing import (
    build_stage_result,
    finish_trace,
    record_message,
    record_tool_call,
    record_usage,
    start_trace,
)
from desmet.observability import get_langchain_callback
```

- [ ] **Step 7: Update `tests/test_langgraph_adapter.py`**

Update tests to reflect the refactored interface:
- Remove tests for `_create_tools_from_stage_context` (now in `_tools.py`)
- Remove tests for `_create_tools` (deleted)
- Keep/update interface tests for stage methods
- Remove `execute_story` interface test (inherited from base)

- [ ] **Step 8: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All PASSED

- [ ] **Step 9: Commit**

```bash
git add src/desmet/adapters/langgraph.py tests/test_langgraph_adapter.py
git commit -m "refactor(langgraph): use shared _prompts, _tools, _tracing modules (880→~180 lines)"
```

---

### Task 6: Refactor CrewAI Adapter

**Files:**
- Modify: `src/desmet/adapters/crewai.py` (873 → ~180 lines)
- Test: `tests/test_crewai_adapter.py`

Same pattern as LangGraph, but:
- Keep `_create_trace_callbacks()` (CrewAI-specific callback wiring)
- Update it to use `record_message()` and `record_tool_call()` from `_tracing.py`
- Use `get_stage_persona()` from `_prompts.py` for agent role/goal/backstory
- Use `ToolFormat.CREWAI` for tool creation
- `_run_agent()` creates Agent + Task + Crew and calls `crew.kickoff()`

- [ ] **Step 1: Read the current crewai.py thoroughly**

Read: `src/desmet/adapters/crewai.py` (all 873 lines)
Note the exact structure of each stage method and the callback implementation.

- [ ] **Step 2: Refactor stage methods to use shared modules**

Each stage method shrinks to ~20 lines. Example for `generate_requirements`:

```python
async def generate_requirements(self, context: StageContext) -> RequirementsResult:
    trace = start_trace()
    try:
        prompt = build_requirements_prompt(context.story)
        system_msg = build_system_message(context.story)
        tools = create_tools(context.workspace, context.allowed_tools, fmt=ToolFormat.CREWAI)
        iterations, hit_limit = await self._run_agent(
            "requirements", prompt, system_msg, tools, trace, context,
        )
        return build_stage_result(
            RequirementsResult, self.platform_info.id, "requirements",
            trace, success=not hit_limit, iterations=iterations,
        )
    except Exception as e:
        finish_trace(trace, error=str(e))
        return build_stage_result(
            RequirementsResult, self.platform_info.id, "requirements",
            trace, success=False, iterations=0, error_message=str(e),
        )
```

- [ ] **Step 3: Extract `_run_agent()` method**

CrewAI-specific: creates Agent with persona, Task, Crew, and runs `kickoff()`:

```python
async def _run_agent(
    self,
    stage_name: str,
    prompt: str,
    system_msg: str | None,
    tools: list,
    trace: AgentTrace,
    context: StageContext,
) -> tuple[int, bool]:
    """Run a CrewAI agent and record trace data.

    Returns (iteration_count, hit_iteration_limit).
    """
    from crewai import Agent, Crew, Process, Task

    persona = get_stage_persona(stage_name)
    llm = self._create_llm(context)

    agent = Agent(
        role=persona.role,
        goal=persona.goal,
        backstory=persona.backstory,
        verbose=False,
        allow_delegation=False,
        llm=llm,
        tools=tools,
    )

    task = Task(
        description=prompt,
        expected_output=STAGE_EXPECTED_OUTPUTS.get(stage_name, "Complete the task as described."),
        agent=agent,
    )

    step_cb, task_cb, counter = self._create_trace_callbacks(trace)

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
        step_callback=step_cb,
        task_callback=task_cb,
        max_iter=context.max_iterations,
    )

    record_message(trace, "user", prompt)
    result = crew.kickoff()
    record_message(trace, "assistant", str(result))

    iterations = counter[0]
    hit_limit = iterations >= context.max_iterations
    trace.total_iterations = iterations
    finish_trace(trace)
    return iterations, hit_limit
```

- [ ] **Step 4: Update `_create_trace_callbacks` to use `_tracing` helpers**

Replace direct `AgentMessage`/`ToolCall` construction with `record_message()` and `record_tool_call()` calls:

```python
def _create_trace_callbacks(self, trace: AgentTrace):
    """Return (step_callback, task_callback, step_counter)."""
    counter = [0]

    def step_callback(step_output):
        counter[0] += 1
        # Extract tool info if present
        tool_name = getattr(step_output, "tool", None)
        if tool_name:
            tool_input = getattr(step_output, "tool_input", "")
            tool_result = getattr(step_output, "result", "")
            args = tool_input if isinstance(tool_input, dict) else {"input": str(tool_input)}
            record_tool_call(trace, str(tool_name), args, str(tool_result))

        content = getattr(step_output, "log", "") or getattr(step_output, "text", "") or str(step_output)
        record_message(trace, "assistant", content, metadata={"step": counter[0]})
        trace.total_iterations = counter[0]

    def task_callback(task_output):
        record_message(
            trace, "assistant", str(task_output),
            metadata={"event": "task_complete"},
        )

    return step_callback, task_callback, counter
```

- [ ] **Step 5: Delete inline tools, prompts, and execute_story**

Delete:
- `_create_tools_from_stage_context()` (lines 654-751)
- `_create_tools()` (lines 753-850)
- `execute_story()` (lines 526-581)
- All inline prompt construction in stage methods

- [ ] **Step 6: Add imports at top of crewai.py**

```python
from desmet.adapters._prompts import (
    STAGE_EXPECTED_OUTPUTS,
    build_codegen_prompt,
    build_deploy_prompt,
    build_requirements_prompt,
    build_system_message,
    build_testing_prompt,
    get_stage_persona,
)
from desmet.adapters._tools import ToolFormat, create_tools
from desmet.adapters._tracing import (
    build_stage_result,
    finish_trace,
    record_message,
    record_tool_call,
    start_trace,
)
from desmet.observability import enable_litellm_callbacks
```

- [ ] **Step 7: Update `tests/test_crewai_adapter.py`**

Update tests:
- Remove tests for `_create_tools_from_stage_context` (now in `_tools.py`)
- Keep `TestTraceCallbacks` — update to verify callbacks use `_tracing` helpers
- Remove `execute_story` interface test (inherited from base)

- [ ] **Step 8: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All PASSED

- [ ] **Step 9: Commit**

```bash
git add src/desmet/adapters/crewai.py tests/test_crewai_adapter.py
git commit -m "refactor(crewai): use shared _prompts, _tools, _tracing modules (873→~180 lines)"
```

---

### Task 7: Final Validation

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v --tb=short`
Expected: All PASSED

- [ ] **Step 2: Verify line counts**

Run: `wc -l src/desmet/adapters/*.py`
Expected:
- `_prompts.py` ~80 lines
- `_tools.py` ~150 lines
- `_tracing.py` ~80 lines
- `langgraph.py` ~180 lines
- `crewai.py` ~180 lines

- [ ] **Step 3: Verify adapter can still run a benchmark**

Run: `uv run desmet-eval run --platform langgraph --story US-001 --stage requirements --dry-run`
Expected: Dry run output showing the adapter is correctly wired

- [ ] **Step 4: Commit if any cleanup was needed**

```bash
git add -A
git commit -m "chore: final cleanup after adapter refactor"
```
