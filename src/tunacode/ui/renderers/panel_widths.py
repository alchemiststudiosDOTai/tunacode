"""Width helpers for panel renderers."""

from __future__ import annotations

from tunacode.constants import TOOL_PANEL_HORIZONTAL_INSET


def tool_panel_frame_width(max_line_width: int) -> int:
    """Return tool panel frame width including borders and padding.

    Preconditions:
        - max_line_width is already clamped to a positive value.
    """
    return max_line_width + TOOL_PANEL_HORIZONTAL_INSET
