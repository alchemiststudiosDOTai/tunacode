"""LSP client orchestrator for diagnostic feedback.

This module provides the public API for getting diagnostics from language servers.
It manages server lifecycle and provides formatted diagnostic output.
"""

from pathlib import Path

from tunacode.lsp.client import Diagnostic, LSPClient
from tunacode.lsp.diagnostics import truncate_diagnostic_message
from tunacode.lsp.servers import get_server_command

__all__ = ["get_diagnostics", "format_diagnostics"]


_clients: dict[str, LSPClient] = {}

WORKSPACE_MARKERS: tuple[str, ...] = (
    ".git",
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "requirements.txt",
    "Pipfile",
    "package.json",
    "Cargo.toml",
    "go.mod",
)


def _resolve_workspace_root(path: Path) -> Path:
    start_dir = path if path.is_dir() else path.parent

    for candidate in (start_dir, *start_dir.parents):
        if any((candidate / marker).exists() for marker in WORKSPACE_MARKERS):
            return candidate

    return start_dir


async def get_diagnostics(filepath: Path | str, timeout: float = 5.0) -> list[Diagnostic]:
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

    root = _resolve_workspace_root(path)
    command = get_server_command(path)
    if command is None:
        return []

    command_key = " ".join(command)
    client_key = f"{root}::{command_key}"

    if client_key not in _clients:
        client = LSPClient(command=command, root=root)
        started = await client.start()
        if not started:
            return []
        _clients[client_key] = client

    client = _clients[client_key]
    return await client.get_diagnostics(path, timeout=timeout)


MAX_DIAGNOSTICS_COUNT = 10


def format_diagnostics(diagnostics: list[Diagnostic]) -> str:
    """Format diagnostics as XML block for tool output.

    Args:
        diagnostics: List of diagnostics to format

    Returns:
        Formatted XML string or empty string if no diagnostics
    """
    if not diagnostics:
        return ""

    errors = sum(1 for d in diagnostics if d.severity == "error")
    warnings = sum(1 for d in diagnostics if d.severity == "warning")

    lines: list[str] = ["<file_diagnostics>"]

    if errors > 0:
        lines.append(f"ACTION REQUIRED: {errors} error(s) found - fix before continuing")
        if warnings > 0:
            lines.append(f"Additional: {warnings} warning(s)")
    else:
        lines.append(f"Summary: {warnings} warning(s)")

    for diag in diagnostics[:MAX_DIAGNOSTICS_COUNT]:
        severity = diag.severity.capitalize()
        line = diag.line
        message = truncate_diagnostic_message(diag.message)
        lines.append(f"{severity} (line {line}): {message}")

    lines.append("</file_diagnostics>")

    return "\n".join(lines)


