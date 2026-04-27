"""Error Panel System for Textual TUI."""

from __future__ import annotations

from rich.console import RenderableType

from tunacode.exceptions import (
    AgentError,
    ConfigurationError,
    ContextOverflowError,
    FileOperationError,
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
    "GlobalRequestTimeoutError": "error",
    "ContextOverflowError": "error",
    "ConfigurationError": "warning",
    "ValidationError": "warning",
    "UserAbortError": "info",
}


def _extract_tunacode_exception_context(exc: TunaCodeError) -> dict[str, str]:
    match exc:
        case ToolExecutionError(tool_name=tool_name):
            return {"Tool": str(tool_name)}
        case FileOperationError(path=path, operation=operation):
            return {"Path": str(path), "Operation": str(operation)}
        case ContextOverflowError(model=model):
            return {"Model": str(model)}
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
    "FileOperationError": [
        "ls -la <path>  # Check permissions",
        "pwd  # Verify current directory",
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
