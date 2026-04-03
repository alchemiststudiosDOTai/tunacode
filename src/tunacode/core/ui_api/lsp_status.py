"""UI adapter for querying LSP server status.

This module adds a small UI-facing translation layer over `tools.lsp` so UI
components can request server availability without owning the tool details.

Dependency flow: ui -> core/ui_api/lsp_status -> tools/lsp (valid)
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class LspServerInfo:
    """LSP server information for UI display."""

    server_name: str | None
    """Server binary name (e.g., 'ruff', 'gopls') or None if unsupported."""

    language_id: str | None
    """LSP language ID (e.g., 'python', 'go') or None if unsupported."""

    available: bool
    """True if the server binary exists on PATH."""


def get_lsp_server_info(filepath: Path | str) -> LspServerInfo:
    """Get LSP server info for a file.

    Args:
        filepath: Path to the file to check

    Returns:
        LspServerInfo with server name, language, and availability
    """
    from tunacode.tools.lsp.servers import SERVER_CONFIG, get_language_id, get_server_command

    path = Path(filepath)
    ext = path.suffix.lower()

    config = SERVER_CONFIG.get(ext)
    if config is None:
        return LspServerInfo(server_name=None, language_id=None, available=False)

    language_id = get_language_id(path)
    command = get_server_command(path)

    if command is None:
        # Server configured but binary not found
        # Extract server name from config for display
        _, command_options = config
        first_command = command_options[0] if command_options else []
        server_name = first_command[0] if first_command else None
        return LspServerInfo(server_name=server_name, language_id=language_id, available=False)

    # Server available
    server_name = command[0]
    return LspServerInfo(server_name=server_name, language_id=language_id, available=True)
