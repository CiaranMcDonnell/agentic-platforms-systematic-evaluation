"""Web runs: code frameworks always run in their platform container."""

from types import SimpleNamespace

import pytest

from desmet.harness import container_runner
from desmet.harness.adapter import ContainerOnlyAdapter
from desmet.webui import api


@pytest.fixture
def captured_runner(monkeypatch, tmp_path):
    """Run api._execute_run up to the EvaluationRunner and capture it."""
    captured = {}

    class FakeRunner:
        def __init__(self, config, platforms, **kw):
            captured["config"] = config
            captured["platforms"] = platforms

        async def run_full_evaluation(self):
            return {}

    monkeypatch.setattr(api, "EvaluationRunner", FakeRunner)
    monkeypatch.setattr("desmet.observability.init_langfuse", lambda: None)
    monkeypatch.setattr("desmet.observability.start_session", lambda label=None: None)
    monkeypatch.setattr(
        api, "load_all_stories", lambda difficulty=None: [SimpleNamespace(id="US-001")]
    )
    monkeypatch.setattr(api, "resolve_baseline_dir", lambda: tmp_path)
    # A host with no platform images and every SDK importable: the old
    # code fell back to running the framework in-process on the host.
    monkeypatch.setattr(container_runner, "has_image", lambda pid: False)
    monkeypatch.setattr(api, "get_adapter", lambda pid: object())
    return captured


async def _run(platforms):
    run = api.RunState("r-test", {})
    api._runs[run.run_id] = run
    try:
        await api._execute_run(run, api.RunRequest(platforms=platforms))
    finally:
        api._runs.pop(run.run_id, None)
    return run


async def test_code_framework_without_image_uses_container(captured_runner):
    run = await _run(["langgraph", "flowise"])
    assert run.status == "completed", run.error
    platforms = captured_runner["platforms"]
    modes = captured_runner["config"].platform_execution_modes
    assert isinstance(platforms["langgraph"], ContainerOnlyAdapter)
    assert modes["langgraph"] == "container"
    # Visual platforms still drive their external service in-process.
    assert modes["flowise"] == "in_process"
