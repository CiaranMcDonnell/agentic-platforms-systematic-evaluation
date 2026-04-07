"""Tests for the shared adapter tool factory."""


import pytest

from desmet.adapters._tools import (
    AVAILABLE_TOOLS,
    ToolFormat,
    _check_loop,
    _extract_target,
    _safe_resolve,
    create_tools,
    reset_loop_tracker,
)


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "hello.py").write_text("print('hello')")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "data.txt").write_text("some data")
    return tmp_path


@pytest.fixture(autouse=True)
def _reset_loops():
    """Ensure loop-detection state is clean between tests."""
    reset_loop_tracker()
    yield
    reset_loop_tracker()


class TestExtractTarget:
    def test_read_file_target(self):
        assert _extract_target("read_file", "docs/design/spec.md") == "docs/design/spec.md"

    def test_write_file_target(self):
        assert _extract_target("write_file", "src/main.py") == "src/main.py"

    def test_list_directory_returns_none(self):
        # Directories aren't work targets — ignore to avoid false positives.
        assert _extract_target("list_directory", "docs") is None

    def test_shell_command_extracts_mermaid_path(self):
        cmd = "mmdc -p ~/.config/puppeteer.json -i docs/design/use_case.mermaid -o docs/design/use_case.svg"
        # First match — the .mermaid file is found first
        assert _extract_target("execute_shell", cmd) == "docs/design/use_case.mermaid"

    def test_shell_command_no_file_returns_none(self):
        assert _extract_target("execute_shell", "pwd") is None
        assert _extract_target("execute_shell", "ls -la") is None


class TestCrossToolLoopDetection:
    def test_fires_on_six_cross_tool_ops_on_same_file(self, workspace):
        ws = str(workspace)
        target = "docs/design/use_case.mermaid"
        # Simulate the CrewAI loop pattern: write → shell → read → write → shell → read
        results = [
            _check_loop(ws, "write_file", target),
            _check_loop(ws, "execute_shell", f"mmdc -i {target}"),
            _check_loop(ws, "read_file", target),
            _check_loop(ws, "write_file", target),
            _check_loop(ws, "execute_shell", f"mmdc -i {target}"),
            _check_loop(ws, "read_file", target),
        ]
        # First 5 should be None (still under threshold)
        assert all(r is None for r in results[:5])
        # 6th call triggers the cross-tool loop detector
        assert results[5] is not None
        assert "LOOP DETECTED" in results[5]
        assert target in results[5]

    def test_does_not_fire_on_different_files(self, workspace):
        ws = str(workspace)
        # Working on different files across tools — legitimate progress
        results = [
            _check_loop(ws, "write_file", "a.md"),
            _check_loop(ws, "execute_shell", "mmdc -i a.mermaid"),
            _check_loop(ws, "write_file", "b.md"),
            _check_loop(ws, "execute_shell", "mmdc -i b.mermaid"),
            _check_loop(ws, "write_file", "c.md"),
            _check_loop(ws, "execute_shell", "mmdc -i c.mermaid"),
        ]
        assert all(r is None for r in results), f"Expected no loop, got: {results}"

    def test_reset_clears_cross_tool_history(self, workspace):
        ws = str(workspace)
        target = "foo.md"
        for _ in range(5):
            _check_loop(ws, "write_file", target)
        reset_loop_tracker()
        # Next 5 after reset should not trigger
        for i in range(5):
            r = _check_loop(ws, "write_file", target)
            # write_file consecutive threshold is 4 — the 4th identical call fires
            if i >= 3:
                assert r is not None  # consecutive check
                reset_loop_tracker()
                break

    def test_write_file_is_checked(self, workspace):
        """Verify write_file now participates in loop detection (was a gap)."""
        # 4 identical write_file calls in a row should trigger the consecutive check.
        ws = str(workspace)
        results = [_check_loop(ws, "write_file", "same.md") for _ in range(4)]
        assert results[-1] is not None
        assert "LOOP DETECTED" in results[-1]


class TestAvailableTools:
    def test_all_seven_tools_present(self):
        assert len(AVAILABLE_TOOLS) == 7
        assert "read_file" in AVAILABLE_TOOLS
        assert "write_file" in AVAILABLE_TOOLS
        assert "list_directory" in AVAILABLE_TOOLS
        assert "execute_shell" in AVAILABLE_TOOLS
        assert "search_code" in AVAILABLE_TOOLS
        assert "deploy_remote" in AVAILABLE_TOOLS
        assert "check_completion" in AVAILABLE_TOOLS

    def test_is_tuple(self):
        assert isinstance(AVAILABLE_TOOLS, tuple)


class TestSafeResolve:
    def test_valid_relative_path(self, workspace):
        result = _safe_resolve(workspace, "hello.py")
        assert result == (workspace / "hello.py").resolve()

    def test_rejects_path_traversal(self, workspace):
        with pytest.raises(ValueError, match="resolves outside workspace"):
            _safe_resolve(workspace, "../../etc/passwd")

    def test_rejects_deeply_nested_escape(self, workspace):
        with pytest.raises(ValueError, match="resolves outside workspace"):
            _safe_resolve(workspace, "subdir/../../../../../../etc/passwd")

    def test_subdirectory_path_works(self, workspace):
        result = _safe_resolve(workspace, "subdir/data.txt")
        assert result == (workspace / "subdir" / "data.txt").resolve()

    def test_dot_path_works(self, workspace):
        result = _safe_resolve(workspace, ".")
        assert result == workspace.resolve()

    def test_rejects_absolute_path(self, workspace):
        with pytest.raises(ValueError, match="resolves outside workspace"):
            _safe_resolve(workspace, "../../../../../../tmp/evil")


class TestCreateToolsCallable:
    def test_returns_correct_count_for_subset(self, workspace):
        tools = create_tools(workspace, ["read_file", "write_file"])
        assert len(tools) == 2

    def test_returns_five_tools_without_platform_context(self, workspace):
        # deploy_remote is filtered out when platform_id/story_id are not provided
        tools = create_tools(workspace, list(AVAILABLE_TOOLS))
        assert len(tools) == 5

    def test_skips_unknown_tool_names(self, workspace):
        tools = create_tools(
            workspace,
            ["read_file", "nonexistent_tool", "write_file"],
        )
        assert len(tools) == 2

    def test_tools_have_meaningful_names(self, workspace):
        tools = create_tools(workspace, list(AVAILABLE_TOOLS))
        names = {t.__name__ for t in tools}
        # deploy_remote excluded without platform context; check_completion excluded without stage_name
        assert names == set(AVAILABLE_TOOLS) - {"deploy_remote", "check_completion"}

    def test_read_file_reads_content(self, workspace):
        tools = create_tools(workspace, ["read_file"])
        read_file = tools[0]
        result = read_file(path="hello.py")
        assert result == "print('hello')"

    def test_read_file_returns_error_for_missing(self, workspace):
        tools = create_tools(workspace, ["read_file"])
        read_file = tools[0]
        result = read_file(path="nonexistent.py")
        assert "File not found" in result

    def test_write_file_creates_file(self, workspace):
        tools = create_tools(workspace, ["write_file"])
        write_file = tools[0]
        result = write_file(path="new_file.txt", content="hello world")
        assert "Successfully wrote to new_file.txt" in result
        assert (workspace / "new_file.txt").read_text() == "hello world"

    def test_write_file_creates_parent_dirs(self, workspace):
        tools = create_tools(workspace, ["write_file"])
        write_file = tools[0]
        result = write_file(path="deep/nested/file.txt", content="nested content")
        assert "Successfully wrote" in result
        assert (workspace / "deep" / "nested" / "file.txt").read_text() == "nested content"

    def test_list_directory_lists_entries(self, workspace):
        tools = create_tools(workspace, ["list_directory"])
        list_dir = tools[0]
        result = list_dir(path=".")
        assert "hello.py" in result
        assert "subdir" in result

    def test_list_directory_returns_sorted(self, workspace):
        tools = create_tools(workspace, ["list_directory"])
        list_dir = tools[0]
        result = list_dir(path=".")
        lines = result.strip().split("\n")
        assert lines == sorted(lines)

    def test_list_directory_error_for_missing(self, workspace):
        tools = create_tools(workspace, ["list_directory"])
        list_dir = tools[0]
        result = list_dir(path="nonexistent_dir")
        assert "Directory not found" in result

    def test_search_code_finds_matches(self, workspace):
        tools = create_tools(workspace, ["search_code"])
        search = tools[0]
        result = search(pattern="hello")
        assert "hello.py" in result
        assert "print" in result

    def test_search_code_no_matches(self, workspace):
        tools = create_tools(workspace, ["search_code"])
        search = tools[0]
        result = search(pattern="zzz_no_match_zzz")
        assert result == "No matches found"

    def test_search_code_invalid_regex(self, workspace):
        tools = create_tools(workspace, ["search_code"])
        search = tools[0]
        result = search(pattern="[unclosed")
        assert "Invalid search pattern" in result

    def test_search_code_in_subdirectory(self, workspace):
        tools = create_tools(workspace, ["search_code"])
        search = tools[0]
        result = search(pattern="some data", path="subdir")
        assert "data.txt" in result

    def test_execute_shell_runs_command(self, workspace):
        tools = create_tools(workspace, ["execute_shell"])
        shell = tools[0]
        result = shell(command="echo hello_from_shell")
        assert "hello_from_shell" in result

    def test_execute_shell_captures_stderr(self, workspace):
        tools = create_tools(workspace, ["execute_shell"])
        shell = tools[0]
        # Use python to write to stderr since it is cross-platform
        result = shell(
            command='python -c "import sys; sys.stderr.write(\'err_msg\\n\')"'
        )
        assert "err_msg" in result

    def test_read_file_rejects_path_traversal(self, workspace):
        tools = create_tools(workspace, ["read_file"])
        read_file = tools[0]
        result = read_file(path="../../etc/passwd")
        assert "outside workspace" in result.lower() or "error" in result.lower()

    def test_write_file_rejects_path_traversal(self, workspace):
        tools = create_tools(workspace, ["write_file"])
        write_file = tools[0]
        result = write_file(path="../../evil.txt", content="malicious")
        assert "outside workspace" in result.lower() or "error" in result.lower()
        # File should NOT have been created
        assert not (workspace.parent.parent / "evil.txt").exists()

    def test_default_format_is_callable(self, workspace):
        # Calling without fmt should default to CALLABLE
        tools = create_tools(workspace, ["read_file"])
        assert callable(tools[0])

    def test_empty_allowed_tools(self, workspace):
        tools = create_tools(workspace, [])
        assert tools == []


class TestCreateToolsLangchain:
    @pytest.fixture(autouse=True)
    def _require_langchain(self):
        pytest.importorskip("langchain_core", reason="langchain_core not installed")

    @pytest.fixture
    def lc_tools(self, workspace):
        return create_tools(
            workspace,
            list(AVAILABLE_TOOLS),
            fmt=ToolFormat.LANGCHAIN,
        )

    def test_returns_correct_count(self, lc_tools):
        # deploy_remote + check_completion filtered out without platform/stage context
        assert len(lc_tools) == 5

    def test_tools_have_correct_names(self, lc_tools):
        names = {t.name for t in lc_tools}
        assert names == set(AVAILABLE_TOOLS) - {"deploy_remote", "check_completion"}

    def test_read_file_tool_works(self, lc_tools):
        read_tool = next(t for t in lc_tools if t.name == "read_file")
        result = read_tool.invoke({"path": "hello.py"})
        assert result == "print('hello')"

    def test_write_file_tool_works(self, lc_tools, workspace):
        write_tool = next(t for t in lc_tools if t.name == "write_file")
        result = write_tool.invoke({"path": "lc_test.txt", "content": "lc content"})
        assert "Successfully wrote" in result
        assert (workspace / "lc_test.txt").read_text() == "lc content"


class TestCreateToolsCrewAI:
    @pytest.fixture(autouse=True)
    def _require_crewai(self):
        pytest.importorskip("crewai", reason="crewai not installed")

    @pytest.fixture
    def crewai_tools(self, workspace):
        return create_tools(
            workspace,
            list(AVAILABLE_TOOLS),
            fmt=ToolFormat.CREWAI,
        )

    def test_returns_correct_count(self, crewai_tools):
        # deploy_remote + check_completion filtered out without platform/stage context
        assert len(crewai_tools) == 5

    def test_tools_have_correct_names(self, crewai_tools):
        names = {t.name for t in crewai_tools}
        assert names == set(AVAILABLE_TOOLS) - {"deploy_remote", "check_completion"}

    def test_read_file_tool_works(self, crewai_tools):
        read_tool = next(t for t in crewai_tools if t.name == "read_file")
        result = read_tool._run(path="hello.py")
        assert result == "print('hello')"

    def test_read_file_missing(self, crewai_tools):
        read_tool = next(t for t in crewai_tools if t.name == "read_file")
        result = read_tool._run(path="nonexistent.py")
        assert "File not found" in result

    def test_write_file_tool_works(self, crewai_tools, workspace):
        write_tool = next(t for t in crewai_tools if t.name == "write_file")
        result = write_tool._run(path="crewai_test.txt", content="crewai content")
        assert "Successfully wrote" in result
        assert (workspace / "crewai_test.txt").read_text() == "crewai content"

    def test_list_directory_tool_works(self, crewai_tools):
        list_tool = next(t for t in crewai_tools if t.name == "list_directory")
        result = list_tool._run(path=".")
        assert "hello.py" in result
        assert "subdir" in result

    def test_execute_shell_tool_works(self, crewai_tools):
        shell_tool = next(t for t in crewai_tools if t.name == "execute_shell")
        result = shell_tool._run(command="echo crewai_shell_test")
        assert "crewai_shell_test" in result

    def test_search_code_tool_works(self, crewai_tools):
        search_tool = next(t for t in crewai_tools if t.name == "search_code")
        result = search_tool._run(pattern="hello")
        assert "hello.py" in result

    def test_read_file_rejects_traversal(self, crewai_tools):
        read_tool = next(t for t in crewai_tools if t.name == "read_file")
        result = read_tool._run(path="../../etc/passwd")
        assert "outside workspace" in result.lower() or "error" in result.lower()

    def test_tools_are_crewai_base_tools(self, crewai_tools):
        from crewai.tools import BaseTool as CrewAIBaseTool
        for tool in crewai_tools:
            assert isinstance(tool, CrewAIBaseTool)


class TestCreateToolsOpenAI:
    def test_openai_function_enum_removed(self):
        assert not hasattr(ToolFormat, "OPENAI_FUNCTION")
        assert hasattr(ToolFormat, "OPENAI_AGENTS")


class TestCreateToolsOpenAIAgents:
    @pytest.fixture(autouse=True)
    def _require_openai_agents(self):
        pytest.importorskip("agents", reason="openai-agents not installed")

    @pytest.fixture
    def oai_tools(self, workspace):
        return create_tools(
            workspace,
            list(AVAILABLE_TOOLS),
            fmt=ToolFormat.OPENAI_AGENTS,
        )

    def test_returns_correct_count(self, oai_tools):
        # deploy_remote + check_completion filtered out without platform/stage context
        assert len(oai_tools) == 5

    def test_tools_have_correct_names(self, oai_tools):
        names = {t.name for t in oai_tools}
        assert names == set(AVAILABLE_TOOLS) - {"deploy_remote", "check_completion"}

    def test_tools_are_function_tools(self, oai_tools):
        from agents import FunctionTool
        for tool in oai_tools:
            assert isinstance(tool, FunctionTool)

    def test_tools_have_json_schemas(self, oai_tools):
        """Each FunctionTool should have a params_json_schema for the LLM."""
        for tool in oai_tools:
            assert tool.params_json_schema is not None
            assert isinstance(tool.params_json_schema, dict)


class TestDeployRemoteTool:
    def test_deploy_remote_excluded_without_platform_id(self, workspace):
        tools = create_tools(workspace, ["deploy_remote"], fmt=ToolFormat.CALLABLE)
        assert len(tools) == 0

    def test_deploy_remote_included_with_platform_id(self, workspace):
        tools = create_tools(
            workspace, ["deploy_remote"], fmt=ToolFormat.CALLABLE,
            platform_id="crewai", story_id="US-001",
        )
        assert len(tools) == 1

    def test_deploy_remote_callable_format(self, workspace):
        tools = create_tools(
            workspace, ["deploy_remote"], fmt=ToolFormat.CALLABLE,
            platform_id="crewai", story_id="US-001",
        )
        assert len(tools) == 1
        # Tool should be callable
        assert callable(tools[0])

    def test_deploy_remote_crewai_format(self, workspace):
        pytest.importorskip("crewai", reason="crewai not installed")
        tools = create_tools(
            workspace, ["deploy_remote"], fmt=ToolFormat.CREWAI,
            platform_id="crewai", story_id="US-001",
        )
        assert len(tools) == 1
        assert tools[0].name == "deploy_remote"

    def test_existing_tools_unaffected_by_new_kwargs(self, workspace):
        tools = create_tools(
            workspace, ["read_file", "write_file"], fmt=ToolFormat.CALLABLE,
            platform_id="crewai", story_id="US-001",
        )
        assert len(tools) == 2


class TestAgentFrameworkToolFormat:
    def test_agent_framework_enum_exists(self):
        from desmet.adapters._tools import ToolFormat
        assert hasattr(ToolFormat, "AGENT_FRAMEWORK")

    def test_create_agent_framework_tools(self, tmp_path):
        from desmet.adapters._tools import ToolFormat, create_tools
        tools = create_tools(
            tmp_path,
            ["read_file", "write_file", "list_directory"],
            fmt=ToolFormat.AGENT_FRAMEWORK,
        )
        assert len(tools) == 3

    def test_agent_framework_tools_are_callable(self, tmp_path):
        from desmet.adapters._tools import ToolFormat, create_tools
        tools = create_tools(tmp_path, ["read_file"], fmt=ToolFormat.AGENT_FRAMEWORK)
        assert callable(tools[0])

    def test_agent_framework_read_file_works(self, tmp_path):
        from desmet.adapters._tools import ToolFormat, create_tools
        (tmp_path / "hello.txt").write_text("world")
        tools = create_tools(tmp_path, ["read_file"], fmt=ToolFormat.AGENT_FRAMEWORK)
        read_file = tools[0]
        result = read_file(path="hello.txt")
        assert result == "world"

    def test_agent_framework_check_completion_included(self, tmp_path):
        from desmet.adapters._tools import ToolFormat, create_tools
        tools = create_tools(
            tmp_path,
            ["check_completion"],
            fmt=ToolFormat.AGENT_FRAMEWORK,
            stage_name="codegen",
        )
        assert len(tools) == 1

    def test_agent_framework_tools_have_descriptions(self, tmp_path):
        """Agent Framework @tool functions need docstrings for schema inference."""
        from desmet.adapters._tools import ToolFormat, create_tools
        tools = create_tools(
            tmp_path,
            ["read_file", "write_file", "execute_shell"],
            fmt=ToolFormat.AGENT_FRAMEWORK,
        )
        for t in tools:
            assert t.__doc__ is not None and len(t.__doc__) > 5


# ---------------------------------------------------------------------------
# split_tools tests
# ---------------------------------------------------------------------------

from desmet.adapters._tools import split_tools


class _MockNamedTool:
    def __init__(self, name: str):
        self.name = name


def _make_callable(name: str):
    def fn(): pass
    fn.__name__ = name
    return fn


class TestSplitTools:
    def test_executor_excludes_check_completion(self) -> None:
        tools = [_MockNamedTool(n) for n in ["read_file", "write_file", "check_completion"]]
        executor, _ = split_tools(tools, ToolFormat.LANGCHAIN)
        assert all(t.name != "check_completion" for t in executor)

    def test_reviewer_gets_inspection_tools(self) -> None:
        tools = [_MockNamedTool(n) for n in [
            "read_file", "write_file", "execute_shell",
            "list_directory", "search_code", "check_completion",
        ]]
        _, reviewer = split_tools(tools, ToolFormat.CREWAI)
        assert {t.name for t in reviewer} == {"read_file", "list_directory", "search_code", "check_completion"}

    def test_callable_tools_uses_dunder_name(self) -> None:
        tools = [_make_callable(n) for n in ["read_file", "write_file", "check_completion"]]
        executor, _ = split_tools(tools, ToolFormat.AGENT_FRAMEWORK)
        assert all(t.__name__ != "check_completion" for t in executor)

    def test_empty_tools(self) -> None:
        executor, reviewer = split_tools([], ToolFormat.LANGCHAIN)
        assert executor == [] and reviewer == []


class TestSplitToolsCallable:
    def test_split_tools_callable_format(self, tmp_path):
        from desmet.adapters._tools import ToolFormat, create_tools, split_tools
        tools = create_tools(
            tmp_path, ["read_file", "write_file", "check_completion"],
            fmt=ToolFormat.CALLABLE, stage_name="codegen",
        )
        executor, reviewer = split_tools(tools, ToolFormat.CALLABLE)
        executor_names = [t.__name__ for t in executor]
        reviewer_names = [t.__name__ for t in reviewer]
        assert "check_completion" not in executor_names
        assert "read_file" in reviewer_names
        assert "check_completion" in reviewer_names
