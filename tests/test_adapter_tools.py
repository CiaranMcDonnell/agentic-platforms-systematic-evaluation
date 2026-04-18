"""Tests for the shared adapter tool factory."""


import pytest

from desmet.adapters._shared.tools import (
    AVAILABLE_TOOLS,
    ToolFormat,
    _CROSS_TOOL_THRESHOLD,
    _check_loop,
    _execute_shell,
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
    def test_fires_on_cross_tool_ops_on_same_file(self, workspace):
        ws = str(workspace)
        target = "docs/design/use_case.mermaid"
        # Build a 5-item cycle so no individual tool accumulates 4+ identical
        # consecutive calls (the per-tool consecutive threshold) before the
        # cross-tool threshold is reached.  Each element appears exactly twice
        # across _CROSS_TOOL_THRESHOLD (10) iterations.
        cycle = [
            ("write_file", target),
            ("execute_shell", f"mmdc -i {target}"),
            ("read_file", target),
            ("execute_shell", f"cat {target}"),
            ("execute_shell", f"wc -l {target}"),
        ]
        n = _CROSS_TOOL_THRESHOLD
        results: list[str | None] = []
        for i in range(n):
            tool, arg = cycle[i % len(cycle)]
            results.append(_check_loop(ws, tool, arg))
        assert all(r is None for r in results[: n - 1])
        assert results[-1] is not None
        assert "LOOP DETECTED" in results[-1]
        assert target in results[-1]

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

    def test_locked_target_blocks_all_subsequent_tools(self, workspace):
        """After cross-tool loop fires, the target is LOCKED for the stage.

        The LLM can't work around the warning by switching tools — any
        subsequent read/write/render on the locked file gets REFUSED.
        """
        ws = str(workspace)
        target = "docs/design/use_case.mermaid"

        # Build up enough cross-tool ops to trigger the lock.
        # Use a 5-item cycle so no individual tool accumulates 4 identical
        # consecutive calls (per-tool consecutive threshold) before the
        # cross-tool threshold is reached.
        cycle = [
            ("write_file", target),
            ("execute_shell", f"mmdc -i {target}"),
            ("read_file", target),
            ("execute_shell", f"cat {target}"),
            ("execute_shell", f"wc -l {target}"),
        ]
        sequence = [cycle[i % len(cycle)] for i in range(_CROSS_TOOL_THRESHOLD)]
        results = [_check_loop(ws, tool, arg) for tool, arg in sequence]
        # The final call triggers the cross-tool loop and LOCKS the target
        assert results[-1] is not None
        assert "LOCKED" in results[-1]

        # Any subsequent attempt — DIFFERENT tool, DIFFERENT arg — refused
        refused_read = _check_loop(ws, "read_file", target)
        assert refused_read is not None
        assert "REFUSED" in refused_read
        assert target in refused_read

        refused_write = _check_loop(ws, "write_file", target)
        assert refused_write is not None
        assert "REFUSED" in refused_write

        # Shell command that also touches this target → refused
        refused_shell = _check_loop(
            ws, "execute_shell", f"cat {target}",
        )
        assert refused_shell is not None
        assert "REFUSED" in refused_shell

        # But OTHER files are still fine
        other_file = _check_loop(ws, "write_file", "docs/design/other.md")
        assert other_file is None

    def test_reset_clears_locked_targets(self, workspace):
        """reset_loop_tracker() must clear locked targets (between stages)."""
        ws = str(workspace)
        target = "stuck.md"

        # Trigger a lock
        # Use a varied 5-item cycle to reach the cross-tool threshold without
        # triggering the per-tool consecutive check first.
        cycle = [
            ("write_file", target),
            ("execute_shell", f"mmdc -i {target}"),
            ("read_file", target),
            ("execute_shell", f"cat {target}"),
            ("execute_shell", f"wc -l {target}"),
        ]
        for i in range(_CROSS_TOOL_THRESHOLD):
            tool, arg = cycle[i % len(cycle)]
            _check_loop(ws, tool, arg)
        refused = _check_loop(ws, "write_file", target)
        assert refused is not None

        # Reset → fresh state
        reset_loop_tracker()

        # Same file is now workable again
        assert _check_loop(ws, "write_file", target) is None


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

    def test_write_file_strips_markdown_fences_for_mermaid(self, workspace):
        """``.mermaid`` files should have their markdown code fences stripped
        so ``mmdc`` can render them — LLMs default to fenced output."""
        tools = create_tools(workspace, ["write_file"])
        write_file = tools[0]
        fenced = "```mermaid\nclassDiagram\n    class Foo\n```"
        write_file(path="diagram.mermaid", content=fenced)
        on_disk = (workspace / "diagram.mermaid").read_text()
        assert on_disk.startswith("classDiagram")
        assert "```" not in on_disk

    def test_write_file_preserves_fences_for_non_mermaid(self, workspace):
        """Markdown files (and anything non-``.mermaid``) should keep fences
        intact — they're legitimate markdown syntax there."""
        tools = create_tools(workspace, ["write_file"])
        write_file = tools[0]
        fenced = "```python\nprint('hi')\n```"
        write_file(path="notes.md", content=fenced)
        assert (workspace / "notes.md").read_text() == fenced

    def test_execute_shell_surfaces_nonzero_exit_code(self, workspace, tmp_path):
        """Non-zero shell exits must be surfaced with an ``[EXIT=N]`` prefix
        so the agent can tell a silent-fail command apart from one that
        succeeded with no output."""
        import sys
        cmd = f'"{sys.executable}" -c "import sys; sys.exit(3)"'
        result = _execute_shell(workspace, cmd, stage=None)
        assert result.startswith("[EXIT=3]"), f"expected EXIT=3 prefix, got: {result!r}"

    def test_execute_shell_omits_exit_code_on_success(self, workspace):
        """Exit 0 commands shouldn't carry an ``[EXIT=...]`` prefix."""
        import sys
        cmd = f'"{sys.executable}" -c "print(\'ok\')"'
        result = _execute_shell(workspace, cmd, stage=None)
        assert "[EXIT=" not in result
        assert "ok" in result

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
        from desmet.adapters._shared.tools import ToolFormat
        assert hasattr(ToolFormat, "AGENT_FRAMEWORK")

    def test_create_agent_framework_tools(self, tmp_path):
        from desmet.adapters._shared.tools import ToolFormat, create_tools
        tools = create_tools(
            tmp_path,
            ["read_file", "write_file", "list_directory"],
            fmt=ToolFormat.AGENT_FRAMEWORK,
        )
        assert len(tools) == 3

    def test_agent_framework_tools_are_callable(self, tmp_path):
        from desmet.adapters._shared.tools import ToolFormat, create_tools
        tools = create_tools(tmp_path, ["read_file"], fmt=ToolFormat.AGENT_FRAMEWORK)
        assert callable(tools[0])

    def test_agent_framework_read_file_works(self, tmp_path):
        from desmet.adapters._shared.tools import ToolFormat, create_tools
        (tmp_path / "hello.txt").write_text("world")
        tools = create_tools(tmp_path, ["read_file"], fmt=ToolFormat.AGENT_FRAMEWORK)
        read_file = tools[0]
        result = read_file(path="hello.txt")
        assert result == "world"

    def test_agent_framework_check_completion_included(self, tmp_path):
        from desmet.adapters._shared.tools import ToolFormat, create_tools
        tools = create_tools(
            tmp_path,
            ["check_completion"],
            fmt=ToolFormat.AGENT_FRAMEWORK,
            stage_name="codegen",
        )
        assert len(tools) == 1

    def test_agent_framework_tools_have_descriptions(self, tmp_path):
        """Agent Framework @tool functions need docstrings for schema inference."""
        from desmet.adapters._shared.tools import ToolFormat, create_tools
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

from desmet.adapters._shared.tools import split_tools


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
        from desmet.adapters._shared.tools import ToolFormat, create_tools, split_tools
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


# ---------------------------------------------------------------------------
# _check_completion hint string tests
# ---------------------------------------------------------------------------

from desmet.adapters._shared.tools import _check_completion


class TestCheckCompletionDeployHint:
    """The deploy hint string is fed back to the agent on retry via the
    Bug B retry-feedback path. It must name every failure mode the
    validator can flag, otherwise the agent can't fix the right thing.
    """

    def test_deploy_hint_mentions_dockerfile(self, tmp_path):
        # Empty workspace → validation fails → returns the hint string.
        passed, msg = _check_completion(tmp_path, "deploy")
        assert passed is False
        assert "Dockerfile" in msg

    def test_deploy_hint_mentions_docker_compose_yaml(self, tmp_path):
        passed, msg = _check_completion(tmp_path, "deploy")
        assert passed is False
        assert "docker-compose.yaml" in msg

    def test_deploy_hint_mentions_port_variable(self, tmp_path):
        """Must include the literal `${PORT}` token so the agent can
        copy it verbatim into its compose file.
        """
        passed, msg = _check_completion(tmp_path, "deploy")
        assert passed is False
        assert "${PORT}" in msg

    def test_deploy_hint_explains_env_injection(self, tmp_path):
        """The hint should tell the agent why ${PORT} matters — that
        the harness injects it via .env at deploy time. Without this
        context the agent might "fix" by hardcoding a port number.
        """
        passed, msg = _check_completion(tmp_path, "deploy")
        assert passed is False
        assert ".env" in msg or "PORT" in msg

    def test_deploy_passes_when_artifacts_complete(self, tmp_path):
        (tmp_path / "Dockerfile").write_text("FROM python:3.11-slim\n")
        (tmp_path / "docker-compose.yaml").write_text(
            "services:\n  app:\n    build: .\n    ports:\n      - \"${PORT}:8000\"\n"
        )
        passed, msg = _check_completion(tmp_path, "deploy")
        assert passed is True
        assert "VALIDATION PASSED" in msg


class TestWriteFileStageAllowlist:
    """_write_file must be gated by stage the same way _execute_shell is:
    the requirements stage is a docs-only scope, so Python/YAML/etc writes
    must be refused. Motivation: Microsoft Agent Framework was observed
    writing email_validator.py during a requirements run, then deleting
    it after the manager re-planned — wasted tokens that a write-scope
    gate would have prevented up front.
    """

    def test_requirements_stage_blocks_python_write(self, workspace):
        from desmet.adapters._shared.tools import _write_file

        result = _write_file(
            workspace,
            "src/email_validator.py",
            "def is_valid(x): return True\n",
            stage="requirements",
        )
        assert result.startswith("BLOCKED"), f"expected BLOCKED prefix, got: {result!r}"
        assert "requirements" in result
        assert not (workspace / "src/email_validator.py").exists(), (
            "blocked write must not create the file on disk"
        )

    def test_requirements_stage_allows_markdown_write(self, workspace):
        from desmet.adapters._shared.tools import _write_file

        result = _write_file(
            workspace,
            "docs/design/requirements.md",
            "# Requirements\n",
            stage="requirements",
        )
        assert "Successfully wrote" in result
        assert (workspace / "docs/design/requirements.md").exists()

    def test_requirements_stage_allows_mermaid_write(self, workspace):
        from desmet.adapters._shared.tools import _write_file

        result = _write_file(
            workspace,
            "docs/design/flow.mermaid",
            "flowchart TD\nA-->B\n",
            stage="requirements",
        )
        assert "Successfully wrote" in result
        assert (workspace / "docs/design/flow.mermaid").exists()

    def test_requirements_stage_allows_txt_write(self, workspace):
        from desmet.adapters._shared.tools import _write_file

        result = _write_file(workspace, "notes.txt", "hello\n", stage="requirements")
        assert "Successfully wrote" in result

    def test_none_stage_allows_any_write(self, workspace):
        """stage=None means unfiltered — matches _check_shell_stage's contract."""
        from desmet.adapters._shared.tools import _write_file

        result = _write_file(workspace, "src/app.py", "print('hi')\n", stage=None)
        assert "Successfully wrote" in result
        assert (workspace / "src/app.py").exists()

    def test_codegen_stage_unrestricted(self, workspace):
        """Only stages listed in _STAGE_WRITE_ALLOWLIST are filtered."""
        from desmet.adapters._shared.tools import _write_file

        result = _write_file(workspace, "src/app.py", "print('hi')\n", stage="codegen")
        assert "Successfully wrote" in result

    def test_block_message_names_allowed_extensions(self, workspace):
        """The blocked-message must tell the agent what IS allowed so it
        can correct course instead of retrying blind."""
        from desmet.adapters._shared.tools import _write_file

        result = _write_file(
            workspace, "src/app.py", "x=1\n", stage="requirements"
        )
        # One of the allowed extensions should appear in the guidance text
        assert any(ext in result for ext in (".md", ".txt", ".mermaid"))


class TestGoogleADKToolFormat:
    """ADK's Gemini function-declaration schema rejects Python parameter
    defaults (emits ~18 WARNING lines per stage in real runs). The
    ToolFormat.GOOGLE_ADK variant returns the same callables but with
    no defaults in the signature, so the schema builder is quiet."""

    def test_format_exists(self):
        from desmet.adapters._shared.tools import ToolFormat

        assert hasattr(ToolFormat, "GOOGLE_ADK")

    def test_list_directory_has_no_default(self, workspace):
        import inspect

        from desmet.adapters._shared.tools import ToolFormat, create_tools

        tools = create_tools(workspace, ["list_directory"], fmt=ToolFormat.GOOGLE_ADK)
        sig = inspect.signature(tools[0])
        assert sig.parameters["path"].default is inspect.Parameter.empty, (
            "ADK tools must have no default — Gemini schema rejects defaults"
        )

    def test_search_code_has_no_default(self, workspace):
        import inspect

        from desmet.adapters._shared.tools import ToolFormat, create_tools

        tools = create_tools(workspace, ["search_code"], fmt=ToolFormat.GOOGLE_ADK)
        sig = inspect.signature(tools[0])
        assert sig.parameters["path"].default is inspect.Parameter.empty

    def test_deploy_remote_has_no_default(self, workspace):
        import inspect

        from desmet.adapters._shared.tools import ToolFormat, create_tools

        tools = create_tools(
            workspace,
            ["deploy_remote"],
            fmt=ToolFormat.GOOGLE_ADK,
            platform_id="google_adk",
            story_id="s1",
        )
        sig = inspect.signature(tools[0])
        assert sig.parameters["url"].default is inspect.Parameter.empty

    def test_tools_still_callable_with_explicit_args(self, workspace):
        from desmet.adapters._shared.tools import ToolFormat, create_tools

        tools = create_tools(
            workspace, ["list_directory", "read_file"], fmt=ToolFormat.GOOGLE_ADK
        )
        by_name = {t.__name__: t for t in tools}
        listing = by_name["list_directory"](path=".")
        assert "hello.py" in listing
        content = by_name["read_file"](path="hello.py")
        assert "print" in content

    def test_write_file_still_stage_gated(self, workspace):
        """ADK tools must still honor the write_file stage allowlist."""
        from desmet.adapters._shared.tools import ToolFormat, create_tools

        tools = create_tools(
            workspace,
            ["write_file"],
            fmt=ToolFormat.GOOGLE_ADK,
            stage_name="requirements",
        )
        result = tools[0](path="app.py", content="x=1\n")
        assert result.startswith("BLOCKED")

    def test_split_tools_recognises_adk_format(self, workspace):
        """split_tools must use __name__ (not .name) for the GOOGLE_ADK format,
        same as CALLABLE and AGENT_FRAMEWORK."""
        from desmet.adapters._shared.tools import (
            ToolFormat,
            create_tools,
            split_tools,
        )

        tools = create_tools(
            workspace,
            ["read_file", "write_file", "check_completion"],
            fmt=ToolFormat.GOOGLE_ADK,
            stage_name="requirements",
        )
        executor, reviewer = split_tools(tools, ToolFormat.GOOGLE_ADK)
        exec_names = {t.__name__ for t in executor}
        rev_names = {t.__name__ for t in reviewer}
        assert "check_completion" not in exec_names
        assert "check_completion" in rev_names
        assert "read_file" in rev_names
