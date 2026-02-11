"""Tests for supported theme enforcement in the Textual app."""

from tunacode.core.session import StateManager
from tunacode.core.ui_api.constants import SUPPORTED_THEME_NAMES, THEME_NAME

from tunacode.ui.app import TextualReplApp


def test_supported_themes_includes_all_declared_names() -> None:
    app = TextualReplApp(state_manager=StateManager())

    assert set(app.supported_themes) == set(SUPPORTED_THEME_NAMES)


def test_supported_themes_is_subset_of_available() -> None:
    app = TextualReplApp(state_manager=StateManager())

    assert set(app.supported_themes).issubset(app.available_themes)


async def test_on_mount_falls_back_to_tunacode_for_unsupported_saved_theme() -> None:
    state_manager = StateManager()
    state_manager.session.user_config = {"settings": {"theme": "nonexistent-theme"}}
    app = TextualReplApp(state_manager=state_manager)

    async with app.run_test(headless=True):
        assert app.theme == THEME_NAME


async def test_on_mount_applies_saved_supported_theme() -> None:
    state_manager = StateManager()
    state_manager.session.user_config = {"settings": {"theme": "dracula"}}
    app = TextualReplApp(state_manager=state_manager)

    async with app.run_test(headless=True):
        assert app.theme == "dracula"
