"""Tests for base tool renderer utility functions.

Source: src/tunacode/ui/renderers/tools/base.py
"""

from __future__ import annotations

from pathlib import Path

from tunacode.core.ui_api.constants import MIN_TOOL_PANEL_LINE_WIDTH

# Force registration of all tool renderers so get_renderer / list_renderers work.
import tunacode.ui.renderers.tools  # noqa: F401
from tunacode.ui.renderers.tools.base import (
    clamp_content_width,
    get_renderer,
    list_renderers,
    pad_lines,
    relative_path,
    truncate_content,
    truncate_line,
)

# ---------------------------------------------------------------------------
# truncate_line
# ---------------------------------------------------------------------------


class TestTruncateLine:
    """Truncate a single line to max_width, appending '...' when trimmed."""

    def test_short_line_unchanged(self) -> None:
        assert truncate_line("hello", 10) == "hello"

    def test_exact_width_unchanged(self) -> None:
        assert truncate_line("hello", 5) == "hello"

    def test_long_line_truncated_with_ellipsis(self) -> None:
        result = truncate_line("hello world", 8)
        assert result == "hello..."
        assert len(result) == 8

    def test_very_short_max_width(self) -> None:
        result = truncate_line("abcdefgh", 4)
        assert result == "a..."
        assert len(result) == 4

    def test_empty_line_unchanged(self) -> None:
        assert truncate_line("", 10) == ""


# ---------------------------------------------------------------------------
# truncate_content
# ---------------------------------------------------------------------------


class TestTruncateContent:
    """Truncate multi-line content to max_lines, returning (str, shown, total)."""

    def test_content_within_limit(self) -> None:
        content = "line1\nline2\nline3"
        result, shown, total = truncate_content(content, max_lines=5, max_width=80)
        assert shown == total == 3
        assert result == content

    def test_content_over_limit(self) -> None:
        content = "a\nb\nc\nd\ne"
        result, shown, total = truncate_content(content, max_lines=3, max_width=80)
        assert shown == 3
        assert total == 5
        assert result == "a\nb\nc"

    def test_exact_line_count(self) -> None:
        content = "x\ny\nz"
        result, shown, total = truncate_content(content, max_lines=3, max_width=80)
        assert shown == total == 3
        assert result == content

    def test_single_line_within_limit(self) -> None:
        content = "only one line"
        result, shown, total = truncate_content(content, max_lines=5, max_width=80)
        assert shown == 1
        assert total == 1
        assert result == content

    def test_empty_content(self) -> None:
        result, shown, total = truncate_content("", max_lines=5, max_width=80)
        assert shown == total == 0  # "".splitlines() returns []
        assert result == ""


# ---------------------------------------------------------------------------
# pad_lines
# ---------------------------------------------------------------------------


class TestPadLines:
    """Pad a list of lines to a minimum height."""

    def test_fewer_lines_padded(self) -> None:
        lines = ["a", "b"]
        result = pad_lines(lines, min_lines=5)
        assert len(result) == 5
        assert result[:2] == ["a", "b"]
        assert all(line == "" for line in result[2:])

    def test_exact_count_unchanged(self) -> None:
        lines = ["a", "b", "c"]
        result = pad_lines(lines, min_lines=3)
        assert result == ["a", "b", "c"]

    def test_more_lines_unchanged(self) -> None:
        lines = ["a", "b", "c", "d", "e"]
        result = pad_lines(lines, min_lines=3)
        assert result == lines

    def test_empty_list_padded(self) -> None:
        result = pad_lines([], min_lines=2)
        assert len(result) == 2
        assert all(line == "" for line in result)

    def test_original_list_not_mutated(self) -> None:
        original = ["x"]
        result = pad_lines(original, min_lines=3)
        assert len(original) == 1
        assert len(result) == 3


# ---------------------------------------------------------------------------
# clamp_content_width
# ---------------------------------------------------------------------------


class TestClampContentWidth:
    """Clamp content width to avoid negative or zero widths after prefix."""

    def test_normal_case(self) -> None:
        result = clamp_content_width(80, 10)
        assert result == 70

    def test_small_width_returns_minimum(self) -> None:
        result = clamp_content_width(5, 10)
        assert result == MIN_TOOL_PANEL_LINE_WIDTH

    def test_exact_minimum(self) -> None:
        # When max_line_width - reserved == MIN_TOOL_PANEL_LINE_WIDTH
        result = clamp_content_width(
            MIN_TOOL_PANEL_LINE_WIDTH + 10,
            10,
        )
        assert result == MIN_TOOL_PANEL_LINE_WIDTH

    def test_zero_reserved(self) -> None:
        result = clamp_content_width(80, 0)
        assert result == 80

    def test_equal_widths(self) -> None:
        result = clamp_content_width(10, 10)
        assert result == max(MIN_TOOL_PANEL_LINE_WIDTH, 0)


# ---------------------------------------------------------------------------
# relative_path
# ---------------------------------------------------------------------------


class TestRelativePath:
    """Return filepath relative to root_path when possible."""

    def test_absolute_inside_root(self) -> None:
        root = Path("/home/user/project")
        result = relative_path("/home/user/project/src/main.py", root)
        assert result == "src/main.py"

    def test_absolute_outside_root(self) -> None:
        root = Path("/home/user/project")
        result = relative_path("/tmp/other/file.py", root)
        assert result == "/tmp/other/file.py"

    def test_relative_path_returned_as_is(self) -> None:
        root = Path("/home/user/project")
        result = relative_path("src/main.py", root)
        assert result == "src/main.py"

    def test_root_itself(self) -> None:
        root = Path("/home/user/project")
        result = relative_path("/home/user/project", root)
        assert result == "."

    def test_nested_deep_path(self) -> None:
        root = Path("/home/user/project")
        result = relative_path(
            "/home/user/project/src/core/agents/main.py",
            root,
        )
        assert result == "src/core/agents/main.py"

    def test_relative_dotslash_path(self) -> None:
        root = Path("/home/user/project")
        result = relative_path("./tests/test_foo.py", root)
        assert result == "tests/test_foo.py"


# ---------------------------------------------------------------------------
# get_renderer
# ---------------------------------------------------------------------------


class TestGetRenderer:
    """Look up registered render functions by tool name."""

    def test_known_tool_returns_function(self) -> None:
        renderer = get_renderer("bash")
        assert renderer is not None
        assert callable(renderer)

    def test_unknown_tool_returns_none(self) -> None:
        renderer = get_renderer("nonexistent_tool_xyz")
        assert renderer is None

    def test_glob_renderer_registered(self) -> None:
        assert get_renderer("glob") is not None

    def test_grep_renderer_registered(self) -> None:
        assert get_renderer("grep") is not None

    def test_read_file_renderer_registered(self) -> None:
        assert get_renderer("read_file") is not None

    def test_write_file_renderer_registered(self) -> None:
        assert get_renderer("write_file") is not None

    def test_list_dir_renderer_registered(self) -> None:
        assert get_renderer("list_dir") is not None

    def test_web_fetch_renderer_registered(self) -> None:
        assert get_renderer("web_fetch") is not None


# ---------------------------------------------------------------------------
# list_renderers
# ---------------------------------------------------------------------------


class TestListRenderers:
    """Get sorted list of registered tool renderer names."""

    def test_returns_sorted_list(self) -> None:
        names = list_renderers()
        assert names == sorted(names)

    def test_contains_known_tools(self) -> None:
        names = list_renderers()
        for tool in ("bash", "glob", "grep", "list_dir", "read_file", "write_file"):
            assert tool in names, f"Expected '{tool}' in registered renderers"

    def test_returns_list_type(self) -> None:
        result = list_renderers()
        assert isinstance(result, list)

    def test_no_duplicates(self) -> None:
        names = list_renderers()
        assert len(names) == len(set(names))
