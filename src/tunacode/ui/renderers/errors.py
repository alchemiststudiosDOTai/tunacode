"""Error Panel System for Textual TUI."""

from __future__ import annotations

from rich.console import RenderableType

from tunacode.exceptions import (
    AgentError,
    ConfigurationError,
    ContextOverflowError,
    FileOperationError,
    GitOperationError,
    ModelConfigurationError,
    SetupValidationError,
    ToolExecutionError,
    TunaCodeError,
    ValidationError,
)
from tunacode.ui.renderers.panels import ErrorDisplayData, RichPanelRenderer
from tunacode.ui.widgets.chat import PanelMeta

ERROR_SEVERITY_MAP: dict[str, str] = {
    "ToolExecutionError": "error",
    "FileOperationError": "error",
    "AgentError": "error",
    "GitOperationError": "error",
    "GlobalRequestTimeoutError": "error",
    "ContextOverflowError": "error",
    "ToolBatchingJSONError": "error",
    "AuthenticationError": "error",
    "ConfigurationError": "warning",
    "ModelConfigurationError": "warning",
    "ValidationError": "warning",
    "SetupValidationError": "warning",
    "UserAbortError": "info",
    "StateError": "info",
}

def _extract_tunacode_exception_context(exc: TunaCodeError) -> dict[str, str]:
    match exc:
        case ToolExecutionError(tool_name=tool_name):
            return {"Tool": str(tool_name)}
        case FileOperationError(path=path, operation=operation):
            return {"Path": str(path), "Operation": str(operation)}
        case GitOperationError(operation=operation):
            return {"Operation": str(operation)}
        case ModelConfigurationError(model=model) | ContextOverflowError(model=model):
            return {"Model": str(model)}
        case SetupValidationError(validation_type=validation_type):
            return {"Validation": str(validation_type)}
        case _:
            return {}


def _extract_tunacode_exception_metadata(
    exc: TunaCodeError,
) -> tuple[str | None, list[str] | None]:
    match exc:
        case ToolExecutionError(suggested_fix=suggested_fix, recovery_commands=recovery_commands):
            return suggested_fix, recovery_commands
        case (
            ConfigurationError(suggested_fix=suggested_fix)
            | ValidationError(suggested_fix=suggested_fix)
            | AgentError(suggested_fix=suggested_fix)
        ):
            return suggested_fix, None
        case _:
            return None, None


DEFAULT_RECOVERY_COMMANDS: dict[str, list[str]] = {
    "ConfigurationError": [
        "tunacode --setup  # Run setup wizard",
        "cat ~/.config/tunacode.json  # Check config",
    ],
    "ModelConfigurationError": [
        "/model  # List available models",
        "tunacode --setup  # Reconfigure",
    ],
    "AuthenticationError": [
        "/model  # Pick model and enter API key",
        "tunacode --setup  # Re-run guided setup",
        "cat ~/.config/tunacode.json  # Verify env key is present",
    ],
    "FileOperationError": [
        "ls -la <path>  # Check permissions",
        "pwd  # Verify current directory",
    ],
    "GitOperationError": [
        "git status  # Check repository state",
        "git stash  # Stash uncommitted changes",
    ],
    "GlobalRequestTimeoutError": [
        "Check network connectivity",
        "Increase timeout in tunacode.json",
    ],
}


def render_exception(exc: Exception) -> tuple[RenderableType, PanelMeta]:
    error_type = type(exc).__name__
    severity = ERROR_SEVERITY_MAP.get(error_type, "error")

    suggested_fix = None
    recovery_commands = None
    context: dict[str, str] = {}
    if isinstance(exc, TunaCodeError):
        suggested_fix, recovery_commands = _extract_tunacode_exception_metadata(exc)
        context = _extract_tunacode_exception_context(exc)

    if not recovery_commands:
        recovery_commands = DEFAULT_RECOVERY_COMMANDS.get(error_type)

    message = str(exc)
    for prefix in ("Fix: ", "Suggested fix: ", "Recovery commands:"):
        if prefix in message:
            message = message.split(prefix)[0].strip()

    data = ErrorDisplayData(
        error_type=error_type,
        message=message,
        suggested_fix=suggested_fix,
        recovery_commands=recovery_commands,
        context=context if context else None,
        severity=severity,
    )

    return RichPanelRenderer.render_error(data)


def render_tool_error(
    tool_name: str,
    message: str,
    suggested_fix: str | None = None,
    file_path: str | None = None,
) -> tuple[RenderableType, PanelMeta]:
    context = {}
    if file_path:
        context["Path"] = file_path
        recovery_commands = [
            f"Check file exists: ls -la {file_path}",
            "Try with different arguments",
        ]
    else:
        recovery_commands = ["Try with different arguments"]

    data = ErrorDisplayData(
        error_type=f"{tool_name} Error",
        message=message,
        suggested_fix=suggested_fix,
        recovery_commands=recovery_commands,
        context=context if context else None,
        severity="error",
    )

    return RichPanelRenderer.render_error(data)


def render_validation_error(
    field: str,
    message: str,
    valid_examples: list[str] | None = None,
) -> tuple[RenderableType, PanelMeta]:
    suggested_fix = None
    if valid_examples:
        suggested_fix = f"Valid examples: {', '.join(valid_examples[:3])}"

    data = ErrorDisplayData(
        error_type="Validation Error",
        message=f"{field}: {message}",
        suggested_fix=suggested_fix,
        context={"Field": field},
        severity="warning",
    )

    return RichPanelRenderer.render_error(data)


def render_connection_error(
    service: str,
    message: str,
    retry_available: bool = True,
) -> tuple[RenderableType, PanelMeta]:
    recovery = []
    if retry_available:
        recovery.append("Retry the operation")
    recovery.extend(
        [
            "Check network connectivity",
            f"Verify {service} service status",
        ]
    )

    data = ErrorDisplayData(
        error_type=f"{service} Connection Error",
        message=message,
        recovery_commands=recovery,
        severity="error",
    )

    return RichPanelRenderer.render_error(data)


def render_user_abort() -> tuple[RenderableType, PanelMeta]:
    data = ErrorDisplayData(
        error_type="Operation Cancelled",
        message="User cancelled the operation",
        severity="info",
    )

    return RichPanelRenderer.render_error(data)


def render_catastrophic_error(
    exc: Exception, context: str | None = None
) -> tuple[RenderableType, PanelMeta]:
    """Render a user-friendly error when something goes very wrong.

    This is the catch-all error display for unexpected failures.
    Shows a clear message asking the user to try again.
    """
    error_details = str(exc)[:200] if str(exc) else type(exc).__name__

    data = ErrorDisplayData(
        error_type="Something Went Wrong",
        message="An unexpected error occurred. Please try again.",
        suggested_fix="If this persists, check the logs or report the issue.",
        context={"Details": error_details} if error_details else None,
        severity="error",
    )

    return RichPanelRenderer.render_error(data)
