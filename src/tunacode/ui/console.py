"""Main console coordination module for TunaCode UI.

Provides high-level console functions and coordinates between different UI components.
"""

# Import and re-export all functions from specialized modules
# Lazy loading of Rich components
from typing import TYPE_CHECKING, Any, Optional

from .input import formatted_text, input, multiline_input
from .keybindings import create_key_bindings
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
    update_spinner_message,
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

if TYPE_CHECKING:
    from rich.console import Console as RichConsole

_console: Optional["RichConsole"] = None
_keybindings: Optional[Any] = None


def get_console() -> "RichConsole":
    """Get or create the Rich console instance lazily."""
    global _console
    if _console is None:
        from rich.console import Console as RichConsole

        _console = RichConsole(force_terminal=True, legacy_windows=False)
    return _console


def get_markdown() -> type:
    """Get the Markdown class lazily."""
    from rich.markdown import Markdown

    return Markdown


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


# Create lazy console object for backward compatibility
class _LazyConsole:
    """Lazy console accessor."""

    def __str__(self):
        return str(get_console())

    def __getattr__(self, name):
        return getattr(get_console(), name)


# Create lazy key bindings object for backward compatibility
class _LazyKeyBindings:
    """Lazy key bindings accessor."""

    def __str__(self):
        return str(get_keybindings())

    def __getattr__(self, name):
        return getattr(get_keybindings(), name)


def get_keybindings() -> Any:
    """Get key bindings lazily."""
    global _keybindings
    if _keybindings is None:
        _keybindings = create_key_bindings()
    return _keybindings


# Module-level lazy instances
console = _LazyConsole()
kb = _LazyKeyBindings()


# Re-export markdown utility for backward compatibility
def markdown(text: str) -> Any:
    """Create a Markdown object lazily."""
    Markdown = get_markdown()
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
    "update_spinner_message",
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
