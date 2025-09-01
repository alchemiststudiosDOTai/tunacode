"""
Module: tunacode.tools.read_file

File reading tool for agent operations in the TunaCode application.
Provides safe file reading with size limits and proper error handling.
"""

import asyncio
import logging
import os
from functools import lru_cache
from typing import Any, Dict

from tunacode.constants import (
    ERROR_FILE_DECODE,
    ERROR_FILE_DECODE_DETAILS,
    ERROR_FILE_NOT_FOUND,
    ERROR_FILE_TOO_LARGE,
    MAX_FILE_SIZE,
    MSG_FILE_SIZE_LIMIT,
)
from tunacode.exceptions import ToolExecutionError
from tunacode.tools.base import FileBasedTool
from tunacode.tools.decorator import tool_definition
from tunacode.tools.registry import ToolCategory
from tunacode.types import ToolResult

logger = logging.getLogger(__name__)


@tool_definition(
    name="Read",
    category=ToolCategory.READ_ONLY,
    description="Reads a file from the local filesystem with size limits and proper error handling",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The absolute path to the file to read",
            },
            "offset": {
                "type": "number",
                "description": "The line number to start reading from",
            },
            "limit": {
                "type": "number",
                "description": "The number of lines to read",
            },
        },
        "required": ["file_path"],
    },
    example_args={"file_path": "/path/to/file.py"},
    brief="Read file contents safely",
)
class ReadFileTool(FileBasedTool):
    """Tool for reading file contents."""

    @property
    def tool_name(self) -> str:
        return "Read"

    @lru_cache(maxsize=1)
    def _get_base_prompt(self) -> str:
        """Generate micro prompt to steer the agent in new_prompt.xml style.

        Returns:
            str: Micro prompt with OpenAI function calling format
        """
        # Get tool definition from decorator
        if hasattr(self.__class__, "_tool_definition"):
            definition = self.__class__._tool_definition

            # Build micro prompt in new_prompt.xml style
            prompt = f"""## Read Tool - File Reading

**Purpose**: {definition.description}

**OpenAI Function Call Format**:
```json
{{
  "tool_calls": [{{
    "id": "call_read",
    "type": "function",
    "function": {{
      "name": "Read",
      "arguments": "{{\\"file_path\\": \\"path/to/file.py\\", \\"offset\\": 1, \\"limit\\": 100}}"
    }}
  }}]
}}
```

**Key Points**:
- Always use absolute or relative paths from current directory
- Large files are automatically paginated (2000 lines max)
- Returns content with line numbers for precise editing
- Use offset/limit for reading specific sections
- Binary files return base64 encoded content

**Examples**:
- Read entire file: `{{"file_path": "src/main.py"}}`
- Read lines 50-100: `{{"file_path": "src/main.py", "offset": 50, "limit": 50}}`
- Check config: `{{"file_path": "config.json"}}`
"""
            return prompt

        # Fallback if no decorator definition
        return """Reads a file from the local filesystem with line numbers"""

    @lru_cache(maxsize=1)
    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get the parameters schema for read_file tool.

        Returns:
            Dict containing the JSON schema for tool parameters
        """
        # Get schema from decorator definition
        if hasattr(self.__class__, "_tool_definition"):
            definition = self.__class__._tool_definition
            if definition.parameters:
                return definition.parameters

        # Fallback to hardcoded schema
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute path to the file to read",
                },
                "offset": {
                    "type": "number",
                    "description": "The line number to start reading from",
                },
                "limit": {
                    "type": "number",
                    "description": "The number of lines to read",
                },
            },
            "required": ["file_path"],
        }

    async def _execute(self, file_path: str) -> ToolResult:
        """Read the contents of a file.

        Args:
            file_path: The path to the file to read.

        Returns:
            ToolResult: The contents of the file or an error message.

        Raises:
            Exception: Any file reading errors
        """
        # Add a size limit to prevent reading huge files
        if os.path.getsize(file_path) > MAX_FILE_SIZE:
            err_msg = ERROR_FILE_TOO_LARGE.format(filepath=file_path) + MSG_FILE_SIZE_LIMIT
            if self.ui:
                await self.ui.error(err_msg)
            raise ToolExecutionError(tool_name=self.tool_name, message=err_msg, original_error=None)

        # Run the blocking file I/O in a separate thread to avoid blocking the event loop
        def _read_sync(path: str) -> str:
            """Synchronous helper to read file contents (runs in thread)."""
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

        content: str = await asyncio.to_thread(_read_sync, file_path)
        return content

    async def _handle_error(self, error: Exception, filepath: str = None) -> ToolResult:
        """Handle errors with specific messages for common cases.

        Raises:
            ToolExecutionError: Always raised with structured error information
        """
        if isinstance(error, FileNotFoundError):
            err_msg = ERROR_FILE_NOT_FOUND.format(filepath=filepath)
        elif isinstance(error, UnicodeDecodeError):
            err_msg = (
                ERROR_FILE_DECODE.format(filepath=filepath)
                + " "
                + ERROR_FILE_DECODE_DETAILS.format(error=error)
            )
        else:
            # Use parent class handling for other errors
            await super()._handle_error(error, filepath)
            return  # super() will raise, this is unreachable

        if self.ui:
            await self.ui.error(err_msg)

        raise ToolExecutionError(tool_name=self.tool_name, message=err_msg, original_error=error)


# Create the function that maintains the existing interface
async def read_file(file_path: str) -> str:
    """
    Read the contents of a file.

    Args:
        file_path: The path to the file to read.

    Returns:
        str: The contents of the file or an error message.
    """
    tool = ReadFileTool(None)  # No UI for pydantic-ai compatibility
    try:
        return await tool.execute(file_path)
    except ToolExecutionError as e:
        # Return error message for pydantic-ai compatibility
        return str(e)
