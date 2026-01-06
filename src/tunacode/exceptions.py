"""
TunaCode CLI exception hierarchy.

This module defines all custom exceptions used throughout the TunaCode CLI.
All exceptions inherit from TunaCodeError for easy catching of any TunaCode-specific error.
"""

from tunacode.types import ErrorMessage, FilePath, OriginalError, ToolName

SECTION_SEPARATOR = "\n\n"
LINE_SEPARATOR = "\n"
BULLET_PREFIX = "  - "
NUMBERED_ITEM_PREFIX = "  {index}. "

SUGGESTED_FIX_LABEL = "Suggested fix"
VALID_EXAMPLES_LABEL = "Valid examples"
RECOVERY_COMMANDS_LABEL = "Recovery commands"
TROUBLESHOOTING_STEPS_LABEL = "Troubleshooting steps"
HELP_LABEL = "More help"

VALIDATION_PREFIX = "Validation failed: "
AGENT_ERROR_PREFIX = "Agent error: "
TOOL_ERROR_PREFIX = "Tool '{tool_name}' failed: "

JSON_TRUNCATION_LIMIT = 100
VALID_MODEL_EXAMPLE_LIMIT = 3


def _format_section(label: str, lines: list[str]) -> str:
    if not lines:
        return ""

    section_header = f"{label}:"
    section_body = LINE_SEPARATOR.join(lines)
    return f"{section_header}{LINE_SEPARATOR}{section_body}"


def _build_error_message(
    base_message: str,
    suggested_fix: str | None = None,
    help_url: str | None = None,
    valid_examples: list[str] | None = None,
    recovery_commands: list[str] | None = None,
    troubleshooting_steps: list[str] | None = None,
) -> str:
    sections: list[str] = []

    if suggested_fix:
        suggested_fix_section = _format_section(SUGGESTED_FIX_LABEL, [suggested_fix])
        sections.append(suggested_fix_section)

    if help_url:
        help_section = _format_section(HELP_LABEL, [help_url])
        sections.append(help_section)

    if valid_examples:
        example_lines = [f"{BULLET_PREFIX}{example}" for example in valid_examples]
        examples_section = _format_section(VALID_EXAMPLES_LABEL, example_lines)
        sections.append(examples_section)

    if recovery_commands:
        recovery_lines = [f"{BULLET_PREFIX}{cmd}" for cmd in recovery_commands]
        recovery_section = _format_section(RECOVERY_COMMANDS_LABEL, recovery_lines)
        sections.append(recovery_section)

    if troubleshooting_steps:
        step_lines = [
            f"{NUMBERED_ITEM_PREFIX.format(index=i + 1)}{step}"
            for i, step in enumerate(troubleshooting_steps)
        ]
        troubleshooting_section = _format_section(TROUBLESHOOTING_STEPS_LABEL, step_lines)
        sections.append(troubleshooting_section)

    if not sections:
        return base_message

    sections_text = SECTION_SEPARATOR.join(sections)
    return f"{base_message}{SECTION_SEPARATOR}{sections_text}"


class TunaCodeError(Exception):
    """Base exception for all TunaCode errors."""

    pass


class ConfigurationError(TunaCodeError):
    """Raised when there's a configuration issue."""

    def __init__(self, message: str, suggested_fix: str | None = None, help_url: str | None = None):
        self.suggested_fix = suggested_fix
        self.help_url = help_url

        full_message = _build_error_message(
            message,
            suggested_fix=suggested_fix,
            help_url=help_url,
        )
        super().__init__(full_message)


# User Interaction Exceptions
class UserAbortError(TunaCodeError):
    """Raised when user aborts an operation."""

    pass


class ValidationError(TunaCodeError):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str,
        suggested_fix: str | None = None,
        valid_examples: list | None = None,
    ):
        self.suggested_fix = suggested_fix
        self.valid_examples = valid_examples or []

        base_message = f"{VALIDATION_PREFIX}{message}"
        full_message = _build_error_message(
            base_message,
            suggested_fix=suggested_fix,
            valid_examples=self.valid_examples,
        )
        super().__init__(full_message)


# Tool and Agent Exceptions
class ToolDeniedError(TunaCodeError):
    """Raised when a tool is blocked by authorization (e.g., plan mode)."""

    def __init__(self, tool_name: ToolName, reason: str = "blocked by plan mode"):
        self.tool_name = tool_name
        self.reason = reason
        super().__init__(f"Tool '{tool_name}' denied: {reason}")


class ToolExecutionError(TunaCodeError):
    """Raised when a tool fails to execute."""

    def __init__(
        self,
        tool_name: ToolName,
        message: ErrorMessage,
        original_error: OriginalError = None,
        suggested_fix: str | None = None,
        recovery_commands: list | None = None,
    ):
        self.tool_name = tool_name
        self.original_error = original_error
        self.suggested_fix = suggested_fix
        self.recovery_commands = recovery_commands or []

        base_message = TOOL_ERROR_PREFIX.format(tool_name=tool_name) + str(message)
        full_message = _build_error_message(
            base_message,
            suggested_fix=suggested_fix,
            recovery_commands=self.recovery_commands,
        )
        super().__init__(full_message)


class AgentError(TunaCodeError):
    """Raised when agent operations fail."""

    def __init__(
        self,
        message: str,
        suggested_fix: str | None = None,
        troubleshooting_steps: list | None = None,
    ):
        self.suggested_fix = suggested_fix
        self.troubleshooting_steps = troubleshooting_steps or []

        base_message = f"{AGENT_ERROR_PREFIX}{message}"
        full_message = _build_error_message(
            base_message,
            suggested_fix=suggested_fix,
            troubleshooting_steps=self.troubleshooting_steps,
        )
        super().__init__(full_message)


# State Management Exceptions
class StateError(TunaCodeError):
    """Raised when there's an issue with application state."""

    pass


# External Service Exceptions
class ServiceError(TunaCodeError):
    """Base exception for external service failures."""

    pass


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


class ModelConfigurationError(ConfigurationError):
    """Raised when model configuration is invalid."""

    def __init__(self, model: str, issue: str, valid_models: list | None = None):
        self.model = model
        self.issue = issue
        self.valid_models = valid_models or []

        suggested_fix = "Use --setup for guided setup or --model with a valid model name"
        help_url = "https://docs.anthropic.com/en/docs/claude-code"

        message = f"Model '{model}' configuration error: {issue}"
        if valid_models:
            examples = valid_models[:VALID_MODEL_EXAMPLE_LIMIT]
            suggested_fix += f"\n\nValid examples: {', '.join(examples)}"

        super().__init__(message, suggested_fix=suggested_fix, help_url=help_url)


class SetupValidationError(ValidationError):
    """Raised when setup validation fails."""

    def __init__(self, validation_type: str, details: str, quick_fixes: list | None = None):
        self.validation_type = validation_type
        self.details = details
        self.quick_fixes = quick_fixes or []

        suggested_fix = "Run 'tunacode --setup' for guided setup"
        if quick_fixes:
            suggested_fix = f"Try these quick fixes: {', '.join(quick_fixes)}"

        super().__init__(
            f"{validation_type} validation failed: {details}",
            suggested_fix=suggested_fix,
            valid_examples=["tunacode --setup", "tunacode --help"],
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


class GlobalRequestTimeoutError(TunaCodeError):
    """Raised when a request exceeds the global timeout limit."""

    def __init__(self, timeout_seconds: float):
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Request exceeded global timeout of {timeout_seconds}s. "
            f"The model API may be slow or unresponsive. "
            f"Try increasing settings.global_request_timeout in tunacode.json "
            f"or check model API status."
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
        truncated_content = json_content[:JSON_TRUNCATION_LIMIT]
        display_content = (
            f"{truncated_content}..." if len(json_content) > JSON_TRUNCATION_LIMIT else json_content
        )

        super().__init__(
            f"The model is having issues with tool batching. "
            f"JSON parsing failed after {retry_count} retries. "
            f"Invalid JSON: {display_content}"
        )


class AggregateToolError(TunaCodeError):
    """Raised when multiple tools fail in parallel execution after retries exhausted."""

    def __init__(self, failures: list[tuple[str, Exception]]):
        self.failures = failures
        tool_names = [name for name, _ in failures]
        super().__init__(f"Multiple tools failed: {', '.join(tool_names)}")
