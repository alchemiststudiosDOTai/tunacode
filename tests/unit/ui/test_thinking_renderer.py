"""Tests for muted thinking renderer."""

from __future__ import annotations

from tunacode.ui.renderers.thinking import render_thinking, render_thinking_panel


def test_render_thinking_returns_short_content_unchanged() -> None:
    content = "line one\nline two"

    rendered = render_thinking(content, max_lines=10)

    assert rendered.plain == content


def test_render_thinking_truncates_to_latest_lines_with_marker() -> None:
    content = "\n".join(["line 1", "line 2", "line 3", "line 4", "line 5"])

    rendered = render_thinking(content, max_lines=2)

    assert rendered.plain == "[[ 3 earlier lines hidden ]]\nline 4\nline 5"


def test_render_thinking_truncates_long_single_line_by_chars() -> None:
    content = "abcdefghijklmnopqrstuvwxyz"

    rendered = render_thinking(content, max_lines=10, max_chars=8)

    assert rendered.plain == "[[ earlier content hidden ]]\nstuvwxyz"


def test_render_thinking_handles_empty_and_whitespace_input() -> None:
    empty_render = render_thinking("", max_lines=3)
    whitespace_render = render_thinking("   ", max_lines=3)

    assert empty_render.plain == ""
    assert whitespace_render.plain == "   "


def test_render_thinking_panel_adds_panel_metadata() -> None:
    content, meta = render_thinking_panel("reasoning")

    assert content.plain == "reasoning"
    assert meta.css_class == "thinking-panel"
    assert "thought" in meta.border_title
