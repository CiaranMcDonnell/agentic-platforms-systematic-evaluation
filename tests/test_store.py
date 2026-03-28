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
