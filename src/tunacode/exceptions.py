"""
TunaCode CLI exception hierarchy.

This module defines all custom exceptions used throughout the TunaCode CLI.
All exceptions inherit from TunaCodeError for easy catching of any TunaCode-specific error.
"""

from tunacode.types import ErrorMessage, FilePath, OriginalError, ToolName


class TunaCodeError(Exception):
    """Base exception for all TunaCode errors."""

    pass


# Configuration and Setup Exceptions
class ConfigurationError(TunaCodeError):
    """Raised when there's a configuration issue."""

    pass


# User Interaction Exceptions
class UserAbortError(TunaCodeError):
    """Raised when user aborts an operation."""

    pass


class ValidationError(TunaCodeError):
    """Raised when input validation fails."""

    pass


# Tool and Agent Exceptions
class ToolExecutionError(TunaCodeError):
    """Raised when a tool fails to execute."""

    def __init__(
        self, tool_name: ToolName, message: ErrorMessage, original_error: OriginalError = None
    ):
        self.tool_name = tool_name
        self.original_error = original_error
        super().__init__(f"Tool '{tool_name}' failed: {message}")


class AgentError(TunaCodeError):
    """Raised when agent operations fail."""

    pass


# State Management Exceptions
class StateError(TunaCodeError):
    """Raised when there's an issue with application state."""

    pass


# External Service Exceptions
class ServiceError(TunaCodeError):
    """Base exception for external service failures."""

    pass


class MCPError(ServiceError):
    """Raised when MCP server operations fail."""

    def __init__(
        self, server_name: str, message: ErrorMessage, original_error: OriginalError = None
    ):
        self.server_name = server_name
        self.original_error = original_error
        super().__init__(f"MCP server '{server_name}' error: {message}")


class GitOperationError(ServiceError):
    """Raised when Git operations fail."""

    def __init__(self, operation: str, message: ErrorMessage, original_error: OriginalError = None):
        self.operation = operation
        self.original_error = original_error
        super().__init__(f"Git {operation} failed: {message}")


# File System Exceptions
class FileOperationError(TunaCodeError):
    """Raised when file system operations fail."""

    def __init__(
        self,
        operation: str,
        path: FilePath,
        message: ErrorMessage,
        original_error: OriginalError = None,
    ):
        self.operation = operation
        self.path = path
        self.original_error = original_error
        super().__init__(f"File {operation} failed for '{path}': {message}")


class TooBroadPatternError(ToolExecutionError):
    """Raised when a search pattern is too broad and times out."""

    def __init__(self, pattern: str, timeout_seconds: float):
        self.pattern = pattern
        self.timeout_seconds = timeout_seconds
        super().__init__(
            "grep",
            f"Pattern '{pattern}' is too broad - no matches found within {timeout_seconds}s. "
            "Please use a more specific pattern.",
        )


class ToolBatchingJSONError(TunaCodeError):
    """Raised when JSON parsing fails during tool batching after all retries are exhausted."""

    def __init__(
        self,
        json_content: str,
        retry_count: int,
        original_error: OriginalError = None,
    ):
        self.json_content = json_content
        self.retry_count = retry_count
        self.original_error = original_error
        
        # Truncate JSON content for display if too long
        display_content = (
            json_content[:100] + "..." if len(json_content) > 100 else json_content
        )
        
        super().__init__(
            f"The model is having issues with tool batching. "
            f"JSON parsing failed after {retry_count} retries. "
            f"Invalid JSON: {display_content}"
        )
