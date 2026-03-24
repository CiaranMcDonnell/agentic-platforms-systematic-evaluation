"""Tests for shared workspace validation."""
import pytest
from desmet.adapters._validation import validate_workspace


class TestValidateWorkspace:
    def test_requirements_passes_with_keywords(self, tmp_path):
        (tmp_path / "requirements.md").write_text(
            "## Functional requirements\n"
            "## Non-functional requirements\n"
            "## Acceptance criteria\n"
            "## Constraint: must be fast\n"
        )
        assert validate_workspace("requirements", str(tmp_path)) is True

    def test_requirements_fails_no_file(self, tmp_path):
        assert validate_workspace("requirements", str(tmp_path)) is False

    def test_requirements_fails_missing_keywords(self, tmp_path):
        (tmp_path / "requirements.md").write_text("just some text")
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

    def test_deploy_passes_with_compose_file(self, tmp_path):
        (tmp_path / "docker-compose.yaml").write_text("version: '3'\n")
        assert validate_workspace("deploy", str(tmp_path)) is True

    def test_deploy_fails_no_compose(self, tmp_path):
        assert validate_workspace("deploy", str(tmp_path)) is False

    def test_unknown_stage_returns_false(self, tmp_path):
        assert validate_workspace("unknown_stage", str(tmp_path)) is False
