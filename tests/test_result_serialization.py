"""Tests for StageResult JSON serialization."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from desmet.harness.results import (
    CodeResult,
    DeployResult,
    RequirementsResult,
    StageResult,
    TestResult,
)
from desmet.harness.trace import AgentTrace, AgentMessage, ToolCall


class TestStageResultSerialization:
    def test_to_dict_returns_dict(self):
        r = StageResult(platform_id="crewai", stage_name="codegen", success=True)
        d = r.to_dict()
        assert isinstance(d, dict)
        assert d["platform_id"] == "crewai"
        assert d["success"] is True

    def test_to_dict_is_json_serializable(self):
        r = StageResult(
            platform_id="crewai", stage_name="codegen",
            start_time=datetime.now(timezone.utc),
        )
        json_str = json.dumps(r.to_dict())
        assert isinstance(json_str, str)

    def test_to_dict_includes_trace(self):
        trace = AgentTrace(total_iterations=5, total_tokens_input=100)
        r = StageResult(platform_id="x", stage_name="y", trace=trace)
        d = r.to_dict()
        assert d["trace"]["total_iterations"] == 5
        assert d["trace"]["total_tokens_input"] == 100

    def test_to_dict_includes_subclass_fields(self):
        r = TestResult(
            platform_id="x", stage_name="testing",
            tests_run=10, tests_passed=8, tests_failed=2,
        )
        d = r.to_dict()
        assert d["tests_run"] == 10
        assert d["tests_passed"] == 8
        assert d["_type"] == "TestResult"

    def test_from_dict_roundtrip(self):
        r = CodeResult(
            platform_id="langgraph", stage_name="codegen",
            success=True, iterations=12,
            output_files=["main.py", "utils.py"],
        )
        d = r.to_dict()
        json_str = json.dumps(d)
        restored = StageResult.from_dict(json.loads(json_str))
        assert isinstance(restored, CodeResult)
        assert restored.platform_id == "langgraph"
        assert restored.output_files == ["main.py", "utils.py"]
        assert restored.iterations == 12

    def test_from_dict_restores_trace(self):
        trace = AgentTrace(
            total_iterations=3,
            messages=[
                AgentMessage(role="user", content="hello", timestamp=datetime.now(timezone.utc)),
            ],
            tool_calls=[
                ToolCall(
                    tool_name="read_file", arguments={"path": "x.py"},
                    result="ok", timestamp=datetime.now(timezone.utc),
                    duration_ms=50.0, success=True,
                ),
            ],
        )
        r = StageResult(platform_id="x", stage_name="y", trace=trace)
        d = r.to_dict()
        restored = StageResult.from_dict(json.loads(json.dumps(d)))
        assert restored.trace.total_iterations == 3
        assert len(restored.trace.messages) == 1
        assert len(restored.trace.tool_calls) == 1
        assert restored.trace.tool_calls[0].tool_name == "read_file"


class TestDeployResultSerialization:
    def test_roundtrip(self):
        r = DeployResult(
            platform_id="x", stage_name="deploy",
            build_success=True, deployment_ready=True,
        )
        d = r.to_dict()
        restored = StageResult.from_dict(json.loads(json.dumps(d)))
        assert isinstance(restored, DeployResult)
        assert restored.build_success is True


def test_agent_trace_has_metadata_field():
    """AgentTrace must have a mutable metadata dict for adapter annotations like plan_source."""
    from desmet.harness.trace import AgentTrace
    t = AgentTrace()
    assert hasattr(t, "metadata")
    assert t.metadata == {}
    t.metadata["plan_source"] = "structured"
    assert t.metadata == {"plan_source": "structured"}
    # Instances must get independent dicts (default_factory, not shared default).
    t2 = AgentTrace()
    assert t2.metadata == {}


class TestRequirementsResultSerialization:
    def test_roundtrip(self):
        r = RequirementsResult(
            platform_id="x", stage_name="requirements",
            functional_requirements=[{"id": "FR1", "desc": "Login"}],
        )
        d = r.to_dict()
        restored = StageResult.from_dict(json.loads(json.dumps(d)))
        assert isinstance(restored, RequirementsResult)
        assert restored.functional_requirements[0]["id"] == "FR1"
