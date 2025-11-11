"""Prompt configuration and management for TunaCode UI."""

from dataclasses import dataclass
from typing import Optional

from prompt_toolkit.completion import Completer
from prompt_toolkit.formatted_text import HTML, FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.shortcuts import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.validation import Validator

from tunacode.constants import UI_COLORS
from tunacode.core.state import StateManager
from tunacode.exceptions import UserAbortError


@dataclass
class PromptConfig:
    """Configuration for prompt sessions."""

    multiline: bool = False
    is_password: bool = False
    validator: Optional[Validator] = None
    key_bindings: Optional[KeyBindings] = None
    placeholder: Optional[FormattedText] = None
    completer: Optional[Completer] = None
    lexer: Optional[Lexer] = None
    timeoutlen: float = 0.05


class PromptManager:
    """Manages prompt sessions and their lifecycle."""

    def __init__(self, state_manager: Optional[StateManager] = None):
        """Initialize the prompt manager.

        Args:
            state_manager: Optional state manager for session persistence
        """
        self.state_manager = state_manager
        self._temp_sessions: dict[str, PromptSession] = {}  # For when no state manager is available
        self._style = self._create_style()

    def _create_style(self) -> Style:
        """Create the style for the prompt with file reference highlighting."""
        return Style.from_dict(
            {
                "file-reference": UI_COLORS.get("file_ref", "light_blue"),
            }
        )

    def get_session(self, session_key: str, config: PromptConfig) -> PromptSession:
        """Get or create a prompt session.

        Args:
            session_key: Unique key for the session
            config: Configuration for the session

        Returns:
            PromptSession instance
        """
        if self.state_manager:
            # Use state manager's session storage
            if session_key not in self.state_manager.session.input_sessions:
                self.state_manager.session.input_sessions[session_key] = PromptSession(
                    key_bindings=config.key_bindings,
                    placeholder=config.placeholder,
                    completer=config.completer,
                    lexer=config.lexer,
                    style=self._style,
                )
            return self.state_manager.session.input_sessions[session_key]
        else:
            # Use temporary storage
            if session_key not in self._temp_sessions:
                self._temp_sessions[session_key] = PromptSession(
                    key_bindings=config.key_bindings,
                    placeholder=config.placeholder,
                    completer=config.completer,
                    lexer=config.lexer,
                    style=self._style,
                )
            return self._temp_sessions[session_key]

    async def get_input(self, session_key: str, prompt: str, config: PromptConfig) -> str:
        """Get user input using the specified configuration.

        Args:
            session_key: Unique key for the session
            prompt: The prompt text to display
            config: Configuration for the input

        Returns:
            User input string

        Raises:
            UserAbortError: If user cancels input
        """
        session = self.get_session(session_key, config)

        # Create a custom prompt that changes based on input
        def get_prompt():
            # Start with the base prompt
            base_prompt = prompt

            # Check if current buffer starts with "!"
            if hasattr(session.app, "current_buffer") and session.app.current_buffer:
                text = session.app.current_buffer.text
                if text.startswith("!"):
                    # Use bright yellow background with black text for high visibility
                    return HTML('<style bg="#ffcc00" fg="black"><b> ◆ BASH MODE ◆ </b></style> ')

            return HTML(base_prompt) if isinstance(base_prompt, str) else base_prompt

        try:
            # Get user input with dynamic prompt
            response = await session.prompt_async(
                get_prompt,
                is_password=config.is_password,
                validator=config.validator,
                multiline=config.multiline,
            )

            # Clean up response
            if isinstance(response, str):
                response = response.strip()

            return response

        except (KeyboardInterrupt, EOFError):
            raise UserAbortError
