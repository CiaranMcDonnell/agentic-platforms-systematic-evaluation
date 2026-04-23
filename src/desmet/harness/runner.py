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
import os
import shutil
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from desmet.observability import (
    get_logger,
    langfuse_span,
    langfuse_trace,
    record_generation,
)
from desmet.harness.story_loader import prepare_stage_context

from .adapter import BasePlatformAdapter
from .auto_rubric import compute_auto_rubric_scores
from .metrics import MetricsCollector, SetupMetrics, StageMetrics, StoryMetrics
from .results import CodeResult, StageResult, TestResult
from .store import ResultStore
from .story import DifficultyLevel, StoryResult, StoryStatus, UserStory

logger = get_logger(__name__)


def _force_remove_readonly(func, path, _exc_info):
    """Handle stubborn files during shutil.rmtree on Windows.

    Covers two cases:
    - Git marks .git/objects/* as read-only → clear the flag and retry.
    - Docker bind-mounts create Linux symlinks (e.g. .venv/lib64 → lib)
      that Windows cannot access ([WinError 1920]) → delete via os.remove.
    """
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        # Last resort: try os.remove (works for dangling symlinks on Windows)
        try:
            os.remove(path)
        except OSError:
            pass


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

    # Repeated-run variance
    repeats: int = 1  # Number of times to run each story for variance measurement

    # Timeouts
    setup_timeout_seconds: int = 300
    story_timeout_multiplier: float = 1.5  # Multiply story budget by this

    # Filtering
    platforms: list[str] | None = None  # None = all platforms
    stories: list[str] | None = None  # None = all stories
    difficulty_levels: list[DifficultyLevel] | None = None

    # Stage filtering (None = all stages)
    stage: str | None = None  # e.g. "codegen", "testing"; None runs all

    # Options
    dry_run: bool = False
    verbose: bool = False
    save_traces: bool = True
    deploy_mode: str = "local"  # "local" or "remote"


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
        progress_callback: Any | None = None,
    ):
        self.config = config
        self.platforms = platforms
        self.stories = stories
        self.baseline_repo = baseline_repo
        self.progress_callback = progress_callback

        # Setup directories
        self.config.results_dir.mkdir(parents=True, exist_ok=True)
        self.config.logs_dir.mkdir(parents=True, exist_ok=True)

        # Initialize metrics collector
        self.metrics = MetricsCollector(self.config.results_dir)

        # Track execution state
        self.results: dict[str, dict[str, StoryResult]] = {}  # platform -> story -> result

        # Persistent result store
        self.store = ResultStore(db_path=self.config.results_dir / "desmet.duckdb")

    async def run_full_evaluation(self) -> dict[str, Any]:
        """
        Run the complete evaluation across all platforms and stories.

        Returns:
            Summary of evaluation results
        """
        logger.info("Starting DESMET Agentic Platforms Evaluation")
        start_time = datetime.now(timezone.utc)

        # Create a persistent run record
        self._current_run_id = self.store.create_run(
            model=os.environ.get("DESMET_MODEL"),
            temperature=float(os.environ.get("DESMET_TEMPERATURE", "0")),
            platforms_filter=self.config.platforms,
            stories_filter=self.config.stories,
        )

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
                    repeat_results: list[StoryResult] = []
                    for repeat_idx in range(self.config.repeats):
                        result = await self._run_story(
                            platform_id, adapter, story, trace=trace,
                            repeat_index=repeat_idx,
                        )
                        repeat_results.append(result)
                        self._record_story_metrics(platform_id, story, result)

                    self.results[platform_id][story.id] = repeat_results[-1]

                    if len(repeat_results) > 1:
                        from desmet.harness.metrics import compute_variance_metrics
                        vm = compute_variance_metrics(repeat_results)
                        self.metrics.record_variance_metrics(
                            platform_id, story.id, vm,
                        )

                # Finalize platform metrics
                self.metrics.finalize_platform(platform_id)
                self._persist_platform_scores(platform_id)

                # Reset platform state for next run
                await adapter.reset_state()

                structlog.contextvars.unbind_contextvars("platform_id")

        # Shutdown all platforms
        await self._shutdown_platforms(platforms_to_run)

        # Export results
        self._export_results()

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        logger.info("evaluation_completed", duration_seconds=round(duration, 1))

        self.store.finish_run(self._current_run_id)

        return self._generate_summary()

    async def run_single_story(
        self,
        platform_id: str,
        story_id: str,
        *,
        run_id: str | None = None,
    ) -> StoryResult:
        """Run a single story on a single platform.

        When *run_id* is provided, all executions are saved under that
        existing persistent run instead of creating a new one.  This is
        what callers running the same story across multiple platforms
        (e.g. the management console "Run on selected platforms" loop)
        must use, otherwise each call creates its own DuckDB run and the
        Scoring page — which loads the latest run by default — only sees
        the platform that ran last.
        """
        if platform_id not in self.platforms:
            raise ValueError(f"Unknown platform: {platform_id}")

        story = next((s for s in self.stories if s.id == story_id), None)
        if not story:
            raise ValueError(f"Unknown story: {story_id}")

        adapter = self.platforms[platform_id]
        self._current_run_id = run_id or self.store.create_run(
            model=os.environ.get("DESMET_MODEL"),
            temperature=float(os.environ.get("DESMET_TEMPERATURE", "0")),
            platforms_filter=[platform_id],
            stories_filter=[story_id],
        )
        # Track whether we own the run lifecycle so a shared run isn't
        # finished prematurely by the first platform to complete.
        self._owns_current_run = run_id is None
        await adapter.initialize()

        # Ensure metrics container exists for this platform
        self.metrics.get_or_create_platform_metrics(
            platform_id=platform_id,
            platform_name=adapter.platform_info.name,
        )

        with langfuse_trace(
            f"desmet-single-{platform_id}-{story_id}",
            metadata={"platform_id": platform_id, "story_id": story_id},
            tags=["single-story"],
        ) as trace:
            try:
                repeat_results: list[StoryResult] = []
                for repeat_idx in range(self.config.repeats):
                    result = await self._run_story(
                        platform_id, adapter, story, trace=trace,
                        repeat_index=repeat_idx,
                    )
                    repeat_results.append(result)
                    self._record_story_metrics(platform_id, story, result)

                if len(repeat_results) > 1:
                    from desmet.harness.metrics import compute_variance_metrics
                    vm = compute_variance_metrics(repeat_results)
                    self.metrics.record_variance_metrics(
                        platform_id, story.id, vm,
                    )

                self.metrics.finalize_platform(platform_id)
                self._persist_platform_scores(platform_id)
                self._export_results()
                if getattr(self, "_owns_current_run", True):
                    self.store.finish_run(self._current_run_id)
                return repeat_results[-1]
            finally:
                await adapter.shutdown()

    async def _initialize_platforms(
        self,
        platforms: dict[str, BasePlatformAdapter],
    ):
        """Initialize all platforms, removing those that fail."""
        logger.info("Initializing platforms...")
        failed: list[str] = []

        for platform_id, adapter in platforms.items():
            logger.info(f"  Initializing {adapter.platform_info.name}...")
            try:
                start = datetime.now(timezone.utc)
                await asyncio.wait_for(
                    adapter.initialize(),
                    timeout=self.config.setup_timeout_seconds,
                )
                duration = (datetime.now(timezone.utc) - start).total_seconds()

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
                failed.append(platform_id)
            except Exception as e:
                logger.error(f"    Error initializing {platform_id}: {e}")
                failed.append(platform_id)

        for pid in failed:
            platforms.pop(pid, None)

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
        repeat_index: int = 0,
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

        suffix = f"_r{repeat_index}" if repeat_index > 0 else ""
        result = StoryResult(
            story_id=story.id,
            platform_id=platform_id,
            execution_id=f"{platform_id}_{story.id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}{suffix}",
            status=StoryStatus.RUNNING,
            start_time=datetime.now(timezone.utc),
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
            # Capture Langfuse trace ID for linking in the web UI
            from desmet.observability import get_langfuse
            lf_client = get_langfuse()
            if lf_client is not None:
                result.langfuse_trace_id = lf_client.get_current_trace_id()

            try:
                # Create isolated workspace: copy baseline into per-platform directory
                workspace = (
                    self.config.results_dir / platform_id / story.id / "workspace"
                )
                if workspace.exists():
                    shutil.rmtree(workspace, onerror=_force_remove_readonly)
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
                    platform_id=platform_id,
                )
                stage_ctx.progress_callback = self.progress_callback

                # Snapshot baseline file paths for post-stage scope auditing
                _skip = {".git", "__pycache__", ".venv", "venv", "node_modules"}
                _baseline: set[str] = set()
                for _dp, _dn, _fn in os.walk(workspace):
                    _dn[:] = [d for d in _dn if d not in _skip]
                    for f in _fn:
                        _baseline.add(
                            str(Path(_dp, f).relative_to(workspace)).replace("\\", "/")
                        )
                stage_ctx.metadata["baseline_files"] = sorted(_baseline)

                # Accumulator for per-stage results
                stage_results: dict[str, StageResult] = {}

                # Determine which stages to execute
                if self.config.stage:
                    stages_to_run = [
                        (k, m) for k, m in self._STAGES if k == self.config.stage
                    ]
                else:
                    stages_to_run = self._STAGES

                # Initialise git remote in workspace for deploy stage
                self._init_deploy_repo(workspace, platform_id, story.id)

                # Build platform image once per story (always rebuild
                # so source/config changes are picked up).  Run in a
                # thread so the blocking subprocess doesn't freeze the
                # event loop (WebSocket, cancel, etc. stay responsive).
                import asyncio as _aio
                from desmet.harness import container_runner
                if self.progress_callback:
                    self.progress_callback(
                        f"  Building Docker image for {platform_id}..."
                    )
                build_ok = await _aio.to_thread(
                    container_runner.build_image,
                    platform_id,
                    progress_callback=self.progress_callback,
                )
                if not build_ok and not hasattr(adapter, "generate_requirements"):
                    raise RuntimeError(f"Docker image build failed for {platform_id}")

                # Execute selected stages sequentially
                for stage_key, method_name in stages_to_run:
                    # Grant access to deploy_remote tool for the deploy stage
                    if stage_key == "deploy" and "deploy_remote" not in stage_ctx.allowed_tools:
                        stage_ctx.allowed_tools.append("deploy_remote")
                    if stage_key == "deploy":
                        os.environ["DESMET_DEPLOY_MODE"] = self.config.deploy_mode

                    if self.progress_callback is not None:
                        self.progress_callback(
                            f"  [{stage_key.upper()}] Starting {stage_key} stage..."
                        )

                    try:
                        with langfuse_span(
                            span,
                            f"stage-{stage_key}",
                            metadata={"platform_id": platform_id, "story_id": story.id},
                        ):
                            if await _aio.to_thread(container_runner.has_image, platform_id):
                                stage_result = await container_runner.run_stage_in_container(
                                    platform_id, stage_key, stage_ctx,
                                    self.progress_callback,
                                )
                            else:
                                stage_method = getattr(adapter, method_name)
                                stage_result = await stage_method(stage_ctx)
                            stage_ctx.add_artifacts(stage_key, stage_result)
                            stage_results[stage_key] = stage_result

                            # Record per-stage metrics
                            self.metrics.record_stage_metrics(
                                platform_id,
                                StageMetrics(
                                    story_id=story.id,
                                    platform_id=platform_id,
                                    stage_name=stage_key,
                                    success=stage_result.success,
                                    wall_clock_seconds=stage_result.wall_clock_seconds,
                                    iterations=stage_result.iterations,
                                    tool_calls=stage_result.tool_calls_count,
                                    tokens_input=stage_result.tokens_input,
                                    tokens_output=stage_result.tokens_output,
                                    human_interventions=stage_result.human_interventions,
                                ),
                            )

                            logger.info(
                                f"stage_{stage_key}_completed",
                                success=stage_result.success,
                            )

                            if self.progress_callback is not None:
                                status = "PASSED" if stage_result.success else "FAILED"
                                total_tokens = stage_result.tokens_input + stage_result.tokens_output
                                cost_part = f", ${stage_result.cost_usd:.4f}" if stage_result.cost_usd > 0 else ""
                                error_part = f" — {stage_result.error_message}" if stage_result.error_message else ""
                                self.progress_callback(
                                    f"  [{stage_key.upper()}] {status} — "
                                    f"{stage_result.wall_clock_seconds:.1f}s, "
                                    f"{stage_result.iterations} iterations, "
                                    f"{stage_result.tool_calls_count} tool calls, "
                                    f"{total_tokens:,} tokens{cost_part}{error_part}"
                                )
                    except Exception as e:
                        logger.error(f"stage_{stage_key}_failed", error=str(e))
                        if self.progress_callback is not None:
                            self.progress_callback(f"  [{stage_key.upper()}] ERROR — {e}")
                        # Continue -- do NOT block later stages

                # Clean up platform container after story completes
                from desmet.harness import container_runner
                await _aio.to_thread(container_runner.stop_container, platform_id, story.id)

                # Stop eval container before post-processing — Docker
                # ----- Aggregate results into StoryResult -----
                result.status = StoryStatus.COMPLETED
                result.finalize_timing()

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
                result.api_cost_usd = sum(
                    sr.cost_usd for sr in stage_results.values()
                )
                result.human_interventions = sum(
                    sr.human_interventions for sr in stage_results.values()
                )

                # Aggregate framework metrics across stages.
                # all_fm also gates the auto-rubric block below, so the
                # vacuous-True corner of `all(sr.success for sr in ...)`
                # cannot be reached with zero stages — at least one stage
                # must have produced framework_metrics for any rubric
                # scoring to happen.
                all_fm = [
                    sr.framework_metrics
                    for sr in stage_results.values()
                    if sr.framework_metrics
                ]
                if all_fm:
                    agg: dict[str, float | None] = {}
                    for key in ("tokens_per_stage", "iteration_ratio",
                                "redundant_tool_call_rate", "tool_failure_rate"):
                        vals = [fm[key] for fm in all_fm if fm.get(key) is not None]
                        agg[key] = sum(vals) / len(vals) if vals else None
                    latencies = [fm["first_action_latency_ms"] for fm in all_fm
                                 if fm.get("first_action_latency_ms") is not None]
                    agg["first_action_latency_ms"] = (
                        sum(latencies) / len(latencies) if latencies else None
                    )
                    overheads = [fm["framework_overhead_ms"] for fm in all_fm
                                 if fm.get("framework_overhead_ms") is not None]
                    agg["framework_overhead_ms"] = sum(overheads) if overheads else None
                    result.framework_metrics = agg
                    # Auto-compute the three trace-derivable rubric
                    # dimensions.  The other two (pipeline_completeness,
                    # autonomy) stay manual via the webui Scoring page.
                    # Skipped when all_fm is empty (total early failure):
                    # without framework metrics the rubric has no signal.
                    # `all(...)` is vacuously True on a dict containing only
                    # stages that actually ran — that is the intended
                    # semantics for score_error_recovery.
                    # Trace selection: prefer the deepest completed stage.
                    # Single-stage runs (e.g. requirements-only benchmarks)
                    # land on that stage's trace; end-to-end runs score
                    # using the deploy trace, which sees the full pipeline.
                    rubric_trace = None
                    for stage_name in ("deploy", "testing", "codegen", "requirements"):
                        sr = stage_results.get(stage_name)
                        if sr is not None and getattr(sr, "trace", None) is not None:
                            rubric_trace = sr.trace
                            break
                    if rubric_trace is not None:
                        try:
                            auto_scores = compute_auto_rubric_scores(
                                success=all(sr.success for sr in stage_results.values()),
                                framework_metrics=agg,
                                trace=rubric_trace,
                            )
                            for dim, val in auto_scores.items():
                                result.add_score(dim, val)
                        except Exception as e:
                            logger.warning(
                                "auto_rubric_scoring_failed",
                                error=str(e),
                                story_id=story.id,
                            )

                # Aggregate resource metrics across stages
                resource_stages = [
                    (sr.resource_metrics, sr.wall_clock_seconds)
                    for sr in stage_results.values()
                    if sr.resource_metrics and sr.resource_metrics.get("samples", 0) > 0
                ]
                if resource_stages:
                    total_duration = sum(dur for _, dur in resource_stages)
                    result.resource_metrics = {
                        "peak_memory_bytes": max(
                            rm["peak_memory_bytes"] for rm, _ in resource_stages
                        ),
                        "avg_memory_bytes": int(sum(
                            rm["avg_memory_bytes"] * dur
                            for rm, dur in resource_stages
                        ) / total_duration) if total_duration > 0 else 0,
                        "avg_cpu_percent": round(sum(
                            rm["avg_cpu_percent"] * dur
                            for rm, dur in resource_stages
                        ) / total_duration, 2) if total_duration > 0 else 0.0,
                        "peak_cpu_percent": max(
                            rm["peak_cpu_percent"] for rm, _ in resource_stages
                        ),
                        "net_rx_total_bytes": sum(
                            rm["net_rx_total_bytes"] for rm, _ in resource_stages
                        ),
                        "net_tx_total_bytes": sum(
                            rm["net_tx_total_bytes"] for rm, _ in resource_stages
                        ),
                        "startup_to_ready_ms": resource_stages[0][0]["startup_to_ready_ms"],
                    }

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
                result.finalize_timing()
                logger.warning("story_timeout", duration_seconds=round(result.wall_clock_seconds, 1))

            except Exception as e:
                result.status = StoryStatus.FAILED
                result.error_message = str(e)
                result.finalize_timing()
                logger.error("story_error", error=str(e))

        structlog.contextvars.unbind_contextvars("story_id", "execution_id")
        return result

    def _persist_platform_scores(self, platform_id: str) -> None:
        """Write platform-level dimension scores + overall_score to DuckDB."""
        run_id = getattr(self, "_current_run_id", None)
        if not run_id:
            return
        pm = self.metrics.platform_metrics.get(platform_id)
        if not pm or not pm.dimension_scores:
            return
        dim_to_col = {
            "pipeline_completeness": "score_pipeline_completeness",
            "efficiency": "score_efficiency",
            "orchestration": "score_orchestration",
            "autonomy": "score_autonomy",
        }
        scores: dict[str, float] = {}
        for ds in pm.dimension_scores:
            col = dim_to_col.get(ds.dimension.value)
            if col:
                scores[col] = ds.score
        scores["overall_score"] = pm.overall_score
        self.store.update_platform_scores(run_id, platform_id, scores)

    def _record_story_metrics(self, platform_id, story, result):
        """Record story-level metrics from the completed StoryResult."""
        metrics = StoryMetrics.from_story_result(
            result,
            time_budget_seconds=story.time_budget_seconds,
        )
        self.metrics.record_story_metrics(platform_id, metrics)
        if getattr(self, "_current_run_id", None):
            self.store.save_execution(self._current_run_id, result, metrics)

    @staticmethod
    def _init_deploy_repo(workspace: Path, platform_id: str, story_id: str) -> None:
        """Initialise a git repo in the workspace with the deploy remote.

        This runs before any stage so the workspace is ready for the deploy
        stage's ``push`` action which commits and pushes to a branch.
        Uses HTTPS + token for the local push remote (works with any SSH
        agent setup).  The server-side pull still uses the SSH deploy key.
        """
        import subprocess as _sp

        deploy_repo = os.environ.get("DEPLOY_REPO", "")
        if not deploy_repo:
            return

        from desmet.adapters._shared.tools import _git_push_url
        push_url = _git_push_url(deploy_repo)
        branch = f"{platform_id}/{story_id}"

        cmds = [
            ["git", "init"],
            ["git", "checkout", "-b", branch],
            ["git", "remote", "add", "deploy", push_url],
            ["git", "add", "-A"],
            ["git", "commit", "-m", "initial baseline"],
        ]
        for cmd in cmds:
            _sp.run(cmd, cwd=workspace, capture_output=True, timeout=30)

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
                "cost_usd": sr.cost_usd,
                "human_interventions": sr.human_interventions,
                "start_time": sr.start_time.isoformat() if sr.start_time else None,
                "end_time": sr.end_time.isoformat() if sr.end_time else None,
                "langsmith_run_id": sr.langsmith_run_id,
            }
            if sr.framework_metrics:
                stage_entry["framework_metrics"] = sr.framework_metrics
            if sr.resource_metrics:
                stage_entry["resource_metrics"] = sr.resource_metrics
            # Include message trace when available
            if sr.trace and sr.trace.messages:
                def _truncate(content: object, limit: int = 500) -> str:
                    s = str(content)
                    return s[:limit] + "..." if len(s) > limit else s

                stage_entry["messages"] = [
                    {
                        "role": msg.role,
                        "content": _truncate(msg.content),
                        "timestamp": msg.timestamp.isoformat(),
                        "metadata": msg.metadata if msg.metadata else {},
                    }
                    for msg in sr.trace.messages
                ]
            # Include per-tool-call details so downstream analysis can
            # determine *which* tools each platform actually used.
            if sr.trace and sr.trace.tool_calls:
                stage_entry["tool_calls"] = [
                    {
                        "tool_name": tc.tool_name,
                        "arguments": tc.arguments,
                        "success": tc.success,
                        "duration_ms": tc.duration_ms,
                    }
                    for tc in sr.trace.tool_calls
                ]
            if sr.trace and sr.trace.node_events:
                stage_entry["node_events"] = sr.trace.node_events
            stages_data[stage_key] = stage_entry

        trace_data = {
            "execution_id": result.execution_id,
            "platform_id": result.platform_id,
            "story_id": result.story_id,
            "langfuse_trace_id": result.langfuse_trace_id,
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
