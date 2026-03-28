# DuckDB Result Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace overwrite-on-every-run JSON exports with a DuckDB persistence layer that stores all evaluation runs and enables historical comparison.

**Architecture:** A new `ResultStore` class in `src/desmet/harness/store.py` owns the DuckDB file (`results/desmet.duckdb`). The runner writes runs/executions to it. The dashboard reads from it via a compatibility shim that preserves the existing dict format. The webui gains a run selector and export endpoints.

**Tech Stack:** DuckDB (via `duckdb` Python package), existing Pydantic/dataclass models, Svelte 5 frontend

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/desmet/harness/store.py` | DuckDB ResultStore class |
| Create | `tests/test_store.py` | Unit tests for ResultStore |
| Modify | `src/desmet/harness/__init__.py` | Re-export ResultStore |
| Modify | `src/desmet/harness/runner.py:104-126,128-199,719-736` | Wire store into runner lifecycle |
| Modify | `src/desmet/dashboard/data.py:138-157` | Read from store instead of JSON |
| Modify | `src/desmet/webui/api.py:44-60,590-720` | Add run selector endpoints, pass run_id |
| Modify | `src/desmet/webui/frontend/src/lib/stores.ts` | Add `selectedResultsRunId` store |
| Modify | `src/desmet/webui/frontend/src/lib/api.ts` | Add `fetchResultRuns`, thread `run_id` param |
| Create | `src/desmet/webui/frontend/src/lib/components/RunSelector.svelte` | Dropdown component |
| Modify | `src/desmet/webui/frontend/src/lib/pages/ResultsOverview.svelte` | Mount RunSelector |

---

### Task 1: Add DuckDB Dependency

- [ ] **Step 1: Add duckdb to project**

Run: `uv add duckdb`

- [ ] **Step 2: Verify import**

Run: `uv run python -c "import duckdb; print(duckdb.__version__)"`
Expected: prints version without error

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: add duckdb for result persistence"
```

---

### Task 2: ResultStore — Schema and Create/Finish Run

**Files:**
- Create: `src/desmet/harness/store.py`
- Create: `tests/test_store.py`

- [ ] **Step 1: Write failing tests for schema creation and run lifecycle**

```python
# tests/test_store.py
"""Tests for the DuckDB result store."""

import duckdb
import pytest
from pathlib import Path
from desmet.harness.store import ResultStore


@pytest.fixture
def store(tmp_path: Path) -> ResultStore:
    """Create a ResultStore backed by a temporary DuckDB file."""
    s = ResultStore(db_path=tmp_path / "test.duckdb")
    yield s
    s.close()


class TestSchema:
    def test_tables_created(self, store: ResultStore):
        tables = store._conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
        names = {t[0] for t in tables}
        assert "runs" in names
        assert "executions" in names
        assert "store_meta" in names

    def test_schema_version(self, store: ResultStore):
        version = store._conn.execute("SELECT version FROM store_meta").fetchone()
        assert version is not None
        assert version[0] == 1


class TestRunLifecycle:
    def test_create_run(self, store: ResultStore):
        run_id = store.create_run(
            model="gpt-4o",
            temperature=0.0,
            platforms_filter=["langgraph"],
            stories_filter=None,
        )
        assert run_id is not None
        row = store._conn.execute(
            "SELECT run_id, model, temperature, platforms_filter, finished_at FROM runs WHERE run_id = ?",
            [run_id],
        ).fetchone()
        assert row is not None
        assert row[1] == "gpt-4o"
        assert row[2] == 0.0
        assert row[3] == ["langgraph"]
        assert row[4] is None  # not finished yet

    def test_finish_run(self, store: ResultStore):
        run_id = store.create_run()
        store.finish_run(run_id)
        finished_at = store._conn.execute(
            "SELECT finished_at FROM runs WHERE run_id = ?", [run_id]
        ).fetchone()[0]
        assert finished_at is not None

    def test_latest_run_id_empty(self, store: ResultStore):
        assert store.latest_run_id() is None

    def test_latest_run_id(self, store: ResultStore):
        r1 = store.create_run()
        r2 = store.create_run()
        assert store.latest_run_id() == r2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'desmet.harness.store'`

- [ ] **Step 3: Implement ResultStore with schema init and run lifecycle**

```python
# src/desmet/harness/store.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_store.py -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/desmet/harness/store.py tests/test_store.py
git commit -m "feat: add ResultStore with schema init and run lifecycle"
```

---

### Task 3: ResultStore — save_execution and get_executions

**Files:**
- Modify: `src/desmet/harness/store.py`
- Modify: `tests/test_store.py`

- [ ] **Step 1: Write failing tests for save_execution and get_executions**

Add to `tests/test_store.py`:

```python
class TestExecutions:
    def _make_story_result(self):
        """Build a minimal StoryResult for testing."""
        from desmet.harness.story import StoryResult, StoryStatus
        return StoryResult(
            story_id="US-001",
            platform_id="langgraph",
            execution_id="langgraph_US-001_20260328_092300",
            status=StoryStatus.COMPLETED,
            start_time=datetime(2026, 3, 28, 9, 19, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 28, 9, 22, 0, tzinfo=timezone.utc),
            wall_clock_seconds=180.0,
            iterations=3,
            tool_calls=25,
            tokens_input=105000,
            tokens_output=5000,
            api_cost_usd=0.025,
            human_interventions=0,
            framework_metrics={"tokens_per_stage": 110000.0},
        )

    def _make_story_metrics(self, result):
        from desmet.harness.metrics import StoryMetrics
        return StoryMetrics.from_story_result(result, time_budget_seconds=300.0)

    def test_save_and_retrieve(self, store: ResultStore):
        from datetime import datetime, timezone
        run_id = store.create_run()
        result = self._make_story_result()
        metrics = self._make_story_metrics(result)

        store.save_execution(run_id, result, metrics)

        df = store.get_executions(run_id)
        assert len(df) == 1
        row = df.iloc[0]
        assert row["platform_id"] == "langgraph"
        assert row["story_id"] == "US-001"
        assert row["status"] == "completed"
        assert row["wall_clock_seconds"] == 180.0
        assert row["tokens_input"] == 105000
        assert row["cost_usd"] == 0.025

    def test_get_executions_empty(self, store: ResultStore):
        run_id = store.create_run()
        df = store.get_executions(run_id)
        assert len(df) == 0

    def test_multiple_runs_isolated(self, store: ResultStore):
        from datetime import datetime, timezone
        r1 = store.create_run()
        r2 = store.create_run()
        result = self._make_story_result()
        metrics = self._make_story_metrics(result)

        store.save_execution(r1, result, metrics)

        assert len(store.get_executions(r1)) == 1
        assert len(store.get_executions(r2)) == 0
```

Add these imports at the top of the file:

```python
from datetime import datetime, timezone
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `uv run pytest tests/test_store.py::TestExecutions -v`
Expected: FAIL — `AttributeError: 'ResultStore' object has no attribute 'save_execution'`

- [ ] **Step 3: Implement save_execution and get_executions**

Add to the `ResultStore` class in `src/desmet/harness/store.py`, in the "Write path" section after `finish_run`:

```python
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
            "  framework_metrics, trace_path, langfuse_trace_id, langsmith_run_id"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
            ],
        )
```

Add to the "Read path" section after `latest_run_id`:

```python
    def get_executions(self, run_id: str) -> pd.DataFrame:
        """All executions for a run as a DataFrame."""
        return self._conn.execute(
            "SELECT * FROM executions WHERE run_id = ? ORDER BY platform_id, story_id",
            [run_id],
        ).df()
```

- [ ] **Step 4: Run all tests to verify they pass**

Run: `uv run pytest tests/test_store.py -v`
Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/desmet/harness/store.py tests/test_store.py
git commit -m "feat: add save_execution and get_executions to ResultStore"
```

---

### Task 4: ResultStore — list_runs, get_run, update_scores, get_platform_history

**Files:**
- Modify: `src/desmet/harness/store.py`
- Modify: `tests/test_store.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_store.py`:

```python
class TestListRuns:
    def test_list_runs_order(self, store: ResultStore):
        r1 = store.create_run(model="gpt-4o")
        r2 = store.create_run(model="claude-sonnet")
        df = store.list_runs()
        assert len(df) == 2
        # newest first
        assert df.iloc[0]["run_id"] == r2
        assert df.iloc[1]["run_id"] == r1

    def test_get_run(self, store: ResultStore):
        run_id = store.create_run(model="gpt-4o")
        df = store.get_run(run_id)
        assert len(df) == 1
        assert df.iloc[0]["model"] == "gpt-4o"


class TestUpdateScores:
    def test_update_rubric_scores(self, store: ResultStore):
        run_id = store.create_run()
        from desmet.harness.story import StoryResult, StoryStatus
        result = StoryResult(
            story_id="US-001",
            platform_id="langgraph",
            execution_id="lg_us001_test",
            status=StoryStatus.COMPLETED,
        )
        from desmet.harness.metrics import StoryMetrics
        metrics = StoryMetrics.from_story_result(result)
        store.save_execution(run_id, result, metrics)

        store.update_scores("lg_us001_test", {
            "rubric_pipeline_completeness": 2.0,
            "rubric_tool_integration": 3.0,
            "score_orchestration": 4.5,
        })

        df = store.get_executions(run_id)
        row = df.iloc[0]
        assert row["rubric_pipeline_completeness"] == 2.0
        assert row["rubric_tool_integration"] == 3.0
        assert row["score_orchestration"] == 4.5


class TestPlatformHistory:
    def test_history_across_runs(self, store: ResultStore):
        from desmet.harness.story import StoryResult, StoryStatus
        from desmet.harness.metrics import StoryMetrics

        for i in range(3):
            run_id = store.create_run()
            result = StoryResult(
                story_id="US-001",
                platform_id="langgraph",
                execution_id=f"lg_us001_{i}",
                status=StoryStatus.COMPLETED,
                wall_clock_seconds=100.0 + i * 10,
            )
            metrics = StoryMetrics.from_story_result(result)
            store.save_execution(run_id, result, metrics)

        df = store.get_platform_history("langgraph")
        assert len(df) == 3
        # oldest first
        assert df.iloc[0]["execution_id"] == "lg_us001_0"
        assert df.iloc[2]["execution_id"] == "lg_us001_2"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_store.py::TestListRuns tests/test_store.py::TestUpdateScores tests/test_store.py::TestPlatformHistory -v`
Expected: FAIL — missing methods

- [ ] **Step 3: Implement list_runs, get_run, update_scores, get_platform_history**

Add to the "Read path" section of `src/desmet/harness/store.py`:

```python
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
```

- [ ] **Step 4: Run all tests to verify they pass**

Run: `uv run pytest tests/test_store.py -v`
Expected: all 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/desmet/harness/store.py tests/test_store.py
git commit -m "feat: add list_runs, get_run, update_scores, get_platform_history"
```

---

### Task 5: ResultStore — JSON/CSV Export

**Files:**
- Modify: `src/desmet/harness/store.py`
- Modify: `tests/test_store.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_store.py`:

```python
import json as json_mod


class TestExport:
    def _seed_run(self, store: ResultStore):
        from desmet.harness.story import StoryResult, StoryStatus
        from desmet.harness.metrics import StoryMetrics

        run_id = store.create_run(model="gpt-4o")
        result = StoryResult(
            story_id="US-001",
            platform_id="langgraph",
            execution_id="lg_us001_export",
            status=StoryStatus.COMPLETED,
            wall_clock_seconds=180.0,
            iterations=3,
            tool_calls=25,
            tokens_input=100000,
            tokens_output=5000,
            api_cost_usd=0.025,
        )
        metrics = StoryMetrics.from_story_result(result, time_budget_seconds=300.0)
        store.save_execution(run_id, result, metrics)
        store.finish_run(run_id)
        return run_id

    def test_export_json(self, store: ResultStore, tmp_path: Path):
        run_id = self._seed_run(store)
        out = store.export_run_json(run_id, tmp_path / "out.json")
        assert out.exists()
        data = json_mod.loads(out.read_text())
        assert "platforms" in data
        assert "langgraph" in data["platforms"]

    def test_export_csv(self, store: ResultStore, tmp_path: Path):
        run_id = self._seed_run(store)
        out = store.export_run_csv(run_id, tmp_path / "out.csv")
        assert out.exists()
        df = pd.read_csv(out)
        assert len(df) == 1
        assert df.iloc[0]["platform_id"] == "langgraph"
```

Add `import pandas as pd` at the top of the test file if not present.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_store.py::TestExport -v`
Expected: FAIL — missing methods

- [ ] **Step 3: Implement export_run_json and export_run_csv**

Add to `src/desmet/harness/store.py` after `update_scores`:

```python
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
                fm_raw = row.get("framework_metrics")
                if fm_raw and isinstance(fm_raw, str):
                    sm["framework_metrics"] = json.loads(fm_raw)
                story_metrics.append(sm)

            platforms[str(pid)] = {
                "platform_id": str(pid),
                "platform_name": str(pid),  # name not stored; use id
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
```

- [ ] **Step 4: Run all tests**

Run: `uv run pytest tests/test_store.py -v`
Expected: all 15 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/desmet/harness/store.py tests/test_store.py
git commit -m "feat: add JSON/CSV export to ResultStore"
```

---

### Task 6: Re-export ResultStore from harness __init__

**Files:**
- Modify: `src/desmet/harness/__init__.py`

- [ ] **Step 1: Add import and __all__ entry**

In `src/desmet/harness/__init__.py`, add the import:

```python
from .store import ResultStore
```

Add `"ResultStore"` to the `__all__` list.

- [ ] **Step 2: Verify import works**

Run: `uv run python -c "from desmet.harness import ResultStore; print(ResultStore)"`
Expected: `<class 'desmet.harness.store.ResultStore'>`

- [ ] **Step 3: Commit**

```bash
git add src/desmet/harness/__init__.py
git commit -m "feat: re-export ResultStore from harness __init__"
```

---

### Task 7: Wire ResultStore into EvaluationRunner

**Files:**
- Modify: `src/desmet/harness/runner.py`

- [ ] **Step 1: Add store to RunnerConfig and EvaluationRunner.__init__**

In `src/desmet/harness/runner.py`, add the import at the top (after the existing imports):

```python
from .store import ResultStore
```

In the `EvaluationRunner.__init__` method (line 104), after `self.results: dict[str, dict[str, StoryResult]] = {}` (line 126), add:

```python
        # Persistent result store
        self.store = ResultStore(db_path=self.config.results_dir / "desmet.duckdb")
```

- [ ] **Step 2: Wire create_run/finish_run into run_full_evaluation**

In `run_full_evaluation()` (line 128), after the `start_time = datetime.now(timezone.utc)` line (line 136), add:

```python
        # Create a persistent run record
        self._current_run_id = self.store.create_run(
            model=os.environ.get("DESMET_MODEL"),
            temperature=float(os.environ.get("DESMET_TEMPERATURE", "0")),
            platforms_filter=self.config.platforms,
            stories_filter=self.config.stories,
        )
```

Before the `return self._generate_summary()` line (line 199), add:

```python
        self.store.finish_run(self._current_run_id)
```

- [ ] **Step 3: Wire save_execution into the story completion flow**

In `_record_story_metrics` (line 576), after `self.metrics.record_story_metrics(platform_id, metrics)` (line 582), add:

```python
        if hasattr(self, "_current_run_id") and self._current_run_id:
            self.store.save_execution(self._current_run_id, result, metrics)
```

The method signature needs `result` — update it from:

```python
    def _record_story_metrics(self, platform_id, story, result):
```

to keep the same signature (it already receives `result`). Just add the store call using the existing `result` and the newly created `metrics`.

- [ ] **Step 4: Remove automatic JSON/CSV export from _export_results**

Replace the `_export_results` method (lines 719-736) with:

```python
    def _export_results(self):
        """Export results for the current run.

        When a persistent store is available, exports are written via the
        store. The legacy MetricsCollector JSON/CSV paths are still written
        for backwards compatibility with external tooling.
        """
        logger.info("Exporting results...")

        # Legacy JSON/CSV (still useful for quick inspection)
        json_path = self.metrics.export_json()
        logger.info(f"  JSON: {json_path}")

        csv_path = self.metrics.export_csv()
        logger.info(f"  CSV: {csv_path}")

        # Text report
        report = self.metrics.generate_comparison_report()
        report_path = self.config.results_dir / "comparison_report.txt"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info(f"  Report: {report_path}")
```

- [ ] **Step 5: Wire store into run_single_story**

In `run_single_story()` (line 201), after `adapter = self.platforms[platform_id]` (line 214), add:

```python
        self._current_run_id = self.store.create_run(
            model=os.environ.get("DESMET_MODEL"),
            temperature=float(os.environ.get("DESMET_TEMPERATURE", "0")),
            platforms_filter=[platform_id],
            stories_filter=[story_id],
        )
```

In the `try` block, before `return result` (line 233), add:

```python
                self.store.finish_run(self._current_run_id)
```

- [ ] **Step 6: Verify the runner still imports cleanly**

Run: `uv run python -c "from desmet.harness.runner import EvaluationRunner; print('OK')"`
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add src/desmet/harness/runner.py
git commit -m "feat: wire ResultStore into EvaluationRunner lifecycle"
```

---

### Task 8: Update dashboard data layer to read from store

**Files:**
- Modify: `src/desmet/dashboard/data.py`

- [ ] **Step 1: Add store singleton and update load_results_raw**

In `src/desmet/dashboard/data.py`, add the import near the top (after the `from pathlib import Path` line):

```python
from desmet.harness.store import ResultStore
```

Add a module-level store accessor after the path constants:

```python
_store: ResultStore | None = None


def _get_store() -> ResultStore:
    """Lazily create a singleton ResultStore."""
    global _store
    if _store is None:
        _store = ResultStore(db_path=RESULTS_DIR / "desmet.duckdb")
    return _store
```

Replace the `load_results_raw` function (lines 138-147) with:

```python
def load_results_raw(run_id: str | None = None) -> dict[str, Any]:
    """Load evaluation results for a specific run.

    When *run_id* is ``None``, loads the most recent run. Falls back to
    the legacy JSON file when the DuckDB store has no data (e.g., for
    results produced before the store was introduced).
    """
    store = _get_store()
    target_id = run_id or store.latest_run_id()

    if target_id is None:
        # No runs in DB — fall back to legacy JSON
        if not RESULTS_JSON.exists():
            return {"platforms": {}}
        with open(RESULTS_JSON, encoding="utf-8") as fh:
            return json.load(fh)

    exec_df = store.get_executions(target_id)
    if exec_df.empty:
        # Run exists but no executions — return empty
        return {"platforms": {}, "run_id": target_id}

    # Reshape into the legacy dict format expected by downstream functions
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
                "scored": any(
                    row.get(f"rubric_{d}") not in (None, 0.0)
                    for d in ["pipeline_completeness", "tool_integration",
                              "error_recovery", "trace_quality",
                              "time_efficiency", "autonomy"]
                ),
            }
            fm_raw = row.get("framework_metrics")
            if fm_raw and isinstance(fm_raw, str):
                sm["framework_metrics"] = json.loads(fm_raw)
            story_metrics.append(sm)

        platforms[str(pid)] = {
            "platform_id": str(pid),
            "platform_name": str(pid),
            "stories_total": len(group),
            "stories_completed": int((group["status"] == "completed").sum()),
            "stories_failed": int((group["status"] != "completed").sum()),
            "overall_score": float(group["overall_score"].mean()) if group["overall_score"].notna().any() else 0.0,
            "story_metrics": story_metrics,
            "dimension_scores": [],  # computed on-the-fly by dashboard
        }

    run_df = store.get_run(target_id)
    started = run_df.iloc[0]["started_at"] if len(run_df) else None

    return {
        "evaluation_date": str(started) if started else None,
        "run_id": target_id,
        "platforms": platforms,
    }
```

- [ ] **Step 2: Update save_results to write through store**

Replace `save_results` (lines 150-157) with:

```python
def save_results(data: dict[str, Any]) -> None:
    """Write evaluation results back.

    Delegates score updates to the store.  Also writes the legacy JSON
    file for backwards compatibility.
    """
    # Legacy file write
    RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_JSON, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)
```

- [ ] **Step 3: Verify the dashboard module imports without error**

Run: `uv run python -c "from desmet.dashboard.data import load_results_raw; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/desmet/dashboard/data.py
git commit -m "feat: update dashboard data layer to read from DuckDB store"
```

---

### Task 9: Add backend API endpoints for runs and run_id filtering

**Files:**
- Modify: `src/desmet/webui/api.py`

- [ ] **Step 1: Add store import and /api/result-runs endpoint**

At the top of `src/desmet/webui/api.py`, after the existing `from desmet.dashboard.data import ...` block (line 44), add:

```python
from desmet.harness.store import ResultStore
```

Add a module-level store accessor near the top of the file (after the `load_dotenv()` call):

```python
_result_store: ResultStore | None = None


def _get_result_store() -> ResultStore:
    global _result_store
    if _result_store is None:
        from desmet.dashboard.data import RESULTS_DIR
        _result_store = ResultStore(db_path=RESULTS_DIR / "desmet.duckdb")
    return _result_store
```

Add a new endpoint before the dashboard endpoints section:

```python
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
```

- [ ] **Step 2: Add run_id query param to dashboard_stats**

Update the `dashboard_stats` endpoint signature (around line 591) from:

```python
async def dashboard_stats():
```

to:

```python
async def dashboard_stats(run_id: str | None = None):
```

And change `data = load_results_raw()` to `data = load_results_raw(run_id)`.

- [ ] **Step 3: Add run_id query param to all other dashboard endpoints**

Apply the same pattern to every endpoint that calls `load_results_raw()`. Each gets a `run_id: str | None = None` parameter and passes it through:

- `dashboard_overview` (line ~624)
- `chart_rankings` (line ~664)
- `chart_completion` (line ~674)
- `chart_radar` (line ~684)
- `chart_efficiency` (line ~705)
- `chart_story_comparison` (line ~717)
- `chart_dimension_comparison` (line ~736)
- `scoring_matrix` (line ~748)
- `get_story_score` (line ~786)
- `framework_metrics_summary` (line ~873)
- `dashboard_story_detail` (line ~888)
- `scoring_submit` (line ~900)
- `agent_communication_graph` (line ~937)

For each: add `run_id: str | None = None` to the function signature and change `load_results_raw()` to `load_results_raw(run_id)`.

- [ ] **Step 4: Verify the API server starts**

Run: `uv run python -c "from desmet.webui.api import app; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/desmet/webui/api.py
git commit -m "feat: add result-runs API and run_id filtering to dashboard endpoints"
```

---

### Task 10: Frontend — RunSelector component and wiring

**Files:**
- Modify: `src/desmet/webui/frontend/src/lib/stores.ts`
- Modify: `src/desmet/webui/frontend/src/lib/api.ts`
- Create: `src/desmet/webui/frontend/src/lib/components/RunSelector.svelte`
- Modify: `src/desmet/webui/frontend/src/lib/pages/ResultsOverview.svelte`

- [ ] **Step 1: Add selectedResultsRunId store**

In `src/desmet/webui/frontend/src/lib/stores.ts`, add:

```typescript
/** Selected run for Results section — null = latest */
export const selectedResultsRunId = writable<string | null>(null)
```

- [ ] **Step 2: Add fetchResultRuns to api.ts**

In `src/desmet/webui/frontend/src/lib/api.ts`, add the type and function:

```typescript
export interface ResultRun {
  run_id: string;
  started_at: string | null;
  finished_at: string | null;
  model: string | null;
  platforms_filter: string[] | null;
  note: string | null;
}

export const fetchResultRuns = () =>
  request<{ runs: ResultRun[] }>('/api/result-runs');
```

- [ ] **Step 3: Create RunSelector.svelte**

```svelte
<!-- src/desmet/webui/frontend/src/lib/components/RunSelector.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { selectedResultsRunId } from '../stores';
  import { fetchResultRuns } from '../api';
  import type { ResultRun } from '../api';

  let runs = $state<ResultRun[]>([]);
  let selected = $state<string>('latest');

  selectedResultsRunId.subscribe((v) => {
    selected = v ?? 'latest';
  });

  onMount(async () => {
    try {
      const res = await fetchResultRuns();
      runs = res.runs;
    } catch {
      runs = [];
    }
  });

  function onChange(e: Event) {
    const val = (e.target as HTMLSelectElement).value;
    selectedResultsRunId.set(val === 'latest' ? null : val);
  }

  function formatDate(iso: string | null): string {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
</script>

{#if runs.length > 0}
  <div class="run-selector">
    <label for="run-select">Run:</label>
    <select id="run-select" value={selected} onchange={onChange}>
      <option value="latest">Latest</option>
      {#each runs as run}
        <option value={run.run_id}>
          {formatDate(run.started_at)}{run.model ? ` · ${run.model}` : ''}{run.note ? ` — ${run.note}` : ''}
        </option>
      {/each}
    </select>
  </div>
{/if}

<style>
  .run-selector {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--text-1);
  }

  label {
    font-weight: 500;
    color: var(--text-2);
  }

  select {
    background: var(--bg-1);
    color: var(--text-0);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 13px;
    cursor: pointer;
    min-width: 200px;
  }

  select:hover {
    border-color: var(--text-2);
  }
</style>
```

- [ ] **Step 4: Mount RunSelector in ResultsOverview**

In `src/desmet/webui/frontend/src/lib/pages/ResultsOverview.svelte`, add the import:

```typescript
import RunSelector from '../components/RunSelector.svelte';
```

Then add `<RunSelector />` at the top of the page content (just inside the first content container, before the heading or stats section).

- [ ] **Step 5: Thread run_id through fetchOverview**

In `src/desmet/webui/frontend/src/lib/api.ts`, update `fetchOverview`:

```typescript
export const fetchOverview = (runId?: string | null) => {
  const qs = runId ? `?run_id=${runId}` : '';
  return request<OverviewData>(`/api/dashboard/overview${qs}`);
};
```

In `ResultsOverview.svelte`, update the `onMount` to subscribe to the store:

```typescript
import { selectedResultsRunId } from '../stores';

let currentRunId = $state<string | null>(null);
selectedResultsRunId.subscribe((v) => (currentRunId = v));

// Replace onMount fetch with $effect
$effect(() => {
  const rid = currentRunId;
  fetchOverview(rid).then((d) => (data = d));
  fetchFrameworkMetrics().then((fm) => (fmPlatforms = fm.platforms)).catch(() => (fmPlatforms = []));
});
```

Remove the `onMount` block since `$effect` handles reactivity.

- [ ] **Step 6: Build the frontend**

Run: `cd src/desmet/webui/frontend && bun run build`
Expected: build succeeds

- [ ] **Step 7: Commit**

```bash
git add src/desmet/webui/frontend/src/lib/stores.ts \
       src/desmet/webui/frontend/src/lib/api.ts \
       src/desmet/webui/frontend/src/lib/components/RunSelector.svelte \
       src/desmet/webui/frontend/src/lib/pages/ResultsOverview.svelte
git commit -m "feat: add run selector dropdown to Results section"
```

---

### Task 11: Add desmet.duckdb to .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add DuckDB file pattern to .gitignore**

Add to `.gitignore`:

```
# DuckDB result store
results/*.duckdb
results/*.duckdb.wal
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore DuckDB result store files"
```
