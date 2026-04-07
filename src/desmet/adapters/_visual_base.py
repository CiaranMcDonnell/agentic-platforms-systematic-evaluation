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
