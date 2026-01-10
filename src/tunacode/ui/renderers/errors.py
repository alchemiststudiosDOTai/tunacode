"""Error Panel System for Textual TUI."""

from __future__ import annotations

from rich.console import RenderableType

from tunacode.ui.renderers.panels import ErrorDisplayData, RichPanelRenderer

ERROR_SEVERITY_MAP: dict[str, str] = {
    "ToolExecutionError": "error",
    "FileOperationError": "error",
    "AgentError": "error",
    "GitOperationError": "error",
    "GlobalRequestTimeoutError": "error",
    "ToolBatchingJSONError": "error",
    "ConfigurationError": "warning",
    "ModelConfigurationError": "warning",
    "ValidationError": "warning",
    "SetupValidationError": "warning",
    "UserAbortError": "info",
    "StateError": "info",
}

EXCEPTION_CONTEXT_ATTRS: dict[str, str] = {
    "tool_name": "Tool",
    "path": "Path",
    "operation": "Operation",
    "server_name": "Server",
    "model": "Model",
    "step": "Step",
    "validation_type": "Validation",
}


def _extract_exception_context(exc: Exception) -> dict[str, str]:
    context: dict[str, str] = {}
    for attr, label in EXCEPTION_CONTEXT_ATTRS.items():
        if hasattr(exc, attr):
            value = getattr(exc, attr)
            if value is not None:
                context[label] = str(value)
    return context


DEFAULT_RECOVERY_COMMANDS: dict[str, list[str]] = {
    "ConfigurationError": [
        "tunacode --setup  # Run setup wizard",
        "cat ~/.config/tunacode.json  # Check config",
    ],
    "ModelConfigurationError": [
        "/model  # List available models",
        "tunacode --setup  # Reconfigure",
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


def render_exception(exc: Exception) -> RenderableType:
    error_type = type(exc).__name__
    severity = ERROR_SEVERITY_MAP.get(error_type, "error")

    suggested_fix = getattr(exc, "suggested_fix", None)
    recovery_commands = getattr(exc, "recovery_commands", None)

    context = _extract_exception_context(exc)

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
) -> RenderableType:
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
) -> RenderableType:
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
) -> RenderableType:
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


def render_user_abort() -> RenderableType:
    data = ErrorDisplayData(
        error_type="Operation Cancelled",
        message="User cancelled the operation",
        severity="info",
    )

    return RichPanelRenderer.render_error(data)


def render_catastrophic_error(exc: Exception, context: str | None = None) -> RenderableType:
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
