# Result Storage — DuckDB Persistence Layer

**Date:** 2026-03-28
**Status:** Approved

## Problem

Evaluation results are stored in a single `results/evaluation_results.json` that gets overwritten on every run. There is no way to compare results across runs, track score trends over time, or revisit historical evaluations.

Stage trace files (`results/logs/{platform}/{story}/{exec_id}_stages.json`) already accumulate, but aggregated metrics and scores do not.

## Decision Summary

- **Storage backend:** DuckDB (single file, zero infrastructure, native DataFrame integration)
- **Granularity:** Two-level — `runs` (per evaluation invocation) and `executions` (per platform×story within a run)
- **UI model:** Default to latest run with a dropdown to select older runs
- **Existing exports:** DuckDB is primary source of truth. JSON/CSV become on-demand exports (e.g., for sharing with advisor), not written automatically on every run.
- **Artifacts on disk:** Workspace files, trace JSONs, and generated code stay as files. The DB stores pointers (`trace_path`), not BLOBs.

## Database Schema

File location: `results/desmet.duckdb`

```sql
-- One row per run_full_evaluation() call
CREATE TABLE runs (
    run_id          VARCHAR PRIMARY KEY,  -- UUID
    started_at      TIMESTAMP NOT NULL,
    finished_at     TIMESTAMP,
    model           VARCHAR,              -- from DESMET_MODEL env
    temperature     FLOAT,                -- from DESMET_TEMPERATURE env
    platforms_filter VARCHAR[],           -- which platforms were requested (NULL = all)
    stories_filter  VARCHAR[],            -- which stories were requested (NULL = all)
    note            VARCHAR               -- optional user annotation
);

-- One row per platform × story execution within a run
CREATE TABLE executions (
    execution_id    VARCHAR PRIMARY KEY,
    run_id          VARCHAR NOT NULL REFERENCES runs(run_id),
    platform_id     VARCHAR NOT NULL,
    story_id        VARCHAR NOT NULL,
    status          VARCHAR NOT NULL,     -- completed/failed/timeout
    started_at      TIMESTAMP,
    finished_at     TIMESTAMP,

    -- Aggregated metrics (from StoryResult)
    wall_clock_seconds  DOUBLE,
    iterations          INTEGER,
    tool_calls          INTEGER,
    tokens_input        BIGINT,
    tokens_output       BIGINT,
    cost_usd            DOUBLE,
    human_interventions INTEGER,

    -- Scoring (4 cross-cutting dimensions, 1-5 Likert)
    score_pipeline_completeness DOUBLE,
    score_efficiency            DOUBLE,
    score_orchestration         DOUBLE,
    score_autonomy              DOUBLE,
    overall_score               DOUBLE,

    -- Per-stage rubric scores (6 dimensions, 0-3)
    rubric_pipeline_completeness DOUBLE,
    rubric_tool_integration      DOUBLE,
    rubric_error_recovery        DOUBLE,
    rubric_trace_quality         DOUBLE,
    rubric_time_efficiency       DOUBLE,
    rubric_autonomy              DOUBLE,

    -- Framework-specific metrics blob
    framework_metrics   VARCHAR,          -- JSON string

    -- Trace file pointer
    trace_path          VARCHAR,
    langfuse_trace_id   VARCHAR,
    langsmith_run_id    VARCHAR
);

-- Schema versioning
CREATE TABLE store_meta (
    version INTEGER NOT NULL
);
```

## Store Module — `src/desmet/harness/store.py`

Public API:

```python
class ResultStore:
    def __init__(self, db_path: Path = Path("results/desmet.duckdb")):
        """Opens/creates the DB, runs migrations if needed."""

    # --- Write path (called by runner) ---
    def create_run(self, config: RunnerConfig) -> str:
    def finish_run(self, run_id: str) -> None:
    def save_execution(self, run_id: str, result: StoryResult, metrics: StoryMetrics) -> None:
    def update_scores(self, execution_id: str, scores: dict[str, float]) -> None:

    # --- Read path (called by dashboard/webui) ---
    def list_runs(self) -> pd.DataFrame:
    def get_run(self, run_id: str) -> pd.DataFrame:
    def latest_run_id(self) -> str | None:
    def get_executions(self, run_id: str) -> pd.DataFrame:
    def get_platform_history(self, platform_id: str) -> pd.DataFrame:

    # --- Export ---
    def export_run_json(self, run_id: str, path: Path) -> Path:
    def export_run_csv(self, run_id: str, path: Path) -> Path:

    def close(self) -> None:
```

Migrations: a `store_meta` table tracks the schema version. On `__init__`, if the table is missing or the version is behind, run CREATE/ALTER statements inline. No external migration framework.

## Integration Points

### `harness/runner.py` — EvaluationRunner

- Constructor accepts an optional `ResultStore` (default: created from `config.results_dir / "desmet.duckdb"`).
- `run_full_evaluation()`: calls `store.create_run()` at start, `store.finish_run()` at end.
- `_run_story()`: calls `store.save_execution()` after each platform×story completes.
- `_export_results()`: removed from automatic run flow. JSON/CSV export available via `store.export_run_json()` / `store.export_run_csv()` on demand.

### `harness/metrics.py` — MetricsCollector

- `export_json()` and `export_csv()` become thin wrappers delegating to the store's export methods.
- In-memory aggregation (dimension score computation) stays unchanged.

### `dashboard/data.py`

- `load_results_raw()` gains a `run_id: str | None` parameter (`None` = latest run).
- Internally reads from `ResultStore` and reshapes into the existing dict format so all downstream DataFrame builders (`get_story_metrics_df`, `get_dimension_scores_df`) keep working without changes.
- `save_results()` routes score updates through `store.update_scores()`.

### `webui/api.py`

- `GET /api/runs` — returns `store.list_runs()` for the dropdown.
- Existing endpoints gain an optional `?run_id=` query param (omitted = latest).
- `POST /api/runs/{run_id}/export` — triggers JSON/CSV export.

### Webui Frontend (Svelte)

- Run selector dropdown in the header/toolbar, populated from `/api/runs`.
- Selected run ID stored in a Svelte store, threaded through all data-fetching calls.
- Defaults to latest run on page load.

## What Stays Unchanged

- Trace files continue writing to `results/logs/{platform}/{story}/` as JSON.
- Workspace artifacts stay at `results/{platform}/{story}/workspace/`.
- `StoryResult`, `StageResult`, and all harness dataclasses remain as-is.
- `MetricsCollector` in-memory computation logic is untouched.

## Dependencies

- `duckdb` — added via `uv add duckdb`
