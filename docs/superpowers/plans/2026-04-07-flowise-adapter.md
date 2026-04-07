# Flowise Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Flowise platform adapter and extract a shared `VisualAgentAdapter` base class from the n8n adapter, establishing the pattern for all visual/workflow platform adapters.

**Architecture:** Extract the retry loop, trace management, prompt building, and SDLC stage methods from `N8nAdapter` into a new `VisualAgentAdapter` base class. Both `N8nAdapter` and the new `FlowiseAdapter` inherit from it. Flowise uses synchronous execution (no polling) and env-var credentials (no provisioning API).

**Tech Stack:** httpx (async HTTP), Flowise REST API, existing `_tracing`/`_validation`/`_prompts` shared modules

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/desmet/adapters/_visual_base.py` | Create | `VisualAgentAdapter` — shared retry loop, trace, SDLC methods |
| `src/desmet/adapters/n8n.py` | Modify | Refactor to inherit `VisualAgentAdapter`, remove duplicated code |
| `src/desmet/adapters/flowise.py` | Replace stub | `FlowiseClient` + `FlowiseAdapter` |
| `src/desmet/adapters/flowise_templates.py` | Create | Chatflow template dicts for 4 SDLC stages |
| `infrastructure/docker-compose.yaml` | Modify | Add env vars + workspace volume to flowise service |
| `src/desmet/adapters/registry.py` | Modify | Add `"flowise"` to `_IMPLEMENTED_PLATFORMS` |
| `tests/test_visual_base.py` | Create | Tests for shared base class |
| `tests/test_flowise_adapter.py` | Create | Tests for Flowise client, templates, adapter |

---

### Task 1: Docker Compose — enable Flowise workspace and credentials

**Files:**
- Modify: `infrastructure/docker-compose.yaml:76-94` (flowise service block)

- [ ] **Step 1: Add environment variables and workspace volume to flowise service**

In `infrastructure/docker-compose.yaml`, update the flowise service block. Add these environment variables after the existing ones:

```yaml
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      - FLOWISE_SECRETKEY_OVERWRITE=${FLOWISE_API_KEY:-}
```

And add the workspace volume mount after the existing `flowise_data` volume:

```yaml
      - ${DESMET_RESULTS_DIR:-../results}:/desmet-results
```

The full flowise service block should look like:

```yaml
  flowise:
    image: flowiseai/flowise:latest
    container_name: desmet-flowise
    environment:
      - FLOWISE_USERNAME=${FLOWISE_USERNAME:-admin}
      - FLOWISE_PASSWORD=${FLOWISE_PASSWORD:-admin}
      - DATABASE_PATH=/root/.flowise
      - APIKEY_PATH=/root/.flowise
      - LOG_PATH=/root/.flowise/logs
      - SECRETKEY_PATH=/root/.flowise
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      - FLOWISE_SECRETKEY_OVERWRITE=${FLOWISE_API_KEY:-}
    volumes:
      - flowise_data:/root/.flowise
      - ${DESMET_RESULTS_DIR:-../results}:/desmet-results
    ports:
      - "3000:3000"
    restart: unless-stopped
    profiles:
      - flowise
      - visual-platforms
```

- [ ] **Step 2: Commit**

```bash
git add infrastructure/docker-compose.yaml
git commit -m "infra: enable Flowise workspace volume and LLM credentials"
```

---

### Task 2: VisualAgentAdapter shared base class

**Files:**
- Create: `src/desmet/adapters/_visual_base.py`
- Create: `tests/test_visual_base.py`

- [ ] **Step 1: Write failing tests for VisualAgentAdapter**

Create `tests/test_visual_base.py`:

```python
"""Tests for the shared VisualAgentAdapter base class."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _MockVisualAdapter:
    """Create a concrete subclass of VisualAgentAdapter for testing."""

    @staticmethod
    def create(run_workflow_return=None):
        from desmet.adapters._visual_base import VisualAgentAdapter
        from desmet.harness.models import PlatformInfo, PlatformCategory, PlatformRuntime

        class ConcreteAdapter(VisualAgentAdapter):
            def __init__(self):
                super().__init__(
                    base_url="http://localhost:9999",
                    api_key="test",
                    config={},
                )
                self._run_workflow_return = run_workflow_return or {
                    "status": "success",
                }

            @property
            def platform_info(self) -> PlatformInfo:
                return PlatformInfo(
                    name="MockVisual", id="mock_visual",
                    category=PlatformCategory.VISUAL_WORKFLOW_PLATFORM,
                    runtime=PlatformRuntime.DOCKER, version="test",
                )

            async def initialize(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

            async def health_check(self) -> bool:
                return True

            async def create_workflow(self, definition: dict) -> str:
                return "wf-1"

            async def execute_workflow(self, workflow_id: str, inputs: dict) -> dict:
                return {}

            async def delete_workflow(self, workflow_id: str) -> None:
                pass

            async def _run_workflow(self, stage_name, prompt, system_msg, workspace):
                return self._run_workflow_return

            def _collect_execution_metrics(self, trace, exec_data):
                pass

        return ConcreteAdapter()


class TestTranslateWorkspace:
    def test_linux_path(self):
        adapter = _MockVisualAdapter.create()
        result = adapter._translate_workspace("/home/user/project/results/n8n/story/workspace")
        assert result == "/desmet-results/n8n/story/workspace"

    def test_windows_path(self):
        adapter = _MockVisualAdapter.create()
        result = adapter._translate_workspace("C:\\Users\\user\\results\\n8n\\story\\workspace")
        assert result == "/desmet-results/n8n/story/workspace"

    def test_no_results_segment_returns_normalised(self):
        adapter = _MockVisualAdapter.create()
        result = adapter._translate_workspace("/tmp/workspace")
        assert result == "/tmp/workspace"


class TestExecuteVisualStage:
    @pytest.mark.asyncio
    async def test_successful_stage_returns_success(self):
        from desmet.harness.story import UserStory, DifficultyLevel
        from desmet.harness.results import RequirementsResult

        adapter = _MockVisualAdapter.create()
        story = UserStory(
            id="test_01", title="Test", description="Test",
            difficulty=DifficultyLevel.BASIC, category="test",
            prompt="Do the thing",
        )
        context = MagicMock()
        context.story = story
        context.workspace = "/tmp/results/mock_visual/test_01/workspace"
        context.platform_id = "mock_visual"
        context.max_iterations = 25
        context.metadata = {}

        with patch("desmet.adapters._visual_base.audit_workspace", return_value=[]):
            result = await adapter._execute_visual_stage(
                "requirements",
                lambda s, **kw: "Analyse: " + s.prompt,
                RequirementsResult,
                context,
            )

        assert result.success is True
        assert result.platform_id == "mock_visual"
        assert result.stage_name == "requirements"

    @pytest.mark.asyncio
    async def test_failed_validation_retries(self):
        from desmet.harness.story import UserStory, DifficultyLevel
        from desmet.harness.results import CodeResult

        adapter = _MockVisualAdapter.create()
        adapter._run_workflow = AsyncMock(return_value={"status": "success"})

        story = UserStory(
            id="test_02", title="Test", description="Test",
            difficulty=DifficultyLevel.BASIC, category="test",
            prompt="Build it",
        )
        context = MagicMock()
        context.story = story
        context.workspace = "/tmp/results/mock_visual/test_02/workspace"
        context.platform_id = "mock_visual"
        context.max_iterations = 25
        context.metadata = {}

        call_count = 0
        def mock_audit(stage, ws, baseline):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return ["missing file: main.py"]
            return []

        with patch("desmet.adapters._visual_base.audit_workspace", side_effect=mock_audit):
            result = await adapter._execute_visual_stage(
                "codegen",
                lambda s, **kw: "Build: " + s.prompt,
                CodeResult,
                context,
            )

        assert result.success is True
        assert adapter._run_workflow.await_count == 2

    @pytest.mark.asyncio
    async def test_exception_returns_failure(self):
        from desmet.harness.story import UserStory, DifficultyLevel
        from desmet.harness.results import TestResult

        adapter = _MockVisualAdapter.create()
        adapter._run_workflow = AsyncMock(side_effect=RuntimeError("connection failed"))

        story = UserStory(
            id="test_03", title="Test", description="Test",
            difficulty=DifficultyLevel.BASIC, category="test",
            prompt="Test it",
        )
        context = MagicMock()
        context.story = story
        context.workspace = "/tmp/workspace"
        context.platform_id = "mock_visual"
        context.max_iterations = 25
        context.metadata = {}

        result = await adapter._execute_visual_stage(
            "testing",
            lambda s, **kw: "Test: " + s.prompt,
            TestResult,
            context,
        )

        assert result.success is False
        assert "connection failed" in result.error_message
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_visual_base.py -v`
Expected: FAIL — `_visual_base` module not found

- [ ] **Step 3: Implement VisualAgentAdapter**

Create `src/desmet/adapters/_visual_base.py`:

```python
"""Shared base class for visual/workflow platform adapters.

Provides the ``_execute_visual_stage`` retry loop and concrete SDLC
stage methods.  Subclasses implement ``_run_workflow`` with their
platform-specific execution logic and ``_collect_execution_metrics``
for metric extraction.

Hierarchy:
    VisualPlatformAdapter (harness/adapter.py)
        └── VisualAgentAdapter (this file)
                ├── N8nAdapter
                └── FlowiseAdapter
"""
from __future__ import annotations

import logging
import re
from abc import abstractmethod
from typing import Any

from desmet.adapters._prompts import (
    build_codegen_prompt,
    build_deploy_prompt,
    build_requirements_prompt,
    build_system_message,
    build_testing_prompt,
)
from desmet.adapters._tracing import (
    build_stage_result,
    finish_trace,
    record_message,
    start_trace,
)
from desmet.adapters._validation import audit_workspace
from desmet.harness.adapter import VisualPlatformAdapter
from desmet.harness.context import StageContext
from desmet.harness.results import (
    CodeResult,
    DeployResult,
    RequirementsResult,
    StageResult,
    TestResult,
)

_CONTAINER_RESULTS_ROOT = "/desmet-results"

logger = logging.getLogger(__name__)


class VisualAgentAdapter(VisualPlatformAdapter):
    """Intermediate base for visual adapters that use the shared retry/trace pipeline.

    Subclasses must implement ``_run_workflow`` and ``_collect_execution_metrics``.
    The four SDLC stage methods and the ``_execute_visual_stage`` template are
    provided here so that concrete adapters don't need to duplicate them.
    """

    max_retries: int = 3

    @abstractmethod
    async def _run_workflow(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str,
        workspace: str,
    ) -> dict:
        """Execute one workflow attempt on the platform.

        Creates the workflow, executes it, cleans it up, and returns the
        raw execution data dict.  Called once per retry attempt.
        """
        ...

    @abstractmethod
    def _collect_execution_metrics(self, trace: Any, exec_data: dict) -> None:
        """Extract timing and token usage from platform execution response."""
        ...

    # ── Workspace path translation ─────────────────────────────────────

    def _translate_workspace(self, host_path: str) -> str:
        """Translate a host workspace path to the container-side path.

        The docker-compose volume mounts the host results dir at
        ``/desmet-results``.  This method finds the ``results/`` segment
        in the host path and maps everything after it.
        """
        normalised = host_path.replace("\\", "/")
        match = re.search(r"results/(.+)$", normalised)
        if match:
            return f"{_CONTAINER_RESULTS_ROOT}/{match.group(1)}"
        return normalised

    # ── Stage executor ─────────────────────────────────────────────────

    async def _execute_visual_stage(
        self,
        stage_name: str,
        prompt_fn,
        result_cls: type[StageResult],
        context: StageContext,
    ) -> StageResult:
        """Shared template: build prompt → run workflow → validate → retry → build result."""
        platform_id = self.platform_info.id
        trace = start_trace()
        try:
            if stage_name == "codegen":
                prior = context.get_prior_result("requirements")
                prompt = prompt_fn(context.story, prior_requirements=prior)
            else:
                prompt = prompt_fn(context.story)
            system_msg = build_system_message(context.story)
            workspace = self._translate_workspace(str(context.workspace))

            record_message(trace, "user", prompt)

            iterations = 0
            success = False

            for attempt in range(self.max_retries + 1):
                exec_data = await self._run_workflow(
                    stage_name, prompt, system_msg or "", workspace,
                )

                iterations += 1
                self._collect_execution_metrics(trace, exec_data)

                scope_warnings = audit_workspace(
                    stage_name, str(context.workspace),
                    set(context.metadata.get("baseline_files", [])),
                )

                if not scope_warnings:
                    success = True
                    break

                feedback = "; ".join(scope_warnings)
                logger.info(
                    "%s stage %s attempt %d/%d failed validation: %s",
                    platform_id, stage_name,
                    attempt + 1, self.max_retries + 1, feedback,
                )
                record_message(
                    trace, "system",
                    f"Validation failed (attempt {attempt + 1}): {feedback}",
                )

                prompt = (
                    f"{prompt}\n\n"
                    f"PREVIOUS ATTEMPT FAILED VALIDATION:\n{feedback}\n"
                    f"Please fix these issues."
                )

            return build_stage_result(
                result_cls, platform_id, stage_name, trace,
                success=success, iterations=iterations,
            )

        except Exception as e:
            finish_trace(trace, error=str(e))
            return build_stage_result(
                result_cls, platform_id, stage_name, trace,
                success=False, iterations=0, error_message=str(e),
            )

    # ── Concrete SDLC stage methods ────────────────────────────────────

    async def generate_requirements(self, context: StageContext) -> RequirementsResult:
        return await self._execute_visual_stage(
            "requirements", build_requirements_prompt, RequirementsResult, context,
        )

    async def generate_code(self, context: StageContext) -> CodeResult:
        return await self._execute_visual_stage(
            "codegen", build_codegen_prompt, CodeResult, context,
        )

    async def generate_tests(self, context: StageContext) -> TestResult:
        return await self._execute_visual_stage(
            "testing", build_testing_prompt, TestResult, context,
        )

    async def build_and_deploy(self, context: StageContext) -> DeployResult:
        return await self._execute_visual_stage(
            "deploy", build_deploy_prompt, DeployResult, context,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_visual_base.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/desmet/adapters/_visual_base.py tests/test_visual_base.py
git commit -m "feat: add VisualAgentAdapter shared base for visual platform adapters"
```

---

### Task 3: Refactor N8nAdapter to use VisualAgentAdapter

**Files:**
- Modify: `src/desmet/adapters/n8n.py`
- Test: `tests/test_n8n_adapter.py` (verify no regressions)

- [ ] **Step 1: Run existing n8n tests to establish baseline**

Run: `uv run pytest tests/test_n8n_adapter.py -v`
Expected: 19 passed

- [ ] **Step 2: Refactor N8nAdapter**

In `src/desmet/adapters/n8n.py`, make these changes:

**a) Replace imports** — remove the imports that are now in `_visual_base.py` and add the new base import. The top-of-file imports should become:

```python
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

from desmet.adapters._tracing import (
    record_llm_duration,
    record_usage,
)
from desmet.adapters._visual_base import VisualAgentAdapter
from desmet.adapters.registry import load_platform_info
from desmet.harness.models import PlatformInfo
from desmet.llm_config import get_config as get_llm_config
```

(The `_prompts`, `_validation`, `build_stage_result`, `finish_trace`, `record_message`, `start_trace`, `StageContext`, and result imports are no longer needed — they're used by the base class.)

**b) Change the class declaration** from `VisualPlatformAdapter` to `VisualAgentAdapter`:

```python
class N8nAdapter(VisualAgentAdapter):
```

**c) Remove `_CONTAINER_RESULTS_ROOT`** — it's now in `_visual_base.py`.

**d) Remove `_translate_workspace`** — inherited from base.

**e) Replace `_execute_n8n_stage` with `_run_workflow`** — the retry loop is now in the base class. The new method handles one workflow attempt:

```python
    async def _run_workflow(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str,
        workspace: str,
    ) -> dict:
        """Create, execute, poll, and clean up one n8n workflow."""
        from desmet.adapters.n8n_templates import build_workflow

        wf_def = build_workflow(
            stage_name=stage_name,
            prompt=prompt,
            system_msg=system_msg,
            workspace=workspace,
            model_name=self._model_name or "",
            credential_id=self._credential_id or "",
        )
        workflow_id = await self._client.create_workflow(wf_def)
        try:
            try:
                await self._client.activate_workflow(workflow_id)
            except Exception:
                pass

            exec_id = await self._client.execute_workflow(workflow_id, {
                "prompt": prompt,
                "workspace": workspace,
            })
            exec_data = await self._client.wait_for_execution(exec_id)
            return exec_data
        finally:
            try:
                await self._client.delete_workflow(workflow_id)
            except Exception:
                pass
```

**f) Remove the 4 SDLC stage methods** (`generate_requirements`, `generate_code`, `generate_tests`, `build_and_deploy`) — inherited from base.

**g) `_collect_execution_metrics` stays as-is** — it's n8n-specific.

- [ ] **Step 3: Update test to use new method name**

In `tests/test_n8n_adapter.py`, the `TestN8nStageExecution` class calls `adapter._execute_n8n_stage(...)`. Change it to call `adapter._execute_visual_stage(...)` instead (the base class method):

Find:
```python
            result = await adapter._execute_n8n_stage(
```

Replace with:
```python
            result = await adapter._execute_visual_stage(
```

- [ ] **Step 4: Run tests to verify no regressions**

Run: `uv run pytest tests/test_n8n_adapter.py tests/test_visual_base.py -v`
Expected: All tests PASS (19 n8n + 6 visual base)

- [ ] **Step 5: Commit**

```bash
git add src/desmet/adapters/n8n.py tests/test_n8n_adapter.py
git commit -m "refactor(n8n): inherit from VisualAgentAdapter, remove duplicated code"
```

---

### Task 4: FlowiseClient and credential handling

**Files:**
- Create: `src/desmet/adapters/flowise.py` (replace stub)
- Create: `tests/test_flowise_adapter.py`

- [ ] **Step 1: Write failing tests for FlowiseClient**

Create `tests/test_flowise_adapter.py`:

```python
"""Tests for the Flowise adapter."""
from __future__ import annotations

import pytest


class TestFlowiseClientInit:
    def test_client_sets_base_url(self):
        from desmet.adapters.flowise import FlowiseClient

        client = FlowiseClient("http://localhost:3000")
        assert client.base_url == "http://localhost:3000"

    def test_client_strips_trailing_slash(self):
        from desmet.adapters.flowise import FlowiseClient

        client = FlowiseClient("http://localhost:3000/")
        assert client.base_url == "http://localhost:3000"

    def test_auth_header_set_when_api_key_provided(self):
        from desmet.adapters.flowise import FlowiseClient

        client = FlowiseClient("http://localhost:3000", api_key="my-key")
        assert client._headers["Authorization"] == "Bearer my-key"

    def test_no_auth_header_when_no_api_key(self):
        from desmet.adapters.flowise import FlowiseClient

        client = FlowiseClient("http://localhost:3000")
        assert "Authorization" not in client._headers
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_flowise_adapter.py -v`
Expected: FAIL — `FlowiseClient` not found

- [ ] **Step 3: Implement FlowiseClient**

Replace `src/desmet/adapters/flowise.py` with:

```python
"""
Flowise Platform Adapter

Communicates with Flowise via its REST API to create and execute
AI Agent chatflows for each SDLC pipeline stage.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from desmet.adapters._tracing import (
    record_llm_duration,
    record_usage,
)
from desmet.adapters._visual_base import VisualAgentAdapter
from desmet.adapters.registry import load_platform_info
from desmet.harness.models import PlatformInfo

logger = logging.getLogger(__name__)


# ── FlowiseClient ─────────────────────────────────────────────────────


class FlowiseClient:
    """Async wrapper around the Flowise REST API."""

    def __init__(self, base_url: str, api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self._headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._headers,
                timeout=300.0,  # longer timeout — predict is synchronous
            )
        return self._client

    # ── Chatflows ──────────────────────────────────────────────────────

    async def create_chatflow(self, definition: dict) -> str:
        """Create a chatflow. Returns the chatflow ID."""
        client = await self._ensure_client()
        resp = await client.post("/api/v1/chatflows", json=definition)
        resp.raise_for_status()
        return resp.json()["id"]

    async def delete_chatflow(self, chatflow_id: str) -> None:
        client = await self._ensure_client()
        resp = await client.delete(f"/api/v1/chatflows/{chatflow_id}")
        if resp.status_code != 404:
            resp.raise_for_status()

    # ── Execution ──────────────────────────────────────────────────────

    async def predict(self, chatflow_id: str, question: str) -> dict:
        """Send a prediction request. Returns result synchronously."""
        client = await self._ensure_client()
        resp = await client.post(
            f"/api/v1/prediction/{chatflow_id}",
            json={"question": question},
        )
        resp.raise_for_status()
        return resp.json()

    # ── Health ─────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        try:
            client = await self._ensure_client()
            resp = await client.get("/api/v1/chatflows", params={"limit": 1})
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_flowise_adapter.py::TestFlowiseClientInit -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/desmet/adapters/flowise.py tests/test_flowise_adapter.py
git commit -m "feat(flowise): add FlowiseClient async HTTP wrapper"
```

---

### Task 5: Flowise chatflow templates

**Files:**
- Create: `src/desmet/adapters/flowise_templates.py`
- Test: `tests/test_flowise_adapter.py` (append)

- [ ] **Step 1: Write failing tests for templates**

Append to `tests/test_flowise_adapter.py`:

```python
class TestChatflowTemplates:
    def test_all_four_stages_have_templates(self):
        from desmet.adapters.flowise_templates import STAGE_TEMPLATES

        assert set(STAGE_TEMPLATES.keys()) == {
            "requirements", "codegen", "testing", "deploy",
        }

    def test_template_has_agent_node(self):
        from desmet.adapters.flowise_templates import STAGE_TEMPLATES

        for stage, template in STAGE_TEMPLATES.items():
            nodes = template["nodes"]
            agent_nodes = [n for n in nodes if "agent" in n.get("data", {}).get("category", "").lower()
                          or "agent" in n.get("data", {}).get("name", "").lower()]
            assert len(agent_nodes) >= 1, f"Stage {stage} missing agent node"

    def test_template_has_tool_nodes(self):
        from desmet.adapters.flowise_templates import STAGE_TEMPLATES

        for stage, template in STAGE_TEMPLATES.items():
            nodes = template["nodes"]
            assert len(nodes) >= 3, f"Stage {stage} has too few nodes"

    def test_build_chatflow_injects_parameters(self):
        from desmet.adapters.flowise_templates import build_chatflow

        cf = build_chatflow(
            stage_name="requirements",
            prompt="Analyse this story",
            system_msg="You are a requirements analyst",
            workspace="/desmet-results/flowise/story_01/workspace",
            model_name="gpt-5.4-2026-03-05",
        )
        cf_str = str(cf)
        assert "You are a requirements analyst" in cf_str
        assert "/desmet-results/flowise/story_01/workspace" in cf_str
        assert "gpt-5.4" in cf_str
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_flowise_adapter.py::TestChatflowTemplates -v`
Expected: FAIL — `flowise_templates` module not found

- [ ] **Step 3: Implement chatflow templates**

Create `src/desmet/adapters/flowise_templates.py`:

```python
"""Flowise chatflow template definitions for SDLC stages.

Each template is a Python dict representing a Flowise chatflow JSON
structure with an agent node, LLM node, and tool nodes.  The
``build_chatflow`` function deep-copies and parameterises a template
for a specific stage execution.
"""
from __future__ import annotations

import copy
from typing import Any


def _make_base_template(stage_name: str) -> dict[str, Any]:
    """Build the base chatflow template structure for any stage."""
    return {
        "name": f"desmet-{stage_name}",
        "deployed": False,
        "isPublic": False,
        "type": "CHATFLOW",
        "nodes": [
            {
                "id": "agent_0",
                "data": {
                    "id": "agent_0",
                    "label": "Tool Agent",
                    "name": "toolAgent",
                    "type": "AgentFlow",
                    "category": "Agents",
                    "inputs": {
                        "systemMessage": "",
                        "maxIterations": "25",
                    },
                },
                "position": {"x": 450, "y": 300},
                "type": "customNode",
            },
            {
                "id": "llm_0",
                "data": {
                    "id": "llm_0",
                    "label": "ChatOpenAI",
                    "name": "chatOpenAI",
                    "type": "ChatOpenAI",
                    "category": "Chat Models",
                    "inputs": {
                        "modelName": "",
                        "temperature": "0",
                    },
                },
                "position": {"x": 200, "y": 500},
                "type": "customNode",
            },
            {
                "id": "tool_exec_0",
                "data": {
                    "id": "tool_exec_0",
                    "label": "Execute Shell",
                    "name": "customTool",
                    "type": "CustomTool",
                    "category": "Tools",
                    "inputs": {
                        "toolName": "execute_shell",
                        "toolDesc": "Execute a shell command in the workspace directory.",
                        "toolFunc": "",
                    },
                },
                "position": {"x": 600, "y": 500},
                "type": "customNode",
            },
            {
                "id": "tool_read_0",
                "data": {
                    "id": "tool_read_0",
                    "label": "Read File",
                    "name": "customTool",
                    "type": "CustomTool",
                    "category": "Tools",
                    "inputs": {
                        "toolName": "read_file",
                        "toolDesc": "Read the contents of a file in the workspace. Input: relative file path.",
                        "toolFunc": "",
                    },
                },
                "position": {"x": 750, "y": 500},
                "type": "customNode",
            },
            {
                "id": "tool_write_0",
                "data": {
                    "id": "tool_write_0",
                    "label": "Write File",
                    "name": "customTool",
                    "type": "CustomTool",
                    "category": "Tools",
                    "inputs": {
                        "toolName": "write_file",
                        "toolDesc": "Write content to a file in the workspace. Input: JSON with 'path' and 'content' fields.",
                        "toolFunc": "",
                    },
                },
                "position": {"x": 900, "y": 500},
                "type": "customNode",
            },
        ],
        "edges": [
            {"source": "llm_0", "target": "agent_0", "sourceHandle": "llm_0-output-chatOpenAI-ChatOpenAI", "targetHandle": "agent_0-input-model-ChatModel"},
            {"source": "tool_exec_0", "target": "agent_0", "sourceHandle": "tool_exec_0-output-customTool-CustomTool", "targetHandle": "agent_0-input-tools-Tool"},
            {"source": "tool_read_0", "target": "agent_0", "sourceHandle": "tool_read_0-output-customTool-CustomTool", "targetHandle": "agent_0-input-tools-Tool"},
            {"source": "tool_write_0", "target": "agent_0", "sourceHandle": "tool_write_0-output-customTool-CustomTool", "targetHandle": "agent_0-input-tools-Tool"},
        ],
    }


def _tool_js_execute(workspace: str) -> str:
    """JS code for the execute_shell custom tool."""
    return (
        'const { execSync } = require("child_process");\n'
        'try {\n'
        f'  const result = execSync($input, {{ cwd: "{workspace}", timeout: 120000, encoding: "utf-8", maxBuffer: 1024 * 1024 }});\n'
        '  return result;\n'
        '} catch (e) {\n'
        '  return e.stderr || e.message;\n'
        '}'
    )


def _tool_js_read(workspace: str) -> str:
    """JS code for the read_file custom tool."""
    return (
        'const fs = require("fs");\n'
        'const path = require("path");\n'
        f'const fullPath = path.resolve("{workspace}", $input);\n'
        f'if (!fullPath.startsWith("{workspace}")) return "Error: path outside workspace";\n'
        'try {\n'
        '  return fs.readFileSync(fullPath, "utf-8");\n'
        '} catch (e) {\n'
        '  return "Error: " + e.message;\n'
        '}'
    )


def _tool_js_write(workspace: str) -> str:
    """JS code for the write_file custom tool."""
    return (
        'const fs = require("fs");\n'
        'const path = require("path");\n'
        'const input = JSON.parse($input);\n'
        f'const fullPath = path.resolve("{workspace}", input.path);\n'
        f'if (!fullPath.startsWith("{workspace}")) return "Error: path outside workspace";\n'
        'try {\n'
        '  fs.mkdirSync(path.dirname(fullPath), { recursive: true });\n'
        '  fs.writeFileSync(fullPath, input.content);\n'
        '  return "Written: " + input.path;\n'
        '} catch (e) {\n'
        '  return "Error: " + e.message;\n'
        '}'
    )


STAGE_TEMPLATES: dict[str, dict[str, Any]] = {
    stage: _make_base_template(stage)
    for stage in ("requirements", "codegen", "testing", "deploy")
}


def build_chatflow(
    stage_name: str,
    prompt: str,
    system_msg: str,
    workspace: str,
    model_name: str,
) -> dict[str, Any]:
    """Deep-copy a stage template and inject runtime parameters."""
    if stage_name not in STAGE_TEMPLATES:
        raise ValueError(f"Unknown stage: {stage_name}")

    cf = copy.deepcopy(STAGE_TEMPLATES[stage_name])
    cf["name"] = f"desmet-{stage_name}"

    nodes_by_id = {n["id"]: n for n in cf["nodes"]}

    # Inject system message into agent node
    nodes_by_id["agent_0"]["data"]["inputs"]["systemMessage"] = system_msg

    # Inject model name into LLM node
    nodes_by_id["llm_0"]["data"]["inputs"]["modelName"] = model_name

    # Inject tool JS code with workspace path
    nodes_by_id["tool_exec_0"]["data"]["inputs"]["toolFunc"] = _tool_js_execute(workspace)
    nodes_by_id["tool_read_0"]["data"]["inputs"]["toolFunc"] = _tool_js_read(workspace)
    nodes_by_id["tool_write_0"]["data"]["inputs"]["toolFunc"] = _tool_js_write(workspace)

    return cf
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_flowise_adapter.py::TestChatflowTemplates -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/desmet/adapters/flowise_templates.py tests/test_flowise_adapter.py
git commit -m "feat(flowise): add chatflow templates for 4 SDLC stages"
```

---

### Task 6: FlowiseAdapter class

**Files:**
- Modify: `src/desmet/adapters/flowise.py` (add FlowiseAdapter after FlowiseClient)
- Test: `tests/test_flowise_adapter.py` (append)

- [ ] **Step 1: Write failing tests for FlowiseAdapter**

Append to `tests/test_flowise_adapter.py`:

```python
class TestFlowiseAdapterStructure:
    def test_imports(self):
        from desmet.adapters.flowise import FlowiseAdapter

        adapter = FlowiseAdapter(config={"base_url": "http://localhost:3000"})
        assert adapter.platform_info.id == "flowise"

    def test_platform_info_category(self):
        from desmet.adapters.flowise import FlowiseAdapter
        from desmet.harness.models import PlatformCategory

        adapter = FlowiseAdapter()
        assert adapter.platform_info.category == PlatformCategory.VISUAL_WORKFLOW_PLATFORM

    def test_platform_info_runtime_is_docker(self):
        from desmet.adapters.flowise import FlowiseAdapter
        from desmet.harness.models import PlatformRuntime

        adapter = FlowiseAdapter()
        assert adapter.platform_info.runtime == PlatformRuntime.DOCKER

    def test_observability_info(self):
        from desmet.adapters.flowise import FlowiseAdapter

        adapter = FlowiseAdapter()
        info = adapter.get_observability_info()
        assert isinstance(info, dict)
        assert "has_tracing" in info


from unittest.mock import AsyncMock, MagicMock, patch


class TestFlowiseStageExecution:
    @pytest.fixture
    def adapter(self):
        from desmet.adapters.flowise import FlowiseAdapter

        a = FlowiseAdapter(config={"base_url": "http://localhost:3000"})
        a._initialized = True
        a._model_name = "gpt-5.4-2026-03-05"
        a._client = MagicMock()
        return a

    @pytest.mark.asyncio
    async def test_run_workflow_creates_and_deletes_chatflow(self, adapter):
        adapter._client.create_chatflow = AsyncMock(return_value="cf-1")
        adapter._client.predict = AsyncMock(return_value={
            "text": "Done",
            "chatMessageId": "msg-1",
        })
        adapter._client.delete_chatflow = AsyncMock()

        result = await adapter._run_workflow(
            "requirements",
            "Analyse this story",
            "You are a requirements analyst",
            "/desmet-results/flowise/story_01/workspace",
        )

        assert isinstance(result, dict)
        adapter._client.create_chatflow.assert_awaited_once()
        adapter._client.predict.assert_awaited_once()
        adapter._client.delete_chatflow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_visual_stage_end_to_end(self, adapter):
        from desmet.harness.story import UserStory, DifficultyLevel
        from desmet.harness.results import RequirementsResult

        adapter._client.create_chatflow = AsyncMock(return_value="cf-1")
        adapter._client.predict = AsyncMock(return_value={
            "text": "Requirements complete",
        })
        adapter._client.delete_chatflow = AsyncMock()

        story = UserStory(
            id="test_01", title="Test", description="Test story",
            difficulty=DifficultyLevel.BASIC, category="test",
            prompt="Build a hello world app",
        )
        context = MagicMock()
        context.story = story
        context.workspace = "/tmp/results/flowise/test_01/workspace"
        context.platform_id = "flowise"
        context.max_iterations = 25
        context.metadata = {}

        with patch("desmet.adapters._visual_base.audit_workspace", return_value=[]):
            result = await adapter._execute_visual_stage(
                "requirements",
                lambda s, **kw: "Analyse: " + s.prompt,
                RequirementsResult,
                context,
            )

        assert result.platform_id == "flowise"
        assert result.stage_name == "requirements"
        assert result.success is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_flowise_adapter.py::TestFlowiseAdapterStructure tests/test_flowise_adapter.py::TestFlowiseStageExecution -v`
Expected: FAIL — `FlowiseAdapter` not found

- [ ] **Step 3: Implement FlowiseAdapter**

Add the `FlowiseAdapter` class to the bottom of `src/desmet/adapters/flowise.py` (after `FlowiseClient`):

```python
# ── FlowiseAdapter ─────────────────────────────────────────────────────


class FlowiseAdapter(VisualAgentAdapter):
    """Flowise adapter — creates AI Agent chatflows via the REST API."""

    def __init__(self, config: dict[str, Any] | None = None):
        config = config or {}
        super().__init__(
            base_url=config.get("base_url", "http://localhost:3000"),
            api_key=config.get("api_key") or os.environ.get("FLOWISE_API_KEY"),
            config=config,
        )
        self._client: FlowiseClient | None = None
        self._model_name: str | None = None

    @property
    def platform_info(self) -> PlatformInfo:
        return load_platform_info("flowise")

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def initialize(self) -> None:
        self._client = FlowiseClient(
            self.base_url,
            api_key=self.api_key or os.environ.get("FLOWISE_API_KEY"),
        )
        if not await self._client.health_check():
            raise RuntimeError(
                f"Flowise is not reachable at {self.base_url}. "
                "Start it with: docker compose --profile flowise up -d"
            )
        from desmet.llm_config import get_config as get_llm_config
        cfg = get_llm_config(model=self.config.get("model"))
        self._model_name = cfg.model
        self._initialized = True
        logger.info("Flowise adapter initialized")

    async def shutdown(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None
        self._initialized = False

    async def health_check(self) -> bool:
        if self._client is None:
            return False
        return await self._client.health_check()

    # ── VisualPlatformAdapter contract ─────────────────────────────────

    async def create_workflow(self, workflow_definition: dict) -> str:
        assert self._client is not None
        return await self._client.create_chatflow(workflow_definition)

    async def execute_workflow(self, workflow_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        assert self._client is not None
        return await self._client.predict(workflow_id, inputs.get("question", ""))

    async def delete_workflow(self, workflow_id: str) -> None:
        assert self._client is not None
        await self._client.delete_chatflow(workflow_id)

    # ── VisualAgentAdapter abstract methods ─────────────────────────────

    async def _run_workflow(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str,
        workspace: str,
    ) -> dict:
        """Create a chatflow, execute it, clean up, return result."""
        from desmet.adapters.flowise_templates import build_chatflow

        cf_def = build_chatflow(
            stage_name=stage_name,
            prompt=prompt,
            system_msg=system_msg,
            workspace=workspace,
            model_name=self._model_name or "",
        )
        chatflow_id = await self._client.create_chatflow(cf_def)
        try:
            result = await self._client.predict(chatflow_id, prompt)
            return result
        finally:
            try:
                await self._client.delete_chatflow(chatflow_id)
            except Exception:
                pass

    def _collect_execution_metrics(self, trace, exec_data: dict) -> None:
        """Extract token usage from Flowise prediction response."""
        usage = exec_data.get("usedTools", [])
        # Flowise may include token usage in chatMessageId metadata
        token_usage = exec_data.get("tokenUsage") or exec_data.get("usage")
        if token_usage and isinstance(token_usage, dict):
            inp = token_usage.get("promptTokens", 0) or token_usage.get("prompt_tokens", 0)
            out = token_usage.get("completionTokens", 0) or token_usage.get("completion_tokens", 0)
            if inp or out:
                record_usage(trace, int(inp), int(out), model=self._model_name)

    # ── Metadata ──────────────────────────────────────────────────────

    def get_observability_info(self) -> dict[str, Any]:
        return {
            "has_tracing": True,
            "has_step_through": False,
            "has_replay": False,
            "has_state_inspection": True,
            "has_memory_inspection": False,
            "trace_format": "Flowise chatflow log",
            "notes": (
                "Execution data from prediction API. "
                "Chatflow logs available via Flowise UI."
            ),
        }

    def get_failure_handling_info(self) -> dict[str, Any]:
        return {
            "has_checkpointing": False,
            "has_auto_recovery": False,
            "has_graceful_degradation": False,
            "supports_human_handoff": False,
            "is_idempotent": True,
            "notes": (
                "Adapter-side retry loop with workspace validation. "
                "Flowise does not natively checkpoint agent state."
            ),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_flowise_adapter.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/desmet/adapters/flowise.py tests/test_flowise_adapter.py
git commit -m "feat(flowise): add FlowiseAdapter with chatflow execution"
```

---

### Task 7: Registry update and final integration

**Files:**
- Modify: `src/desmet/adapters/registry.py:118`

- [ ] **Step 1: Add flowise to _IMPLEMENTED_PLATFORMS**

In `src/desmet/adapters/registry.py`, update the `_IMPLEMENTED_PLATFORMS` frozenset to include `"flowise"`:

Change:
```python
_IMPLEMENTED_PLATFORMS: frozenset[str] = frozenset({"langgraph", "crewai", "openai_agents_sdk", "microsoft_agent_framework", "google_adk", "n8n"})
```

To:
```python
_IMPLEMENTED_PLATFORMS: frozenset[str] = frozenset({"langgraph", "crewai", "openai_agents_sdk", "microsoft_agent_framework", "google_adk", "n8n", "flowise"})
```

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest tests/test_n8n_adapter.py tests/test_visual_base.py tests/test_flowise_adapter.py -v`
Expected: All tests PASS — n8n (19), visual base (6), flowise (10+)

- [ ] **Step 3: Verify registry**

Run: `uv run python -c "from desmet.adapters.registry import list_available_platforms; print(list_available_platforms())"`
Expected: Output includes both `"flowise"` and `"n8n"`

- [ ] **Step 4: Commit**

```bash
git add src/desmet/adapters/registry.py
git commit -m "feat(flowise): register flowise as implemented platform"
```
