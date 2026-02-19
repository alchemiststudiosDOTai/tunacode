"""Inline API key entry screen for model selection flow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Static

from tunacode.core.ui_api.configuration import get_provider_env_var
from tunacode.core.ui_api.user_configuration import save_config

if TYPE_CHECKING:
    from tunacode.core.session import StateManager


MODAL_WIDTH = 70
MODAL_PADDING_VERTICAL = 1
MODAL_PADDING_HORIZONTAL = 2
SECTION_MARGIN_BOTTOM = 1


class ApiKeyEntryScreen(Screen[bool | None]):
    """Capture a provider API key inline and persist it to user config."""

    CSS = f"""
    ApiKeyEntryScreen {{
        align: center middle;
    }}

    #api-key-entry-container {{
        width: {MODAL_WIDTH};
        height: auto;
        border: solid $primary;
        background: $surface;
        padding: {MODAL_PADDING_VERTICAL} {MODAL_PADDING_HORIZONTAL};
    }}

    #api-key-entry-title {{
        text-style: bold;
        color: $accent;
        text-align: center;
        margin-bottom: {SECTION_MARGIN_BOTTOM};
    }}

    #api-key-entry-provider {{
        margin-bottom: {SECTION_MARGIN_BOTTOM};
    }}

    #api-key-entry-env-var {{
        color: $text-muted;
        margin-bottom: {SECTION_MARGIN_BOTTOM};
    }}

    #button-row {{
        margin-top: 1;
        align: center middle;
    }}

    #save-button {{
        margin-right: 2;
    }}

    #cancel-button {{
        margin-left: 2;
    }}
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, provider_id: str, state_manager: StateManager) -> None:
        super().__init__()
        self._provider_id = provider_id
        self._state_manager = state_manager
        self._env_var = get_provider_env_var(provider_id)

    def compose(self) -> ComposeResult:
        with Vertical(id="api-key-entry-container"):
            yield Static("API Key Required", id="api-key-entry-title")
            yield Static(f"Provider: {self._provider_id}", id="api-key-entry-provider")
            yield Static(f"Required key: {self._env_var}", id="api-key-entry-env-var")
            yield Input(
                placeholder=f"Enter {self._env_var}",
                password=True,
                id="api-key-input",
            )
            yield Static("", id="error-label")
            with Horizontal(id="button-row"):
                yield Button("Save", variant="success", id="save-button")
                yield Button("Cancel", variant="default", id="cancel-button")

    def on_mount(self) -> None:
        self.query_one("#api-key-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "api-key-input":
            return

        self._save_and_dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-button":
            self._save_and_dismiss()
            return

        if event.button.id == "cancel-button":
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _save_and_dismiss(self) -> None:
        error_label = self.query_one("#error-label", Static)
        error_label.update("")

        api_key_input = self.query_one("#api-key-input", Input)
        api_key = api_key_input.value.strip()
        if not api_key:
            error_label.update("API key is required")
            return

        user_config = self._state_manager.session.user_config
        env_config = user_config.setdefault("env", {})
        if not isinstance(env_config, dict):
            error_label.update("Configuration error: invalid env mapping")
            return

        env_config[self._env_var] = api_key

        try:
            save_config(self._state_manager)
        except OSError as exc:
            error_label.update(f"Failed to save configuration: {exc}")
            return

        self.dismiss(True)
