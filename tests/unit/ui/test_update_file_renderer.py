from __future__ import annotations

from pathlib import Path

from rich.table import Table

from tunacode.ui.renderers.tools.update_file import (
    DiffSideBySideLine,
    UpdateFileData,
    _renderer,
)

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


def test_parse_side_by_side_rows() -> None:
    diff = """--- a/src/file.py
+++ b/src/file.py
@@ -1,3 +1,3 @@
-old line 1
+new line 1
 context line
"""

    rows = _renderer._parse_side_by_side_rows(diff)

    assert rows == [
        DiffSideBySideLine(1, "old line 1", None, "", "delete"),
        DiffSideBySideLine(None, "", 1, "new line 1", "insert"),
        DiffSideBySideLine(2, "context line", 2, "context line", "context"),
    ]


def test_build_viewport_returns_table_for_side_by_side_diff() -> None:
    diff = """--- a/src/file.py
+++ b/src/file.py
@@ -1,2 +1,2 @@
-old line
+new line
"""
    data = UpdateFileData(
        filepath="src/file.py",
        filename="file.py",
        root_path=Path("."),
        message="File updated",
        diff_content=diff,
        additions=1,
        deletions=1,
        hunks=1,
        diagnostics_block=None,
    )

    viewport = _renderer.build_viewport(data, TEST_MAX_LINE_WIDTH)

    assert isinstance(viewport, Table)
