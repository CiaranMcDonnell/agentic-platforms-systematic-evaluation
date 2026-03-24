"""Tests for the harness base data models."""

import pytest

from desmet.harness.context import StageContext
from desmet.harness.results import (
    CodeResult,
    DeployResult,
    RequirementsResult,
    StageResult,
    TestResult,
    UMLDiagram,
)
from desmet.harness.story import DifficultyLevel, UserStory


@pytest.fixture
def sample_story():
    return UserStory(
        id="US-001",
        title="Test Story",
        description="A test story",
        difficulty=DifficultyLevel.BASIC,
        category="code_generation",
        prompt="Implement a hello world function",
    )


@pytest.fixture
def sample_context(sample_story, tmp_path):
    return StageContext(
        story=sample_story,
        workspace=tmp_path,
        time_budget_seconds=300,
        max_iterations=25,
    )


class TestStageContext:
    def test_create_with_story(self, sample_context, sample_story):
        assert sample_context.story == sample_story
        assert sample_context.artifacts == {}

    def test_add_artifacts(self, sample_context):
        reqs = RequirementsResult(
            platform_id="langgraph",
            stage_name="requirements",
            functional_requirements=[{"id": "FR-1", "title": "Test"}],
        )
        sample_context.add_artifacts("requirements", reqs)
        assert "requirements" in sample_context.artifacts
        assert sample_context.artifacts["requirements"] is reqs

    def test_get_prior_result(self, sample_context):
        reqs = RequirementsResult(
            platform_id="langgraph",
            stage_name="requirements",
            functional_requirements=[{"id": "FR-1", "title": "Test"}],
        )
        sample_context.add_artifacts("requirements", reqs)
        assert sample_context.get_prior_result("requirements") is reqs
        assert sample_context.get_prior_result("codegen") is None


class TestStageResult:
    def test_stage_result_defaults(self):
        result = StageResult(platform_id="langgraph", stage_name="test")
        assert result.success is False
        assert result.wall_clock_seconds == 0.0
        assert result.trace is not None

    def test_stage_result_duration(self):
        result = StageResult(
            platform_id="langgraph",
            stage_name="test",
            wall_clock_seconds=42.5,
        )
        assert result.wall_clock_seconds == 42.5


class TestRequirementsResult:
    def test_create_with_requirements(self):
        result = RequirementsResult(
            platform_id="langgraph",
            stage_name="requirements",
            success=True,
            functional_requirements=[{"id": "FR-1", "title": "Login"}],
            non_functional_requirements=[{"id": "NFR-1", "title": "Performance"}],
            use_cases=[{"id": "UC-1", "name": "User Login"}],
            uml_diagrams=[
                UMLDiagram(diagram_type="class", title="Domain Model", content="@startuml\n@enduml")
            ],
        )
        assert len(result.functional_requirements) == 1
        assert len(result.uml_diagrams) == 1
        assert result.uml_diagrams[0].diagram_type == "class"


class TestCodeResult:
    def test_create_with_output(self):
        result = CodeResult(
            platform_id="langgraph",
            stage_name="codegen",
            success=True,
            output_files=["src/main.py"],
            git_diff="diff --git a/src/main.py",
        )
        assert len(result.output_files) == 1
        assert result.git_diff is not None


class TestTestResult:
    def test_create_with_test_metrics(self):
        result = TestResult(
            platform_id="langgraph",
            stage_name="testing",
            success=True,
            test_files=["tests/test_main.py"],
            tests_run=10,
            tests_passed=9,
            tests_failed=1,
            coverage_percentage=85.0,
        )
        assert result.tests_run == 10
        assert result.test_pass_rate == 90.0


class TestDeployResult:
    def test_create_with_deploy_info(self):
        result = DeployResult(
            platform_id="langgraph",
            stage_name="deploy",
            success=True,
            build_success=True,
            deployment_ready=True,
            build_log="Build completed successfully",
        )
        assert result.build_success is True
        assert result.deployment_ready is True
