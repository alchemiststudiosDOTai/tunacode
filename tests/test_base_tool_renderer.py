"""Tests for BaseToolRenderer helper functions and registry."""

from tunacode.constants import MAX_PANEL_LINE_WIDTH, MIN_VIEWPORT_LINES, TOOL_VIEWPORT_LINES
from tunacode.ui.renderers.tools.base import (
    RendererConfig,
    get_renderer,
    list_renderers,
    pad_lines,
    tool_renderer,
    truncate_content,
    truncate_line,
)


class TestTruncateLine:
    """Tests for truncate_line()."""

    def test_short_line_unchanged(self):
        """Lines under max_width are returned unchanged."""
        line = "short line"
        result = truncate_line(line, max_width=50)
        assert result == line

    def test_exact_length_unchanged(self):
        """Lines exactly at max_width are unchanged."""
        line = "x" * 50
        result = truncate_line(line, max_width=50)
        assert result == line

    def test_long_line_truncated(self):
        """Lines over max_width are truncated with ellipsis."""
        line = "x" * 60
        result = truncate_line(line, max_width=50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_uses_default_max_width(self):
        """Uses MAX_PANEL_LINE_WIDTH as default."""
        line = "x" * (MAX_PANEL_LINE_WIDTH + 10)
        result = truncate_line(line)
        assert len(result) == MAX_PANEL_LINE_WIDTH
        assert result.endswith("...")

    def test_empty_line(self):
        """Empty lines are unchanged."""
        assert truncate_line("") == ""


class TestTruncateContent:
    """Tests for truncate_content()."""

    def test_short_content_unchanged(self):
        """Content under limits is unchanged."""
        content = "line1\nline2\nline3"
        result, shown, total = truncate_content(content, max_lines=10, max_width=100)
        assert result == content
        assert shown == 3
        assert total == 3

    def test_truncates_lines(self):
        """Content over max_lines is truncated."""
        lines = [f"line{i}" for i in range(20)]
        content = "\n".join(lines)
        result, shown, total = truncate_content(content, max_lines=5, max_width=100)
        assert shown == 5
        assert total == 20
        assert result.count("\n") == 4  # 5 lines = 4 newlines

    def test_truncates_width(self):
        """Long lines are truncated."""
        content = "x" * 100
        result, shown, total = truncate_content(content, max_lines=10, max_width=50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_uses_defaults(self):
        """Uses TOOL_VIEWPORT_LINES and MAX_PANEL_LINE_WIDTH as defaults."""
        lines = [f"line{i}" for i in range(TOOL_VIEWPORT_LINES + 5)]
        content = "\n".join(lines)
        result, shown, total = truncate_content(content)
        assert shown == TOOL_VIEWPORT_LINES
        assert total == TOOL_VIEWPORT_LINES + 5

    def test_empty_content(self):
        """Empty content returns empty result."""
        result, shown, total = truncate_content("")
        assert result == ""
        assert shown == 0  # splitlines on "" gives []
        assert total == 0


class TestPadLines:
    """Tests for pad_lines()."""

    def test_short_list_padded(self):
        """Lists under min_lines are padded with empty strings."""
        lines = ["a", "b"]
        result = pad_lines(lines, min_lines=5)
        assert len(result) == 5
        assert result[:2] == ["a", "b"]
        assert result[2:] == ["", "", ""]

    def test_exact_length_unchanged(self):
        """Lists at min_lines are unchanged."""
        lines = ["a", "b", "c"]
        result = pad_lines(lines, min_lines=3)
        assert result == ["a", "b", "c"]

    def test_long_list_unchanged(self):
        """Lists over min_lines are unchanged."""
        lines = ["a", "b", "c", "d", "e"]
        result = pad_lines(lines, min_lines=3)
        assert result == ["a", "b", "c", "d", "e"]

    def test_uses_default_min_lines(self):
        """Uses MIN_VIEWPORT_LINES as default."""
        lines = ["a"]
        result = pad_lines(lines)
        assert len(result) == MIN_VIEWPORT_LINES

    def test_empty_list(self):
        """Empty list is padded."""
        result = pad_lines([], min_lines=3)
        assert result == ["", "", ""]

    def test_does_not_mutate_input(self):
        """Original list is not modified."""
        lines = ["a"]
        result = pad_lines(lines, min_lines=3)
        assert lines == ["a"]
        assert len(result) == 3


class TestRendererRegistry:
    """Tests for tool_renderer decorator and registry functions."""

    def test_tool_renderer_registers_function(self):
        """@tool_renderer decorator registers the function."""

        @tool_renderer("test_tool_registry")
        def render_test(args, result, duration_ms):
            return "test"

        assert get_renderer("test_tool_registry") is render_test

    def test_get_renderer_returns_none_for_unknown(self):
        """get_renderer returns None for unregistered tools."""
        assert get_renderer("nonexistent_tool_xyz") is None

    def test_list_renderers_returns_sorted_list(self):
        """list_renderers returns sorted list of registered tools."""
        result = list_renderers()
        assert isinstance(result, list)
        assert result == sorted(result)


class TestRendererConfig:
    """Tests for RendererConfig dataclass."""

    def test_creates_with_tool_name(self):
        """Creates config with required tool_name."""
        config = RendererConfig(tool_name="test_tool")
        assert config.tool_name == "test_tool"

    def test_has_default_colors(self):
        """Config has default color values."""
        config = RendererConfig(tool_name="test_tool")
        assert config.success_color is not None
        assert config.warning_color is not None
        assert config.muted_color is not None

    def test_custom_colors(self):
        """Can override default colors."""
        config = RendererConfig(
            tool_name="test_tool",
            success_color="#00ff00",
            warning_color="#ffff00",
            muted_color="#888888",
        )
        assert config.success_color == "#00ff00"
        assert config.warning_color == "#ffff00"
        assert config.muted_color == "#888888"
