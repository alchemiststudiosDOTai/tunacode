"""Tests for tool decorators - error handling, and XML prompt loading.

Tests @base_tool and @file_tool decorator behavior in isolation.
"""

import pytest
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
