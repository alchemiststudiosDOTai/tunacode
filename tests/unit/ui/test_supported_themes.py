"""Tests for supported theme enforcement in the Textual app."""

from tunacode.core.session import StateManager
from tunacode.core.ui_api.constants import NEXTSTEP_THEME_NAME, THEME_NAME

from tunacode.ui.app import TextualReplApp


def test_supported_themes_only_include_project_themes() -> None:
    app = TextualReplApp(state_manager=StateManager())

    assert set(app.supported_themes) == {THEME_NAME, NEXTSTEP_THEME_NAME}


async def test_on_mount_falls_back_to_tunacode_for_unsupported_saved_theme() -> None:
    state_manager = StateManager()
    state_manager.session.user_config = {"settings": {"theme": "dracula"}}
    app = TextualReplApp(state_manager=state_manager)

    async with app.run_test(headless=True):
        assert app.theme == THEME_NAME


async def test_on_mount_applies_saved_supported_theme() -> None:
    state_manager = StateManager()
    state_manager.session.user_config = {"settings": {"theme": NEXTSTEP_THEME_NAME}}
    app = TextualReplApp(state_manager=state_manager)

    async with app.run_test(headless=True):
        assert app.theme == NEXTSTEP_THEME_NAME
