"""Layout tests for the bottom StatusBar widget."""

from tunacode.core.session import StateManager

from tunacode.ui.app import TextualReplApp
from tunacode.ui.widgets.status_bar import StatusBar

MIN_STATUS_BAR_CONTENT_HEIGHT = 1


async def test_status_bar_content_region_is_visible() -> None:
    """StatusBar must reserve a content row in addition to its top bevel border."""
    app = TextualReplApp(state_manager=StateManager())

    async with app.run_test(headless=True):
        status_bar = app.query_one(StatusBar)
        assert status_bar.content_region.height >= MIN_STATUS_BAR_CONTENT_HEIGHT
