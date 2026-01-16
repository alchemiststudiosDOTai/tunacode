from __future__ import annotations

from tunacode.ui.renderers.tools.update_file import _renderer

EXTRA_CHAR_COUNT: int = 1
FILLER_CHAR: str = "a"
SINGLE_LINE_COUNT: int = 1
TEST_MAX_LINE_WIDTH: int = 64


def test_truncate_diff_caps_line_width() -> None:
    overlong_length: int = TEST_MAX_LINE_WIDTH + EXTRA_CHAR_COUNT
    overlong_line: str = FILLER_CHAR * overlong_length
    diff_content: str = overlong_line

    truncated, shown, total = _renderer._truncate_diff(diff_content, TEST_MAX_LINE_WIDTH)

    assert truncated == overlong_line
    assert shown == SINGLE_LINE_COUNT
    assert total == SINGLE_LINE_COUNT
