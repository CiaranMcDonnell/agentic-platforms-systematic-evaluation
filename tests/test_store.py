"""Tests for the DuckDB result store."""

import duckdb
import pytest
from datetime import datetime, timezone
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
        r1 = store.create_run()
        r2 = store.create_run()
        result = self._make_story_result()
        metrics = self._make_story_metrics(result)

        store.save_execution(r1, result, metrics)

        assert len(store.get_executions(r1)) == 1
        assert len(store.get_executions(r2)) == 0


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
