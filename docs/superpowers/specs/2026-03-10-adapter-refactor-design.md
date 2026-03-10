# Adapter Refactor Design

**Date**: 2026-03-10
**Status**: Approved (rev 3 — all review issues resolved)
**Goal**: Extract shared adapter boilerplate into reusable modules so each platform adapter only contains platform-specific wiring.

## Problem

LangGraph and CrewAI adapters are ~870 lines each. ~80% is duplicated:
- Identical prompt construction for all 4 stages
- Identical tool definitions (read_file, write_file, list_directory, execute_shell)
- Identical trace recording (AgentTrace setup, message/tool-call appending)
- Identical result construction (RequirementsResult, CodeResult, TestResult, DeployResult)
- Identical prior-stage context injection (appending requirements to codegen prompt)

8 more adapters need to be built. Without refactoring, that's ~7000 lines of copy-paste.

## Platform Categories

### Python SDK Platforms (6)
LangGraph, CrewAI, AutoGen, OpenAI Agents SDK, Google ADK, Semantic Kernel

All follow the same pattern:
1. Create an LLM client
2. Create tools (read_file, write_file, list_directory, execute_shell)
3. Build a stage prompt
4. Run an agent with those tools and prompt
5. Collect trace data
6. Build a result object

Differences are only in agent creation/execution:
- LangGraph: `create_react_agent` + `astream()`
- CrewAI: `Agent` + `Task` + `Crew.kickoff()`
- AutoGen: `AssistantAgent` + `UserProxyAgent` conversation
- OpenAI Agents: `Agent` + `Runner.run()`
- Google ADK: `Agent` + tools
- Semantic Kernel: `Kernel` + plugins + planner

### Visual/Workflow Platforms (4)
Flowise, LangFlow, Dify, n8n

Run as Docker services. Evaluated via HTTP APIs:
1. `initialize()` — upload a pre-built workflow template via the platform's API
2. Stage methods — send the prompt to the platform's chat/execution API
3. `shutdown()` — delete the workflow

Workflow templates stored in `config/workflows/{platform}/agent.json`.
Tool access via Docker volume mount (workspace mounted into the container).

## Architecture

### New Shared Modules

```
src/desmet/adapters/
  _prompts.py    — Stage prompt builders
  _tools.py      — Tool factory for Python SDK platforms
  _tracing.py    — Trace recording + result construction helpers
```

All prefixed with `_` to indicate internal/shared modules, not adapters.

### `_prompts.py` — Stage Prompt Builders

Shared by all 10 platforms. Pure functions, no framework dependencies.

```python
def build_requirements_prompt(story: UserStory) -> str:
    """Build the prompt for the requirements analysis stage.

    Includes story.title, story.description, and story.prompt (the full task
    prompt). NOTE: acceptance_criteria are intentionally NOT injected into the
    prompt — they are used for evaluation scoring, not as agent input. This
    matches the current adapter behaviour.
    """

def build_codegen_prompt(story: UserStory, prior_requirements: RequirementsResult | None) -> str:
    """Build the prompt for code generation, optionally appending prior requirements.

    Includes story.title, story.description, story.prompt, and when
    prior_requirements is provided, appends the generated requirements text
    as additional context.
    """

def build_testing_prompt(story: UserStory) -> str:
    """Build the prompt for test generation and execution.

    Includes story.title, story.description, and story.prompt.
    """

def build_deploy_prompt(story: UserStory) -> str:
    """Build the prompt for build and deployment verification.

    Includes story.title and story.description (NOT story.prompt — the deploy
    stage focuses on build/dependency verification, not the original task).
    Instructs the agent to install dependencies, run build, run tests,
    and verify deployment readiness.
    """

def build_system_message(story: UserStory) -> str | None:
    """Return the system message, or None.

    Prefers story.system_prompt if set; falls back to story.context if
    non-empty. Returns None when neither is provided. This resolves the
    ambiguity between the two fields — system_prompt is the explicit
    override, context is the legacy field used by current adapters.
    """
```

The prior-stage context injection (appending requirements to codegen prompt) lives here, not in each adapter.

#### Agent Personas (CrewAI-specific)

CrewAI requires a `role`, `goal`, and `backstory` per agent. These are stage-specific:

```python
@dataclass
class AgentPersona:
    role: str
    goal: str
    backstory: str

def get_stage_persona(stage_name: str) -> AgentPersona:
    """Return the agent persona for a given stage.

    Personas:
      requirements → Requirements Analyst
      codegen      → Software Developer
      testing      → QA Engineer
      deploy       → DevOps Engineer
    """
```

This lives in `_prompts.py` since it's prompt-adjacent content. Only used by CrewAI (and potentially AutoGen, which also supports role-based agents).

### `_tools.py` — Tool Factory

Shared by the 6 Python SDK platforms. Returns tools in the requested format.

```python
class ToolFormat(Enum):
    LANGCHAIN = "langchain"       # @tool decorated functions
    CREWAI = "crewai"             # BaseTool subclasses
    OPENAI_FUNCTION = "openai"    # dict-based function definitions
    CALLABLE = "callable"         # plain Python callables

# All available tool names
AVAILABLE_TOOLS = ("read_file", "write_file", "list_directory", "execute_shell", "search_code")

def create_tools(
    workspace: Path,
    allowed_tools: list[str],
    fmt: ToolFormat = ToolFormat.CALLABLE,
) -> list:
    """Create sandbox tools scoped to the given workspace.

    Returns tools in the format expected by the target framework.
    All tools operate relative to `workspace` and cannot escape it.

    Available tools:
      read_file      — Read a file's contents
      write_file     — Write content to a file
      list_directory — List files/dirs in a directory
      execute_shell  — Run a shell command in the workspace
      search_code    — Search file contents by pattern (grep-like)
    """
```

Internally, the core logic (read file, write file, etc.) is defined once. Format adapters wrap it for each framework's tool interface.

**Path traversal safety**: All file-based tools (`read_file`, `write_file`, `list_directory`, `search_code`) resolve the requested path relative to `workspace` and reject any path that escapes it via `..` traversal or symlinks. The `execute_shell` tool sets `cwd=workspace` and inherits the sandboxed environment.

Not used by visual platforms — they configure tool nodes in workflow JSON.

### `_tracing.py` — Trace + Result Helpers

Shared by all 10 platforms. Handles AgentTrace lifecycle and StageResult construction.

```python
def start_trace() -> AgentTrace:
    """Create a new AgentTrace with start_time set to datetime.now(UTC)."""

def record_message(trace: AgentTrace, role: str, content: str, **kwargs) -> None:
    """Append an AgentMessage to trace.messages."""

def record_usage(trace: AgentTrace, input_tokens: int = 0, output_tokens: int = 0) -> None:
    """Accumulate token usage into the trace.

    Called by adapters that can extract token counts from their framework's
    response metadata. LangGraph can read usage from LangChain message
    response_metadata; CrewAI token tracking comes via litellm callbacks
    to Langfuse (not captured back into the trace). When no adapter calls
    this, token fields remain 0 — a known limitation, not a bug.
    """

def record_tool_call(trace: AgentTrace, name: str, args: dict, result: Any,
                     duration_ms: float = 0.0, success: bool = True) -> None:
    """Append a ToolCall to trace.tool_calls."""

def finish_trace(trace: AgentTrace, final_state: dict | None = None,
                 error: str | None = None) -> None:
    """Set end_time, final_state, and optionally append error to trace.errors."""

def build_stage_result(
    result_cls: type[StageResult],   # RequirementsResult, CodeResult, etc.
    platform_id: str,
    stage_name: str,
    trace: AgentTrace,
    success: bool,
    iterations: int,
    error_message: str | None = None,
    **extra_fields,
) -> StageResult:
    """Construct a StageResult subclass from trace data.

    Automatically derives these fields from the trace:
      - wall_clock_seconds  ← trace.duration_seconds
      - tool_calls_count    ← len(trace.tool_calls)
      - start_time          ← trace.start_time
      - end_time            ← trace.end_time
      - tokens_input        ← trace.total_tokens_input
      - tokens_output       ← trace.total_tokens_output
      - completed           ← success (unless overridden in extra_fields)
      - trace               ← the trace object itself

    Calls finish_trace() if end_time is not yet set.

    **extra_fields are passed through to the result_cls constructor,
    allowing stage-specific fields (e.g. build_success for DeployResult).
    """
```

#### CrewAI Callback Tracing

CrewAI's `step_callback` and `task_callback` feed trace data through closures that capture the `AgentTrace`. This is **platform-specific** and stays in `crewai.py`:

```python
# In CrewAI adapter (not in _tracing.py)
def _create_trace_callbacks(self, trace: AgentTrace) -> tuple[Callable, Callable, list[int]]:
    """Return (step_callback, task_callback, step_counter).

    step_callback: called after each agent step — records tool calls
                   and messages to the trace via _tracing helpers
    task_callback: called on task completion — records final output
    step_counter:  single-element list used to track iteration count
    """
```

The callbacks use `record_message()` and `record_tool_call()` from `_tracing.py` but the callback wiring itself is CrewAI-specific. LangGraph parses trace data from `astream()` events instead.

### Refactored Adapter Structure

After refactoring, each Python SDK adapter implements:

```python
class SomeAdapter(BasePlatformAdapter):
    # platform_info property (~10 lines)
    # initialize() — create LLM client, enable callbacks (~15 lines)
    # shutdown() — cleanup (~5 lines)
    # health_check() — verify connectivity (~10 lines)

    # _create_agent(tools, llm) — platform-specific agent creation
    # _run_agent(agent, prompt, system_msg, trace) — platform-specific execution loop

    # generate_requirements() — uses shared prompt + tools + tracing (~20 lines)
    # generate_code() — same pattern (~20 lines)
    # generate_tests() — same pattern (~20 lines)
    # build_and_deploy() — same pattern (~20 lines)
```

Each stage method follows the same template:
```python
async def generate_requirements(self, context: StageContext) -> RequirementsResult:
    trace = start_trace()
    try:
        prompt = build_requirements_prompt(context.story)
        system_msg = build_system_message(context.story)
        tools = create_tools(context.workspace, context.allowed_tools, fmt=self.TOOL_FORMAT)
        iterations, hit_limit = await self._run_agent(prompt, system_msg, tools, trace, context)
        return build_stage_result(
            RequirementsResult, self.platform_info.id, "requirements",
            trace, success=not hit_limit, iterations=iterations,
        )
    except Exception as e:
        finish_trace(trace)
        return build_stage_result(
            RequirementsResult, self.platform_info.id, "requirements",
            trace, success=False, iterations=0, error_message=str(e),
        )
```

This is similar enough across stages that a further helper could reduce it, but keeping it explicit per-stage avoids over-abstraction and allows stage-specific customization when needed.

### Visual Platform Adapter Structure

```python
class FlowiseAdapter(VisualPlatformAdapter):
    # platform_info property
    # initialize() — upload workflow template via HTTP API
    # shutdown() — delete workflow

    # _execute_prompt(prompt) — send prompt to chat API, return response

    # generate_requirements() — build_requirements_prompt() → _execute_prompt()
    # generate_code() — build_codegen_prompt() → _execute_prompt()
    # ... etc
```

Workflow templates stored in `config/workflows/{platform}/agent.json`.
Workspace mounted as Docker volume so the platform's tool nodes can access files.

### What Gets Deleted

From `langgraph.py`:
- `_create_tools()` and `_create_tools_from_stage_context()` — replaced by `_tools.py`
- All 4 prompt-building blocks — replaced by `_prompts.py`
- All trace setup/recording code — replaced by `_tracing.py`
- All result construction code — replaced by `_tracing.py`

From `crewai.py`:
- Same deletions as LangGraph
- `_create_trace_callbacks()` stays (CrewAI-specific, uses `_tracing.py` helpers internally)

### `execute_story()` Backwards-Compat Wrapper

Both LangGraph and CrewAI currently have identical `execute_story()` methods (~50 lines each) that convert legacy `EvaluationContext` to `StageContext` and delegate to `generate_code()`. This moves to `BasePlatformAdapter` as a default implementation so all adapters inherit it.

### Langfuse Integration

Already wired in, no changes needed:
- `_tracing.py` uses the existing `observability.py` helpers
- LangGraph: `get_langchain_callback()` passed via config (per-stage)
- CrewAI: `enable_litellm_callbacks()` called once at init
- Session ID propagated via `start_session()` in CLI

### File Impact Summary

| File | Action |
|------|--------|
| `adapters/_prompts.py` | New — ~80 lines |
| `adapters/_tools.py` | New — ~150 lines |
| `adapters/_tracing.py` | New — ~80 lines |
| `adapters/langgraph.py` | Refactor 880 → ~180 lines |
| `adapters/crewai.py` | Refactor 873 → ~180 lines |
| `adapters/autogen.py` | Rewrite stub → ~150 lines |
| `adapters/openai_agents.py` | Rewrite stub → ~150 lines |
| `adapters/google_adk.py` | Rewrite stub → ~150 lines |
| `adapters/semantic_kernel.py` | Rewrite stub → ~150 lines |
| `adapters/flowise.py` | Rewrite stub → ~120 lines |
| `adapters/langflow.py` | Rewrite stub → ~120 lines |
| `adapters/dify.py` | Rewrite stub → ~120 lines |
| `adapters/n8n.py` | Rewrite stub → ~120 lines |
| `harness/base.py` | Add default `execute_story()` wrapper |
| `config/workflows/` | New — 4 workflow template JSONs |

**Before**: 1,753 lines for 2 adapters + 496 lines of stubs = 2,249 lines
**After**: ~310 shared + ~1,560 adapters = ~1,870 lines for all 10 adapters
