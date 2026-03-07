"""Tests for tool panel CSS class composition in tool_panel_smart."""

from __future__ import annotations

import pytest
from rich.console import Console

from tunacode.constants import HOOK_ARROW_PREFIX

from tunacode.ui.renderers.panels import tool_panel_smart
from tunacode.ui.renderers.tools.base import list_renderers

TEST_MAX_LINE_WIDTH: int = 96
TEST_DURATION_MS: float = 42.0
TEST_CONSOLE_WIDTH: int = 120


def _css_classes(css_class: str) -> set[str]:
    return {token for token in css_class.split() if token}


def _render_text(renderable: object) -> str:
    console = Console(width=TEST_CONSOLE_WIDTH, record=True)
    console.print(renderable)
    return console.export_text()


# ---------------------------------------------------------------------------
# Minimal valid results per renderer
# ---------------------------------------------------------------------------

BASH_RESULT = "\n".join([
    "Command: echo hello",
    "Exit Code: 0",
    "Working Directory: /tmp",
    "",
    "STDOUT:",
    "hello",
    "",
    "STDERR:",
    "(no errors)",
])

GLOB_RESULT = "\n".join([
    "[source:index]",
    "Found 2 files matching pattern: **/*.py",
    "",
    "/src/a.py",
    "/src/b.py",
])

GREP_RESULT = "\n".join([
    "Found 1 match for pattern: hello",
    "Strategy: smart | Candidates: 5 files | ...",
    "\U0001f4c1 src/main.py:10",
    "\u25b6  10\u2502before\u27e8hello\u27e9after",
])

WRITE_FILE_RESULT = "Successfully wrote to new file: /tmp/out.py"

WEB_FETCH_RESULT = "Example web page content\nLine two of the page."

LIST_DIR_RESULT = "\n".join([
    "3 files  1 dirs  0 ignored",
    "src",
    "\u251c\u2500\u2500 main.py",
    "\u251c\u2500\u2500 utils.py",
    "\u2514\u2500\u2500 lib/",
])

DISCOVER_RESULT = "\n".join([
    "# Discovery: test query",
    "Found relevant files.",
    "(10 scanned \u2192 3 relevant)",
    "",
    "## Core",
    "Core module files",
    "\u2605 `src/main.py` \u2014 entry point (50L)",
    "defines: main, run",
])


# ---------------------------------------------------------------------------
# read_file tests (existing)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# hashline_edit tests (existing)
# ---------------------------------------------------------------------------


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
    assert "tool-update-file" in classes  # Special alias
    assert "completed" in classes


# ---------------------------------------------------------------------------
# Status class tests (existing)
# ---------------------------------------------------------------------------


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


def test_running_tool_panel_uses_running_status_class() -> None:
    _, panel_meta = tool_panel_smart(
        name="read_file",
        status="running",
        args={"filepath": "src/streaming.py"},
        result=None,
        duration_ms=None,
        max_line_width=TEST_MAX_LINE_WIDTH,
    )

    classes = _css_classes(panel_meta.css_class)
    assert "tool-panel" in classes
    assert "tool-read-file" in classes
    assert "running" in classes


# ---------------------------------------------------------------------------
# bash renderer CSS class test
# ---------------------------------------------------------------------------


def test_bash_panel_has_tool_and_completed_classes() -> None:
    _, panel_meta = tool_panel_smart(
        name="bash",
        status="completed",
        args={"command": "echo hello"},
        result=BASH_RESULT,
        duration_ms=TEST_DURATION_MS,
        max_line_width=TEST_MAX_LINE_WIDTH,
    )

    classes = _css_classes(panel_meta.css_class)
    assert "tool-panel" in classes
    assert "tool-bash" in classes
    assert "completed" in classes


# ---------------------------------------------------------------------------
# glob renderer CSS class test
# ---------------------------------------------------------------------------


def test_glob_panel_has_tool_and_completed_classes() -> None:
    _, panel_meta = tool_panel_smart(
        name="glob",
        status="completed",
        args={"pattern": "**/*.py"},
        result=GLOB_RESULT,
        duration_ms=TEST_DURATION_MS,
        max_line_width=TEST_MAX_LINE_WIDTH,
    )

    classes = _css_classes(panel_meta.css_class)
    assert "tool-panel" in classes
    assert "tool-glob" in classes
    assert "completed" in classes


# ---------------------------------------------------------------------------
# grep renderer CSS class test
# ---------------------------------------------------------------------------


def test_grep_panel_has_tool_and_completed_classes() -> None:
    _, panel_meta = tool_panel_smart(
        name="grep",
        status="completed",
        args={"pattern": "hello"},
        result=GREP_RESULT,
        duration_ms=TEST_DURATION_MS,
        max_line_width=TEST_MAX_LINE_WIDTH,
    )

    classes = _css_classes(panel_meta.css_class)
    assert "tool-panel" in classes
    assert "tool-grep" in classes
    assert "completed" in classes


# ---------------------------------------------------------------------------
# write_file renderer CSS class test
# ---------------------------------------------------------------------------


def test_write_file_panel_has_tool_and_completed_classes() -> None:
    _, panel_meta = tool_panel_smart(
        name="write_file",
        status="completed",
        args={"filepath": "/tmp/out.py", "content": "print('hi')"},
        result=WRITE_FILE_RESULT,
        duration_ms=TEST_DURATION_MS,
        max_line_width=TEST_MAX_LINE_WIDTH,
    )

    classes = _css_classes(panel_meta.css_class)
    assert "tool-panel" in classes
    assert "tool-write-file" in classes
    assert "completed" in classes


# ---------------------------------------------------------------------------
# web_fetch renderer CSS class test
# ---------------------------------------------------------------------------


def test_web_fetch_panel_has_tool_and_completed_classes() -> None:
    _, panel_meta = tool_panel_smart(
        name="web_fetch",
        status="completed",
        args={"url": "https://example.com"},
        result=WEB_FETCH_RESULT,
        duration_ms=TEST_DURATION_MS,
        max_line_width=TEST_MAX_LINE_WIDTH,
    )

    classes = _css_classes(panel_meta.css_class)
    assert "tool-panel" in classes
    assert "tool-web-fetch" in classes
    assert "completed" in classes


# ---------------------------------------------------------------------------
# list_dir renderer CSS class test
# ---------------------------------------------------------------------------


def test_list_dir_panel_has_tool_and_completed_classes() -> None:
    _, panel_meta = tool_panel_smart(
        name="list_dir",
        status="completed",
        args={"directory": "src"},
        result=LIST_DIR_RESULT,
        duration_ms=TEST_DURATION_MS,
        max_line_width=TEST_MAX_LINE_WIDTH,
    )

    classes = _css_classes(panel_meta.css_class)
    assert "tool-panel" in classes
    assert "tool-list-dir" in classes
    assert "completed" in classes


# ---------------------------------------------------------------------------
# discover renderer CSS class test
# ---------------------------------------------------------------------------


def test_discover_panel_has_tool_and_completed_classes() -> None:
    _, panel_meta = tool_panel_smart(
        name="discover",
        status="completed",
        args={"query": "test query"},
        result=DISCOVER_RESULT,
        duration_ms=TEST_DURATION_MS,
        max_line_width=TEST_MAX_LINE_WIDTH,
    )

    classes = _css_classes(panel_meta.css_class)
    assert "tool-panel" in classes
    assert "tool-discover" in classes
    assert "completed" in classes


# ---------------------------------------------------------------------------
# Conformance test: auto-discover all renderers and validate class flow
# ---------------------------------------------------------------------------

# Minimal valid (args, result) pairs keyed by renderer name.
# Every registered renderer must have an entry here.
_RENDERER_FIXTURES: dict[str, tuple[dict[str, object] | None, str]] = {
    "bash": ({"command": "echo hi"}, BASH_RESULT),
    "discover": ({"query": "test"}, DISCOVER_RESULT),
    "glob": ({"pattern": "*.py"}, GLOB_RESULT),
    "grep": ({"pattern": "hello"}, GREP_RESULT),
    "hashline_edit": (
        {"filepath": "src/example.py"},
        "Updated file\n--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-old\n+new",
    ),
    "list_dir": ({"directory": "src"}, LIST_DIR_RESULT),
    "read_file": (
        {"filepath": "src/example.py", "offset": 0},
        "<file>\n1:ab|print('hello')\n(End of file - total 1 lines)\n</file>",
    ),
    "web_fetch": ({"url": "https://example.com"}, WEB_FETCH_RESULT),
    "write_file": (
        {"filepath": "/tmp/out.py", "content": "x = 1"},
        WRITE_FILE_RESULT,
    ),
}


def test_all_renderers_have_fixture_entry() -> None:
    """Every registered renderer must have an entry in _RENDERER_FIXTURES.

    This fails when a new renderer is added to the registry but not
    covered by the conformance fixtures, preventing silent class-flow gaps.
    """
    registered = set(list_renderers())
    covered = set(_RENDERER_FIXTURES.keys())
    missing = registered - covered
    assert not missing, (
        f"Registered renderers missing from _RENDERER_FIXTURES: {sorted(missing)}. "
        "Add a (args, result) fixture for each new renderer."
    )


@pytest.mark.parametrize("tool_name", sorted(_RENDERER_FIXTURES.keys()))
def test_renderer_completed_emits_correct_css_classes(tool_name: str) -> None:
    """Each renderer's completed panel must contain tool-panel, tool-{name}, and completed."""
    args, result = _RENDERER_FIXTURES[tool_name]
    _, panel_meta = tool_panel_smart(
        name=tool_name,
        status="completed",
        args=args,
        result=result,
        duration_ms=TEST_DURATION_MS,
        max_line_width=TEST_MAX_LINE_WIDTH,
    )

    classes = _css_classes(panel_meta.css_class)
    expected_identity = f"tool-{tool_name.replace('_', '-')}"

    assert "tool-panel" in classes, f"{tool_name}: missing 'tool-panel'"
    assert expected_identity in classes, f"{tool_name}: missing '{expected_identity}'"
    assert "completed" in classes, f"{tool_name}: missing 'completed'"


@pytest.mark.parametrize("tool_name", sorted(_RENDERER_FIXTURES.keys()))
def test_renderer_failed_emits_failed_class(tool_name: str) -> None:
    """Each renderer's failed panel must contain tool-panel, tool-{name}, and failed."""
    args, result = _RENDERER_FIXTURES[tool_name]
    _, panel_meta = tool_panel_smart(
        name=tool_name,
        status="failed",
        args=args,
        result=result,
        duration_ms=TEST_DURATION_MS,
        max_line_width=TEST_MAX_LINE_WIDTH,
    )

    classes = _css_classes(panel_meta.css_class)
    expected_identity = f"tool-{tool_name.replace('_', '-')}"

    assert "tool-panel" in classes, f"{tool_name}: missing 'tool-panel'"
    assert expected_identity in classes, f"{tool_name}: missing '{expected_identity}'"
    assert "failed" in classes, f"{tool_name}: missing 'failed'"


@pytest.mark.parametrize("tool_name", sorted(_RENDERER_FIXTURES.keys()))
def test_renderer_running_emits_running_class(tool_name: str) -> None:
    """Each renderer's running panel must contain tool-panel, tool-{name}, and running."""
    args, _ = _RENDERER_FIXTURES[tool_name]
    _, panel_meta = tool_panel_smart(
        name=tool_name,
        status="running",
        args=args,
        result=None,
        duration_ms=None,
        max_line_width=TEST_MAX_LINE_WIDTH,
    )

    classes = _css_classes(panel_meta.css_class)
    expected_identity = f"tool-{tool_name.replace('_', '-')}"

    assert "tool-panel" in classes, f"{tool_name}: missing 'tool-panel'"
    assert expected_identity in classes, f"{tool_name}: missing '{expected_identity}'"
    assert "running" in classes, f"{tool_name}: missing 'running'"
