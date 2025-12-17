"""LSP client orchestrator for diagnostic feedback.

This module provides the public API for getting diagnostics from language servers.
It manages server lifecycle and provides formatted diagnostic output.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from tunacode.lsp.client import LSPClient
from tunacode.lsp.servers import get_server_command

if TYPE_CHECKING:
    from tunacode.lsp.client import Diagnostic

__all__ = ["get_diagnostics", "format_diagnostics"]

# Cache of active LSP clients by server command
_clients: dict[str, LSPClient] = {}


async def get_diagnostics(filepath: Path | str, timeout: float = 5.0) -> list["Diagnostic"]:
    """Get diagnostics for a file from the appropriate language server.

    Args:
        filepath: Path to the file to check
        timeout: Maximum time to wait for diagnostics in seconds

    Returns:
        List of diagnostics, empty if server unavailable or no errors
    """
    path = Path(filepath).resolve()

    if not path.exists():
        return []

    command = get_server_command(path)
    if command is None:
        return []

    command_key = " ".join(command)

    if command_key not in _clients:
        client = LSPClient(command=command, root=path.parent)
        started = await client.start()
        if not started:
            return []
        _clients[command_key] = client

    client = _clients[command_key]
    return await client.get_diagnostics(path, timeout=timeout)


MAX_DIAGNOSTIC_MESSAGE_LENGTH = 80
MAX_DIAGNOSTICS_COUNT = 10


def _truncate_message(message: str) -> str:
    """Truncate verbose diagnostic messages to first line, max length.

    Pyright produces verbose multi-line type explanations.
    We keep only the first line (the actionable part).
    """
    first_line = message.split("\n")[0].strip()
    if len(first_line) > MAX_DIAGNOSTIC_MESSAGE_LENGTH:
        return first_line[: MAX_DIAGNOSTIC_MESSAGE_LENGTH - 3] + "..."
    return first_line


def format_diagnostics(diagnostics: list["Diagnostic"]) -> str:
    """Format diagnostics as XML block for tool output.

    Args:
        diagnostics: List of diagnostics to format

    Returns:
        Formatted XML string or empty string if no diagnostics
    """
    if not diagnostics:
        return ""

    # Count by severity for summary
    errors = sum(1 for d in diagnostics if d.severity == "error")
    warnings = sum(1 for d in diagnostics if d.severity == "warning")

    lines: list[str] = ["<file_diagnostics>"]

    # Add summary line (helps agent understand severity quickly)
    lines.append(f"Summary: {errors} errors, {warnings} warnings")

    for diag in diagnostics[:MAX_DIAGNOSTICS_COUNT]:
        severity = diag.severity.capitalize()
        line = diag.line
        message = _truncate_message(diag.message)
        lines.append(f"{severity} (line {line}): {message}")

    lines.append("</file_diagnostics>")

    return "\n".join(lines)


async def shutdown_all() -> None:
    """Shutdown all active LSP clients."""
    for client in _clients.values():
        await client.shutdown()
    _clients.clear()
