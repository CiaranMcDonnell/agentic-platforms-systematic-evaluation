# n8n Platform Adapter — Design Spec

**Date:** 2026-04-06
**Status:** Approved

## Summary

Implement the n8n adapter as the first real visual/workflow platform adapter in DESMET. The adapter extends `VisualPlatformAdapter`, communicates with n8n via its REST API v1, and uses n8n's native AI Agent node to execute SDLC stages. This evaluates n8n's actual agentic capabilities rather than bypassing them.

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Agent approach | n8n AI Agent node | Evaluates native agentic capabilities, which is DESMET's purpose |
| LLM credentials | Auto-provisioned via REST API | Keeps evaluation fully automated |
| Stage mapping | 4 separate workflows | Matches `_execute_stage` pattern, simpler templates, isolated failures |
| Agent pattern | Single AI Agent node per stage | Tests n8n as n8n, not a forced multi-agent pattern |
| Retry handling | Adapter-side retry loop | Comparable metrics with coded adapters |
| Implementation scope | Full adapter (no premature abstraction) | YAGNI — extract shared visual base after second adapter |

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  Harness Runner                                      │
│  calls generate_requirements / generate_code / etc.  │
└──────────────┬───────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────┐
│  N8nAdapter (extends VisualPlatformAdapter)           │
│                                                      │
│  ┌─────────────────┐  ┌──────────────────────────┐   │
│  │ N8nClient        │  │ Credential Provisioner   │   │
│  │ (httpx async)    │  │ (auto-creates LLM creds) │   │
│  └────────┬────────┘  └──────────┬───────────────┘   │
│           │                      │                   │
│  ┌────────▼──────────────────────▼───────────────┐   │
│  │ Stage Executor                                │   │
│  │ - loads workflow template                     │   │
│  │ - injects prompt + workspace path             │   │
│  │ - creates → executes → polls → collects       │   │
│  │ - retry loop with audit_workspace             │   │
│  └───────────────────────────────────────────────┘   │
└──────────────┬───────────────────────────────────────┘
               │ HTTP (REST API v1)
┌──────────────▼───────────────────────────────────────┐
│  n8n container (desmet-n8n, port 5678)               │
│                                                      │
│  Workflow: [Trigger] → [AI Agent] → [Tool Nodes]     │
│                                                      │
│  Volume mount: /workspaces ↔ host workspaces dir     │
└──────────────────────────────────────────────────────┘
```

## Component Details

### 1. N8nClient

Thin async HTTP wrapper using `httpx.AsyncClient` targeting n8n REST API v1 (`/api/v1/`).

**Auth:** API key via `X-N8N-API-KEY` header. Read from `N8N_API_KEY` env var or `config["api_key"]`.

**Methods:**

```python
class N8nClient:
    def __init__(self, base_url: str, api_key: str | None = None): ...

    # Credentials
    async def create_credential(self, cred_type: str, name: str, data: dict) -> str
    async def delete_credential(self, credential_id: str) -> None

    # Workflows
    async def create_workflow(self, definition: dict) -> str
    async def activate_workflow(self, workflow_id: str) -> None
    async def execute_workflow(self, workflow_id: str, data: dict) -> str
    async def delete_workflow(self, workflow_id: str) -> None

    # Executions
    async def get_execution(self, execution_id: str) -> dict
    async def wait_for_execution(self, execution_id: str, timeout: int) -> dict

    # Health
    async def health_check(self) -> bool

    async def close(self) -> None
```

**Polling:** `wait_for_execution` polls `GET /executions/{id}` with exponential backoff until status is `success`, `error`, or timeout.

### 2. Credential Provisioner

Auto-creates LLM credentials in n8n's credential store during `initialize()`.

**Flow:**
1. Read provider/model from `llm_config.get_config()`
2. Map provider to n8n credential type:
   - `openai` → `openAiApi` (`apiKey` field)
   - `anthropic` → `anthropicApi` (`apiKey` field)
   - OpenAI-compatible with custom base_url → `openAiApi` with `baseUrl` override
3. `POST /credentials` with type + data → cache credential ID
4. `shutdown()` deletes the credential

Workflow templates reference credentials by placeholder name `desmet-llm`; the adapter injects the real credential ID at workflow creation time.

### 3. Workflow Templates

Python dicts in `src/desmet/adapters/n8n_templates.py` (one per SDLC stage). Not separate JSON files — keeps them co-located and allows programmatic parameterization.

**Workflow structure (all 4 stages):**

```
[Manual Trigger] → [AI Agent] → [Output]
                       │
              ┌────────┼────────┐
              ▼        ▼        ▼
         [Execute  [Read    [Write
          Command]  File]    File]
```

**Nodes:**
- **Manual Trigger** — entry point, receives `prompt` and `workspace` as input
- **AI Agent** — `@n8n/n8n-nodes-langchain.agent` node with:
  - System message from `_prompts.py` (`build_*_prompt` + `build_system_message`)
  - Model credential: reference to provisioned `desmet-llm`
  - Model name from `DESMET_MODEL`
- **Tool nodes** connected to AI Agent:
  - Execute Command — shell access, working directory set to workspace
  - Read File — reads from workspace
  - Write File — writes to workspace

**Parameterization:**
```python
def _build_workflow(self, stage_name: str, prompt: str, system_msg: str, workspace: str) -> dict:
    # Deep-copy template, inject prompt, system_msg, workspace path,
    # credential_id, and model name into appropriate node fields
```

### 4. Stage Executor & Retry Loop

Shared `_execute_n8n_stage` method (analogous to `ToolAgentAdapter._execute_stage`):

```
1. Build prompt via prompt_fn(context.story)
2. Build system message via build_system_message(context.story)
3. For attempt in range(max_retries + 1):
   a. Build workflow JSON from template + prompt + workspace
   b. POST workflow to n8n → workflow_id
   c. Activate workflow
   d. Execute workflow → execution_id
   e. Poll wait_for_execution(execution_id, timeout)
   f. Extract execution metrics (duration, node runs, errors)
   g. Validate workspace: audit_workspace(stage, workspace)
   h. If passed → break
   i. If retries remain → amend prompt with validation feedback
   j. Delete workflow (cleanup before retry)
4. Delete final workflow (cleanup)
5. Build and return StageResult with metrics
```

### 5. Metrics Collection

Extracted from n8n execution response data:
- **Timing:** `startedAt` / `stoppedAt` from execution response
- **Iterations:** count of AI Agent node executions within the workflow
- **Token usage:** from AI Agent node output metadata (when available; `None` if not exposed)
- **Success/failure:** execution status + `audit_workspace` result

Result building uses `build_stage_result` from `_tracing.py`. The adapter constructs a minimal `TraceData` from n8n execution metrics so the same result-building path works.

### 6. N8nAdapter Class

```python
class N8nAdapter(VisualPlatformAdapter):
    def __init__(self, config: dict | None = None): ...

    # Lifecycle
    async def initialize(self) -> None      # create client, health check, provision credentials
    async def shutdown(self) -> None         # delete credentials, close client
    async def health_check(self) -> bool     # GET /api/v1/workflows → 200

    # SDLC stages (all delegate to _execute_n8n_stage)
    async def generate_requirements(self, context) -> RequirementsResult
    async def generate_code(self, context) -> CodeResult
    async def generate_tests(self, context) -> TestResult
    async def build_and_deploy(self, context) -> DeployResult

    # VisualPlatformAdapter contract (delegate to N8nClient)
    async def create_workflow(self, definition) -> str
    async def execute_workflow(self, workflow_id, inputs) -> dict
    async def delete_workflow(self, workflow_id) -> None

    # Internal
    async def _execute_n8n_stage(self, stage_name, prompt_fn, result_cls, context) -> StageResult
    def _build_workflow(self, stage_name, prompt, system_msg, workspace) -> dict
```

## Infrastructure Changes

**`docker-compose.yaml`** — additions to n8n service:

```yaml
environment:
  - N8N_API_KEY=${N8N_API_KEY:-desmet-n8n-api-key}
  - EXECUTIONS_DATA_SAVE_ON_SUCCESS=all
  - EXECUTIONS_DATA_SAVE_ON_ERROR=all
volumes:
  - n8n_data:/home/node/.n8n
  - ${DESMET_RESULTS_DIR:-../results}:/desmet-results
```

**Workspace path translation:** The harness creates workspaces at `results/<platform_id>/<story_id>/workspace` on the host. The adapter translates this to `/desmet-results/<platform_id>/<story_id>/workspace` inside the container when injecting into workflow templates. The `N8nAdapter` stores the container-side results root (`/desmet-results`) and performs the path mapping in `_build_workflow`.

**`registry.py`** — add `"n8n"` to `_IMPLEMENTED_PLATFORMS`.

## File Inventory

| File | Action |
|---|---|
| `src/desmet/adapters/n8n.py` | Replace stub with full implementation |
| `src/desmet/adapters/n8n_templates.py` | New — workflow template dicts for 4 stages |
| `infrastructure/docker-compose.yaml` | Add env vars + workspace volume to n8n service |
| `src/desmet/adapters/registry.py` | Add `"n8n"` to `_IMPLEMENTED_PLATFORMS` |

## Testing

- **Unit tests:** Mock `N8nClient` HTTP calls, verify workflow template parameterization, credential provisioning logic, retry loop behavior
- **Integration tests:** Require running n8n container (`--profile n8n`), verify end-to-end workflow creation → execution → result collection on a basic story
