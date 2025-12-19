from __future__ import annotations

from tunacode.constants import MAX_PANEL_LINE_WIDTH
from tunacode.ui.renderers.tools import update_file as update_file_renderer

EXTRA_CHAR_COUNT: int = 1
FILLER_CHAR: str = "a"
SINGLE_LINE_COUNT: int = 1


def test_truncate_diff_caps_line_width() -> None:
    overlong_length: int = MAX_PANEL_LINE_WIDTH + EXTRA_CHAR_COUNT
    overlong_line: str = FILLER_CHAR * overlong_length
    diff_content: str = overlong_line

    truncated, shown, total = update_file_renderer._truncate_diff(diff_content)

    expected_line_prefix: str = FILLER_CHAR * MAX_PANEL_LINE_WIDTH
    expected_line: str = f"{expected_line_prefix}{update_file_renderer.LINE_TRUNCATION_SUFFIX}"

    assert truncated == expected_line
    assert shown == SINGLE_LINE_COUNT
    assert total == SINGLE_LINE_COUNT
