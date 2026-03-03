"""
Evaluation Runner

Orchestrates the execution of user stories across all platforms.

The runner drives a four-stage SDLC pipeline for every story:
  Stage 2 -- Requirements Analysis  (adapter.generate_requirements)
  Stage 3 -- Code Generation        (adapter.generate_code)
  Stage 4 -- Test Generation        (adapter.generate_tests)
  Stage 5 -- Build & Deploy         (adapter.build_and_deploy)

Stage 1 (story loading / context preparation) is handled by the harness
itself via ``prepare_stage_context``.
"""

import asyncio
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import structlog

from desmet.observability import (
    get_logger,
    langfuse_span,
    langfuse_trace,
    record_generation,
)
from desmet.stages.stage1_stories.loader import prepare_stage_context

from .base import (
    BasePlatformAdapter,
    EvaluationContext,
    ExecutionResult,
    StageContext,
    StageResult,
    RequirementsResult,
    CodeResult,
    TestResult,
    DeployResult,
)
from .story import UserStory, StoryResult, StoryStatus, DifficultyLevel
from .metrics import MetricsCollector, StoryMetrics, SetupMetrics


logger = get_logger(__name__)


@dataclass
class RunnerConfig:
    """Configuration for the evaluation runner."""
    # Output paths
    results_dir: Path = Path("./results")
    logs_dir: Path = Path("./results/logs")

    # Execution settings
    max_parallel: int = 1
    retry_failed: bool = True
    max_retries: int = 2

    # Timeouts
    setup_timeout_seconds: int = 300
    story_timeout_multiplier: float = 1.5  # Multiply story budget by this

    # Filtering
    platforms: list[str] | None = None  # None = all platforms
    stories: list[str] | None = None  # None = all stories
    difficulty_levels: list[DifficultyLevel] | None = None

    # Options
    dry_run: bool = False
    verbose: bool = False
    save_traces: bool = True


class EvaluationRunner:
    """
    Main runner for DESMET evaluation.

    Orchestrates:
    1. Platform initialization
    2. Story execution across platforms
    3. Metrics collection
    4. Results export
    """

    def __init__(
        self,
        config: RunnerConfig,
        platforms: dict[str, BasePlatformAdapter],
        stories: list[UserStory],
        baseline_repo: Path,
    ):
        self.config = config
        self.platforms = platforms
        self.stories = stories
        self.baseline_repo = baseline_repo

        # Setup directories
        self.config.results_dir.mkdir(parents=True, exist_ok=True)
        self.config.logs_dir.mkdir(parents=True, exist_ok=True)

        # Initialize metrics collector
        self.metrics = MetricsCollector(self.config.results_dir)

        # Track execution state
        self.results: dict[str, dict[str, StoryResult]] = {}  # platform -> story -> result

    async def run_full_evaluation(self) -> dict[str, Any]:
        """
        Run the complete evaluation across all platforms and stories.

        Returns:
            Summary of evaluation results
        """
        logger.info("Starting DESMET Agentic Platforms Evaluation")
        start_time = datetime.now()

        # Filter platforms and stories if configured
        platforms_to_run = self._filter_platforms()
        stories_to_run = self._filter_stories()

        logger.info(
            "evaluation_plan",
            platforms=len(platforms_to_run),
            stories=len(stories_to_run),
        )

        # Initialize all platforms
        await self._initialize_platforms(platforms_to_run)

        with langfuse_trace(
            "desmet-full-evaluation",
            metadata={"platforms": list(platforms_to_run.keys()), "stories": len(stories_to_run)},
            tags=["full-evaluation"],
        ) as trace:
            # Run evaluation for each platform
            for platform_id, adapter in platforms_to_run.items():
                structlog.contextvars.bind_contextvars(platform_id=platform_id)

                logger.info(f"\n{'='*60}")
                logger.info("evaluating_platform", platform=adapter.platform_info.name)
                logger.info(f"{'='*60}")

                self.results[platform_id] = {}

                # Create metrics container
                self.metrics.get_or_create_platform_metrics(
                    platform_id=platform_id,
                    platform_name=adapter.platform_info.name,
                )

                # Run each story
                for story in stories_to_run:
                    result = await self._run_story(platform_id, adapter, story, trace=trace)
                    self.results[platform_id][story.id] = result

                    # Record metrics
                    self._record_story_metrics(platform_id, story, result)

                # Finalize platform metrics
                self.metrics.finalize_platform(platform_id)

                # Reset platform state for next run
                await adapter.reset_state()

                structlog.contextvars.unbind_contextvars("platform_id")

        # Shutdown all platforms
        await self._shutdown_platforms(platforms_to_run)

        # Export results
        self._export_results()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("evaluation_completed", duration_seconds=round(duration, 1))

        return self._generate_summary()

    async def run_single_story(
        self,
        platform_id: str,
        story_id: str,
    ) -> StoryResult:
        """Run a single story on a single platform."""
        if platform_id not in self.platforms:
            raise ValueError(f"Unknown platform: {platform_id}")

        story = next((s for s in self.stories if s.id == story_id), None)
        if not story:
            raise ValueError(f"Unknown story: {story_id}")

        adapter = self.platforms[platform_id]
        await adapter.initialize()

        with langfuse_trace(
            f"desmet-single-{platform_id}-{story_id}",
            metadata={"platform_id": platform_id, "story_id": story_id},
            tags=["single-story"],
        ) as trace:
            try:
                result = await self._run_story(platform_id, adapter, story, trace=trace)
                return result
            finally:
                await adapter.shutdown()

    async def _initialize_platforms(
        self,
        platforms: dict[str, BasePlatformAdapter],
    ):
        """Initialize all platforms."""
        logger.info("Initializing platforms...")

        for platform_id, adapter in platforms.items():
            logger.info(f"  Initializing {adapter.platform_info.name}...")
            try:
                start = datetime.now()
                await asyncio.wait_for(
                    adapter.initialize(),
                    timeout=self.config.setup_timeout_seconds,
                )
                duration = (datetime.now() - start).total_seconds()

                # Record setup time
                setup_metrics = SetupMetrics(
                    platform_id=platform_id,
                    time_to_first_agent_minutes=duration / 60,
                )
                self.metrics.record_setup_metrics(platform_id, setup_metrics)

                # Health check
                healthy = await adapter.health_check()
                if not healthy:
                    logger.warning(f"    Health check failed for {platform_id}")

                logger.info(f"    Initialized in {duration:.1f}s")

            except asyncio.TimeoutError:
                logger.error(f"    Timeout initializing {platform_id}")
            except Exception as e:
                logger.error(f"    Error initializing {platform_id}: {e}")

    async def _shutdown_platforms(
        self,
        platforms: dict[str, BasePlatformAdapter],
    ):
        """Shutdown all platforms."""
        logger.info("Shutting down platforms...")
        for platform_id, adapter in platforms.items():
            try:
                await adapter.shutdown()
            except Exception as e:
                logger.warning(f"Error shutting down {platform_id}: {e}")

    # ------------------------------------------------------------------
    # Stage-by-stage pipeline definition
    # ------------------------------------------------------------------

    #: Ordered list of (stage_key, adapter_method_name) tuples.
    _STAGES: list[tuple[str, str]] = [
        ("requirements", "generate_requirements"),
        ("codegen", "generate_code"),
        ("testing", "generate_tests"),
        ("deploy", "build_and_deploy"),
    ]

    async def _run_story(
        self,
        platform_id: str,
        adapter: BasePlatformAdapter,
        story: UserStory,
        trace: Any | None = None,
    ) -> StoryResult:
        """Run a single story through the four-stage SDLC pipeline.

        Stage 1 (context preparation) is performed by the harness.  Stages
        2-5 are delegated to the adapter's ``generate_requirements``,
        ``generate_code``, ``generate_tests``, and ``build_and_deploy``
        methods respectively.

        Individual stage failures are logged but do **not** prevent later
        stages from executing.
        """
        logger.info("running_story", story_id=story.id, title=story.title)

        result = StoryResult(
            story_id=story.id,
            platform_id=platform_id,
            execution_id=f"{platform_id}_{story.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            status=StoryStatus.RUNNING,
            start_time=datetime.now(),
        )

        structlog.contextvars.bind_contextvars(
            story_id=story.id,
            execution_id=result.execution_id,
        )

        if self.config.dry_run:
            logger.info("dry_run_skip")
            result.status = StoryStatus.SKIPPED
            structlog.contextvars.unbind_contextvars("story_id", "execution_id")
            return result

        with langfuse_span(trace, f"story-{story.id}", metadata={"platform_id": platform_id}) as span:
            try:
                # Create isolated workspace: copy baseline into per-platform directory
                workspace = (
                    self.config.results_dir / platform_id / story.id / "workspace"
                )
                if workspace.exists():
                    shutil.rmtree(workspace)
                shutil.copytree(self.baseline_repo, workspace)
                logger.info(
                    "workspace_created",
                    workspace=str(workspace),
                )

                # Stage 1: Prepare context (harness-only, no adapter call)
                stage_ctx = prepare_stage_context(
                    story,
                    workspace=workspace,
                    timeout_multiplier=self.config.story_timeout_multiplier,
                )

                # Accumulator for per-stage results
                stage_results: dict[str, StageResult] = {}

                # Stages 2-5: call each adapter method sequentially
                for stage_key, method_name in self._STAGES:
                    stage_method = getattr(adapter, method_name)
                    try:
                        with langfuse_span(
                            span,
                            f"stage-{stage_key}",
                            metadata={"platform_id": platform_id, "story_id": story.id},
                        ):
                            stage_result = await stage_method(stage_ctx)
                            stage_ctx.add_artifacts(stage_key, stage_result)
                            stage_results[stage_key] = stage_result
                            logger.info(
                                f"stage_{stage_key}_completed",
                                success=stage_result.success,
                            )
                    except Exception as e:
                        logger.error(f"stage_{stage_key}_failed", error=str(e))
                        # Continue -- do NOT block later stages

                # ----- Aggregate results into StoryResult -----
                result.status = StoryStatus.COMPLETED
                result.end_time = datetime.now()
                result.wall_clock_seconds = (result.end_time - result.start_time).total_seconds()

                # Sum metrics across all completed stages
                result.iterations = sum(
                    sr.iterations for sr in stage_results.values()
                )
                result.tool_calls = sum(
                    sr.tool_calls_count for sr in stage_results.values()
                )
                result.tokens_input = sum(
                    sr.tokens_input for sr in stage_results.values()
                )
                result.tokens_output = sum(
                    sr.tokens_output for sr in stage_results.values()
                )
                result.human_interventions = sum(
                    sr.human_interventions for sr in stage_results.values()
                )

                # Pull artifact-specific fields from code / test / deploy stages
                code_result = stage_results.get("codegen")
                if isinstance(code_result, CodeResult):
                    result.output_files = code_result.output_files
                    result.git_diff = code_result.git_diff

                test_result = stage_results.get("testing")
                if isinstance(test_result, TestResult):
                    result.tests_run = test_result.tests_run
                    result.tests_passed = test_result.tests_passed
                    result.tests_failed = test_result.tests_failed

                # Store the full stage_results dict as raw_result for
                # downstream consumers
                result.raw_result = stage_results

                # Collect error messages from failed stages
                errors: list[str] = []
                for stage_key in ("requirements", "codegen", "testing", "deploy"):
                    sr = stage_results.get(stage_key)
                    if sr and not sr.success and sr.error_message:
                        errors.append(f"{stage_key}: {sr.error_message}")
                if errors:
                    result.error_message = "; ".join(errors)

                # Record generation observation in Langfuse (aggregate)
                record_generation(
                    parent=span,
                    name=f"execute-{story.id}",
                    input=story.prompt,
                    output=result.error_message or "success",
                    usage={
                        "input": result.tokens_input,
                        "output": result.tokens_output,
                    },
                    metadata={
                        "iterations": result.iterations,
                        "tool_calls": result.tool_calls,
                        "stages_completed": list(stage_results.keys()),
                    },
                )

                # Save per-stage traces if configured
                if self.config.save_traces:
                    trace_path = self._save_stage_traces(result, stage_results)
                    result.trace_file = str(trace_path)

                logger.info(
                    "story_completed",
                    stages_completed=list(stage_results.keys()),
                    duration_seconds=round(result.wall_clock_seconds, 1),
                    iterations=result.iterations,
                )

            except asyncio.TimeoutError:
                result.status = StoryStatus.TIMEOUT
                result.error_message = "Execution timed out"
                result.end_time = datetime.now()
                result.wall_clock_seconds = (result.end_time - result.start_time).total_seconds()
                logger.warning("story_timeout", duration_seconds=round(result.wall_clock_seconds, 1))

            except Exception as e:
                result.status = StoryStatus.FAILED
                result.error_message = str(e)
                result.end_time = datetime.now()
                result.wall_clock_seconds = (result.end_time - result.start_time).total_seconds()
                logger.error("story_error", error=str(e))

        structlog.contextvars.unbind_contextvars("story_id", "execution_id")
        return result

    def _record_story_metrics(
        self,
        platform_id: str,
        story: UserStory,
        result: StoryResult,
    ):
        """Record metrics from a story execution."""
        metrics = StoryMetrics(
            story_id=story.id,
            platform_id=platform_id,
            execution_id=result.execution_id,
            success=result.success,
            completed=result.status == StoryStatus.COMPLETED,
            wall_clock_seconds=result.wall_clock_seconds,
            time_budget_seconds=story.time_budget_seconds,
            iterations=result.iterations,
            tool_calls=result.tool_calls,
            tokens_input=result.tokens_input,
            tokens_output=result.tokens_output,
            human_interventions=result.human_interventions,
            correctness_score=next(
                (s.score for s in result.scores if s.dimension == "correctness"), 0
            ),
            completeness_score=next(
                (s.score for s in result.scores if s.dimension == "completeness"), 0
            ),
            code_quality_score=next(
                (s.score for s in result.scores if s.dimension == "code_quality"), 0
            ),
            test_quality_score=next(
                (s.score for s in result.scores if s.dimension == "test_quality"), 0
            ),
            tests_run=result.tests_run,
            tests_passed=result.tests_passed,
            coverage_delta=result.coverage_delta,
            criteria_total=len(story.acceptance_criteria),
            criteria_passed=sum(1 for v in result.criteria_results.values() if v),
        )
        self.metrics.record_story_metrics(platform_id, metrics)

    def _save_trace(
        self,
        result: StoryResult,
        exec_result: ExecutionResult,
    ) -> Path:
        """Save execution trace to file (legacy single-result path)."""
        trace_dir = self.config.logs_dir / result.platform_id / result.story_id
        trace_dir.mkdir(parents=True, exist_ok=True)

        trace_path = trace_dir / f"{result.execution_id}_trace.json"

        trace_data = {
            "execution_id": result.execution_id,
            "platform_id": result.platform_id,
            "story_id": result.story_id,
            "start_time": result.start_time.isoformat() if result.start_time else None,
            "end_time": result.end_time.isoformat() if result.end_time else None,
            "status": result.status.value,
            "iterations": result.iterations,
            "tool_calls": result.tool_calls,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content[:500] + "..." if len(msg.content) > 500 else msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                }
                for msg in exec_result.trace.messages
            ] if exec_result.trace.messages else [],
        }

        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(trace_data, f, indent=2)

        return trace_path

    def _save_stage_traces(
        self,
        result: StoryResult,
        stage_results: dict[str, StageResult],
    ) -> Path:
        """Save per-stage execution traces to a single JSON file.

        Each stage's trace (messages, tool calls, timing) is stored under
        its stage key.  The file is written to the logs directory alongside
        any legacy trace files.
        """
        trace_dir = self.config.logs_dir / result.platform_id / result.story_id
        trace_dir.mkdir(parents=True, exist_ok=True)

        trace_path = trace_dir / f"{result.execution_id}_stages.json"

        stages_data: dict[str, Any] = {}
        for stage_key, sr in stage_results.items():
            stage_entry: dict[str, Any] = {
                "stage_name": sr.stage_name,
                "success": sr.success,
                "error_message": sr.error_message,
                "wall_clock_seconds": sr.wall_clock_seconds,
                "iterations": sr.iterations,
                "tool_calls_count": sr.tool_calls_count,
                "tokens_input": sr.tokens_input,
                "tokens_output": sr.tokens_output,
                "human_interventions": sr.human_interventions,
                "start_time": sr.start_time.isoformat() if sr.start_time else None,
                "end_time": sr.end_time.isoformat() if sr.end_time else None,
            }
            # Include message trace when available
            if sr.trace and sr.trace.messages:
                stage_entry["messages"] = [
                    {
                        "role": msg.role,
                        "content": (
                            msg.content[:500] + "..."
                            if len(msg.content) > 500
                            else msg.content
                        ),
                        "timestamp": msg.timestamp.isoformat(),
                    }
                    for msg in sr.trace.messages
                ]
            stages_data[stage_key] = stage_entry

        trace_data = {
            "execution_id": result.execution_id,
            "platform_id": result.platform_id,
            "story_id": result.story_id,
            "start_time": result.start_time.isoformat() if result.start_time else None,
            "end_time": result.end_time.isoformat() if result.end_time else None,
            "status": result.status.value,
            "iterations": result.iterations,
            "tool_calls": result.tool_calls,
            "stages": stages_data,
        }

        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(trace_data, f, indent=2)

        return trace_path

    def _filter_platforms(self) -> dict[str, BasePlatformAdapter]:
        """Filter platforms based on config."""
        if self.config.platforms is None:
            return self.platforms
        return {
            pid: adapter
            for pid, adapter in self.platforms.items()
            if pid in self.config.platforms
        }

    def _filter_stories(self) -> list[UserStory]:
        """Filter stories based on config."""
        stories = self.stories

        if self.config.stories is not None:
            stories = [s for s in stories if s.id in self.config.stories]

        if self.config.difficulty_levels is not None:
            stories = [s for s in stories if s.difficulty in self.config.difficulty_levels]

        return stories

    def _export_results(self):
        """Export all results to files."""
        logger.info("Exporting results...")

        # JSON export
        json_path = self.metrics.export_json()
        logger.info(f"  JSON: {json_path}")

        # CSV export
        csv_path = self.metrics.export_csv()
        logger.info(f"  CSV: {csv_path}")

        # Text report
        report = self.metrics.generate_comparison_report()
        report_path = self.config.results_dir / "comparison_report.txt"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info(f"  Report: {report_path}")

    def _generate_summary(self) -> dict[str, Any]:
        """Generate evaluation summary."""
        summary = {
            "platforms_evaluated": len(self.metrics.platform_metrics),
            "stories_total": sum(m.stories_total for m in self.metrics.platform_metrics.values()),
            "rankings": [],
        }

        # Rank platforms by overall score
        ranked = sorted(
            self.metrics.platform_metrics.items(),
            key=lambda x: x[1].overall_score,
            reverse=True,
        )

        for rank, (pid, metrics) in enumerate(ranked, 1):
            summary["rankings"].append({
                "rank": rank,
                "platform_id": pid,
                "platform_name": metrics.platform_name,
                "overall_score": metrics.overall_score,
                "completion_rate": metrics.stories_completed / metrics.stories_total if metrics.stories_total > 0 else 0,
            })

        return summary
