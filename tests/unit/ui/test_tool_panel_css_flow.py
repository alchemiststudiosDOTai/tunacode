"""Tests for tool panel CSS class composition in tool_panel_smart."""

from rich.console import Console

from tunacode.constants import HOOK_ARROW_PREFIX

from tunacode.ui.renderers.panels import tool_panel_smart

TEST_MAX_LINE_WIDTH: int = 96
TEST_DURATION_MS: float = 42.0

TEST_CONSOLE_WIDTH: int = 120


def _css_classes(css_class: str) -> set[str]:
    return {token for token in css_class.split() if token}


def _render_text(renderable: object) -> str:
    console = Console(width=TEST_CONSOLE_WIDTH, record=True)
    console.print(renderable)
    return console.export_text()


def test_read_file_panel_has_tool_and_completed_classes() -> None:
    read_result = "\n".join(
        [
            "<file>",
            "1:ab|print('hello')",
            "(End of file - total 1 lines)",
            "</file>",
        ]
    )

    _, panel_meta = tool_panel_smart(
        name="read_file",
        status="completed",
        args={"filepath": "src/example.py", "offset": 0},
        result=read_result,
        duration_ms=TEST_DURATION_MS,
        max_line_width=TEST_MAX_LINE_WIDTH,
    )

    classes = _css_classes(panel_meta.css_class)
    assert "tool-panel" in classes
    assert "tool-read-file" in classes
    assert "completed" in classes


def test_read_file_panel_params_show_hook_arrow_prefix() -> None:
    read_result = "\n".join(
        [
            "<file>",
            "1:ab|print('hello')",
            "(End of file - total 1 lines)",
            "</file>",
        ]
    )

    content, _panel_meta = tool_panel_smart(
        name="read_file",
        status="completed",
        args={"filepath": "src/example.py", "offset": 0},
        result=read_result,
        duration_ms=TEST_DURATION_MS,
        max_line_width=TEST_MAX_LINE_WIDTH,
    )

    rendered = _render_text(content)
    assert HOOK_ARROW_PREFIX.strip() in rendered
    assert "filepath:" not in rendered


def test_read_file_panel_handles_missing_closing_tag() -> None:
    truncated_result = "\n".join(
        [
            "<file>",
            "1:ab|print('hello')",
            "2:cd|print('world')",
            "... [truncated for safety]",
        ]
    )

    content, panel_meta = tool_panel_smart(
        name="read_file",
        status="completed",
        args={"filepath": "src/example.py", "offset": 0},
        result=truncated_result,
        duration_ms=TEST_DURATION_MS,
        max_line_width=TEST_MAX_LINE_WIDTH,
    )

    classes = _css_classes(panel_meta.css_class)
    assert "tool-read-file" in classes

    rendered = _render_text(content)
    assert HOOK_ARROW_PREFIX.strip() in rendered
    assert "lines 1-2" in rendered
    assert "filepath:" not in rendered
    assert "<file>" not in rendered


def test_hashline_edit_panel_has_update_file_alias_class() -> None:
    edit_result = "\n".join(
        [
            "Updated file",
            "--- a/src/example.py",
            "+++ b/src/example.py",
            "@@ -1 +1 @@",
            "-old",
            "+new",
        ]
    )

    _, panel_meta = tool_panel_smart(
        name="hashline_edit",
        status="completed",
        args={"filepath": "src/example.py"},
        result=edit_result,
        duration_ms=TEST_DURATION_MS,
        max_line_width=TEST_MAX_LINE_WIDTH,
    )

    classes = _css_classes(panel_meta.css_class)
    assert "tool-panel" in classes
    assert "tool-hashline-edit" in classes
    assert "tool-update-file" in classes
    assert "completed" in classes


def test_failed_tool_panel_uses_failed_status_class() -> None:
    _, panel_meta = tool_panel_smart(
        name="read_file",
        status="failed",
        args={"filepath": "src/missing.py"},
        result="File not found",
        duration_ms=TEST_DURATION_MS,
        max_line_width=TEST_MAX_LINE_WIDTH,
    )

    classes = _css_classes(panel_meta.css_class)
    assert "tool-panel" in classes
    assert "tool-read-file" in classes
    assert "failed" in classes
