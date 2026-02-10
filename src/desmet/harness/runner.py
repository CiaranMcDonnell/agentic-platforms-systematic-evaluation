"""
Evaluation Runner

Orchestrates the execution of user stories across all platforms.
"""

import asyncio
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

from .base import BasePlatformAdapter, EvaluationContext, ExecutionResult
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

    async def _run_story(
        self,
        platform_id: str,
        adapter: BasePlatformAdapter,
        story: UserStory,
        trace: Any | None = None,
    ) -> StoryResult:
        """Run a single story on a platform."""
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

                # Create evaluation context
                context = EvaluationContext(
                    story_id=story.id,
                    story_prompt=story.prompt,
                    story_context=story.context,
                    repo_path=workspace,
                    target_files=story.target_files,
                    time_budget_seconds=int(story.time_budget_seconds * self.config.story_timeout_multiplier),
                    max_iterations=story.max_iterations,
                )

                # Execute
                exec_result = await adapter.execute_story(context)

                # Update result from execution
                result.status = StoryStatus.COMPLETED if exec_result.completed else StoryStatus.FAILED
                result.end_time = datetime.now()
                result.wall_clock_seconds = (result.end_time - result.start_time).total_seconds()
                result.iterations = exec_result.trace.total_iterations
                result.tool_calls = len(exec_result.trace.tool_calls)
                result.tokens_input = exec_result.trace.total_tokens_input
                result.tokens_output = exec_result.trace.total_tokens_output
                result.human_interventions = len(exec_result.interventions)
                result.output_files = exec_result.output_files
                result.git_diff = exec_result.git_diff
                result.raw_result = exec_result

                if not exec_result.success:
                    result.error_message = exec_result.error_message

                # Record generation observation in Langfuse
                record_generation(
                    parent=span,
                    name=f"execute-{story.id}",
                    input=story.prompt,
                    output=exec_result.error_message if not exec_result.success else "success",
                    usage={
                        "input": exec_result.trace.total_tokens_input or 0,
                        "output": exec_result.trace.total_tokens_output or 0,
                    },
                    metadata={
                        "iterations": exec_result.trace.total_iterations,
                        "tool_calls": len(exec_result.trace.tool_calls),
                    },
                )

                # Save trace if configured
                if self.config.save_traces:
                    trace_path = self._save_trace(result, exec_result)
                    result.trace_file = str(trace_path)

                logger.info(
                    "story_completed",
                    success=exec_result.success,
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
        """Save execution trace to file."""
        trace_dir = self.config.logs_dir / result.platform_id / result.story_id
        trace_dir.mkdir(parents=True, exist_ok=True)

        trace_path = trace_dir / f"{result.execution_id}_trace.json"

        import json
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
