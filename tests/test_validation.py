"""Tests for shared workspace validation."""
import pytest
from desmet.adapters._validation import validate_workspace


class TestValidateWorkspace:
    def test_requirements_passes_with_keywords(self, tmp_path):
        design = tmp_path / "docs" / "design"
        design.mkdir(parents=True)
        (design / "requirements.md").write_text(
            "## Functional requirements\n"
            "## Non-functional requirements\n"
            "## Acceptance criteria\n"
            "## Constraint: must be fast\n"
        )
        assert validate_workspace("requirements", str(tmp_path)) is True

    def test_requirements_fails_no_file(self, tmp_path):
        assert validate_workspace("requirements", str(tmp_path)) is False

    def test_requirements_fails_wrong_location(self, tmp_path):
        """Requirements doc outside docs/design/ should not pass."""
        (tmp_path / "requirements.md").write_text(
            "## Functional requirements\n"
            "## Non-functional requirements\n"
        )
        assert validate_workspace("requirements", str(tmp_path)) is False

    def test_requirements_fails_missing_keywords(self, tmp_path):
        design = tmp_path / "docs" / "design"
        design.mkdir(parents=True)
        (design / "requirements.md").write_text("just some text")
        assert validate_workspace("requirements", str(tmp_path)) is False

    def test_codegen_passes_with_valid_python(self, tmp_path):
        (tmp_path / "app.py").write_text("def hello(): return 'hi'\n")
        assert validate_workspace("codegen", str(tmp_path)) is True

    def test_codegen_fails_no_python_file(self, tmp_path):
        assert validate_workspace("codegen", str(tmp_path)) is False

    def test_testing_passes_with_test_file(self, tmp_path):
        (tmp_path / "test_app.py").write_text("def test_hello(): assert True\n")
        assert validate_workspace("testing", str(tmp_path)) is True

    def test_testing_fails_no_test_functions(self, tmp_path):
        (tmp_path / "test_app.py").write_text("def helper(): pass\n")
        assert validate_workspace("testing", str(tmp_path)) is False

    def test_deploy_passes_when_both_files_present_with_port_var(self, tmp_path):
        (tmp_path / "Dockerfile").write_text(
            "FROM python:3.11-slim\n"
            "COPY . /app\n"
            "WORKDIR /app\n"
            "CMD [\"uvicorn\", \"app.main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]\n"
        )
        (tmp_path / "docker-compose.yaml").write_text(
            "services:\n"
            "  app:\n"
            "    build: .\n"
            "    ports:\n"
            "      - \"${PORT}:8000\"\n"
        )
        assert validate_workspace("deploy", str(tmp_path)) is True

    def test_deploy_fails_when_dockerfile_missing(self, tmp_path):
        (tmp_path / "docker-compose.yaml").write_text(
            "services:\n"
            "  app:\n"
            "    build: .\n"
            "    ports:\n"
            "      - \"${PORT}:8000\"\n"
        )
        # No Dockerfile written.
        assert validate_workspace("deploy", str(tmp_path)) is False

    def test_deploy_fails_when_compose_missing(self, tmp_path):
        (tmp_path / "Dockerfile").write_text("FROM python:3.11-slim\n")
        # No docker-compose.yaml written.
        assert validate_workspace("deploy", str(tmp_path)) is False

    def test_deploy_fails_when_compose_hardcodes_port(self, tmp_path):
        (tmp_path / "Dockerfile").write_text("FROM python:3.11-slim\n")
        (tmp_path / "docker-compose.yaml").write_text(
            "services:\n"
            "  app:\n"
            "    build: .\n"
            "    ports:\n"
            "      - \"8001:8000\"\n"  # hardcoded host port — no ${PORT}
        )
        assert validate_workspace("deploy", str(tmp_path)) is False

    def test_deploy_fails_with_neither_file(self, tmp_path):
        # Empty workspace — both files missing.
        assert validate_workspace("deploy", str(tmp_path)) is False

    def test_requirements_passes_in_subdirectory(self, tmp_path):
        docs = tmp_path / "docs" / "design"
        docs.mkdir(parents=True)
        (docs / "requirements.md").write_text(
            "## Functional requirements\n"
            "## Non-functional requirements\n"
            "## Acceptance criteria\n"
            "## Constraint: must be fast\n"
        )
        assert validate_workspace("requirements", str(tmp_path)) is True

    def test_codegen_passes_in_subdirectory(self, tmp_path):
        pkg = tmp_path / "app"
        pkg.mkdir()
        (pkg / "main.py").write_text("def hello(): return 'hi'\n")
        assert validate_workspace("codegen", str(tmp_path)) is True

    def test_testing_passes_in_subdirectory(self, tmp_path):
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_app.py").write_text("def test_hello(): assert True\n")
        assert validate_workspace("testing", str(tmp_path)) is True

    def test_unknown_stage_returns_false(self, tmp_path):
        assert validate_workspace("unknown_stage", str(tmp_path)) is False
