"""LSP diagnostics helpers shared by file tools."""

from __future__ import annotations

import asyncio
from pathlib import Path

from tunacode.configuration.defaults import DEFAULT_USER_CONFIG
from tunacode.configuration.user_config import load_config
from tunacode.types import LspSettings

from tunacode.tools.lsp import format_diagnostics, get_diagnostics

LSP_DEFAULT_TIMEOUT_SECONDS: float = 5.0
LSP_ORCHESTRATION_OVERHEAD_SECONDS: float = 1.0


def _get_lsp_settings() -> LspSettings:
    config = load_config()
    if config is None:
        return DEFAULT_USER_CONFIG["settings"]["lsp"]
    return config["settings"]["lsp"]


def is_lsp_enabled() -> bool:
    """Check if LSP diagnostics are enabled in user config."""
    try:
        return _get_lsp_settings()["enabled"]
    except Exception:
        return False


def get_lsp_timeout() -> float:
    """Get LSP timeout from user config."""
    try:
        return _get_lsp_settings()["timeout"]
    except Exception:
        return LSP_DEFAULT_TIMEOUT_SECONDS


async def maybe_prepend_lsp_diagnostics(result: str, filepath: Path) -> str:
    """Return result with LSP diagnostics prepended when enabled."""
    if not is_lsp_enabled():
        return result

    try:
        timeout = get_lsp_timeout()
        diagnostics = await asyncio.wait_for(
            get_diagnostics(filepath, timeout=timeout),
            timeout=timeout + LSP_ORCHESTRATION_OVERHEAD_SECONDS,
        )
        diagnostics_output = format_diagnostics(diagnostics)
        if diagnostics_output:
            return f"{diagnostics_output}\n\n{result}"
    except TimeoutError:
        return result
    except Exception:
        return result

    return result
