"""Module: tunacode.core.setup.config_wizard

Wizard-style onboarding helpers extracted from ConfigSetup to reduce file size
and keep responsibilities focused.
"""

import json
from pathlib import Path
from typing import Dict, Optional

from tunacode.constants import UI_COLORS
from tunacode.exceptions import ConfigurationError
from tunacode.ui import console as ui
from tunacode.utils import user_configuration


class ConfigWizard:
    """Encapsulates the interactive configuration wizard flow."""

    def __init__(self, state_manager, model_registry, config_file: Path):
        self.state_manager = state_manager
        self.model_registry = model_registry
        self.config_file = config_file
        self._wizard_selected_provider: Optional[Dict[str, str]] = None

    async def run_onboarding(self) -> None:
        """Run enhanced wizard-style onboarding process for new users."""
        initial_config = json.dumps(self.state_manager.session.user_config, sort_keys=True)

        # Welcome message with provider guidance
        await ui.panel(
            "Welcome to TunaCode Setup Wizard!",
            "This guided setup will help you configure TunaCode in under 5 minutes.\n"
            "We'll help you choose a provider, set up your API keys, and configure your "
            "preferred model.",
            border_style=UI_COLORS["primary"],
        )

        # Steps
        await self._step1_provider_selection()
        await self._step2_api_key_setup()
        await self._step3_model_selection()
        await self._step4_optional_settings()

        # Save configuration and finish
        current_config = json.dumps(self.state_manager.session.user_config, sort_keys=True)
        if initial_config != current_config:
            try:
                user_configuration.save_config(self.state_manager)
                await ui.panel(
                    "Setup Complete!",
                    f"Configuration saved to: [bold]{self.config_file}[/bold]\n\n"
                    "You're ready to start using TunaCode!\n"
                    "Use [green]/quickstart[/green] anytime for a tutorial.",
                    border_style=UI_COLORS["success"],
                )
            except ConfigurationError as e:
                await ui.error(str(e))

    async def _step1_provider_selection(self) -> None:
        """Wizard step 1: Provider selection with detailed explanations."""
        provider_info = {
            "1": {
                "name": "OpenRouter",
                "description": "Access to multiple models (GPT-4, Claude, Gemini, etc.)",
                "signup": "https://openrouter.ai/",
                "key_name": "OPENROUTER_API_KEY",
            },
            "2": {
                "name": "OpenAI",
                "description": "GPT-4 models",
                "signup": "https://platform.openai.com/signup",
                "key_name": "OPENAI_API_KEY",
            },
            "3": {
                "name": "Anthropic",
                "description": "Claude-3 models",
                "signup": "https://console.anthropic.com/",
                "key_name": "ANTHROPIC_API_KEY",
            },
            "4": {
                "name": "Google",
                "description": "Gemini models",
                "signup": "https://ai.google.dev/",
                "key_name": "GEMINI_API_KEY",
            },
        }

        message = "Choose your AI provider:\n\n"
        for key, info in provider_info.items():
            message += f"  {key} - {info['name']}: {info['description']}\n"

        await ui.panel("Provider Selection", message, border_style=UI_COLORS["primary"])

        while True:
            choice = await ui.input(
                "wizard_provider",
                pretext="  Choose provider (1-4): ",
                state_manager=self.state_manager,
            )

            if choice.strip() in provider_info:
                selected = provider_info[choice.strip()]
                self._wizard_selected_provider = selected

                await ui.success(f"Selected: {selected['name']}")
                await ui.info(f"Sign up at: {selected['signup']}")
                break
            else:
                await ui.error("Please enter 1, 2, 3, or 4")

    async def _step2_api_key_setup(self) -> None:
        """Wizard step 2: API key setup with provider-specific guidance."""
        provider = self._wizard_selected_provider

        message = f"Enter your {provider['name']} API key:\n\n"
        message += f"Get your key from: {provider['signup']}\n"
        message += "Your key will be stored securely in your local config"

        await ui.panel(f"{provider['name']} API Key", message, border_style=UI_COLORS["primary"])

        while True:
            api_key = await ui.input(
                "wizard_api_key",
                pretext=f"  {provider['name']} API Key: ",
                is_password=True,
                state_manager=self.state_manager,
            )

            if api_key.strip():
                # Ensure env dict exists
                if "env" not in self.state_manager.session.user_config:
                    self.state_manager.session.user_config["env"] = {}

                self.state_manager.session.user_config["env"][provider["key_name"]] = (
                    api_key.strip()
                )
                await ui.success("API key saved successfully!")
                break
            else:
                await ui.error("API key cannot be empty")

    async def _step3_model_selection(self) -> None:
        """Wizard step 3: Model selection with smart recommendations."""
        provider = self._wizard_selected_provider

        # Provide smart recommendations based on provider
        recommendations = {
            "OpenAI": [
                ("openai:gpt-4o", "GPT-4o flagship multimodal model (recommended)"),
                ("openai:gpt-4.1", "Latest GPT-4.1 with enhanced coding"),
                ("openai:o3", "Advanced reasoning model for complex tasks"),
            ],
            "Anthropic": [
                ("anthropic:claude-sonnet-4", "Claude Sonnet 4 latest generation (recommended)"),
                ("anthropic:claude-opus-4.1", "Most capable Claude with extended thinking"),
                ("anthropic:claude-3.5-sonnet", "Claude 3.5 Sonnet proven performance"),
            ],
            "OpenRouter": [
                (
                    "openrouter:anthropic/claude-sonnet-4",
                    "Claude Sonnet 4 via OpenRouter (recommended)",
                ),
                ("openrouter:openai/gpt-4.1", "GPT-4.1 via OpenRouter"),
                ("openrouter:google/gemini-2.5-flash", "Google Gemini 2.5 Flash latest"),
            ],
            "Google": [
                (
                    "google:gemini-2.5-pro",
                    "Gemini 2.5 Pro with thinking capabilities (recommended)",
                ),
                ("google:gemini-2.5-flash", "Gemini 2.5 Flash best price-performance"),
                ("google:gemini-2.0-flash", "Gemini 2.0 Flash with native tool use"),
            ],
        }

        models = recommendations.get(provider["name"], [])
        message = f"Choose your default {provider['name']} model:\n\n"

        for i, (model_id, description) in enumerate(models, 1):
            message += f"  {i} - {description}\n"

        message += "\nYou can change this later with [green]/model[/green]"

        await ui.panel("Model Selection", message, border_style=UI_COLORS["primary"])

        while True:
            choice = await ui.input(
                "wizard_model",
                pretext=f"  Choose model (1-{len(models)}): ",
                state_manager=self.state_manager,
            )

            try:
                index = int(choice.strip()) - 1
                if 0 <= index < len(models):
                    selected_model = models[index][0]
                    self.state_manager.session.user_config["default_model"] = selected_model
                    await ui.success(f"Selected: {selected_model}")
                    break
                else:
                    await ui.error(f"Please enter a number between 1 and {len(models)}")
            except ValueError:
                await ui.error("Please enter a valid number")

    async def _step4_optional_settings(self) -> None:
        """Wizard step 4: Optional settings configuration."""
        message = "Configure optional settings:\n\n"
        message += "• Tutorial: Enable interactive tutorial for new users\n"
        message += "\nSkip this step to use recommended defaults"

        await ui.panel("Optional Settings", message, border_style=UI_COLORS["primary"])

        # Ask about tutorial
        tutorial_choice = await ui.input(
            "wizard_tutorial",
            pretext="  Enable tutorial for new users? [Y/n]: ",
            state_manager=self.state_manager,
        )

        enable_tutorial = tutorial_choice.strip().lower() not in ["n", "no", "false"]

        if "settings" not in self.state_manager.session.user_config:
            self.state_manager.session.user_config["settings"] = {}

        self.state_manager.session.user_config["settings"]["enable_tutorial"] = enable_tutorial

        # Streaming is always enabled - no user choice needed

        await ui.info("Optional settings configured!")
