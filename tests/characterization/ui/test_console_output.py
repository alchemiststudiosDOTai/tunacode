"""
Characterization tests for TunaCode UI console coordination module.
Covers: console object, markdown utility, and re-exported functions.
"""


def test_console_object_is_rich_console():
    # Should be a rich.console.Console instance (wrapped with lazy loading)
    from tunacode.ui import console as ui_console

    assert hasattr(ui_console, "console")
    # Console is now lazy-loaded via _LazyConsole wrapper for performance
    assert ui_console.console.__class__.__name__ == "_LazyConsole"
    # But it should behave like a Console when accessed
    assert hasattr(ui_console.console, "print")


def test_markdown_returns_markdown_object():
    from rich.markdown import Markdown

    from tunacode.ui import console as ui_console

    md = ui_console.markdown("# Title")
    assert isinstance(md, Markdown)
    # Current behavior: Markdown object has 'markup' attribute, not '_text'
    assert "# Title" in md.markup


def test_reexported_functions_available():
    # Smoke test: all __all__ functions are present
    from tunacode.ui import console as ui_console

    for name in ui_console.__all__:
        assert hasattr(ui_console, name)
