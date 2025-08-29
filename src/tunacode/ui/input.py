"""User input handling functions for TunaCode UI."""

from typing import Optional

from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.validation import Validator

from tunacode.constants import UI_PROMPT_PREFIX
from tunacode.core.state import StateManager

from .completers import create_completer
from .keybindings import create_key_bindings
from .lexers import FileReferenceLexer
from .prompt_manager import PromptConfig, PromptManager


def formatted_text(text: str) -> HTML:
    """Create formatted HTML text."""
    return HTML(text)


async def input(
    session_key: str,
    pretext: str = UI_PROMPT_PREFIX,
    is_password: bool = False,
    validator: Optional[Validator] = None,
    multiline: bool = False,
    key_bindings: Optional[KeyBindings] = None,
    placeholder: Optional[HTML] = None,
    completer=None,
    lexer=None,
    timeoutlen: float = 0.05,
    state_manager: Optional[StateManager] = None,
) -> str:
    """
    Prompt for user input using simplified prompt management.

    Args:
        session_key: The session key for the prompt
        pretext: The text to display before the input prompt
        is_password: Whether to mask the input
        validator: Optional input validator
        multiline: Whether to allow multiline input
        key_bindings: Optional custom key bindings
        placeholder: Optional placeholder text
        completer: Optional completer for tab completion
        lexer: Optional lexer for syntax highlighting
        timeoutlen: Timeout length for input
        state_manager: The state manager for session storage

    Returns:
        User input string
    """
    # Create prompt configuration
    config = PromptConfig(
        multiline=multiline,
        is_password=is_password,
        validator=validator,
        key_bindings=key_bindings,
        placeholder=placeholder,
        completer=completer,
        lexer=lexer,
        timeoutlen=timeoutlen,
    )

    # Create prompt manager
    manager = PromptManager(state_manager)

    # Get user input
    return await manager.get_input(session_key, pretext, config)


async def multiline_input(
    state_manager: Optional[StateManager] = None, command_registry=None
) -> str:
    """Get multiline input from the user with @file completion and highlighting."""
    kb = create_key_bindings(state_manager)

    # Clear any residual terminal output
    import sys

    sys.stdout.flush()

    # Full placeholder with all keyboard shortcuts
    placeholder = formatted_text(
        (
            "<darkgrey>"
            "<bold>Enter</bold> to submit • "
            "<bold>Esc + Enter</bold> for new line • "
            "<bold>Esc twice</bold> to cancel • "
            "<bold>Shift + Tab</bold> toggle plan mode • "
            "<bold>/help</bold> for commands"
            "</darkgrey>"
        )
    )

    # Create models registry for auto-completion (lazy loaded)
    from ..utils.models_registry import ModelsRegistry
    models_registry = ModelsRegistry()
    # Note: Registry will be loaded lazily by the completer when needed

    # Display input area (Plan Mode indicator is handled dynamically in prompt manager)
    result = await input(
        "multiline",
        pretext="> ",
        key_bindings=kb,
        multiline=True,
        placeholder=placeholder,
        completer=create_completer(command_registry, models_registry),
        lexer=FileReferenceLexer(),
        state_manager=state_manager,
    )

    return result
