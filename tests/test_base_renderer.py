"""Tests for base tool renderer."""

from __future__ import annotations

from rich.panel import Panel

from tunacode.ui.renderers.tools.base import (
    BaseToolRenderer,
    list_renderers,
    truncate_content,
    truncate_line,
)
from tunacode.ui.renderers.tools.bash import BashRenderer
from tunacode.ui.renderers.tools.list_dir import ListDirRenderer


def test_registry_contains_unified_renderers() -> None:
    """Verify unified renderers are registered."""
    renderers = list_renderers()
    assert "list_dir" in renderers
    assert "bash" in renderers


def test_truncate_line_short() -> None:
    """Short lines pass through unchanged."""
    line = "hello world"
    assert truncate_line(line, max_width=50) == line


def test_truncate_line_long() -> None:
    """Long lines get truncated with ellipsis."""
    line = "a" * 100
    result = truncate_line(line, max_width=20)
    assert len(result) == 20
    assert result.endswith("...")


def test_truncate_content_returns_counts() -> None:
    """truncate_content returns (content, shown, total)."""
    content = "line1\nline2\nline3"
    result, shown, total = truncate_content(content, max_lines=100)
    assert shown == 3
    assert total == 3


# All renderers that MUST use BaseToolRenderer
UNIFIED_RENDERERS = {
    "list_dir": ListDirRenderer,
    "bash": BashRenderer,
}


def test_unified_renderers_use_base() -> None:
    """All unified renderers must inherit from BaseToolRenderer."""
    for name, cls in UNIFIED_RENDERERS.items():
        assert issubclass(cls, BaseToolRenderer), f"{name} must use BaseToolRenderer"


def test_unified_renderers_are_registered() -> None:
    """All unified renderers must be in the registry."""
    registered = list_renderers()
    for name in UNIFIED_RENDERERS:
        assert name in registered, f"{name} not registered"
