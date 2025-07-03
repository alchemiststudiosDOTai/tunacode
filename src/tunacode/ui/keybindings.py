"""Key binding handlers for TunaCode UI."""

from prompt_toolkit.key_binding import KeyBindings


def create_key_bindings() -> KeyBindings:
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

    # Add single Escape key handler for interruption
    @kb.add("escape")
    def _escape_interrupt(event):
        """Handle escape key for potential interruption."""
        # Store that escape was pressed in the app's custom data
        if hasattr(event.app, 'custom_data'):
            event.app.custom_data = {'escape_pressed': True}
        # Don't consume the event - let other handlers process it too

    return kb
