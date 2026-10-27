"""Shared pytest fixtures."""
from types import SimpleNamespace

import pytest

from desmet.harness import container_runner
from desmet.harness.results import (
    CodeResult,
    DeployResult,
    RequirementsResult,
    TestResult,
)

_STAGE_RESULTS = {
    "requirements": RequirementsResult,
    "codegen": CodeResult,
    "testing": TestResult,
    "deploy": DeployResult,
}


@pytest.fixture
def fake_containers(monkeypatch):
    """Replace every Docker-touching container_runner call with a recorder."""
    state = SimpleNamespace(
        build_ok=True,
        build_calls=[],
        run_stage_calls=[],
        stop_calls=[],
        digest="sha256:fake-image-digest",
    )

    def build_image(platform_id, *args, **kwargs):
        state.build_calls.append(platform_id)
        return state.build_ok

    async def run_stage_in_container(platform_id, stage_name, *args, **kwargs):
        state.run_stage_calls.append((platform_id, stage_name))
        return _STAGE_RESULTS[stage_name](
            platform_id=platform_id, stage_name=stage_name, success=True
        )

    monkeypatch.setattr(container_runner, "build_image", build_image)
    monkeypatch.setattr(container_runner, "has_image", lambda platform_id: state.build_ok)
    monkeypatch.setattr(container_runner, "run_stage_in_container", run_stage_in_container)
    monkeypatch.setattr(container_runner, "image_digest", lambda platform_id: state.digest)
    monkeypatch.setattr(
        container_runner,
        "stop_container",
        lambda platform_id, story_id: state.stop_calls.append((platform_id, story_id)),
    )
    return state
