"""DuckDB-backed persistence for evaluation runs and executions."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

_SCHEMA_VERSION = 2

_CREATE_SQL = """\
CREATE TABLE IF NOT EXISTS store_meta (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id          VARCHAR PRIMARY KEY,
    started_at      TIMESTAMP NOT NULL,
    finished_at     TIMESTAMP,
    model           VARCHAR,
    temperature     FLOAT,
    platforms_filter VARCHAR[],
    stories_filter  VARCHAR[],
    note            VARCHAR
);

CREATE TABLE IF NOT EXISTS executions (
    execution_id    VARCHAR PRIMARY KEY,
    run_id          VARCHAR NOT NULL REFERENCES runs(run_id),
    platform_id     VARCHAR NOT NULL,
    story_id        VARCHAR NOT NULL,
    status          VARCHAR NOT NULL,
    started_at      TIMESTAMP,
    finished_at     TIMESTAMP,
    wall_clock_seconds  DOUBLE,
    iterations          INTEGER,
    tool_calls          INTEGER,
    tokens_input        BIGINT,
    tokens_output       BIGINT,
    cost_usd            DOUBLE,
    human_interventions INTEGER,
    score_pipeline_completeness DOUBLE,
    score_efficiency            DOUBLE,
    score_orchestration         DOUBLE,
    score_autonomy              DOUBLE,
    overall_score               DOUBLE,
    rubric_pipeline_completeness DOUBLE,
    rubric_tool_integration      DOUBLE,
    rubric_error_recovery        DOUBLE,
    rubric_trace_quality         DOUBLE,
    rubric_time_efficiency       DOUBLE,
    rubric_autonomy              DOUBLE,
    framework_metrics   VARCHAR,
    trace_path          VARCHAR,
    langfuse_trace_id   VARCHAR,
    langsmith_run_id    VARCHAR,
    repeat_index            INTEGER DEFAULT 0,
    resource_peak_memory_bytes  BIGINT,
    resource_avg_cpu_percent    FLOAT,
    resource_net_tx_bytes       BIGINT
);
"""


class ResultStore:
    """DuckDB-backed persistence for evaluation results."""

    def __init__(self, db_path: Path = Path("results/desmet.duckdb")) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(str(self._db_path))
        self._migrate()

    def _migrate(self) -> None:
        """Create tables if needed; run migrations for older schema versions."""
        tables = {
            t[0]
            for t in self._conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main'"
            ).fetchall()
        }
        if "store_meta" not in tables:
            self._conn.execute(_CREATE_SQL)
            self._conn.execute(
                "INSERT INTO store_meta VALUES (?)", [_SCHEMA_VERSION]
            )
            return

        version = self._conn.execute("SELECT version FROM store_meta").fetchone()
        if version is None or version[0] < _SCHEMA_VERSION:
            current = version[0] if version else 0
            if current < 2:
                for col_sql in [
                    "ALTER TABLE executions ADD COLUMN IF NOT EXISTS repeat_index INTEGER DEFAULT 0",
                    "ALTER TABLE executions ADD COLUMN IF NOT EXISTS resource_peak_memory_bytes BIGINT",
                    "ALTER TABLE executions ADD COLUMN IF NOT EXISTS resource_avg_cpu_percent FLOAT",
                    "ALTER TABLE executions ADD COLUMN IF NOT EXISTS resource_net_tx_bytes BIGINT",
                ]:
                    self._conn.execute(col_sql)
            self._conn.execute(
                "UPDATE store_meta SET version = ?", [_SCHEMA_VERSION]
            )

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def create_run(
        self,
        *,
        model: str | None = None,
        temperature: float | None = None,
        platforms_filter: list[str] | None = None,
        stories_filter: list[str] | None = None,
        note: str | None = None,
    ) -> str:
        """Insert a new run row. Returns the generated run_id (UUID)."""
        run_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        self._conn.execute(
            "INSERT INTO runs (run_id, started_at, model, temperature, "
            "platforms_filter, stories_filter, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [run_id, now, model, temperature, platforms_filter, stories_filter, note],
        )
        return run_id

    def finish_run(self, run_id: str) -> None:
        """Set finished_at on a run."""
        now = datetime.now(timezone.utc)
        self._conn.execute(
            "UPDATE runs SET finished_at = ? WHERE run_id = ?", [now, run_id]
        )

    def save_execution(
        self,
        run_id: str,
        result: Any,  # StoryResult
        metrics: Any,  # StoryMetrics
    ) -> None:
        """Insert one platform×story execution row."""
        fm_json = json.dumps(result.framework_metrics) if result.framework_metrics else None
        self._conn.execute(
            "INSERT INTO executions ("
            "  execution_id, run_id, platform_id, story_id, status,"
            "  started_at, finished_at, wall_clock_seconds, iterations,"
            "  tool_calls, tokens_input, tokens_output, cost_usd,"
            "  human_interventions,"
            "  rubric_pipeline_completeness, rubric_tool_integration,"
            "  rubric_error_recovery, rubric_trace_quality,"
            "  rubric_time_efficiency, rubric_autonomy,"
            "  framework_metrics, trace_path, langfuse_trace_id, langsmith_run_id,"
            "  repeat_index, resource_peak_memory_bytes,"
            "  resource_avg_cpu_percent, resource_net_tx_bytes"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                result.execution_id,
                run_id,
                result.platform_id,
                result.story_id,
                result.status.value,
                result.start_time,
                result.end_time,
                result.wall_clock_seconds,
                result.iterations,
                result.tool_calls,
                result.tokens_input,
                result.tokens_output,
                result.api_cost_usd,
                result.human_interventions,
                metrics.pipeline_completeness_score,
                metrics.tool_integration_score,
                metrics.error_recovery_score,
                metrics.trace_quality_score,
                metrics.time_efficiency_score,
                metrics.autonomy_score,
                fm_json,
                result.trace_file,
                result.langfuse_trace_id,
                getattr(result, "langsmith_run_id", None),
                getattr(result, "repeat_index", 0) or 0,
                (result.resource_metrics or {}).get("peak_memory_bytes"),
                (result.resource_metrics or {}).get("avg_cpu_percent"),
                (result.resource_metrics or {}).get("net_tx_total_bytes"),
            ],
        )

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def latest_run_id(self) -> str | None:
        """Return the most recent run_id, or None if no runs exist."""
        row = self._conn.execute(
            "SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None

    def get_executions(self, run_id: str) -> pd.DataFrame:
        """All executions for a run as a DataFrame."""
        return self._conn.execute(
            "SELECT * FROM executions WHERE run_id = ? ORDER BY platform_id, story_id",
            [run_id],
        ).df()

    def list_runs(self) -> pd.DataFrame:
        """All runs, newest first."""
        return self._conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC"
        ).df()

    def get_run(self, run_id: str) -> pd.DataFrame:
        """Single run row as a DataFrame."""
        return self._conn.execute(
            "SELECT * FROM runs WHERE run_id = ?", [run_id]
        ).df()

    def get_platform_history(self, platform_id: str) -> pd.DataFrame:
        """All executions for a platform across all runs, oldest first.

        Includes the run's started_at for time-series use.
        """
        return self._conn.execute(
            "SELECT e.*, r.started_at AS run_started_at "
            "FROM executions e JOIN runs r ON e.run_id = r.run_id "
            "WHERE e.platform_id = ? "
            "ORDER BY r.started_at ASC",
            [platform_id],
        ).df()

    def update_scores(self, execution_id: str, scores: dict[str, float]) -> None:
        """Update score columns on an execution row.

        Keys must match column names (e.g., 'rubric_pipeline_completeness',
        'score_orchestration').
        """
        valid_columns = {
            "score_pipeline_completeness", "score_efficiency",
            "score_orchestration", "score_autonomy", "overall_score",
            "rubric_pipeline_completeness", "rubric_tool_integration",
            "rubric_error_recovery", "rubric_trace_quality",
            "rubric_time_efficiency", "rubric_autonomy",
        }
        updates = {k: v for k, v in scores.items() if k in valid_columns}
        if not updates:
            return
        set_clause = ", ".join(f"{col} = ?" for col in updates)
        values = list(updates.values()) + [execution_id]
        self._conn.execute(
            f"UPDATE executions SET {set_clause} WHERE execution_id = ?",
            values,
        )

    def update_rubric_scores_by_story(
        self,
        run_id: str,
        platform_id: str,
        story_id: str,
        scores: dict[str, float],
    ) -> bool:
        """Update rubric score columns on the execution matching a platform/story.

        *scores* keys are dimension names (e.g. ``"pipeline_completeness"``),
        automatically prefixed with ``rubric_``.  Returns True if a row was
        updated.
        """
        valid_dims = {
            "pipeline_completeness", "tool_integration",
            "error_recovery", "trace_quality",
            "time_efficiency", "autonomy",
        }
        updates = {
            f"rubric_{k}": v for k, v in scores.items() if k in valid_dims
        }
        if not updates:
            return False
        set_clause = ", ".join(f"{col} = ?" for col in updates)
        values = list(updates.values()) + [run_id, platform_id, story_id]
        result = self._conn.execute(
            f"UPDATE executions SET {set_clause} "
            f"WHERE run_id = ? AND platform_id = ? AND story_id = ?",
            values,
        )
        return result.rowcount > 0

    def update_platform_scores(
        self,
        run_id: str,
        platform_id: str,
        scores: dict[str, float],
    ) -> None:
        """Update score columns on ALL execution rows for a platform in a run.

        Used after ``finalize_platform()`` to persist the platform-level
        dimension scores (1-5 Likert) and overall_score to every execution
        row for that platform.
        """
        valid_columns = {
            "score_pipeline_completeness", "score_efficiency",
            "score_orchestration", "score_autonomy", "overall_score",
        }
        updates = {k: v for k, v in scores.items() if k in valid_columns}
        if not updates:
            return
        set_clause = ", ".join(f"{col} = ?" for col in updates)
        values = list(updates.values()) + [run_id, platform_id]
        self._conn.execute(
            f"UPDATE executions SET {set_clause} "
            f"WHERE run_id = ? AND platform_id = ?",
            values,
        )

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_run_json(self, run_id: str, path: Path) -> Path:
        """Export a single run to JSON in the legacy evaluation_results format."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        run_df = self.get_run(run_id)
        exec_df = self.get_executions(run_id)

        platforms: dict[str, Any] = {}
        for pid, group in exec_df.groupby("platform_id"):
            story_metrics = []
            for _, row in group.iterrows():
                sm: dict[str, Any] = {
                    "story_id": row["story_id"],
                    "success": row["status"] == "completed",
                    "wall_clock_seconds": row["wall_clock_seconds"],
                    "iterations": int(row["iterations"] or 0),
                    "tool_calls": int(row["tool_calls"] or 0),
                    "tokens_input": int(row["tokens_input"] or 0),
                    "tokens_output": int(row["tokens_output"] or 0),
                    "api_cost_usd": row["cost_usd"],
                    "pipeline_completeness_score": row["rubric_pipeline_completeness"],
                    "tool_integration_score": row["rubric_tool_integration"],
                    "error_recovery_score": row["rubric_error_recovery"],
                    "trace_quality_score": row["rubric_trace_quality"],
                    "time_efficiency_score": row["rubric_time_efficiency"],
                    "autonomy_score": row["rubric_autonomy"],
                }
                fm_raw = row["framework_metrics"]
                if fm_raw is not None and isinstance(fm_raw, str):
                    sm["framework_metrics"] = json.loads(fm_raw)
                story_metrics.append(sm)

            platforms[str(pid)] = {
                "platform_id": str(pid),
                "platform_name": str(pid),
                "stories_total": len(group),
                "stories_completed": int((group["status"] == "completed").sum()),
                "stories_failed": int((group["status"] != "completed").sum()),
                "story_metrics": story_metrics,
            }

        started = run_df.iloc[0]["started_at"] if len(run_df) else None
        data = {
            "evaluation_date": str(started) if started else None,
            "run_id": run_id,
            "platforms": platforms,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return path

    def export_run_csv(self, run_id: str, path: Path) -> Path:
        """Export a single run's executions to CSV."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        df = self.get_executions(run_id)
        df.to_csv(path, index=False)
        return path

    def close(self) -> None:
        """Close the DuckDB connection."""
        self._conn.close()
