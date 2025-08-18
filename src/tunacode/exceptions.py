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

    def __init__(self, message: str, suggested_fix: str = None, help_url: str = None):
        self.suggested_fix = suggested_fix
        self.help_url = help_url

        # Build enhanced error message with actionable guidance
        full_message = message
        if suggested_fix:
            full_message += f"\n\n💡 Suggested fix: {suggested_fix}"
        if help_url:
            full_message += f"\n📖 More help: {help_url}"

        super().__init__(full_message)


# User Interaction Exceptions
class UserAbortError(TunaCodeError):
    """Raised when user aborts an operation."""

    pass


class ValidationError(TunaCodeError):
    """Raised when input validation fails."""

    def __init__(self, message: str, suggested_fix: str = None, valid_examples: list = None):
        self.suggested_fix = suggested_fix
        self.valid_examples = valid_examples or []

        # Build enhanced error message with actionable guidance
        full_message = f"Validation failed: {message}"
        if suggested_fix:
            full_message += f"\n\n💡 Suggested fix: {suggested_fix}"
        if valid_examples:
            examples_text = "\n".join(f"  • {example}" for example in valid_examples)
            full_message += f"\n\n✅ Valid examples:\n{examples_text}"

        super().__init__(full_message)


# Tool and Agent Exceptions
class ToolExecutionError(TunaCodeError):
    """Raised when a tool fails to execute."""

    def __init__(
        self,
        tool_name: ToolName,
        message: ErrorMessage,
        original_error: OriginalError = None,
        suggested_fix: str = None,
        recovery_commands: list = None,
    ):
        self.tool_name = tool_name
        self.original_error = original_error
        self.suggested_fix = suggested_fix
        self.recovery_commands = recovery_commands or []

        # Build enhanced error message
        full_message = f"Tool '{tool_name}' failed: {message}"
        if suggested_fix:
            full_message += f"\n\n💡 Suggested fix: {suggested_fix}"
        if recovery_commands:
            commands_text = "\n".join(f"  • {cmd}" for cmd in recovery_commands)
            full_message += f"\n\n🔧 Recovery commands:\n{commands_text}"

        super().__init__(full_message)


class AgentError(TunaCodeError):
    """Raised when agent operations fail."""

    def __init__(self, message: str, suggested_fix: str = None, troubleshooting_steps: list = None):
        self.suggested_fix = suggested_fix
        self.troubleshooting_steps = troubleshooting_steps or []

        # Build enhanced error message
        full_message = f"Agent error: {message}"
        if suggested_fix:
            full_message += f"\n\n💡 Suggested fix: {suggested_fix}"
        if troubleshooting_steps:
            steps_text = "\n".join(
                f"  {i + 1}. {step}" for i, step in enumerate(troubleshooting_steps)
            )
            full_message += f"\n\n🔍 Troubleshooting steps:\n{steps_text}"

        super().__init__(full_message)


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


# Additional specialized exception classes for onboarding scenarios
class OnboardingError(TunaCodeError):
    """Raised when onboarding process encounters issues."""

    def __init__(
        self, message: str, step: str = None, suggested_fix: str = None, help_command: str = None
    ):
        self.step = step
        self.suggested_fix = suggested_fix
        self.help_command = help_command

        # Build enhanced error message
        full_message = f"Onboarding failed: {message}"
        if step:
            full_message = f"Onboarding failed at step '{step}': {message}"
        if suggested_fix:
            full_message += f"\n\n💡 Suggested fix: {suggested_fix}"
        if help_command:
            full_message += f"\n🆘 For help: {help_command}"

        super().__init__(full_message)


class ModelConfigurationError(ConfigurationError):
    """Raised when model configuration is invalid."""

    def __init__(self, model: str, issue: str, valid_models: list = None):
        self.model = model
        self.issue = issue
        self.valid_models = valid_models or []

        suggested_fix = "Use --wizard for guided setup or --model with a valid model name"
        help_url = "https://docs.anthropic.com/en/docs/claude-code"

        message = f"Model '{model}' configuration error: {issue}"
        if valid_models:
            examples = valid_models[:3]  # Show first 3 examples
            suggested_fix += f"\n\nValid examples: {', '.join(examples)}"

        super().__init__(message, suggested_fix=suggested_fix, help_url=help_url)


class SetupValidationError(ValidationError):
    """Raised when setup validation fails."""

    def __init__(self, validation_type: str, details: str, quick_fixes: list = None):
        self.validation_type = validation_type
        self.details = details
        self.quick_fixes = quick_fixes or []

        suggested_fix = "Run 'tunacode --wizard' for guided setup"
        if quick_fixes:
            suggested_fix = f"Try these quick fixes: {', '.join(quick_fixes)}"

        super().__init__(
            f"{validation_type} validation failed: {details}",
            suggested_fix=suggested_fix,
            valid_examples=["tunacode --wizard", "tunacode --setup", "tunacode --help"],
        )


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
        display_content = json_content[:100] + "..." if len(json_content) > 100 else json_content

        super().__init__(
            f"The model is having issues with tool batching. "
            f"JSON parsing failed after {retry_count} retries. "
            f"Invalid JSON: {display_content}"
        )
