"""
Module: tunacode.tools.write_file

File writing tool for agent operations in the TunaCode application.
Provides safe file creation with conflict detection and encoding handling.
"""

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import defusedxml.ElementTree as ET
from pydantic_ai.exceptions import ModelRetry

from tunacode.exceptions import ToolExecutionError
from tunacode.tools.base import FileBasedTool
from tunacode.tools.decorator import tool_definition
from tunacode.tools.registry import ToolCategory
from tunacode.types import ToolResult

logger = logging.getLogger(__name__)


@tool_definition(
    name="Write",
    category=ToolCategory.WRITE,
    description="Writes a file to the local filesystem, fails if file already exists",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The absolute path to the file to write",
            },
            "content": {
                "type": "string",
                "description": "The content to write to the file",
            },
        },
        "required": ["file_path", "content"],
    },
    example_args={"file_path": "/path/to/new_file.py", "content": "print('Hello World')"},
    brief="Create new files with content",
)
class WriteFileTool(FileBasedTool):
    """Tool for writing content to new files."""

    @property
    def tool_name(self) -> str:
        return "Write"

    @lru_cache(maxsize=1)
    def _get_base_prompt(self) -> str:
        """Load and return the base prompt from XML file.

        Returns:
            str: The loaded prompt from XML or a default prompt
        """
        try:
            # Load prompt from XML file
            prompt_file = Path(__file__).parent / "prompts" / "write_file_prompt.xml"
            if prompt_file.exists():
                tree = ET.parse(prompt_file)
                root = tree.getroot()
                description = root.find("description")
                if description is not None:
                    return description.text.strip()
        except Exception as e:
            logger.warning(f"Failed to load XML prompt for write_file: {e}")

        # Fallback to default prompt
        return """Writes a file to the local filesystem"""

    @lru_cache(maxsize=1)
    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get the parameters schema for write_file tool.

        Returns:
            Dict containing the JSON schema for tool parameters
        """
        # Try to load from XML first
        try:
            prompt_file = Path(__file__).parent / "prompts" / "write_file_prompt.xml"
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
            logger.warning(f"Failed to load parameters from XML for write_file: {e}")

        # Fallback to hardcoded schema
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute path to the file to write",
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file",
                },
            },
            "required": ["file_path", "content"],
        }

    async def _execute(self, filepath: str, content: str) -> ToolResult:
        """Write content to a new file. Fails if the file already exists.

        Args:
            filepath: The path to the file to write to.
            content: The content to write to the file.

        Returns:
            ToolResult: A message indicating success.

        Raises:
            ModelRetry: If the file already exists
            Exception: Any file writing errors
        """
        # Prevent overwriting existing files with this tool.
        if os.path.exists(filepath):
            # Use ModelRetry to guide the LLM
            raise ModelRetry(
                f"File '{filepath}' already exists. "
                "Use the `update_file` tool to modify it, or choose a different filepath."
            )

        # Create directories if they don't exist
        dirpath = os.path.dirname(filepath)
        if dirpath and not os.path.exists(dirpath):
            os.makedirs(dirpath, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as file:
            file.write(content)

        return f"Successfully wrote to new file: {filepath}"

    def _format_args(self, filepath: str, content: str = None) -> str:
        """Format arguments, truncating content for display."""
        if content is not None and len(content) > 50:
            return f"{repr(filepath)}, content='{content[:47]}...'"
        return super()._format_args(filepath, content)


# Create the function that maintains the existing interface
async def write_file(filepath: str, content: str) -> str:
    """
    Write content to a new file. Fails if the file already exists.
    Requires confirmation before writing.

    Args:
        filepath: The path to the file to write to.
        content: The content to write to the file.

    Returns:
        A message indicating the success or failure of the operation.
    """
    tool = WriteFileTool(None)  # No UI for pydantic-ai compatibility
    try:
        return await tool.execute(filepath, content)
    except ToolExecutionError as e:
        # Return error message for pydantic-ai compatibility
        return str(e)
