from textual.containers import Container

from tunacode.core.session import StateManager

from tunacode.ui.app import TextualReplApp


async def test_context_panel_toggle_ctrl_e() -> None:
    app = TextualReplApp(state_manager=StateManager())

    async with app.run_test(headless=True) as pilot:
        context_rail = app.query_one("#context-rail", Container)
        assert context_rail.has_class(app.CONTEXT_PANEL_COLLAPSED_CLASS)

        await pilot.press("ctrl+e")
        assert app._context_panel_visible is True
        assert not context_rail.has_class(app.CONTEXT_PANEL_COLLAPSED_CLASS)

        await pilot.press("ctrl+e")
        assert app._context_panel_visible is False
        assert context_rail.has_class(app.CONTEXT_PANEL_COLLAPSED_CLASS)
