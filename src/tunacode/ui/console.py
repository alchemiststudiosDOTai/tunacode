"""Main console coordination module for TunaCode UI.

Provides high-level console functions and coordinates between different UI components.
"""

from rich.console import Console as RichConsole
from rich.markdown import Markdown

# Import and re-export all functions from specialized modules
from .input import formatted_text, input, multiline_input
from .keybindings import create_key_bindings

# Unified UI logger compatibility layer
from .logging_compat import ui_logger
from .output import (
    banner,
    clear,
    line,
    muted,
    print,
    spinner,
    sync_print,
    update_available,
    usage,
    version,
)
from .panels import (
    StreamingAgentPanel,
    agent,
    agent_streaming,
    dump_messages,
    help,
    models,
    panel,
    sync_panel,
    sync_tool_confirm,
    tool_confirm,
)
from .prompt_manager import PromptConfig, PromptManager
from .validators import ModelValidator


# Async wrappers for UI logging
async def info(message: str) -> None:
    await ui_logger.info(message)


async def warning(message: str) -> None:
    await ui_logger.warning(message)


async def error(message: str) -> None:
    await ui_logger.error(message)


async def debug(message: str) -> None:
    await ui_logger.debug(message)


async def success(message: str) -> None:
    await ui_logger.success(message)


# Create console object for backward compatibility
console = RichConsole(force_terminal=True, legacy_windows=False)

# Create key bindings object for backward compatibility
kb = create_key_bindings()


# Re-export markdown utility for backward compatibility
def markdown(text: str) -> Markdown:
    """Create a Markdown object."""
    return Markdown(text)


# All functions are now available through imports above
__all__ = [
    # From input module
    "formatted_text",
    "input",
    "multiline_input",
    # From keybindings module
    "create_key_bindings",
    "kb",
    # From output module
    "banner",
    "clear",
    "console",
    "line",
    "muted",
    "print",
    "spinner",
    "sync_print",
    "update_available",
    "usage",
    "version",
    # Unified logging wrappers
    "info",
    "warning",
    "error",
    "debug",
    "success",
    # From panels module
    "agent",
    "agent_streaming",
    "dump_messages",
    "help",
    "models",
    "panel",
    "StreamingAgentPanel",
    "sync_panel",
    "sync_tool_confirm",
    "tool_confirm",
    # From prompt_manager module
    "PromptConfig",
    "PromptManager",
    # From validators module
    "ModelValidator",
    # Local utilities
    "markdown",
]
