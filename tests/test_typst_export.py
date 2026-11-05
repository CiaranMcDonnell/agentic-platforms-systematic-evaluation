"""Tests for the Typst export helpers."""

import json

import pandas as pd

from desmet.harness.typst_export import _stage_success


def _write_stages(path, codegen_ok):
    path.write_text(
        json.dumps(
            {"stages": {"requirements": {"success": True}, "codegen": {"success": codegen_ok}}}
        ),
        encoding="utf-8",
    )


def test_stage_success_uses_row_not_newest_file(tmp_path):
    story_dir = tmp_path / "p" / "US-001"
    story_dir.mkdir(parents=True)
    older = story_dir / "a_stages.json"
    newer = story_dir / "z_stages.json"
    _write_stages(older, codegen_ok=False)
    _write_stages(newer, codegen_ok=True)

    row = pd.Series({"execution_id": "e1", "trace_path": str(older)})
    empty = pd.DataFrame(columns=["execution_id", "stage_name", "success"])
    assert _stage_success(row, empty, tmp_path) == {"requirements": True, "codegen": False}


def test_stage_success_prefers_stage_rows(tmp_path):
    row = pd.Series({"execution_id": "e1", "trace_path": None})
    stage_df = pd.DataFrame(
        [
            {"execution_id": "e1", "stage_name": "requirements", "success": True},
            {"execution_id": "e1", "stage_name": "codegen", "success": False},
            {"execution_id": "other", "stage_name": "testing", "success": True},
        ]
    )
    assert _stage_success(row, stage_df, tmp_path) == {"requirements": True, "codegen": False}


def test_stage_success_none_without_rows_or_trace(tmp_path):
    row = pd.Series({"execution_id": "e1", "trace_path": None})
    assert _stage_success(row, pd.DataFrame(), tmp_path) is None
