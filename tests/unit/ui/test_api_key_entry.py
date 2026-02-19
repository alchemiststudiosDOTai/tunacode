from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Input, Static

from tunacode.core.session import StateManager

from tunacode.ui.screens.api_key_entry import ApiKeyEntryScreen


class TestApiKeyEntryHostApp(App[None]):
    __test__ = False

    def __init__(self, state_manager: StateManager) -> None:
        super().__init__()
        self.state_manager = state_manager

    def compose(self) -> ComposeResult:
        yield Static("host")


def _static_text(widget: Static) -> str:
    renderable = widget.render()
    if hasattr(renderable, "plain"):
        return renderable.plain
    return str(renderable)


async def test_api_key_entry_empty_input_shows_inline_error(monkeypatch) -> None:
    state_manager = StateManager()
    app = TestApiKeyEntryHostApp(state_manager)
    screen = ApiKeyEntryScreen("openai", state_manager)
    dismissed_results: list[bool | None] = []
    monkeypatch.setattr(screen, "dismiss", lambda result: dismissed_results.append(result))

    async with app.run_test(headless=True) as pilot:
        app.push_screen(screen)
        await pilot.pause()

        api_key_input = screen.query_one("#api-key-input", Input)
        api_key_input.value = "   "
        screen._save_and_dismiss()

        error_label = screen.query_one("#error-label", Static)
        assert _static_text(error_label) == "API key is required"
        assert dismissed_results == []


async def test_api_key_entry_valid_input_persists_and_dismisses_true(monkeypatch) -> None:
    state_manager = StateManager()
    app = TestApiKeyEntryHostApp(state_manager)
    screen = ApiKeyEntryScreen("openai", state_manager)
    dismissed_results: list[bool | None] = []
    save_calls: list[StateManager] = []

    monkeypatch.setattr(screen, "dismiss", lambda result: dismissed_results.append(result))

    def fake_save_config(manager: StateManager) -> None:
        save_calls.append(manager)

    monkeypatch.setattr("tunacode.ui.screens.api_key_entry.save_config", fake_save_config)

    async with app.run_test(headless=True) as pilot:
        app.push_screen(screen)
        await pilot.pause()

        api_key_input = screen.query_one("#api-key-input", Input)
        api_key_input.value = "test-api-key"
        screen._save_and_dismiss()

    assert state_manager.session.user_config["env"]["OPENAI_API_KEY"] == "test-api-key"
    assert dismissed_results == [True]
    assert save_calls == [state_manager]


async def test_api_key_entry_cancel_dismisses_none(monkeypatch) -> None:
    state_manager = StateManager()
    app = TestApiKeyEntryHostApp(state_manager)
    screen = ApiKeyEntryScreen("openai", state_manager)
    dismissed_results: list[bool | None] = []

    monkeypatch.setattr(screen, "dismiss", lambda result: dismissed_results.append(result))

    async with app.run_test(headless=True) as pilot:
        app.push_screen(screen)
        await pilot.pause()

        screen.action_cancel()

    assert dismissed_results == [None]
