"""Tests for the DuckDB result store."""

import json as json_mod

import duckdb
import pandas as pd
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
        assert version[0] == 6


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


class TestRecomputeUsesStageOutcome:
    def _save(self, store: ResultStore, run_id: str, stage_success: bool) -> None:
        from desmet.harness.metrics import StoryMetrics
        from desmet.harness.results import StageResult
        from desmet.harness.story import StoryResult, StoryStatus

        result = StoryResult(
            story_id="US-001",
            platform_id="p",
            execution_id=f"e-{stage_success}",
            status=StoryStatus.COMPLETED,
        )
        result.raw_result = {
            "codegen": StageResult(platform_id="p", stage_name="codegen", success=stage_success)
        }
        store.save_execution(run_id, result, StoryMetrics.from_story_result(result))

    @pytest.mark.parametrize("stage_success", [True, False])
    def test_recompute_respects_failed_stages(self, store: ResultStore, stage_success: bool):
        from desmet.harness.metrics import recompute_platform_likert_from_store

        run_id = store.create_run()
        self._save(store, run_id, stage_success)
        assert bool(store.get_executions(run_id)["stages_passed"].iloc[0]) is stage_success

        scores = recompute_platform_likert_from_store(store, run_id, "p", {"US-001": 600})
        # Unscored pipeline rubric -> completion ratio alone: 1.0 -> 5, 0.0 -> 1
        assert scores["score_pipeline_completeness"] == (5.0 if stage_success else 1.0)


_V5_CREATE_SQL = """\nCREATE TABLE IF NOT EXISTS store_meta (
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
    resource_net_tx_bytes       BIGINT,
    stages_passed       BOOLEAN,
    tests_run           INTEGER,
    tests_passed        INTEGER,
    tests_failed        INTEGER,
    pytest_exit_code    INTEGER,
    artifact_path       VARCHAR,
    criteria_results    VARCHAR,
    deploy_healthy      BOOLEAN
);
"""


class TestSchemaV6:
    def test_v5_db_migrates_to_v6(self, tmp_path: Path):
        db = tmp_path / "d.duckdb"
        conn = duckdb.connect(str(db))
        conn.execute(_V5_CREATE_SQL)
        conn.execute("INSERT INTO store_meta VALUES (5)")
        conn.execute("INSERT INTO runs (run_id, started_at) VALUES ('r1', now())")
        conn.execute(
            "INSERT INTO executions (execution_id, run_id, platform_id, story_id, status) "
            "VALUES ('e1', 'r1', 'p', 'US-001', 'completed')"
        )
        conn.close()

        store = ResultStore(db)
        assert store._conn.execute("SELECT version FROM store_meta").fetchone()[0] == 6
        df = store.get_executions("r1")
        assert pd.isna(df.loc[0, "execution_mode"])
        assert pd.isna(df.loc[0, "reported_tests_run"])
        assert store.get_stage_executions("r1").empty
        assert pd.isna(store.get_run("r1").iloc[0]["git_sha"])
        store.close()

    def test_save_execution_writes_stage_rows_and_new_fields(self, store: ResultStore):
        from desmet.harness.metrics import StoryMetrics
        from desmet.harness.results import RequirementsResult, StageResult
        from desmet.harness.story import StoryResult, StoryStatus

        run_id = store.create_run()
        result = StoryResult(
            story_id="US-001",
            platform_id="p",
            execution_id="e1",
            status=StoryStatus.COMPLETED,
            execution_mode="container",
            repeat_index=2,
            reported_tests_run=5,
            reported_tests_passed=4,
            reported_tests_failed=1,
        )
        result.raw_result = {
            "requirements": RequirementsResult(
                platform_id="p", stage_name="requirements", success=True, iterations=3
            ),
            "codegen": StageResult(
                platform_id="p", stage_name="codegen", success=False, error_message="boom"
            ),
        }
        store.save_execution(
            run_id, result, StoryMetrics.from_story_result(result, time_budget_seconds=600)
        )
        row = store.get_executions(run_id).iloc[0]
        assert row["repeat_index"] == 2 and row["execution_mode"] == "container"
        assert row["reported_tests_passed"] == 4
        stages = store.get_stage_executions(run_id).set_index("stage_name")
        assert bool(stages.loc["requirements", "success"]) is True
        assert stages.loc["requirements", "iterations"] == 3
        assert stages.loc["codegen", "error_message"] == "boom"

    def test_non_dict_raw_result_writes_no_stage_rows(self, store: ResultStore):
        from desmet.harness.metrics import StoryMetrics
        from desmet.harness.story import StoryResult, StoryStatus

        run_id = store.create_run()
        result = StoryResult(
            story_id="US-001", platform_id="p", execution_id="e1", status=StoryStatus.COMPLETED
        )
        result.raw_result = "dry-run"
        store.save_execution(run_id, result, StoryMetrics.from_story_result(result))
        assert store.get_stage_executions(run_id).empty

    def test_update_run_manifest_ignores_unknown_keys(self, store: ResultStore):
        run_id = store.create_run()
        store.update_run_manifest(
            run_id, {"git_sha": "abc", "image_digests": {"p": "sha256:1"}, "bogus": 1}
        )
        run = store.get_run(run_id).iloc[0]
        assert run["git_sha"] == "abc"
        assert json_mod.loads(run["image_digests"]) == {"p": "sha256:1"}


class TestRepeatScopedRubric:
    def _save_repeat(self, store, run_id, repeat_index):
        from desmet.harness.metrics import StoryMetrics
        from desmet.harness.story import StoryResult, StoryStatus

        result = StoryResult(
            story_id="US-001",
            platform_id="p",
            execution_id=f"p_US-001_r{repeat_index}",
            status=StoryStatus.COMPLETED,
            start_time=datetime(2026, 3, 28, 9, 19, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 28, 9, 22, 0, tzinfo=timezone.utc),
            wall_clock_seconds=10.0,
            repeat_index=repeat_index,
        )
        store.save_execution(
            run_id, result, StoryMetrics.from_story_result(result, time_budget_seconds=300.0)
        )

    def test_rubric_update_scoped_to_repeat(self, store: ResultStore):
        run_id = store.create_run()
        self._save_repeat(store, run_id, 0)
        self._save_repeat(store, run_id, 1)

        assert store.update_rubric_scores_by_story(
            run_id, "p", "US-001", {"autonomy": 2.0}, repeat_index=1
        )
        df = store.get_executions(run_id).set_index("repeat_index")
        assert pd.isna(df.loc[0, "rubric_autonomy"])
        assert df.loc[1, "rubric_autonomy"] == 2.0

    def test_repeat_indices(self, store: ResultStore):
        run_id = store.create_run()
        assert store.repeat_indices(run_id, "p", "US-001") == []
        self._save_repeat(store, run_id, 1)
        self._save_repeat(store, run_id, 0)
        assert store.repeat_indices(run_id, "p", "US-001") == [0, 1]
