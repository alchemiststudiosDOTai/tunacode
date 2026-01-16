"""Tests for slim update_file renderer."""

from __future__ import annotations

from tunacode.ui.renderers.tools.update_file import (
    build_diff_viewport,
    parse_update_file_result,
)


def test_parse_update_file_result_extracts_stats() -> None:
    """Parse result extracts additions and deletions."""
    result = """File 'src/test.py' updated successfully.

--- a/src/test.py
+++ b/src/test.py
@@ -10,3 +10,5 @@
 context line
-removed line
+added line 1
+added line 2
"""
    data = parse_update_file_result(None, result)
    assert data is not None
    assert data.additions == 2
    assert data.deletions == 1
    assert data.filepath == "src/test.py"


def test_build_diff_viewport_with_colors() -> None:
    """Diff viewport returns proper line structure."""
    diff = """--- a/file.py
+++ b/file.py
@@ -1,3 +1,4 @@
 context
-removed
+added
+new
"""
    viewport, shown, total = build_diff_viewport(diff, max_lines=10)
    assert shown > 0
    assert total > 0
