"""Setup screen for TunaCode first-time configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Select, Static

from tunacode.configuration.models import (
    get_models_for_provider,
    get_provider_base_url,
    get_provider_env_var,
    get_providers,
)
from tunacode.constants import SETTINGS_BASE_URL
from tunacode.utils.config import save_config

if TYPE_CHECKING:
    from tunacode.core.state import StateManager


class SetupScreen(Screen[bool]):
    """Setup wizard screen for first-time configuration."""

    CSS = """
    SetupScreen {
        align: center middle;
    }

    #setup-container {
        width: 70;
        height: auto;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    #setup-title {
        text-style: bold;
        color: $accent;
        text-align: center;
        margin-bottom: 1;
    }

    #setup-subtitle {
        color: $text-muted;
        text-align: center;
        margin-bottom: 1;
    }

    .field-label {
        margin-top: 1;
        color: $text;
    }

    #provider-select {
        width: 100%;
        margin-bottom: 1;
    }

    #model-select {
        width: 100%;
        margin-bottom: 1;
    }

    #api-key-input {
        width: 100%;
        margin-bottom: 1;
    }

    #button-row {
        margin-top: 1;
        align: center middle;
    }

    #save-button {
        margin-right: 2;
    }

    #skip-button {
        margin-left: 2;
    }

    #error-label {
        color: $error;
        text-align: center;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("escape", "skip", "Skip Setup"),
    ]

    def __init__(self, state_manager: StateManager) -> None:
        super().__init__()
        self.state_manager = state_manager
        self._selected_provider: str = ""

    def compose(self) -> ComposeResult:
        providers = get_providers()
        has_openai = any(p[1] == "openai" for p in providers)
        default_provider = "openai" if has_openai else (providers[0][1] if providers else "")

        with Vertical(id="setup-container"):
            yield Static("TunaCode Setup", id="setup-title")
            yield Static("Configure your AI provider to get started.", id="setup-subtitle")

            yield Label("Provider:", classes="field-label")
            yield Select(
                options=providers,
                value=default_provider,
                id="provider-select",
                allow_blank=False,
            )

            yield Label("Model:", classes="field-label")
            initial_models = get_models_for_provider(default_provider) if default_provider else []
            yield Select(
                options=initial_models,
                value=initial_models[0][1] if initial_models else Select.BLANK,
                id="model-select",
                allow_blank=False,
            )

            yield Label("API Key:", classes="field-label")
            yield Input(
                placeholder="Enter your API key",
                password=True,
                id="api-key-input",
            )

            yield Static("", id="error-label")

            with Horizontal(id="button-row"):
                yield Button("Save & Start", variant="success", id="save-button")
                yield Button("Skip", variant="default", id="skip-button")

        self._selected_provider = default_provider

    def on_select_changed(self, event: Select.Changed) -> None:
        """Update model options when provider changes."""
        if event.select.id != "provider-select":
            return

        provider = str(event.value)
        self._selected_provider = provider

        models = get_models_for_provider(provider)
        model_select = self.query_one("#model-select", Select)
        model_select.set_options(models)

        if models:
            model_select.value = models[0][1]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "save-button":
            self._save_and_dismiss()
        elif event.button.id == "skip-button":
            self.dismiss(False)

    def action_skip(self) -> None:
        """Skip setup without saving."""
        self.dismiss(False)

    def _save_and_dismiss(self) -> None:
        """Validate inputs, save config, and dismiss screen."""
        error_label = self.query_one("#error-label", Static)
        error_label.update("")

        provider_select = self.query_one("#provider-select", Select)
        model_select = self.query_one("#model-select", Select)
        api_key_input = self.query_one("#api-key-input", Input)

        provider = str(provider_select.value) if provider_select.value != Select.BLANK else ""
        model = str(model_select.value) if model_select.value != Select.BLANK else ""
        api_key = api_key_input.value.strip()

        if not provider:
            error_label.update("Please select a provider")
            return

        if not model:
            error_label.update("Please select a model")
            return

        if not api_key:
            error_label.update("API key is required")
            return

        full_model = f"{provider}:{model}"
        env_var = get_provider_env_var(provider)
        base_url = get_provider_base_url(provider)

        user_config = self.state_manager.session.user_config
        user_config["default_model"] = full_model

        if "env" not in user_config:
            user_config["env"] = {}
        user_config["env"][env_var] = api_key

        if base_url:
            if "settings" not in user_config:
                user_config["settings"] = {}
            user_config["settings"][SETTINGS_BASE_URL] = base_url

        self.state_manager.session.current_model = full_model

        try:
            save_config(self.state_manager)
            self.notify("Configuration saved!", severity="information")
            self.dismiss(True)
        except Exception as e:
            error_label.update(f"Failed to save: {e}")
