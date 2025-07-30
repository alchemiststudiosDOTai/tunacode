"""Key binding handlers for TunaCode UI."""

import logging
import time

from prompt_toolkit.application import run_in_terminal
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
        """Handle ESC key with double-press logic: first press warns, second cancels."""
        if not state_manager:
            logger.debug("Escape key pressed without state manager")
            return

        current_time = time.time()
        session = state_manager.session

        # Reset counter if too much time has passed (3 seconds timeout)
        if session.last_esc_time and (current_time - session.last_esc_time) > 3.0:
            session.esc_press_count = 0

        session.esc_press_count += 1
        session.last_esc_time = current_time

        logger.debug(f"ESC key pressed: count={session.esc_press_count}, time={current_time}")

        if session.esc_press_count == 1:
            # First ESC press - show warning message
            from ..ui.output import warning

            run_in_terminal(lambda: warning("Hit ESC again within 3 seconds to cancel operation"))
            logger.debug("First ESC press - showing warning")
        else:
            # Second ESC press - cancel operation
            session.esc_press_count = 0  # Reset counter
            logger.debug("Second ESC press - initiating cancellation")

            # Mark the session as being cancelled to prevent new operations
            session.operation_cancelled = True

            current_task = session.current_task
            if current_task and not current_task.done():
                logger.debug(f"Cancelling current task: {current_task}")
                try:
                    current_task.cancel()
                    logger.debug("Task cancellation initiated successfully")
                except Exception as e:
                    logger.debug(f"Failed to cancel task: {e}")
            else:
                logger.debug(f"No active task to cancel: current_task={current_task}")

            # Force exit the current input by raising KeyboardInterrupt
            # This will be caught by the prompt manager and converted to UserAbortError
            logger.debug("Raising KeyboardInterrupt to abort current operation")
            raise KeyboardInterrupt()

    return kb
