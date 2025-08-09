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
        """Handle ESC key - trigger Ctrl+C behavior."""
        logger.debug("ESC key pressed - simulating Ctrl+C")

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

        # Trigger the same behavior as Ctrl+C by sending the signal
        import os
        import signal
        os.kill(os.getpid(), signal.SIGINT)

    @kb.add("s-tab")  # shift+tab
    def _toggle_plan_mode(event):
        """Toggle between Plan Mode and normal mode."""
        if state_manager:
            # Toggle the state
            if state_manager.is_plan_mode():
                state_manager.exit_plan_mode()
                logger.debug("Toggled to normal mode via Shift+Tab")
            else:
                state_manager.enter_plan_mode()
                logger.debug("Toggled to Plan Mode via Shift+Tab")

            # Clear the current buffer and refresh the display
            event.current_buffer.reset()

            # Force a refresh of the application without exiting
            event.app.invalidate()

    return kb
