"""Key binding handlers for TunaCode UI."""

import logging

from prompt_toolkit.key_binding import KeyBindings

from ..core.state import StateManager

logger = logging.getLogger(__name__)


def create_key_bindings(state_manager: StateManager = None) -> KeyBindings:
    """Create and configure key bindings for the UI."""
    kb = KeyBindings()

    @kb.add("enter")
    def _submit(event):
        """Submit the current buffer."""
        event.current_buffer.validate_and_handle()

    @kb.add("c-o")  # ctrl+o
    def _newline(event):
        """Insert a newline character."""
        event.current_buffer.insert_text("\n")

    @kb.add("escape", "enter")
    def _escape_enter(event):
        """Insert a newline when escape then enter is pressed."""
        event.current_buffer.insert_text("\n")

    @kb.add("escape")
    def _escape(event):
        """Handle ESC key - simulate validation with special escape signal."""
        logger.debug("ESC key pressed - using validation bypass for clean exit")

        # Cancel any active task if present
        if state_manager and hasattr(state_manager.session, "current_task"):
            current_task = state_manager.session.current_task
            if current_task and not current_task.done():
                logger.debug(f"Cancelling current task: {current_task}")
                try:
                    current_task.cancel()
                    logger.debug("Task cancellation initiated successfully")
                except Exception as e:
                    logger.debug(f"Failed to cancel task: {e}")

        # Set a special escape marker in the buffer and validate to complete the input
        # This allows the input to complete normally but with a signal that it was escaped
        event.current_buffer.text = "__TUNACODE_ESC_SIGNAL__"
        event.current_buffer.validate_and_handle()

    @kb.add("s-tab")  # shift+tab
    def _toggle_plan_mode(event):
        """Toggle between Plan Mode and normal mode."""
        if state_manager:
            from rich.console import Console
            console = Console()
            
            # Toggle the state
            if state_manager.is_plan_mode():
                state_manager.exit_plan_mode()
                logger.debug("Toggled to normal mode via Shift+Tab")
                # Move cursor up 2 lines and clear the Plan Mode indicator
                print("\033[2A\033[K", end="", flush=True)
                print("")  # Empty line for spacing
                print("\033[1B", end="", flush=True)  # Move back down
            else:
                state_manager.enter_plan_mode()
                logger.debug("Toggled to Plan Mode via Shift+Tab")
                # Move cursor up 2 lines and show the Plan Mode indicator
                print("\033[2A", end="", flush=True)
                console.print("⏸  PLAN MODE ON", style="bold #40E0D0")
                print("\033[1B", end="", flush=True)  # Move back down
            
            # Refresh the display without submitting
            event.app.invalidate()

    return kb
