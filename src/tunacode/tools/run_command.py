"""
Module: tunacode.tools.run_command

Command execution tool for agent operations in the TunaCode application.
Provides controlled shell command execution with output capture and truncation.
"""

import logging
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import defusedxml.ElementTree as ET

from tunacode.constants import (
    CMD_OUTPUT_FORMAT,
    CMD_OUTPUT_NO_ERRORS,
    CMD_OUTPUT_NO_OUTPUT,
    CMD_OUTPUT_TRUNCATED,
    COMMAND_OUTPUT_END_SIZE,
    COMMAND_OUTPUT_START_INDEX,
    COMMAND_OUTPUT_THRESHOLD,
    ERROR_COMMAND_EXECUTION,
    MAX_COMMAND_OUTPUT,
)
from tunacode.exceptions import ToolExecutionError
from tunacode.tools.base import BaseTool
from tunacode.types import ToolResult
from tunacode.utils.security import CommandSecurityError, safe_subprocess_popen

logger = logging.getLogger(__name__)


class RunCommandTool(BaseTool):
    """Tool for running shell commands."""

    @lru_cache(maxsize=1)
    def _get_base_prompt(self) -> str:
        """Load and return the base prompt from XML file.

        Returns:
            str: The loaded prompt from XML or a default prompt
        """
        try:
            # Load prompt from XML file
            prompt_file = Path(__file__).parent / "prompts" / "run_command_prompt.xml"
            if prompt_file.exists():
                tree = ET.parse(prompt_file)
                root = tree.getroot()
                description = root.find("description")
                if description is not None:
                    return description.text.strip()
        except Exception as e:
            logger.warning(f"Failed to load XML prompt for run_command: {e}")

        # Fallback to default prompt
        return """Executes system commands with enhanced control and monitoring capabilities"""

    @lru_cache(maxsize=1)
    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get the parameters schema for run_command tool.

        Returns:
            Dict containing the JSON schema for tool parameters
        """
        # Try to load from XML first
        try:
            prompt_file = Path(__file__).parent / "prompts" / "run_command_prompt.xml"
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
            logger.warning(f"Failed to load parameters from XML for run_command: {e}")

        # Fallback to hardcoded schema
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to execute",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory for the command",
                },
                "env": {
                    "type": "object",
                    "description": "Additional environment variables",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Command timeout in seconds",
                },
                "capture_output": {
                    "type": "boolean",
                    "description": "Whether to capture stdout/stderr",
                },
            },
            "required": ["command"],
        }

    @property
    def tool_name(self) -> str:
        return "Shell"

    async def _execute(self, command: str) -> ToolResult:
        """Run a shell command and return the output.

        Args:
            command: The command to run.

        Returns:
            ToolResult: The output of the command (stdout and stderr).

        Raises:
            FileNotFoundError: If command not found
            CommandSecurityError: If command fails security validation
            Exception: Any command execution errors
        """
        process = None
        try:
            # Use secure subprocess execution with validation
            process = safe_subprocess_popen(
                command,
                shell=True,  # CLI tool requires shell features
                validate=True,  # Enable security validation
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = process.communicate()
        except CommandSecurityError as e:
            # Security validation failed - return error without execution
            return f"Security validation failed: {str(e)}"
        finally:
            # Ensure process cleanup regardless of success or failure
            if process is not None and process.poll() is None:
                try:
                    # Multi-stage escalation: graceful → terminate → kill
                    process.terminate()
                    try:
                        process.wait(timeout=5.0)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=1.0)
                except Exception as cleanup_error:
                    self.logger.warning(f"Failed to cleanup process: {cleanup_error}")

        output = stdout.strip() or CMD_OUTPUT_NO_OUTPUT
        error = stderr.strip() or CMD_OUTPUT_NO_ERRORS
        resp = CMD_OUTPUT_FORMAT.format(output=output, error=error).strip()

        # Truncate if the output is too long to prevent issues
        if len(resp) > MAX_COMMAND_OUTPUT:
            # Include both the beginning and end of the output
            start_part = resp[:COMMAND_OUTPUT_START_INDEX]
            end_part = (
                resp[-COMMAND_OUTPUT_END_SIZE:]
                if len(resp) > COMMAND_OUTPUT_THRESHOLD
                else resp[COMMAND_OUTPUT_START_INDEX:]
            )
            truncated_resp = start_part + CMD_OUTPUT_TRUNCATED + end_part
            return truncated_resp

        return resp

    async def _handle_error(self, error: Exception, command: str = None) -> ToolResult:
        """Handle errors with specific messages for common cases.

        Raises:
            ToolExecutionError: Always raised with structured error information
        """
        if isinstance(error, FileNotFoundError):
            err_msg = ERROR_COMMAND_EXECUTION.format(command=command, error=error)
        elif isinstance(error, CommandSecurityError):
            err_msg = f"Command blocked for security: {str(error)}"
        else:
            # Use parent class handling for other errors
            await super()._handle_error(error, command)
            return  # super() will raise, this is unreachable

        if self.ui:
            await self.ui.error(err_msg)

        raise ToolExecutionError(tool_name=self.tool_name, message=err_msg, original_error=error)

    def _get_error_context(self, command: str = None) -> str:
        """Get error context for command execution."""
        if command:
            return f"running command '{command}'"
        return super()._get_error_context()


# Create the function that maintains the existing interface
async def run_command(command: str) -> str:
    """
    Run a shell command and return the output. User must confirm risky commands.

    Args:
        command (str): The command to run.

    Returns:
        ToolResult: The output of the command (stdout and stderr) or an error message.
    """
    tool = RunCommandTool(None)  # No UI for pydantic-ai compatibility
    try:
        return await tool.execute(command)
    except ToolExecutionError as e:
        # Return error message for pydantic-ai compatibility
        return str(e)
