"""Positioning helpers for editor autocomplete dropdowns."""

from __future__ import annotations

from textual.geometry import Offset, Region, Spacing
from textual_autocomplete import AutoComplete


def align_autocomplete_above_target(autocomplete: AutoComplete) -> None:
    """Align an autocomplete dropdown above its target cursor."""
    x, y = autocomplete.target.cursor_screen_offset
    dropdown = autocomplete.option_list
    width, height = dropdown.outer_size

    x, y, _width, _height = Region(x - 1, y - height - 1, width, height).constrain(
        "inside",
        "none",
        Spacing.all(0),
        autocomplete.screen.scrollable_content_region,
    )
    autocomplete.absolute_offset = Offset(x, y)
