"""File autocomplete dropdown widget for @ mentions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import Input
from textual_autocomplete import AutoComplete, DropdownItem, TargetState

if TYPE_CHECKING:
    from tunacode.core.ui_api.file_filter import FileFilter


class FileAutoComplete(AutoComplete):
    """Real-time @ file autocomplete dropdown."""

    def __init__(self, target: Input) -> None:
        self._filter: FileFilter | None = None
        super().__init__(target)

    def _align_to_target(self) -> None:
        """Align dropdown above the input bar instead of below."""
        from textual.geometry import Offset, Region, Spacing

        x, y = self.target.cursor_screen_offset
        dropdown = self.option_list
        width, height = dropdown.outer_size

        # Position above the cursor and keep the dropdown constrained to screen bounds.
        x, y, _width, _height = Region(x - 1, y - height - 1, width, height).constrain(
            "inside",
            "none",
            Spacing.all(0),
            self.screen.scrollable_content_region,
        )
        self.absolute_offset = Offset(x, y)

    def _get_filter(self) -> FileFilter:
        file_filter = self._filter
        if file_filter is None:
            from tunacode.core.ui_api.file_filter import FileFilter

            file_filter = FileFilter()
            self._filter = file_filter
        return file_filter

    def get_search_string(self, target_state: TargetState) -> str:
        """Extract ONLY the part after @ symbol."""
        text = target_state.text
        cursor = target_state.cursor_position
        at_pos = text.rfind("@", 0, cursor)
        if at_pos == -1:
            return ""
        prefix_region = text[at_pos + 1 : cursor]
        if " " in prefix_region:
            return ""
        return prefix_region

    def get_candidates(self, target_state: TargetState) -> list[DropdownItem]:
        """Return file candidates for current search."""
        search = self.get_search_string(target_state)
        at_pos = target_state.text.rfind("@", 0, target_state.cursor_position)
        if at_pos == -1:
            return []
        candidates = self._get_filter().complete(search)
        return [DropdownItem(main=f"@{path}") for path in candidates]

    def apply_completion(self, value: str, state: TargetState) -> None:
        """Replace @path region with completed value."""
        text = state.text
        cursor = state.cursor_position
        at_pos = text.rfind("@", 0, cursor)
        if at_pos != -1:
            new_text = text[:at_pos] + value + text[cursor:]
            self.target.value = new_text
            self.target.cursor_position = at_pos + len(value)
