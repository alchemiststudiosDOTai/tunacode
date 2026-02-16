from textual.containers import Container

from tunacode.core.session import StateManager

from tunacode.ui.app import TextualReplApp
from tunacode.ui.widgets import ResourceBar


async def test_context_panel_toggle_ctrl_e() -> None:
    app = TextualReplApp(state_manager=StateManager())

    async with app.run_test(headless=True) as pilot:
        context_rail = app.query_one("#context-rail", Container)
        resource_bar = app.query_one(ResourceBar)
        assert not resource_bar.has_class(app.CONTEXT_PANEL_COLLAPSED_CLASS)
        assert context_rail.has_class(app.CONTEXT_PANEL_COLLAPSED_CLASS)

        await pilot.press("ctrl+e")
        assert app._context_panel_visible is True
        assert not context_rail.has_class(app.CONTEXT_PANEL_COLLAPSED_CLASS)
        assert resource_bar.has_class(app.CONTEXT_PANEL_COLLAPSED_CLASS)

        await pilot.press("ctrl+e")
        assert app._context_panel_visible is False
        assert context_rail.has_class(app.CONTEXT_PANEL_COLLAPSED_CLASS)
        assert not resource_bar.has_class(app.CONTEXT_PANEL_COLLAPSED_CLASS)


async def test_context_panel_auto_collapses_on_narrow_resize() -> None:
    app = TextualReplApp(state_manager=StateManager())

    async with app.run_test(headless=True) as pilot:
        context_rail = app.query_one("#context-rail", Container)
        resource_bar = app.query_one(ResourceBar)

        await pilot.press("ctrl+e")
        assert app._context_panel_visible is True
        assert not context_rail.has_class(app.CONTEXT_PANEL_COLLAPSED_CLASS)
        assert resource_bar.has_class(app.CONTEXT_PANEL_COLLAPSED_CLASS)

        narrow_width = app.CONTEXT_PANEL_MIN_TERMINAL_WIDTH - 1
        await pilot.resize_terminal(narrow_width, 24)
        await pilot.pause()

        assert app._context_panel_visible is False
        assert context_rail.has_class(app.CONTEXT_PANEL_COLLAPSED_CLASS)
        assert not resource_bar.has_class(app.CONTEXT_PANEL_COLLAPSED_CLASS)


async def test_context_panel_does_not_open_when_terminal_too_narrow() -> None:
    app = TextualReplApp(state_manager=StateManager())

    async with app.run_test(headless=True) as pilot:
        context_rail = app.query_one("#context-rail", Container)
        resource_bar = app.query_one(ResourceBar)

        narrow_width = app.CONTEXT_PANEL_MIN_TERMINAL_WIDTH - 1
        await pilot.resize_terminal(narrow_width, 24)
        await pilot.pause()

        await pilot.press("ctrl+e")

        assert app._context_panel_visible is False
        assert context_rail.has_class(app.CONTEXT_PANEL_COLLAPSED_CLASS)
        assert not resource_bar.has_class(app.CONTEXT_PANEL_COLLAPSED_CLASS)
