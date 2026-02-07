"""Tests for panels.py pure helper functions."""

from __future__ import annotations

from tunacode.ui.renderers.panels import (
    PANEL_STYLES,
    PanelType,
    _truncate_content,
    _truncate_search_results,
    _truncate_value,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SHORT_STRING = "hello"
LONG_STRING = "a" * 100
MAX_LENGTH_20 = 20
MAX_LENGTH_10 = 10

SMALL_CONTENT = "line1\nline2\nline3"
LARGE_CONTENT = "\n".join(f"line{i}" for i in range(50))

DEFAULT_MAX_LINE_WIDTH = 80


# ---------------------------------------------------------------------------
# PanelType enum
# ---------------------------------------------------------------------------


class TestPanelType:
    """PanelType enum values exist."""

    def test_tool_value(self) -> None:
        assert PanelType.TOOL == "tool"

    def test_error_value(self) -> None:
        assert PanelType.ERROR == "error"

    def test_search_value(self) -> None:
        assert PanelType.SEARCH == "search"

    def test_info_value(self) -> None:
        assert PanelType.INFO == "info"

    def test_success_value(self) -> None:
        assert PanelType.SUCCESS == "success"

    def test_warning_value(self) -> None:
        assert PanelType.WARNING == "warning"


class TestPanelStyles:
    """PANEL_STYLES has entries for every PanelType."""

    def test_all_panel_types_have_styles(self) -> None:
        for pt in PanelType:
            assert pt in PANEL_STYLES, f"Missing PANEL_STYLES entry for {pt}"

    def test_each_style_has_required_keys(self) -> None:
        required_keys = {"border", "title", "subtitle"}
        for pt in PanelType:
            style = PANEL_STYLES[pt]
            assert required_keys.issubset(style.keys()), (
                f"{pt} style missing keys: {required_keys - style.keys()}"
            )


# ---------------------------------------------------------------------------
# _truncate_value
# ---------------------------------------------------------------------------


class TestTruncateValue:
    """Truncate display values."""

    def test_short_string_returned_as_is(self) -> None:
        result = _truncate_value(SHORT_STRING, max_length=MAX_LENGTH_20)
        assert result == SHORT_STRING

    def test_long_string_truncated_with_ellipsis(self) -> None:
        result = _truncate_value(LONG_STRING, max_length=MAX_LENGTH_20)
        assert len(result) == MAX_LENGTH_20
        assert result.endswith("...")

    def test_non_string_converted_then_truncated(self) -> None:
        result = _truncate_value(12345678901, max_length=MAX_LENGTH_10)
        assert isinstance(result, str)
        assert result == "1234567..."

    def test_exact_length_not_truncated(self) -> None:
        value = "a" * MAX_LENGTH_20
        result = _truncate_value(value, max_length=MAX_LENGTH_20)
        assert result == value
        assert "..." not in result

    def test_one_over_truncated(self) -> None:
        value = "a" * (MAX_LENGTH_20 + 1)
        result = _truncate_value(value, max_length=MAX_LENGTH_20)
        assert len(result) == MAX_LENGTH_20
        assert result.endswith("...")

    def test_list_converted_to_string(self) -> None:
        result = _truncate_value([1, 2, 3], max_length=MAX_LENGTH_20)
        assert isinstance(result, str)

    def test_none_converted_to_string(self) -> None:
        result = _truncate_value(None, max_length=MAX_LENGTH_20)
        assert result == "None"

    def test_boolean_converted_to_string(self) -> None:
        result = _truncate_value(True, max_length=MAX_LENGTH_20)
        assert result == "True"


# ---------------------------------------------------------------------------
# _truncate_content
# ---------------------------------------------------------------------------


class TestTruncateContent:
    """Line-aware content truncation."""

    def test_content_within_limit_returns_all_lines(self) -> None:
        content, shown, total = _truncate_content(
            SMALL_CONTENT,
            max_lines=10,
            max_line_width=DEFAULT_MAX_LINE_WIDTH,
        )
        assert shown == 3
        assert total == 3
        assert content == SMALL_CONTENT

    def test_content_over_limit_truncated(self) -> None:
        content, shown, total = _truncate_content(
            LARGE_CONTENT,
            max_lines=5,
            max_line_width=DEFAULT_MAX_LINE_WIDTH,
        )
        assert shown == 5
        assert total == 50
        assert content.count("\n") == 4  # 5 lines = 4 newline separators

    def test_returns_tuple_of_three(self) -> None:
        result = _truncate_content(
            SMALL_CONTENT,
            max_lines=10,
            max_line_width=DEFAULT_MAX_LINE_WIDTH,
        )
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_empty_content(self) -> None:
        _content, shown, total = _truncate_content(
            "",
            max_lines=10,
            max_line_width=DEFAULT_MAX_LINE_WIDTH,
        )
        assert total == 0  # "".splitlines() returns []
        assert shown == 0

    def test_single_line(self) -> None:
        content, shown, total = _truncate_content(
            "one line",
            max_lines=10,
            max_line_width=DEFAULT_MAX_LINE_WIDTH,
        )
        assert shown == 1
        assert total == 1
        assert content == "one line"

    def test_exact_limit_not_truncated(self) -> None:
        exact_content = "\n".join(f"line{i}" for i in range(5))
        content, shown, total = _truncate_content(
            exact_content,
            max_lines=5,
            max_line_width=DEFAULT_MAX_LINE_WIDTH,
        )
        assert shown == total == 5
        assert content == exact_content


# ---------------------------------------------------------------------------
# _truncate_search_results
# ---------------------------------------------------------------------------


class TestTruncateSearchResults:
    """Truncate search results list."""

    def test_results_within_limit_returns_all(self) -> None:
        results = [{"file": f"f{i}.py"} for i in range(3)]
        truncated, shown, total = _truncate_search_results(results, max_display=10)
        assert truncated == results
        assert shown == 3
        assert total == 3

    def test_results_over_limit_returns_first_max_display(self) -> None:
        results = [{"file": f"f{i}.py"} for i in range(25)]
        truncated, shown, total = _truncate_search_results(results, max_display=5)
        assert len(truncated) == 5
        assert shown == 5
        assert total == 25
        assert truncated == results[:5]

    def test_empty_results(self) -> None:
        truncated, shown, total = _truncate_search_results([], max_display=10)
        assert truncated == []
        assert shown == 0
        assert total == 0

    def test_exact_limit_not_truncated(self) -> None:
        results = [{"file": f"f{i}.py"} for i in range(5)]
        truncated, shown, total = _truncate_search_results(results, max_display=5)
        assert truncated == results
        assert shown == 5
        assert total == 5

    def test_one_over_limit(self) -> None:
        results = [{"file": f"f{i}.py"} for i in range(6)]
        truncated, shown, total = _truncate_search_results(results, max_display=5)
        assert len(truncated) == 5
        assert total == 6

    def test_default_max_display(self) -> None:
        """Default max_display uses MAX_SEARCH_RESULTS_DISPLAY (20)."""
        results = [{"file": f"f{i}.py"} for i in range(25)]
        _truncated, shown, total = _truncate_search_results(results)
        assert shown == 20
        assert total == 25
