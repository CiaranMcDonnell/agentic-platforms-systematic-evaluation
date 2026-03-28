"""
DESMET Web UI — FastAPI Backend

Provides REST endpoints and a WebSocket for:
  - Platform status & Docker service control
  - Story listing & filtering
  - Benchmark run configuration & execution
  - Live log streaming during runs
  - Dashboard: results overview, scoring, comparison, story detail, chart JSON
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from desmet.adapters.registry import (
    AdapterNotImplementedError,
    get_adapter,
    list_available_platforms,
)
from desmet.dashboard.charts import (
    bar_completion_rates,
    bar_dimension_comparison,
    bar_efficiency_breakdown,
    bar_platform_rankings,
    bar_story_comparison,
    radar_dimensions,
)
from desmet.dashboard.data import (
    CATEGORY_COLOURS,
    SCORING_DIMENSIONS,
    SCORING_RUBRIC,
    get_dimension_scores_df,
    get_platform_colour,
    get_platform_colours,
    get_platform_ids,
    get_platform_summary_df,
    get_rubric_dim_averages,
    get_scoring_progress,
    get_story_metrics_df,
    is_story_scored,
    list_trace_files,
    load_results_raw,
    load_trace,
    save_results,
    update_story_scores,
)
from desmet.harness.graph import build_graph, build_timeline
from desmet.harness.store import ResultStore
from desmet.harness.loader import StoryLoadError, load_all_stories, resolve_baseline_dir
from desmet.harness.runner import EvaluationRunner, RunnerConfig
from desmet.harness.story import DifficultyLevel
from desmet.infra import (
    PLATFORM_CONTAINERS,
    PLATFORM_NAMES,
    PLATFORM_PACKAGES,
    compose_down,
    compose_up,
    get_config_status,
    get_docker_platform_statuses,
    get_infra_statuses,
    get_platform_statuses,
    is_package_importable,
)
from desmet.llm_config import get_config as get_llm_config
from desmet.webui.langfuse_client import (
    check_status as langfuse_check_status,
)
from desmet.webui.langfuse_client import (
    fetch_trace as langfuse_fetch_trace,
)
from desmet.webui.langfuse_client import (
    fetch_traces as langfuse_fetch_traces,
)
from desmet.webui.langsmith_client import (
    check_status as langsmith_check_status,
)
from desmet.webui.langsmith_client import (
    fetch_run_tree as langsmith_fetch_run_tree,
)

load_dotenv()

_result_store: ResultStore | None = None


def _get_result_store() -> ResultStore:
    global _result_store
    if _result_store is None:
        from desmet.dashboard.data import RESULTS_DIR
        _result_store = ResultStore(db_path=RESULTS_DIR / "desmet.duckdb")
    return _result_store


logger = logging.getLogger("desmet.webui")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle for the Management Console."""
    # ── Startup ──────────────────────────────────────────────────────────
    logger.info("DESMET Management Console starting up")

    # Check Docker availability
    docker_available = shutil.which("docker") is not None
    if docker_available:
        statuses = get_platform_statuses()
        running = [s for s in statuses if s.status == "running"]
        if running:
            logger.info(
                "Docker services already running: %s",
                ", ".join(s.name for s in running),
            )
        else:
            logger.info(
                "Docker is available. Start infrastructure from the Management Console when needed."
            )
    else:
        logger.warning(
            "Docker not found on PATH. Visual platforms (Flowise, "
            "Langflow, Dify, n8n) will be unavailable."
        )

    # Check API key configuration
    cfg = get_config_status()
    if cfg.api_keys_set:
        logger.info("API keys configured: %s", ", ".join(cfg.api_keys_set))
    else:
        logger.warning("No API keys detected — set them in .env")

    logger.info("Ready — open the Management Console in your browser")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    logger.info("DESMET Management Console shutting down")


app = FastAPI(
    title="DESMET Management Console",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory state for active runs ─────────────────────────────────────


class RunState:
    """Tracks a single benchmark run."""

    def __init__(self, run_id: str, config: dict):
        self.run_id = run_id
        self.config = config
        self.status = "pending"  # pending | running | completed | failed
        self.started_at: datetime | None = None
        self.finished_at: datetime | None = None
        self.logs: list[str] = []
        self.summary: dict[str, Any] | None = None
        self.error: str | None = None


_runs: dict[str, RunState] = {}
_ws_clients: dict[str, list[WebSocket]] = {}  # run_id -> connected clients
_running_tasks: dict[str, asyncio.Task] = {}  # run_id -> background task (for cancellation)


# ── Pydantic models ─────────────────────────────────────────────────────


class RunRequest(BaseModel):
    platforms: list[str]
    stories: list[str] = []
    difficulties: list[str] = []
    stages: list[str] = []
    dry_run: bool = False
    model: str | None = None
    results_dir: str | None = None


class DockerAction(BaseModel):
    target: str  # flowise, langflow, dify, n8n, langfuse, all


class ScoreSubmission(BaseModel):
    platform_id: str
    story_id: str
    scores: dict[str, float]
    notes: dict[str, str]

    @field_validator("scores")
    @classmethod
    def scores_in_range(cls, v: dict[str, float]) -> dict[str, float]:
        for dim, score in v.items():
            if not (0 <= score <= 3):
                raise ValueError(f"Score for '{dim}' must be between 0 and 3, got {score}")
        return v


# ── Platform endpoints ──────────────────────────────────────────────────


@app.get("/api/platforms")
async def get_platforms():
    """Return all platforms with registry data (no docker calls)."""
    implemented = set(list_available_platforms())

    platforms = []
    for pid in PLATFORM_PACKAGES:
        name = PLATFORM_NAMES[pid]
        package = PLATFORM_PACKAGES[pid]

        if package is not None:
            from desmet.harness.container_runner import has_image
            if has_image(pid):
                status = "ready"
                infra_type = "Docker (isolated)"
            else:
                status = "ready" if is_package_importable(package) else "not installed"
                infra_type = "Python SDK"
        else:
            status = "unknown"
            infra_type = "Docker"

        platforms.append(
            {
                "id": pid,
                "name": name,
                "infra_type": infra_type,
                "status": status,
                "implemented": pid in implemented,
                "category": _get_platform_category(pid),
            }
        )

    return {"platforms": platforms}


@app.get("/api/platforms/status")
async def get_platform_statuses_endpoint():
    """Return live container status for docker-based platforms (slow — docker inspect)."""
    return {"statuses": get_docker_platform_statuses()}


@app.get("/api/config")
async def get_config():
    """Return current configuration (model, API keys, Langfuse)."""
    cfg = get_config_status()
    llm = get_llm_config()

    return {
        "model": cfg.model,
        "provider": llm.provider.value,
        "api_keys_set": cfg.api_keys_set,
        "langfuse_status": cfg.langfuse_status,
        "deploy_status": cfg.deploy_status,
        "temperature": llm.temperature,
        "available_models": [
            "gpt-5.4-2026-03-05",
            "claude-opus-4-6",
            "claude-sonnet-4-6",
        ],
        "allow_custom_model": True,
        "valid_stages": ["requirements", "codegen", "testing", "deploy", "all"],
        "difficulty_levels": ["basic", "intermediate", "advanced"],
        "langsmith_available": None,
    }


# ── Docker control ──────────────────────────────────────────────────────


@app.post("/api/docker/up")
async def docker_up(action: DockerAction):
    try:
        result = compose_up(action.target)
        if result.returncode == 0:
            return {"success": True, "message": f"Started {action.target}"}
        return {"success": False, "message": result.stderr or "Failed to start"}
    except ValueError as exc:
        return {"success": False, "message": str(exc)}
    except FileNotFoundError:
        return {"success": False, "message": "Docker not found"}


@app.post("/api/docker/down")
async def docker_down(action: DockerAction):
    try:
        result = compose_down(action.target)
        if result.returncode == 0:
            return {"success": True, "message": f"Stopped {action.target}"}
        return {"success": False, "message": result.stderr or "Failed to stop"}
    except ValueError as exc:
        return {"success": False, "message": str(exc)}
    except FileNotFoundError:
        return {"success": False, "message": "Docker not found"}


# ── Infrastructure status ───────────────────────────────────────────────


@app.get("/api/infrastructure")
async def get_infrastructure():
    """Return status of infrastructure services (Langfuse, Postgres+Redis)."""
    return {"services": get_infra_statuses()}


# ── Image build endpoints ────────────────────────────────────────────────


@app.post("/api/images/build")
async def build_platform_images(
    request: dict = Body(default={}),
):
    """Build Docker images for SDK platform adapters."""
    from desmet.harness.container_runner import (
        PLATFORM_EXTRA_MAP,
        build_image,
        has_image,
    )

    platforms = request.get("platforms", list(PLATFORM_EXTRA_MAP.keys()))
    results = {}

    for pid in platforms:
        if pid not in PLATFORM_EXTRA_MAP:
            results[pid] = {"status": "skipped", "reason": "not an SDK platform"}
            continue
        if has_image(pid):
            results[pid] = {"status": "exists"}
            continue

        success = build_image(pid)
        results[pid] = {"status": "built" if success else "failed"}

    return {"images": results}


@app.get("/api/images/status")
async def image_status():
    """Return Docker image availability for all SDK platforms."""
    from desmet.harness.container_runner import PLATFORM_EXTRA_MAP, has_image

    return {
        pid: {"exists": has_image(pid)}
        for pid in PLATFORM_EXTRA_MAP
    }


# ── Story endpoints ─────────────────────────────────────────────────────


@app.get("/api/stories")
async def get_stories(difficulty: str | None = None):
    try:
        stories = load_all_stories(difficulty=difficulty)
    except StoryLoadError as exc:
        return {"stories": [], "error": str(exc)}

    return {
        "stories": [
            {
                "id": s.id,
                "title": s.title,
                "description": s.description,
                "difficulty": s.difficulty.value,
                "category": s.category,
                "acceptance_criteria_count": len(s.acceptance_criteria),
                "time_budget_seconds": s.time_budget_seconds,
                "max_iterations": s.max_iterations,
                "tags": s.tags,
            }
            for s in stories
        ]
    }


# ── Run management ──────────────────────────────────────────────────────


@app.get("/api/runs")
async def list_runs():
    return {
        "runs": [
            {
                "run_id": r.run_id,
                "status": r.status,
                "config": r.config,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "log_count": len(r.logs),
                "error": r.error,
                "summary": r.summary,
            }
            for r in _runs.values()
        ]
    }


@app.post("/api/runs/start")
async def start_run(req: RunRequest):
    # Reject if a run is already active — prevents concurrent API quota exhaustion
    active = next((r for r in _runs.values() if r.status in ("pending", "running")), None)
    if active:
        return {
            "error": f"Run {active.run_id} is already in progress. Cancel it first.",
            "active_run_id": active.run_id,
        }

    run_id = str(uuid.uuid4())[:8]
    run = RunState(run_id=run_id, config=req.model_dump())
    _runs[run_id] = run
    _ws_clients[run_id] = []
    task = asyncio.create_task(_execute_run(run, req))
    _running_tasks[run_id] = task
    return {"run_id": run_id, "status": "started"}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "run_id": run.run_id,
        "status": run.status,
        "config": run.config,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "logs": run.logs[-200:],
        "error": run.error,
        "summary": run.summary,
    }


@app.post("/api/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status in ("pending", "running"):
        task = _running_tasks.get(run_id)
        if task and not task.done():
            task.cancel()
        else:
            # Task already done or not tracked — just update state
            run.status = "cancelled"
            run.finished_at = datetime.now(timezone.utc)
            await _broadcast_log(run_id, "[CANCELLED] Run cancelled by user")
    return {"status": run.status}


# ── WebSocket for live logs ─────────────────────────────────────────────


@app.websocket("/ws/runs/{run_id}")
async def ws_run_logs(websocket: WebSocket, run_id: str):
    await websocket.accept()
    if run_id not in _ws_clients:
        _ws_clients[run_id] = []
    _ws_clients[run_id].append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _ws_clients[run_id].remove(websocket)


async def _broadcast_log(run_id: str, message: str):
    run = _runs.get(run_id)
    if run:
        run.logs.append(message)
    clients = _ws_clients.get(run_id, [])
    stale: list[WebSocket] = []
    for ws in clients:
        try:
            await ws.send_text(message)
        except Exception:
            stale.append(ws)
    for ws in stale:
        try:
            clients.remove(ws)
        except ValueError:
            pass


# ── Run execution ───────────────────────────────────────────────────────


async def _execute_run(run: RunState, req: RunRequest):
    run.status = "running"
    run.started_at = datetime.now(timezone.utc)

    # Initialize Langfuse tracing for this run
    from desmet.observability import init_langfuse, start_session

    init_langfuse()
    start_session(label=run.run_id)

    await _broadcast_log(run.run_id, f"[START] Benchmark run {run.run_id} starting...")
    await _broadcast_log(run.run_id, f"  Platforms: {', '.join(req.platforms)}")
    await _broadcast_log(run.run_id, f"  Stages: {', '.join(req.stages) or 'all'}")
    if req.stories:
        await _broadcast_log(run.run_id, f"  Stories: {', '.join(req.stories)}")
    if req.difficulties:
        await _broadcast_log(run.run_id, f"  Difficulties: {', '.join(req.difficulties)}")
    if req.dry_run:
        await _broadcast_log(run.run_id, "  [DRY RUN]")

    try:
        if req.model:
            os.environ["DESMET_MODEL"] = req.model
            await _broadcast_log(run.run_id, f"  Model: {req.model}")

        # Load stories, filtering by first selected difficulty (loader takes one)
        first_difficulty = req.difficulties[0] if len(req.difficulties) == 1 else None
        await _broadcast_log(run.run_id, "[LOAD] Loading stories...")
        stories = load_all_stories(difficulty=first_difficulty)

        # Filter by multiple difficulties if more than one selected
        if len(req.difficulties) > 1:
            diff_set = set(req.difficulties)
            stories = [s for s in stories if s.difficulty.value in diff_set]

        # Filter to specific stories if selected
        if req.stories:
            story_set = set(req.stories)
            stories = [s for s in stories if s.id in story_set]

        await _broadcast_log(run.run_id, f"  Found {len(stories)} stories")

        if not stories:
            raise ValueError("No stories found matching the selected filters")

        baseline = resolve_baseline_dir()
        await _broadcast_log(run.run_id, f"  Baseline: {baseline}")

        await _broadcast_log(run.run_id, "[INIT] Resolving platform adapters...")
        adapters = {}
        for pid in req.platforms:
            try:
                adapters[pid] = get_adapter(pid)
                await _broadcast_log(run.run_id, f"  {pid}: adapter loaded")
            except (KeyError, AdapterNotImplementedError) as exc:
                await _broadcast_log(run.run_id, f"  {pid}: FAILED — {exc}")

        if not adapters:
            raise ValueError("No valid platform adapters found")

        # Stage filtering: empty list or ["all"] = run everything
        resolved_stage = None
        if req.stages and req.stages != ["all"]:
            resolved_stage = req.stages[0] if len(req.stages) == 1 else None
        config = RunnerConfig(dry_run=req.dry_run, verbose=True, stage=resolved_stage)
        if req.results_dir:
            config.results_dir = Path(req.results_dir)
            config.logs_dir = Path(req.results_dir) / "logs"
        if req.difficulties:
            config.difficulty_levels = [DifficultyLevel(d) for d in req.difficulties]

        # Sync→async bridge: adapters call this from any thread (incl.
        # CrewAI's background thread) and it schedules the broadcast on
        # the event loop.
        _loop = asyncio.get_running_loop()

        def _progress(msg: str) -> None:
            asyncio.run_coroutine_threadsafe(
                _broadcast_log(run.run_id, msg),
                _loop,
            )

        runner = EvaluationRunner(
            config=config,
            platforms=adapters,
            stories=stories,
            baseline_repo=baseline,
            progress_callback=_progress,
        )

        await _broadcast_log(run.run_id, "[RUN] Executing evaluation pipeline...")

        if req.stories and len(req.stories) == 1:
            story_id = req.stories[0]
            for pid in adapters:
                await _broadcast_log(run.run_id, f"  Running {story_id} on {pid}...")
                result = await runner.run_single_story(pid, story_id)
                await _broadcast_log(
                    run.run_id,
                    f"  {pid}/{story_id}: {result.status.value} ({result.wall_clock_seconds:.1f}s)",
                )
            run.summary = {"mode": "single_story", "story": story_id}
        else:
            summary = await runner.run_full_evaluation()
            run.summary = summary
            await _broadcast_log(run.run_id, "[RESULTS] Evaluation complete!")
            if summary.get("rankings"):
                for r in summary["rankings"]:
                    await _broadcast_log(
                        run.run_id,
                        f"  #{r['rank']} {r['platform_name']}: "
                        f"score={r['overall_score']:.2f}, "
                        f"completion={r['completion_rate']:.0%}",
                    )

        run.status = "completed"
        await _broadcast_log(run.run_id, f"[DONE] Run {run.run_id} completed successfully")

    except asyncio.CancelledError:
        run.status = "cancelled"
        run.finished_at = datetime.now(timezone.utc)
        await _broadcast_log(run.run_id, "[CANCELLED] Run cancelled by user")
        raise  # must re-raise so asyncio marks the task as cancelled
    except Exception as exc:
        run.status = "failed"
        run.error = str(exc)
        await _broadcast_log(run.run_id, f"[ERROR] {exc}")
    finally:
        run.finished_at = datetime.now(timezone.utc)
        _running_tasks.pop(run.run_id, None)


# ═══════════════════════════════════════════════════════════════════════════
# Dashboard API endpoints — REST + ECharts JSON
# ═══════════════════════════════════════════════════════════════════════════


@app.get("/api/result-runs")
async def list_result_runs():
    """List all persisted evaluation runs for the run selector."""
    store = _get_result_store()
    df = store.list_runs()
    if df.empty:
        return {"runs": []}
    runs = []
    for _, row in df.iterrows():
        runs.append({
            "run_id": row["run_id"],
            "started_at": str(row["started_at"]) if row["started_at"] else None,
            "finished_at": str(row["finished_at"]) if row["finished_at"] else None,
            "model": row["model"],
            "platforms_filter": row["platforms_filter"],
            "note": row["note"],
        })
    return {"runs": runs}


@app.post("/api/result-runs/{run_id}/export")
async def export_result_run(run_id: str, format: str = "json"):
    """Export a run to JSON or CSV."""
    store = _get_result_store()
    from desmet.dashboard.data import RESULTS_DIR
    if format == "csv":
        path = store.export_run_csv(run_id, RESULTS_DIR / f"export_{run_id}.csv")
    else:
        path = store.export_run_json(run_id, RESULTS_DIR / f"export_{run_id}.json")
    return FileResponse(path, filename=path.name)


@app.get("/api/dashboard/stats")
async def dashboard_stats(run_id: str | None = None):
    """High-level stats from persisted results on disk."""
    data = load_results_raw(run_id)
    pdata = data.get("platforms", {})

    platforms_evaluated = list(pdata.keys())
    total_story_runs = 0
    stories_completed = 0
    stories_failed = 0
    unique_stories: set[str] = set()

    for pid, info in pdata.items():
        for sm in info.get("story_metrics", []):
            total_story_runs += 1
            sid = sm.get("story_id", "")
            unique_stories.add(sid)
            if sm.get("success"):
                stories_completed += 1
            else:
                stories_failed += 1

    return {
        "has_data": bool(pdata),
        "platforms_evaluated": platforms_evaluated,
        "platforms_count": len(platforms_evaluated),
        "total_story_runs": total_story_runs,
        "stories_completed": stories_completed,
        "stories_failed": stories_failed,
        "unique_stories": len(unique_stories),
    }


@app.get("/api/dashboard/overview")
async def dashboard_overview(run_id: str | None = None):
    """Overview page data: summary table, scoring progress, colours."""
    data = load_results_raw(run_id)
    platform_ids = get_platform_ids(data)

    if not platform_ids:
        return {"has_data": False}

    summary_df = get_platform_summary_df(data)
    progress = get_scoring_progress(data)
    colours = get_platform_colours(platform_ids)
    dim_avgs = get_rubric_dim_averages(data)

    summary_rows = []
    for _, row in summary_df.iterrows():
        pid = row["platform_id"]
        scored, total = progress.get(pid, (0, 0))
        summary_rows.append(
            {
                "platform_id": pid,
                "platform_name": row["platform_name"],
                "category": row["category"],
                "overall_score": round(row["overall_score"], 2),
                "stories_total": int(row["stories_total"]),
                "stories_completed": int(row["stories_completed"]),
                "completion_rate": round(row["completion_rate"], 3),
                "scored": scored,
                "total_to_score": total,
                "colour": colours.get(pid, "#666"),
                "dim_scores": dim_avgs.get(pid, {}),
            }
        )

    # Sort by score desc
    summary_rows.sort(key=lambda r: r["overall_score"], reverse=True)

    return {"has_data": True, "platforms": summary_rows, "category_colours": CATEGORY_COLOURS}


@app.get("/api/dashboard/charts/rankings")
async def chart_rankings(run_id: str | None = None):
    """ECharts option for platform rankings bar chart."""
    data = load_results_raw(run_id)
    if not get_platform_ids(data):
        return {"chart": None}
    df = get_platform_summary_df(data)
    return {"chart": bar_platform_rankings(df)}


@app.get("/api/dashboard/charts/completion")
async def chart_completion(run_id: str | None = None):
    """ECharts option for completion rates bar chart."""
    data = load_results_raw(run_id)
    if not get_platform_ids(data):
        return {"chart": None}
    df = get_platform_summary_df(data)
    return {"chart": bar_completion_rates(df)}


@app.get("/api/dashboard/charts/radar")
async def chart_radar(run_id: str | None = None):
    """ECharts option for DESMET dimension radar."""
    data = load_results_raw(run_id)
    pids = get_platform_ids(data)
    if not pids:
        return {"chart": None}

    dim_df = get_dimension_scores_df(data)
    if dim_df.empty:
        return {"chart": None}

    # Build {platform_id: {dim: score}} dict
    dim_scores: dict[str, dict[str, float]] = {}
    for pid in pids:
        pdf = dim_df[dim_df["platform_id"] == pid]
        dim_scores[pid] = {row["dimension"]: row["score"] for _, row in pdf.iterrows()}

    return {"chart": radar_dimensions(dim_scores)}


@app.get("/api/dashboard/charts/efficiency")
async def chart_efficiency(run_id: str | None = None):
    """ECharts option for efficiency breakdown."""
    data = load_results_raw(run_id)
    if not get_platform_ids(data):
        return {"chart": None}
    metrics_df = get_story_metrics_df(data)
    if metrics_df.empty:
        return {"chart": None}
    return {"chart": bar_efficiency_breakdown(metrics_df)}


@app.get("/api/dashboard/charts/story-comparison")
async def chart_story_comparison(metric: str = "wall_clock_seconds", platforms: str = "", run_id: str | None = None):
    """ECharts option for story-level metric comparison."""
    data = load_results_raw(run_id)
    if not get_platform_ids(data):
        return {"chart": None}
    metrics_df = get_story_metrics_df(data)
    if metrics_df.empty or metric not in metrics_df.columns:
        return {"chart": None}

    if platforms:
        pids = [p.strip() for p in platforms.split(",")]
        metrics_df = metrics_df[metrics_df["platform_id"].isin(pids)]

    return {"chart": bar_story_comparison(metrics_df, metric)}


@app.get("/api/dashboard/charts/dimension/{dimension}")
async def chart_dimension(dimension: str, run_id: str | None = None):
    """ECharts option for a single dimension comparison."""
    data = load_results_raw(run_id)
    if not get_platform_ids(data):
        return {"chart": None}
    dim_df = get_dimension_scores_df(data)
    if dim_df.empty:
        return {"chart": None}
    return {"chart": bar_dimension_comparison(dim_df, dimension)}


@app.get("/api/dashboard/framework-metrics")
async def dashboard_framework_metrics(run_id: str | None = None):
    """Return aggregated framework metrics per platform."""
    data = load_results_raw(run_id)
    platforms_out = []
    for pid, pdata in data.get("platforms", {}).items():
        pname = pdata.get("platform_name", pid)
        all_fm: list[dict] = []
        for sm in pdata.get("story_metrics", []):
            fm = sm.get("framework_metrics")
            if fm:
                all_fm.append(fm)
        if not all_fm:
            continue
        avg_metrics: dict[str, float | None] = {}
        for key in ("tokens_per_stage", "iteration_ratio",
                     "redundant_tool_call_rate", "tool_failure_rate",
                     "first_action_latency_ms", "framework_overhead_ms"):
            vals = [fm[key] for fm in all_fm if fm.get(key) is not None]
            avg_metrics[key] = round(sum(vals) / len(vals), 2) if vals else None
        platforms_out.append({
            "platform_id": pid,
            "platform_name": pname,
            "story_count": len(all_fm),
            "metrics": avg_metrics,
        })
    return {"platforms": platforms_out}


# ── Scoring endpoints ───────────────────────────────────────────────────


@app.get("/api/dashboard/scoring/rubric")
async def get_rubric():
    """Return the DESMET scoring rubric and dimension list."""
    return {"dimensions": SCORING_DIMENSIONS, "rubric": SCORING_RUBRIC}


@app.get("/api/dashboard/scoring/{platform_id}/{story_id}")
async def get_story_score(platform_id: str, story_id: str, run_id: str | None = None):
    """Get current scores and trace info for a platform/story pair."""
    data = load_results_raw(run_id)
    pdata = data.get("platforms", {}).get(platform_id, {})
    metrics = pdata.get("story_metrics", [])

    story_metric = None
    for sm in metrics:
        if sm.get("story_id") == story_id:
            story_metric = sm
            break

    if not story_metric:
        return {"found": False}

    # Current scores
    scores = {}
    notes = story_metric.get("scoring_notes", {})
    for dim in SCORING_DIMENSIONS:
        scores[dim] = story_metric.get(f"{dim}_score", 0)

    # Trace files
    trace_files = list_trace_files(platform_id, story_id)
    trace_data = None
    langfuse_tid = None
    raw_trace: dict = {}
    if trace_files:
        raw_trace = load_trace(trace_files[-1])  # most recent
        langfuse_tid = raw_trace.get("langfuse_trace_id")
        # Flatten stage messages into a top-level messages list
        messages: list[dict] = []
        for stage in (raw_trace.get("stages") or {}).values():
            messages.extend(stage.get("messages", []))
        if messages:
            trace_data = {"messages": messages}
        elif raw_trace.get("messages"):
            trace_data = raw_trace

    # Also check story_metric for langfuse_trace_id
    if not langfuse_tid:
        langfuse_tid = story_metric.get("langfuse_trace_id")

    # Extract langsmith_run_id from stage data (LangGraph only)
    langsmith_run_id = (
        next(
            (
                s.get("langsmith_run_id")
                for s in (raw_trace.get("stages") or {}).values()
                if s.get("langsmith_run_id")
            ),
            None,
        )
        if trace_files
        else None
    )

    return {
        "found": True,
        "scored": is_story_scored(story_metric),
        "scores": scores,
        "notes": notes,
        "wall_clock_seconds": story_metric.get("wall_clock_seconds", 0),
        "iterations": story_metric.get("iterations", 0),
        "tool_calls": story_metric.get("tool_calls", 0),
        "success": story_metric.get("success", False),
        "trace": _sanitize_trace(trace_data) if trace_data else None,
        "langfuse_trace_id": langfuse_tid,
        "langsmith_run_id": langsmith_run_id,
        "framework_metrics": story_metric.get("framework_metrics") or None,
    }


@app.get("/api/dashboard/graph/{platform_id}/{story_id}")
async def get_agent_graph(platform_id: str, story_id: str):
    """Build and return the agent communication graph and timeline for a run."""
    trace_files = list_trace_files(platform_id, story_id)
    if not trace_files:
        raise HTTPException(status_code=404, detail="No trace files found")
    raw_trace = load_trace(trace_files[-1])
    graph = build_graph(raw_trace)
    timeline = build_timeline(raw_trace)
    result = graph.to_dict()
    result["timeline"] = [e.to_dict() for e in timeline]
    return result


@app.post("/api/dashboard/scoring/submit")
async def submit_score(submission: ScoreSubmission, run_id: str | None = None):
    """Submit dimension scores for a platform/story pair."""
    data = load_results_raw(run_id)
    update_story_scores(
        data,
        submission.platform_id,
        submission.story_id,
        submission.scores,
        submission.notes,
    )
    save_results(data)
    return {"success": True}


@app.get("/api/dashboard/scoring/progress")
async def scoring_progress(run_id: str | None = None):
    """Return per-platform scoring progress."""
    data = load_results_raw(run_id)
    progress = get_scoring_progress(data)
    return {"progress": {pid: {"scored": s, "total": t} for pid, (s, t) in progress.items()}}


@app.get("/api/dashboard/scoring/matrix")
async def scoring_matrix(run_id: str | None = None):
    """Platform × 6-dimension rubric average score matrix.

    Returns all platforms sorted by sum of dimension averages (highest first).
    Platforms with no scored stories have None for all dimensions.
    """
    data = load_results_raw(run_id)
    pids = get_platform_ids(data)
    if not pids:
        return {"platforms": [], "dimensions": SCORING_DIMENSIONS}

    colours = get_platform_colours(pids)
    avgs = get_rubric_dim_averages(data)
    progress = get_scoring_progress(data)

    rows = []
    for pid in pids:
        pdata = data["platforms"][pid]
        scored_count, _ = progress.get(pid, (0, 0))
        rows.append(
            {
                "platform_id": pid,
                "platform_name": pdata.get("platform_name", pid),
                "colour": colours.get(pid, "#666"),
                "scores": avgs.get(pid, {}),
                "scored_count": scored_count,
            }
        )

    # Sort highest total first (None counts as 0)
    rows.sort(
        key=lambda r: sum(v or 0.0 for v in r["scores"].values()),
        reverse=True,
    )
    return {"platforms": rows, "dimensions": SCORING_DIMENSIONS}


# ── Story detail endpoint ───────────────────────────────────────────────


@app.get("/api/dashboard/story/{story_id}")
async def story_detail(story_id: str, run_id: str | None = None):
    """Get per-platform performance for a specific story."""
    data = load_results_raw(run_id)
    pids = get_platform_ids(data)

    rows = []
    for pid in pids:
        pdata = data["platforms"][pid]
        pname = pdata.get("platform_name", pid)
        for sm in pdata.get("story_metrics", []):
            if sm.get("story_id") == story_id:
                row = {
                    "platform_id": pid,
                    "platform_name": pname,
                    "success": sm.get("success", False),
                    "wall_clock_seconds": sm.get("wall_clock_seconds", 0),
                    "iterations": sm.get("iterations", 0),
                    "tool_calls": sm.get("tool_calls", 0),
                    "colour": get_platform_colour(pid),
                }
                for dim in SCORING_DIMENSIONS:
                    row[f"{dim}_score"] = sm.get(f"{dim}_score", None)
                rows.append(row)

    # Trace availability
    traces = {}
    for pid in pids:
        files = list_trace_files(pid, story_id)
        if files:
            trace = load_trace(files[-1])
            traces[pid] = _sanitize_trace(trace)

    return {"story_id": story_id, "platforms": rows, "traces": traces}


@app.get("/api/dashboard/comparison")
async def comparison_data(platforms: str = "", run_id: str | None = None):
    """Return data needed for the comparison page."""
    data = load_results_raw(run_id)
    pids = get_platform_ids(data)

    if platforms:
        selected = [p.strip() for p in platforms.split(",")]
        pids = [p for p in pids if p in selected]

    if len(pids) < 2:
        return {
            "error": "Select at least 2 platforms",
            "platforms_available": get_platform_ids(data),
        }

    summary_df = get_platform_summary_df(data)
    metrics_df = get_story_metrics_df(data)
    dim_df = get_dimension_scores_df(data)

    # Filter to selected
    summary_df = summary_df[summary_df["platform_id"].isin(pids)]
    metrics_df = (
        metrics_df[metrics_df["platform_id"].isin(pids)] if not metrics_df.empty else metrics_df
    )
    dim_df = dim_df[dim_df["platform_id"].isin(pids)] if not dim_df.empty else dim_df

    # Efficiency averages
    efficiency = {}
    if not metrics_df.empty:
        for pid in pids:
            pdf = metrics_df[metrics_df["platform_id"] == pid]
            efficiency[pid] = {
                "avg_time": round(pdf["wall_clock_seconds"].mean(), 1)
                if "wall_clock_seconds" in pdf.columns
                else 0,
                "avg_iterations": round(pdf["iterations"].mean(), 1)
                if "iterations" in pdf.columns
                else 0,
                "avg_tool_calls": round(pdf["tool_calls"].mean(), 1)
                if "tool_calls" in pdf.columns
                else 0,
            }

    # Category averages
    cat_avgs: dict[str, dict[str, float]] = {}
    if not dim_df.empty:
        for _, row in dim_df.iterrows():
            cat = _get_platform_category(row["platform_id"])
            dim = row["dimension"]
            key = f"{cat}/{dim}"
            if key not in cat_avgs:
                cat_avgs[key] = {"sum": 0, "count": 0}
            cat_avgs[key]["sum"] += row["score"]
            cat_avgs[key]["count"] += 1

    return {
        "selected_platforms": pids,
        "all_platforms": get_platform_ids(data),
        "colours": get_platform_colours(pids),
        "efficiency": efficiency,
        "dimensions": SCORING_DIMENSIONS,
    }


# ── Helpers ─────────────────────────────────────────────────────────────

_CATEGORY_DISPLAY: dict[str, str] = {
    "multi_agent_framework": "Multi-Agent Framework",
    "agent_sdk_runtime": "Agent SDK Runtime",
    "visual_workflow_platform": "Visual Workflow",
}


def _get_platform_category(platform_id: str) -> str:
    from desmet.adapters.registry import load_platform_info

    try:
        info = load_platform_info(platform_id)
        return _CATEGORY_DISPLAY.get(info.category.value, info.category.value)
    except KeyError:
        return "Unknown"


def _sanitize_trace(trace: dict[str, Any]) -> dict[str, Any]:
    """Trim trace messages to prevent huge payloads."""
    sanitized = dict(trace)
    messages = sanitized.get("messages", [])
    trimmed = []
    for msg in messages[:100]:  # max 100 messages
        m = dict(msg)
        content = m.get("content", "")
        if isinstance(content, str) and len(content) > 800:
            m["content"] = content[:800] + "… [truncated]"
        trimmed.append(m)
    sanitized["messages"] = trimmed
    return sanitized


# ── Langfuse trace proxy ─────────────────────────────────────────────────


@app.get("/api/langfuse/status")
async def langfuse_status():
    return await langfuse_check_status()


@app.get("/api/langsmith/status")
async def langsmith_status():
    """Check LangSmith availability."""
    return await langsmith_check_status()


@app.get("/api/langsmith/runs/{run_id}")
async def langsmith_run(run_id: str):
    """Proxy a LangSmith run tree for the webUI trace viewer."""
    result = await langsmith_fetch_run_tree(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="LangSmith unavailable or run not found")
    return result


@app.get("/api/langfuse/traces")
async def langfuse_traces(
    session_id: str | None = None,
    tag: str | None = None,
    limit: int = 50,
):
    tags = [tag] if tag else None
    traces = await langfuse_fetch_traces(session_id=session_id, tags=tags, limit=limit)
    return {
        "traces": traces,
        "langfuse_available": len(traces) > 0 or (await langfuse_check_status())["available"],
    }


@app.get("/api/langfuse/traces/{trace_id}")
async def langfuse_trace_detail(trace_id: str):
    data = await langfuse_fetch_trace(trace_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Trace not found or Langfuse unavailable")
    return data


# ── Serve Svelte frontend ────────────────────────────────────────────────

FRONTEND_DIR = Path(__file__).parent / "frontend" / "dist"

if (FRONTEND_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")


@app.get("/")
async def serve_frontend():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "DESMET Management Console API. Frontend not built yet."}


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if full_path.startswith("api/") or full_path.startswith("ws/"):
        return {"error": "Not found"}
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "DESMET Management Console API"}
