"""Shared base class for tool-based platform adapters.

Provides the ``_execute_stage`` template method and concrete implementations
of the four SDLC stage methods (``generate_requirements``, ``generate_code``,
``generate_tests``, ``build_and_deploy``).  Subclasses only need to implement
``_run_agent`` with their platform-specific agent execution logic.

This lives in the *adapters* package (not ``harness``) so it can import from
``_prompts``, ``_tools``, and ``_tracing`` without inverting the dependency
direction (``harness`` never imports from ``adapters``).
"""

from __future__ import annotations

from abc import abstractmethod

from desmet.adapters._prompts import (
    build_codegen_prompt,
    build_deploy_prompt,
    build_requirements_prompt,
    build_system_message,
    build_testing_prompt,
)
from desmet.adapters._tools import ToolFormat, create_tools
from desmet.adapters._observation import ObservationCollector, ObservationRequirements
from desmet.adapters._tracing import (
    build_stage_result,
    compute_framework_metrics,
    finish_trace,
    start_trace,
)
from desmet.harness.adapter import BasePlatformAdapter
from desmet.harness.context import StageContext
from desmet.harness.results import (
    CodeResult,
    DeployResult,
    RequirementsResult,
    StageResult,
    TestResult,
)


class ToolAgentAdapter(BasePlatformAdapter):
    """Intermediate base for adapters that use the shared tool/prompt/trace pipeline.

    Subclasses must set ``TOOL_FORMAT`` and implement ``_run_agent``.
    The four SDLC stage methods and the ``_execute_stage`` template are
    provided here so that concrete adapters don't need to duplicate them.
    """

    TOOL_FORMAT: ToolFormat

    @abstractmethod
    async def _run_agent(
        self,
        stage_name: str,
        prompt: str,
        system_msg: str | None,
        tools: list,
        collector: ObservationCollector,
        context: StageContext,
    ) -> tuple[int, bool]:
        """Run the platform-specific agent for one SDLC stage.

        Records observation data via *collector*.  The caller (``_execute_stage``)
        creates the collector and seals it after this method returns.

        Returns ``(iterations, hit_limit)``.
        """
        ...

    def observation_requirements(self) -> ObservationRequirements:
        """Override to adjust completeness requirements per adapter."""
        return ObservationRequirements()

    def _get_model_name(self) -> str | None:
        """Override to provide the model name for usage recording."""
        return None

    # ── Template method ──────────────────────────────────────────────────

    async def _execute_stage(
        self,
        stage_name: str,
        prompt_fn,
        result_cls: type[StageResult],
        context: StageContext,
    ) -> StageResult:
        """Shared template: build prompt → create tools → run agent → build result."""
        import logging

        trace = start_trace()
        try:
            if stage_name == "codegen":
                prior = context.get_prior_result("requirements")
                prompt = prompt_fn(context.story, prior_requirements=prior)
            else:
                prompt = prompt_fn(context.story)
            system_msg = build_system_message(context.story)
            tools = create_tools(
                context.workspace,
                context.allowed_tools,
                fmt=self.TOOL_FORMAT,
                platform_id=context.platform_id,
                story_id=context.story.id,
                stage_name=stage_name,
            )
            collector = ObservationCollector(
                trace,
                model=self._get_model_name(),
                requirements=self.observation_requirements(),
            )
            iterations, hit_limit = await self._run_agent(
                stage_name, prompt, system_msg, tools, collector, context,
            )
            warnings = collector.seal()
            if warnings:
                log = logging.getLogger(
                    f"desmet.adapters.{self.platform_info.id}"
                )
                for w in warnings:
                    log.warning(
                        "Observation gap [%s/%s]: %s",
                        self.platform_info.id,
                        stage_name,
                        w,
                    )
            fm = compute_framework_metrics(trace, context.max_iterations)
            return build_stage_result(
                result_cls, self.platform_info.id, stage_name,
                trace, success=not hit_limit, iterations=iterations,
                framework_metrics=fm,
            )
        except Exception as e:
            finish_trace(trace, error=str(e))
            return build_stage_result(
                result_cls, self.platform_info.id, stage_name,
                trace, success=False, iterations=0, error_message=str(e),
            )

    # ── Concrete SDLC stage methods ──────────────────────────────────────

    async def generate_requirements(self, context: StageContext) -> RequirementsResult:
        return await self._execute_stage("requirements", build_requirements_prompt, RequirementsResult, context)

    async def generate_code(self, context: StageContext) -> CodeResult:
        return await self._execute_stage("codegen", build_codegen_prompt, CodeResult, context)

    async def generate_tests(self, context: StageContext) -> TestResult:
        return await self._execute_stage("testing", build_testing_prompt, TestResult, context)

    async def build_and_deploy(self, context: StageContext) -> DeployResult:
        return await self._execute_stage("deploy", build_deploy_prompt, DeployResult, context)
