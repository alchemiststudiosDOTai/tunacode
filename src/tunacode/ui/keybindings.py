"""Key binding handlers for TunaCode UI."""

import logging
import time

from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings

from ..core.state import StateManager

logger = logging.getLogger(__name__)


def create_key_bindings(state_manager: StateManager | None = None) -> KeyBindings:
    kb = KeyBindings()

    # --- ESC double-press state (closure) ---
    esc_last = 0.0
    esc_snapshot = {"text": "", "cursor": 0}
    ESC_WINDOW = 3.0  # seconds

    @kb.add("enter")
    def _submit(event):
        event.current_buffer.validate_and_handle()

    @kb.add("c-o")  # ctrl+o => newline
    def _newline(event):
        event.current_buffer.insert_text("\n")

    @kb.add("escape")
    def _escape(event):
        """First ESC: flash 'hit esc to stop'.
        Second ESC within 3s: cancel/stop, keep prompt & restore same input."""
        nonlocal esc_last, esc_snapshot

        now = time.time()
        first_press = (now - esc_last) > ESC_WINDOW
        esc_last = now

        if first_press:
            # Take a snapshot of the current input so we can *guarantee* we restore it.
            buf = event.current_buffer
            esc_snapshot["text"] = buf.document.text
            esc_snapshot["cursor"] = buf.document.cursor_position

            # Flash a transient message and redraw prompt.
            run_in_terminal(lambda: print("⚠️  Hit ESC again within 3s to stop"))
            return

        # Second ESC within window → stop/cancel anything running, keep the prompt.
        try:
            if state_manager:
                # Invalidate generation to stop output immediately
                state_manager.invalidate_generation()
                # Cancel active task
                state_manager.cancel_active()
                logger.debug("Generation invalidated and task cancelled.")
        except Exception as e:
            logger.debug("ESC stop error: %r", e)

        # Restore the exact same input line (text + cursor) and stay in the prompt.
        buf = event.current_buffer
        buf.set_document(
            Document(esc_snapshot["text"], cursor_position=esc_snapshot["cursor"]),
            bypass_readonly=True,
        )
        run_in_terminal(lambda: print("⏹️  Stopped."))

    return kb
