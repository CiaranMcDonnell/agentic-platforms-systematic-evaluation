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

_SCHEMA_VERSION = 1

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
    langsmith_run_id    VARCHAR
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
            # Future migrations go here
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

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def latest_run_id(self) -> str | None:
        """Return the most recent run_id, or None if no runs exist."""
        row = self._conn.execute(
            "SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None

    def close(self) -> None:
        """Close the DuckDB connection."""
        self._conn.close()
