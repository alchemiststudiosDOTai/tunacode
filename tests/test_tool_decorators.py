"""Tests for tool decorators - error handling, XML prompt loading, and signature preservation.

Tests @base_tool and @file_tool decorator behavior in isolation.
"""

import inspect

import pytest
from pydantic_ai import Tool
from pydantic_ai.exceptions import ModelRetry

from tunacode.exceptions import FileOperationError, ToolExecutionError
from tunacode.tools.decorators import base_tool, file_tool


class TestBaseTool:
    """Tests for @base_tool decorator."""

    async def test_wraps_async_function(self, mock_no_xml_prompt):
        """Decorator preserves async function behavior."""

        @base_tool
        async def simple_tool(x: int) -> str:
            return f"result: {x}"

        result = await simple_tool(42)
        assert result == "result: 42"

    async def test_passes_through_model_retry(self, mock_no_xml_prompt):
        """ModelRetry exceptions pass through unchanged."""

        @base_tool
        async def raises_retry():
            raise ModelRetry("retry message")

        with pytest.raises(ModelRetry, match="retry message"):
            await raises_retry()

    async def test_passes_through_tool_execution_error(self, mock_no_xml_prompt):
        """ToolExecutionError exceptions pass through unchanged."""

        @base_tool
        async def raises_tool_error():
            raise ToolExecutionError(tool_name="test", message="tool failed")

        with pytest.raises(ToolExecutionError, match="tool failed"):
            await raises_tool_error()

    async def test_passes_through_file_operation_error(self, mock_no_xml_prompt):
        """FileOperationError exceptions pass through unchanged."""

        @base_tool
        async def raises_file_error():
            raise FileOperationError(operation="read", path="/test.txt", message="file error")

        with pytest.raises(FileOperationError, match="file error"):
            await raises_file_error()

    async def test_wraps_generic_exception_in_tool_execution_error(self, mock_no_xml_prompt):
        """Other exceptions are wrapped in ToolExecutionError."""

        @base_tool
        async def raises_value_error():
            raise ValueError("oops")

        with pytest.raises(ToolExecutionError) as exc_info:
            await raises_value_error()

        assert "oops" in str(exc_info.value)
        assert exc_info.value.tool_name == "raises_value_error"

    def test_loads_xml_prompt_into_docstring(self, mock_xml_prompt):
        """XML prompt is loaded into wrapper's __doc__."""

        @base_tool
        async def tool_with_xml():
            """Original docstring."""
            return "ok"

        assert tool_with_xml.__doc__ == "Test XML prompt"

    def test_preserves_original_docstring_when_no_xml(self, mock_no_xml_prompt):
        """Original docstring preserved when no XML prompt exists."""

        @base_tool
        async def tool_without_xml():
            """Original docstring."""
            return "ok"

        assert tool_without_xml.__doc__ == "Original docstring."

    async def test_preserves_function_name(self, mock_no_xml_prompt):
        """Wrapper preserves original function name."""

        @base_tool
        async def named_tool():
            return "ok"

        assert named_tool.__name__ == "named_tool"


class TestFileTool:
    """Tests for @file_tool decorator."""

    async def test_converts_file_not_found_to_model_retry(self, mock_no_xml_prompt):
        """FileNotFoundError is converted to ModelRetry."""

        @file_tool
        async def read_missing(filepath: str) -> str:
            raise FileNotFoundError(filepath)

        with pytest.raises(ModelRetry, match="File not found"):
            await read_missing("/missing/file.txt")

    async def test_converts_permission_error_to_file_operation_error(self, mock_no_xml_prompt):
        """PermissionError is converted to FileOperationError."""

        @file_tool
        async def read_protected(filepath: str) -> str:
            raise PermissionError("access denied")

        with pytest.raises(FileOperationError) as exc_info:
            await read_protected("/protected/file.txt")

        assert exc_info.value.operation == "access"
        assert exc_info.value.path == "/protected/file.txt"

    async def test_converts_unicode_decode_error_to_file_operation_error(self, mock_no_xml_prompt):
        """UnicodeDecodeError is converted to FileOperationError."""

        @file_tool
        async def read_binary(filepath: str) -> str:
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid byte")

        with pytest.raises(FileOperationError) as exc_info:
            await read_binary("/binary/file.bin")

        assert exc_info.value.operation == "decode"
        assert exc_info.value.path == "/binary/file.bin"

    async def test_converts_io_error_to_file_operation_error(self, mock_no_xml_prompt):
        """IOError is converted to FileOperationError."""

        @file_tool
        async def read_broken(filepath: str) -> str:
            raise OSError("disk error")

        with pytest.raises(FileOperationError) as exc_info:
            await read_broken("/broken/disk.txt")

        assert exc_info.value.operation == "read/write"
        assert exc_info.value.path == "/broken/disk.txt"

    async def test_converts_os_error_to_file_operation_error(self, mock_no_xml_prompt):
        """OSError is converted to FileOperationError."""

        @file_tool
        async def read_os_error(filepath: str) -> str:
            raise OSError("os error")

        with pytest.raises(FileOperationError) as exc_info:
            await read_os_error("/os/error.txt")

        assert exc_info.value.operation == "read/write"
        assert exc_info.value.path == "/os/error.txt"

    async def test_applies_base_tool_wrapper(self, mock_no_xml_prompt):
        """file_tool applies base_tool wrapper for generic errors."""

        @file_tool
        async def raises_generic(filepath: str) -> str:
            raise RuntimeError("unexpected")

        with pytest.raises(ToolExecutionError) as exc_info:
            await raises_generic("/any/file.txt")

        assert "unexpected" in str(exc_info.value)

    async def test_filepath_passed_correctly(self, mock_no_xml_prompt):
        """filepath argument is passed through correctly."""

        @file_tool
        async def echo_path(filepath: str) -> str:
            return f"path: {filepath}"

        result = await echo_path("/test/path.txt")
        assert result == "path: /test/path.txt"

    async def test_additional_args_passed(self, mock_no_xml_prompt):
        """Additional arguments beyond filepath are passed through."""

        @file_tool
        async def write_content(filepath: str, content: str, mode: str = "w") -> str:
            return f"{filepath}:{content}:{mode}"

        result = await write_content("/test.txt", "hello", mode="a")
        assert result == "/test.txt:hello:a"

    async def test_prepends_lsp_diagnostics_for_write_tools(self, mock_no_xml_prompt):
        """Write tools prepend formatted LSP diagnostics when enabled."""
        from unittest.mock import AsyncMock, patch

        expected_diagnostics = "<file_diagnostics>\nError (line 1): msg\n</file_diagnostics>"
        user_config = {"settings": {"lsp": {"enabled": True, "timeout": 0.1}}}

        @file_tool(writes=True)
        async def write_tool(filepath: str) -> str:
            return "ok"

        with (
            patch("tunacode.tools.decorators.load_config", return_value=user_config),
            patch("tunacode.lsp.get_diagnostics", new=AsyncMock(return_value=[])) as mock_get,
            patch(
                "tunacode.lsp.format_diagnostics",
                return_value=expected_diagnostics,
            ) as mock_format,
        ):
            result = await write_tool("/tmp/file.py")

        assert result == f"{expected_diagnostics}\n\nok"
        mock_get.assert_awaited_once()
        mock_format.assert_called_once()


class TestSignaturePreservation:
    """Tests that decorators preserve function signatures for pydantic-ai schema generation.

    pydantic-ai uses inspect.signature() to generate JSON schemas for tool parameters.
    If wrappers don't preserve signatures, pydantic-ai gets wrong/empty schemas.
    """

    def test_base_tool_preserves_signature(self, mock_no_xml_prompt):
        """@base_tool preserves the original function's signature."""

        @base_tool
        async def tool_with_params(
            query: str,
            limit: int = 10,
            recursive: bool = True,
        ) -> str:
            return "ok"

        sig = inspect.signature(tool_with_params)
        params = list(sig.parameters.keys())

        assert params == ["query", "limit", "recursive"]
        assert sig.parameters["query"].annotation is str
        assert sig.parameters["limit"].default == 10
        assert sig.parameters["recursive"].default is True

    def test_file_tool_preserves_signature(self, mock_no_xml_prompt):
        """@file_tool preserves the original function's signature."""

        @file_tool
        async def read_with_options(
            filepath: str,
            offset: int = 0,
            limit: int | None = None,
        ) -> str:
            return "content"

        sig = inspect.signature(read_with_options)
        params = list(sig.parameters.keys())

        assert params == ["filepath", "offset", "limit"]
        assert sig.parameters["filepath"].annotation is str
        assert sig.parameters["offset"].default == 0

    def test_file_tool_with_writes_preserves_signature(self, mock_no_xml_prompt):
        """@file_tool(writes=True) preserves the original function's signature."""

        @file_tool(writes=True)
        async def write_with_options(
            filepath: str,
            content: str,
            create_dirs: bool = False,
        ) -> str:
            return "written"

        sig = inspect.signature(write_with_options)
        params = list(sig.parameters.keys())

        assert params == ["filepath", "content", "create_dirs"]
        assert sig.parameters["content"].annotation is str
        assert sig.parameters["create_dirs"].default is False

    def test_pydantic_ai_can_create_tool_from_base_tool(self, mock_no_xml_prompt):
        """pydantic-ai Tool() can introspect @base_tool decorated functions."""

        @base_tool
        async def search_tool(
            pattern: str,
            directory: str = ".",
            max_results: int = 100,
        ) -> str:
            return "results"

        # This will fail if signature is not preserved - pydantic-ai
        # uses inspect.signature() internally for schema generation
        tool = Tool(search_tool)

        # Verify the tool was created with correct name
        assert tool.name == "search_tool"

    def test_pydantic_ai_can_create_tool_from_file_tool(self, mock_no_xml_prompt):
        """pydantic-ai Tool() can introspect @file_tool decorated functions."""

        @file_tool
        async def read_tool(
            filepath: str,
            encoding: str = "utf-8",
        ) -> str:
            return "content"

        tool = Tool(read_tool)
        assert tool.name == "read_tool"


class TestActualToolSignatures:
    """Tests that actual production tools have correct signatures for pydantic-ai."""

    def test_glob_tool_signature(self):
        """glob tool has introspectable signature."""
        from tunacode.tools.glob import glob

        sig = inspect.signature(glob)
        params = list(sig.parameters.keys())

        assert "pattern" in params
        assert "directory" in params
        assert "recursive" in params

    def test_read_file_tool_signature(self):
        """read_file tool has introspectable signature."""
        from tunacode.tools.read_file import read_file

        sig = inspect.signature(read_file)
        params = list(sig.parameters.keys())

        assert "filepath" in params
        assert "offset" in params
        assert "limit" in params

    def test_list_dir_tool_signature(self):
        """list_dir tool has introspectable signature."""
        from tunacode.tools.list_dir import list_dir

        sig = inspect.signature(list_dir)
        params = list(sig.parameters.keys())

        assert "directory" in params
        assert "max_files" in params

    def test_grep_tool_signature(self):
        """grep tool has introspectable signature."""
        from tunacode.tools.grep import grep

        sig = inspect.signature(grep)
        params = list(sig.parameters.keys())

        assert "pattern" in params
        assert "directory" in params

    def test_bash_tool_signature(self):
        """bash tool has introspectable signature."""
        from tunacode.tools.bash import bash

        sig = inspect.signature(bash)
        params = list(sig.parameters.keys())

        assert "command" in params

    def test_update_file_tool_signature(self):
        """update_file tool has introspectable signature."""
        from tunacode.tools.update_file import update_file

        sig = inspect.signature(update_file)
        params = list(sig.parameters.keys())

        assert "filepath" in params
        assert "old_text" in params
        assert "new_text" in params

    def test_write_file_tool_signature(self):
        """write_file tool has introspectable signature."""
        from tunacode.tools.write_file import write_file

        sig = inspect.signature(write_file)
        params = list(sig.parameters.keys())

        assert "filepath" in params
        assert "content" in params

    def test_web_fetch_tool_signature(self):
        """web_fetch tool has introspectable signature."""
        from tunacode.tools.web_fetch import web_fetch

        sig = inspect.signature(web_fetch)
        params = list(sig.parameters.keys())

        assert "url" in params

    def test_all_tools_work_with_pydantic_ai_tool(self):
        """All production tools can be wrapped by pydantic-ai Tool()."""
        from tunacode.tools.bash import bash
        from tunacode.tools.glob import glob
        from tunacode.tools.grep import grep
        from tunacode.tools.list_dir import list_dir
        from tunacode.tools.read_file import read_file
        from tunacode.tools.update_file import update_file
        from tunacode.tools.web_fetch import web_fetch
        from tunacode.tools.write_file import write_file

        tools = [bash, glob, grep, list_dir, read_file, update_file, web_fetch, write_file]

        for tool_func in tools:
            # This raises if pydantic-ai can't introspect the signature
            pydantic_tool = Tool(tool_func)
            assert pydantic_tool.name == tool_func.__name__, (
                f"Tool {tool_func.__name__} name mismatch"
            )


class TestDynamicToolSignatures:
    """Tests for dynamically created tools (factories)."""

    def test_research_agent_wrap_tool_preserves_signature(self):
        """ProgressTracker.wrap_tool preserves signatures."""
        from tunacode.core.agents.research_agent import ProgressTracker

        async def original_tool(query: str, limit: int = 5) -> str:
            return "result"

        tracker = ProgressTracker(callback=None)
        wrapped = tracker.wrap_tool(original_tool, "test_tool")

        sig = inspect.signature(wrapped)
        params = list(sig.parameters.keys())

        assert params == ["query", "limit"]
        assert sig.parameters["query"].annotation is str
        assert sig.parameters["limit"].default == 5

    def test_todo_tools_have_signatures(self):
        """Todo factory tools have proper signatures."""
        from unittest.mock import MagicMock

        from tunacode.tools.todo import (
            create_todoclear_tool,
            create_todoread_tool,
            create_todowrite_tool,
        )

        mock_state = MagicMock()
        mock_state.get_todos.return_value = []

        todowrite = create_todowrite_tool(mock_state)
        todoread = create_todoread_tool(mock_state)
        todoclear = create_todoclear_tool(mock_state)

        # These should have introspectable signatures
        assert "todos" in inspect.signature(todowrite).parameters
        assert len(inspect.signature(todoread).parameters) == 0
        assert len(inspect.signature(todoclear).parameters) == 0

    def test_present_plan_tool_has_signature(self):
        """present_plan factory tool has proper signature."""
        from unittest.mock import MagicMock

        from tunacode.tools.present_plan import create_present_plan_tool

        mock_state = MagicMock()
        mock_state.session.plan_mode = True

        present_plan = create_present_plan_tool(mock_state)

        sig = inspect.signature(present_plan)
        assert "plan_content" in sig.parameters
