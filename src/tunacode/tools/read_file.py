"""
Module: tunacode.tools.read_file

File reading tool for agent operations in the TunaCode application.
Provides safe file reading with size limits and proper error handling.
"""

import asyncio
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import defusedxml.ElementTree as ET

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
        """Load and return the base prompt from XML file.

        Returns:
            str: The loaded prompt from XML or a default prompt
        """
        try:
            # Load prompt from XML file
            prompt_file = Path(__file__).parent / "prompts" / "read_file_prompt.xml"
            if prompt_file.exists():
                tree = ET.parse(prompt_file)
                root = tree.getroot()
                description = root.find("description")
                if description is not None:
                    return description.text.strip()
        except Exception as e:
            logger.warning(f"Failed to load XML prompt for read_file: {e}")

        # Fallback to default prompt
        return """Reads a file from the local filesystem"""

    @lru_cache(maxsize=1)
    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get the parameters schema for read_file tool.

        Returns:
            Dict containing the JSON schema for tool parameters
        """
        # Try to load from XML first
        try:
            prompt_file = Path(__file__).parent / "prompts" / "read_file_prompt.xml"
            if prompt_file.exists():
                tree = ET.parse(prompt_file)
                root = tree.getroot()
                parameters = root.find("parameters")
                if parameters is not None:
                    schema: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}
                    required_fields: List[str] = []

                    for param in parameters.findall("parameter"):
                        name = param.get("name")
                        required = param.get("required", "false").lower() == "true"
                        param_type = param.find("type")
                        description = param.find("description")

                        if name and param_type is not None:
                            prop = {
                                "type": param_type.text.strip(),
                                "description": description.text.strip()
                                if description is not None
                                else "",
                            }

                            schema["properties"][name] = prop
                            if required:
                                required_fields.append(name)

                    schema["required"] = required_fields
                    return schema
        except Exception as e:
            logger.warning(f"Failed to load parameters from XML for read_file: {e}")

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

    async def _execute(self, filepath: str) -> ToolResult:
        """Read the contents of a file.

        Args:
            filepath: The path to the file to read.

        Returns:
            ToolResult: The contents of the file or an error message.

        Raises:
            Exception: Any file reading errors
        """
        # Add a size limit to prevent reading huge files
        if os.path.getsize(filepath) > MAX_FILE_SIZE:
            err_msg = ERROR_FILE_TOO_LARGE.format(filepath=filepath) + MSG_FILE_SIZE_LIMIT
            if self.ui:
                await self.ui.error(err_msg)
            raise ToolExecutionError(tool_name=self.tool_name, message=err_msg, original_error=None)

        # Run the blocking file I/O in a separate thread to avoid blocking the event loop
        def _read_sync(path: str) -> str:
            """Synchronous helper to read file contents (runs in thread)."""
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

        content: str = await asyncio.to_thread(_read_sync, filepath)
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
async def read_file(filepath: str) -> str:
    """
    Read the contents of a file.

    Args:
        filepath: The path to the file to read.

    Returns:
        str: The contents of the file or an error message.
    """
    tool = ReadFileTool(None)  # No UI for pydantic-ai compatibility
    try:
        return await tool.execute(filepath)
    except ToolExecutionError as e:
        # Return error message for pydantic-ai compatibility
        return str(e)
