"""Slash command autocomplete dropdown widget."""

from __future__ import annotations

from textual.widgets import Input
from textual_autocomplete import AutoComplete, DropdownItem, TargetState

from tunacode.ui.commands import COMMANDS

# Pre-compute sorted command items at module load (8 items)
_COMMAND_ITEMS: list[tuple[str, str]] = sorted(
    [(name, cmd.description) for name, cmd in COMMANDS.items()]
)


class CommandAutoComplete(AutoComplete):
    """Real-time / command autocomplete dropdown."""

    def __init__(self, target: Input) -> None:
        """
        Initialize the CommandAutoComplete bound to a specific input widget.
        
        Parameters:
            target (Input): The input widget this autocomplete will attach to and drive.
        """
        super().__init__(target)

    def get_search_string(self, target_state: TargetState) -> str:
        """
        Return the command prefix typed after a leading "/" up to the cursor, if valid.
        
        Parameters:
            target_state (TargetState): Current input state; used to read the input text and cursor position.
        
        Returns:
            str: The substring after the initial "/" and before the cursor position, or an empty string if the input does not start with "/" or the extracted prefix contains a space.
        """
        text = target_state.text
        if not text.startswith("/"):
            return ""

        prefix = text[1 : target_state.cursor_position]
        return "" if " " in prefix else prefix

    def should_show_dropdown(self, search_string: str) -> bool:  # noqa: ARG002
        """
        Determine whether the autocomplete dropdown should be visible while the user is typing a slash command.
        
        The dropdown is shown only when there are candidate items, the input starts with "/", and the cursor is still within the command name (i.e., there is no space typed before the cursor). The provided `search_string` parameter is ignored.
        
        Returns:
            `true` if the dropdown should be shown, `false` otherwise.
        """
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
        """
        Produce dropdown items matching the current slash-command prefix.
        
        If the input does not start with "/", returns an empty list. Otherwise returns DropdownItem objects for each command whose name starts with the current search string; each item's main text is formatted as "/{name} - {description}".
        
        Returns:
            list[DropdownItem]: Matching command candidates, or an empty list if no match or input does not start with "/".
        """
        if not target_state.text.startswith("/"):
            return []

        search = self.get_search_string(target_state).lower()
        return [
            DropdownItem(main=f"/{name} - {desc}")
            for name, desc in _COMMAND_ITEMS
            if name.startswith(search)
        ]

    def apply_completion(self, value: str, state: TargetState) -> None:
        """
        Replace the leading slash command in the input with the selected command, append a single space, preserve any text after the cursor, and place the cursor immediately after the inserted command.
        
        Parameters:
            value (str): Selected dropdown text, expected in the form "/name - description".
            state (TargetState): Current input state used to obtain the text after the cursor and the cursor position.
        """
        command = value.split(" - ", 1)[0]  # Extracts "/model" from "/model - description"
        trailing = state.text[state.cursor_position :].lstrip()
        new_text = command + " " + trailing
        self.target.value = new_text
        self.target.cursor_position = len(command) + 1