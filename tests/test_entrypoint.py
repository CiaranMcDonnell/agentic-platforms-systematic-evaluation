"""Tests for the container adapter entrypoint."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from desmet.harness.context import StageContext
from desmet.harness.story import UserStory, DifficultyLevel


def _make_context(tmp_path: Path) -> StageContext:
    story = UserStory(
        id="test_story", title="Test", description="Test",
        difficulty=DifficultyLevel.BASIC, category="test",
        prompt="Build something",
    )
    return StageContext(
        story=story, workspace=tmp_path, platform_id="crewai",
        max_iterations=5,
    )


class TestEntrypointModule:
    def test_module_is_importable(self):
        import desmet.harness.entrypoint
        assert hasattr(desmet.harness.entrypoint, "run_entrypoint")

    def test_run_entrypoint_signature(self):
        import inspect
        from desmet.harness.entrypoint import run_entrypoint
        sig = inspect.signature(run_entrypoint)
        params = list(sig.parameters.keys())
        assert "context_path" in params

    def test_writes_context_and_reads_back(self, tmp_path):
        """Test that a context file can be written and parsed."""
        ctx = _make_context(tmp_path)
        context_path = tmp_path / ".desmet-context.json"
        with open(context_path, "w") as f:
            json.dump(ctx.to_dict(), f)

        loaded = json.loads(context_path.read_text())
        assert loaded["platform_id"] == "crewai"
        assert loaded["story"]["id"] == "test_story"


@pytest.fixture(autouse=True)
def _reset_otel_context():
    """Each trace-related test runs with a clean OTel context.

    OTel uses a contextvar that survives across tests in the same
    process; without resetting we get cross-test bleed where one test's
    `attach(extract(...))` is still active when the next test asserts
    "no parent context".
    """
    from opentelemetry.context import attach, Context
    token = attach(Context())
    yield
    from opentelemetry.context import detach
    detach(token)


class TestTraceContextPropagation:
    """The container entrypoint must adopt the host's W3C traceparent so
    Langfuse spans created inside the container roll up under the host's
    stage span instead of starting a new root trace."""

    HOST_TRACE_ID_HEX = "6154e51fdfca76491a23c324443f84ac"
    HOST_TRACEPARENT = f"00-{HOST_TRACE_ID_HEX}-e36d7c06fbb2a3f0-01"

    def test_attach_parent_trace_context_extracts_traceparent(self, monkeypatch):
        """When TRACEPARENT is set, child spans inherit the parent trace_id."""
        from desmet.harness.entrypoint import _attach_parent_trace_context
        from opentelemetry import trace as otel_trace
        from opentelemetry.sdk.trace import TracerProvider

        monkeypatch.setenv("TRACEPARENT", self.HOST_TRACEPARENT)
        otel_trace.set_tracer_provider(TracerProvider())

        _attach_parent_trace_context()

        tracer = otel_trace.get_tracer("test")
        with tracer.start_as_current_span("child") as span:
            tid = format(span.get_span_context().trace_id, "032x")
        assert tid == self.HOST_TRACE_ID_HEX, (
            f"child span should inherit host trace_id but got {tid}"
        )

    def test_attach_parent_trace_context_noop_without_env(self, monkeypatch):
        """No TRACEPARENT env var → helper is a no-op (no exception)."""
        from desmet.harness.entrypoint import _attach_parent_trace_context

        monkeypatch.delenv("TRACEPARENT", raising=False)
        _attach_parent_trace_context()  # must not raise

    def test_try_init_langfuse_swallows_missing_credentials(self, monkeypatch):
        """A missing LANGFUSE_*_KEY must NOT abort stage execution."""
        from desmet.harness.entrypoint import _try_init_langfuse

        monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
        monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
        # Reset cached client so init_langfuse re-evaluates env
        import desmet.observability as obs
        monkeypatch.setattr(obs, "_langfuse_client", None)

        _try_init_langfuse()  # must not raise


class TestHostSidePropagationCapture:
    """The host runner must serialise its current OTel span as a
    TRACEPARENT env var when invoking docker exec, so the container
    can pick it up via TestTraceContextPropagation above."""

    def test_capture_returns_empty_outside_span(self):
        from desmet.harness.container_runner import _current_trace_propagation_env

        # No active OTel span: must return [] (backward compatible — old
        # callers like dry-run scripts must keep working).
        flags = _current_trace_propagation_env()
        assert flags == []

    def test_capture_returns_traceparent_inside_span(self):
        from desmet.harness.container_runner import _current_trace_propagation_env
        from opentelemetry import trace as otel_trace
        from opentelemetry.sdk.trace import TracerProvider

        otel_trace.set_tracer_provider(TracerProvider())
        tracer = otel_trace.get_tracer("test")
        with tracer.start_as_current_span("host-stage") as span:
            expected_tid = format(span.get_span_context().trace_id, "032x")
            flags = _current_trace_propagation_env()

        assert len(flags) >= 2
        assert flags[0] == "-e"
        assert flags[1].startswith("TRACEPARENT=00-")
        assert expected_tid in flags[1]
