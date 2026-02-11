"""Slash command autocomplete dropdown widget."""

from __future__ import annotations

from textual.widgets import Input
from textual_autocomplete import AutoComplete, DropdownItem, TargetState

from tunacode.ui.commands import COMMANDS

# Pre-compute sorted command items at module load.
_COMMAND_ITEMS: list[tuple[str, str]] = sorted(
    [(name, cmd.description) for name, cmd in COMMANDS.items()]
)


class CommandAutoComplete(AutoComplete):
    """Real-time / command autocomplete dropdown."""

    def __init__(self, target: Input) -> None:
        super().__init__(target)

    def get_search_string(self, target_state: TargetState) -> str:
        """Extract text after / symbol at start of input."""
        text = target_state.text
        if not text.startswith("/"):
            return ""

        prefix = text[1 : target_state.cursor_position]
        return "" if " " in prefix else prefix

    def should_show_dropdown(self, search_string: str) -> bool:  # noqa: ARG002
        """Show dropdown only while typing command (before space)."""
        del search_string
        if self.option_list.option_count == 0:
            return False
        # Hide once user has typed a space (command complete, now typing args)
        target_state = self._get_target_state()
        if not target_state.text.startswith("/"):
            return False
        # Check if there's a space before cursor (command already entered)
        prefix = target_state.text[1 : target_state.cursor_position]
        return " " not in prefix

    def get_candidates(self, target_state: TargetState) -> list[DropdownItem]:
        """Return command candidates for current search."""
        if not target_state.text.startswith("/"):
            return []

        search = self.get_search_string(target_state).lower()
        return [
            DropdownItem(main=f"/{name} - {desc}")
            for name, desc in _COMMAND_ITEMS
            if name.startswith(search)
        ]

    def apply_completion(self, value: str, state: TargetState) -> None:
        """Replace /command region with completed value, always add trailing space."""
        command = value.split(" - ", 1)[0]  # Extracts "/model" from "/model - description"
        trailing = state.text[state.cursor_position :].lstrip()
        new_text = command + " " + trailing
        self.target.value = new_text
        self.target.cursor_position = len(command) + 1
