"""Module: tinyagent.core.setup.config_setup

Configuration system initialization for the Sidekick CLI.
Handles user configuration loading, validation, and first-time setup onboarding.
"""

import json
from pathlib import Path

from tunacode.configuration.defaults import DEFAULT_USER_CONFIG
from tunacode.configuration.models import ModelRegistry
from tunacode.constants import APP_NAME, CONFIG_FILE_NAME, UI_COLORS
from tunacode.core.setup.base import BaseSetup
from tunacode.core.state import StateManager
from tunacode.exceptions import ConfigurationError
from tunacode.types import ConfigFile, ConfigPath, UserConfig
from tunacode.ui import console as ui
from tunacode.utils import system, user_configuration
from tunacode.utils.text_utils import key_to_title


class ConfigSetup(BaseSetup):
    """Setup step for configuration and onboarding."""

    def __init__(self, state_manager: StateManager):
        super().__init__(state_manager)
        self.config_dir: ConfigPath = Path.home() / ".config"
        self.config_file: ConfigFile = self.config_dir / CONFIG_FILE_NAME
        self.model_registry = ModelRegistry()
        self.cli_config = None  # Will be set if CLI args are provided

    @property
    def name(self) -> str:
        return "Configuration"

    async def should_run(self, force_setup: bool = False) -> bool:
        """Config setup should always run to load and merge configuration."""
        return True

    async def execute(self, force_setup: bool = False, wizard_mode: bool = False) -> None:
        """Setup configuration and run onboarding if needed, with config fingerprint fast path."""
        import hashlib

        self.state_manager.session.device_id = system.get_device_id()
        loaded_config = user_configuration.load_config()

        # Initialize first-time user settings if needed
        user_configuration.initialize_first_time_user(self.state_manager)

        # Fast path: if config fingerprint matches last loaded and config is already present, skip reprocessing
        new_fp = None
        if loaded_config:
            b = json.dumps(loaded_config, sort_keys=True).encode()
            new_fp = hashlib.sha1(b).hexdigest()[:12]
        last_fp = getattr(self.state_manager, "_config_fingerprint", None)
        if (
            loaded_config
            and not force_setup
            and not wizard_mode
            and new_fp
            and last_fp == new_fp
            and getattr(self.state_manager, "_config_valid", False)
        ):
            # Fast path: config unchanged, already validated
            self.state_manager.session.user_config = loaded_config
            self.state_manager.session.current_model = loaded_config["default_model"]
            return
        # Save current config fingerprint for next run
        self.state_manager._config_fingerprint = new_fp

        # Handle CLI configuration if provided
        if self.cli_config and any(self.cli_config.values()):
            await self._handle_cli_config(loaded_config)
            return

        if loaded_config and not force_setup and not wizard_mode:
            # Silent loading
            # Merge loaded config with defaults to ensure all required keys exist
            self.state_manager.session.user_config = self._merge_with_defaults(loaded_config)
        else:
            if force_setup or wizard_mode:
                if wizard_mode:
                    await ui.muted("Running interactive setup wizard")
                else:
                    await ui.muted("Running setup process, resetting config")

                # Ensure user_config is properly initialized
                if (
                    not hasattr(self.state_manager.session, "user_config")
                    or self.state_manager.session.user_config is None
                ):
                    self.state_manager.session.user_config = {}
                self.state_manager.session.user_config = DEFAULT_USER_CONFIG.copy()
                try:
                    user_configuration.save_config(
                        self.state_manager
                    )  # Save the default config initially
                except ConfigurationError as e:
                    await ui.error(str(e))
                    raise

                if wizard_mode:
                    await self._wizard_onboarding()
                else:
                    await self._onboarding()
            else:
                # No config found - show CLI usage instead of onboarding
                from tunacode.ui.console import console

                console.print("\n[bold red]No configuration found![/bold red]")
                console.print("\n[bold]Quick Setup:[/bold]")
                console.print("Configure TunaCode using CLI flags:")
                console.print("\n[blue]Examples:[/blue]")
                console.print("  [green]tunacode --model 'openai:gpt-4' --key 'your-key'[/green]")
                console.print(
                    "  [green]tunacode --model 'anthropic:claude-3-opus' --key 'your-key'[/green]"
                )
                console.print(
                    "  [green]tunacode --model 'openrouter:anthropic/claude-3.5-sonnet' "
                    "--key 'your-key' --baseurl 'https://openrouter.ai/api/v1'[/green]"
                )
                console.print("\n[yellow]Run 'tunacode --help' for more options[/yellow]\n")
                console.print("\n[cyan]Or use --wizard for guided setup[/cyan]\n")

                raise ConfigurationError(
                    "No configuration found. Please use CLI flags to configure or --wizard for guided setup."
                )

        if not self.state_manager.session.user_config.get("default_model"):
            raise ConfigurationError(
                (
                    f"No default model found in config at [bold]{self.config_file}[/bold]\n\n"
                    "Run [code]sidekick --setup[/code] to rerun the setup process."
                )
            )

        # No model validation - trust user's model choice

        self.state_manager.session.current_model = self.state_manager.session.user_config[
            "default_model"
        ]

    async def validate(self) -> bool:
        """Validate that configuration is properly set up."""
        # Check that we have a user config
        valid = True
        if not self.state_manager.session.user_config:
            valid = False
        elif not self.state_manager.session.user_config.get("default_model"):
            valid = False
        # Cache result for fastpath
        if valid:
            setattr(self.state_manager, "_config_valid", True)
        else:
            setattr(self.state_manager, "_config_valid", False)
        return valid

    def _merge_with_defaults(self, loaded_config: UserConfig) -> UserConfig:
        """Merge loaded config with defaults to ensure all required keys exist."""
        # Start with loaded config if available, otherwise use defaults
        if loaded_config:
            merged = loaded_config.copy()

            # Add missing top-level keys from defaults
            for key, default_value in DEFAULT_USER_CONFIG.items():
                if key not in merged:
                    merged[key] = default_value

            return merged
        else:
            return DEFAULT_USER_CONFIG.copy()

    async def _onboarding(self):
        """Run the onboarding process for new users."""
        initial_config = json.dumps(self.state_manager.session.user_config, sort_keys=True)

        await self._step1_api_keys()

        # Only continue if at least one API key was provided
        env = self.state_manager.session.user_config.get("env", {})
        has_api_key = (
            any(key.endswith("_API_KEY") and env.get(key) for key in env) if env else False
        )

        if has_api_key:
            if not self.state_manager.session.user_config.get("default_model"):
                await self._step2_default_model()

            # Compare configs to see if anything changed
            current_config = json.dumps(self.state_manager.session.user_config, sort_keys=True)
            if initial_config != current_config:
                try:
                    user_configuration.save_config(self.state_manager)
                    message = f"Config saved to: [bold]{self.config_file}[/bold]"
                    await ui.panel("Finished", message, top=0, border_style=UI_COLORS["success"])
                except ConfigurationError as e:
                    await ui.error(str(e))
        else:
            await ui.panel(
                "Setup canceled",
                "At least one API key is required.",
                border_style=UI_COLORS["warning"],
            )

    async def _step1_api_keys(self):
        """Onboarding step 1: Collect API keys."""
        message = (
            f"Welcome to {APP_NAME}!\n"
            "Let's get you setup. First, we'll need to set some environment variables.\n"
            "Skip the ones you don't need."
        )
        await ui.panel("Setup", message, border_style=UI_COLORS["primary"])
        env_config = self.state_manager.session.user_config.get("env")
        if not env_config:
            self.state_manager.session.user_config["env"] = DEFAULT_USER_CONFIG["env"].copy()
            env_config = self.state_manager.session.user_config["env"]

        # Ensure env_config is not None before copying
        if env_config is None:
            env_config = {}
        env_keys = env_config.copy()
        for key in env_keys:
            provider = key_to_title(key)
            val = await ui.input(
                "step1",
                pretext=f"  {provider}: ",
                is_password=True,
                state_manager=self.state_manager,
            )
            val = val.strip()
            if val:
                self.state_manager.session.user_config["env"][key] = val

    async def _step2_default_model(self):
        """Onboarding step 2: Select default model."""
        message = "Which model would you like to use by default?\n\n"

        model_ids = self.model_registry.list_model_ids()
        for index, model_id in enumerate(model_ids):
            message += f"  {index} - {model_id}\n"
        message = message.strip()

        await ui.panel("Default Model", message, border_style=UI_COLORS["primary"])
        choice = await ui.input(
            "step2",
            pretext="  Default model (#): ",
            validator=ui.ModelValidator(len(model_ids)),
            state_manager=self.state_manager,
        )
        self.state_manager.session.user_config["default_model"] = model_ids[int(choice)]

    async def _step2_default_model_simple(self):
        """Simple model selection - just enter model name."""
        await ui.muted("Format: provider:model-name")
        await ui.muted(
            "Examples: openai:gpt-4.1, anthropic:claude-3-opus, google-gla:gemini-2.0-flash"
        )

        while True:
            model_name = await ui.input(
                "step2",
                pretext="  Model (provider:name): ",
                state_manager=self.state_manager,
            )
            model_name = model_name.strip()

            # Check if provider prefix is present
            if ":" not in model_name:
                await ui.error("Model name must include provider prefix")
                await ui.muted("Format: provider:model-name")
                await ui.muted("You can always change it later with /model")
                continue

            # No validation - user is responsible for correct model names
            self.state_manager.session.user_config["default_model"] = model_name
            await ui.warning("Model set without validation - verify the model name is correct")
            await ui.success(f"Selected model: {model_name}")
            break

    async def _handle_cli_config(self, loaded_config: UserConfig) -> None:
        """Handle configuration provided via CLI arguments."""
        # Start with existing config or defaults
        if loaded_config:
            self.state_manager.session.user_config = self._merge_with_defaults(loaded_config)
        else:
            self.state_manager.session.user_config = DEFAULT_USER_CONFIG.copy()

        # Apply CLI overrides
        if self.cli_config and self.cli_config.get("key"):
            # Ensure env dict exists
            if "env" not in self.state_manager.session.user_config:
                self.state_manager.session.user_config["env"] = {}

            # Determine which API key to set based on the model or baseurl
            if (
                self.cli_config
                and self.cli_config.get("baseurl")
                and "openrouter" in self.cli_config["baseurl"]
            ):
                self.state_manager.session.user_config["env"]["OPENROUTER_API_KEY"] = (
                    self.cli_config["key"]
                )
            elif self.cli_config and self.cli_config.get("model"):
                if "claude" in self.cli_config["model"] or "anthropic" in self.cli_config["model"]:
                    self.state_manager.session.user_config["env"]["ANTHROPIC_API_KEY"] = (
                        self.cli_config["key"]
                    )
                elif "gpt" in self.cli_config["model"] or "openai" in self.cli_config["model"]:
                    self.state_manager.session.user_config["env"]["OPENAI_API_KEY"] = (
                        self.cli_config["key"]
                    )
                elif "gemini" in self.cli_config["model"]:
                    self.state_manager.session.user_config["env"]["GEMINI_API_KEY"] = (
                        self.cli_config["key"]
                    )
                else:
                    # Default to OpenRouter for unknown models
                    self.state_manager.session.user_config["env"]["OPENROUTER_API_KEY"] = (
                        self.cli_config["key"]
                    )

        if self.cli_config and self.cli_config.get("baseurl"):
            self.state_manager.session.user_config["env"]["OPENAI_BASE_URL"] = self.cli_config[
                "baseurl"
            ]

        if self.cli_config and self.cli_config.get("model"):
            model = self.cli_config["model"]
            # Require provider prefix
            if ":" not in model:
                raise ConfigurationError(
                    f"Model '{model}' must include provider prefix\n"
                    "Format: provider:model-name\n"
                    "Examples: openai:gpt-4.1, anthropic:claude-3-opus"
                )

            self.state_manager.session.user_config["default_model"] = model

        if self.cli_config and self.cli_config.get("custom_context_window"):
            self.state_manager.session.user_config["context_window_size"] = self.cli_config[
                "custom_context_window"
            ]

        # Set current model
        self.state_manager.session.current_model = self.state_manager.session.user_config[
            "default_model"
        ]

        # Save the configuration
        try:
            user_configuration.save_config(self.state_manager)
            await ui.warning("Model set without validation - verify the model name is correct")
            await ui.success(f"Configuration saved to: {self.config_file}")
        except ConfigurationError as e:
            await ui.error(str(e))

    async def _wizard_onboarding(self):
        """Run enhanced wizard-style onboarding process for new users."""
        initial_config = json.dumps(self.state_manager.session.user_config, sort_keys=True)

        # Welcome message with provider guidance
        await ui.panel(
            "🎯 Welcome to TunaCode Setup Wizard!",
            "This guided setup will help you configure TunaCode in under 5 minutes.\n"
            "We'll help you choose a provider, set up your API keys, and configure your preferred model.",
            border_style=UI_COLORS["primary"],
        )

        # Step 1: Provider selection with detailed guidance
        await self._wizard_step1_provider_selection()

        # Step 2: API key setup with provider-specific guidance
        await self._wizard_step2_api_key_setup()

        # Step 3: Model selection with smart recommendations
        await self._wizard_step3_model_selection()

        # Step 4: Optional settings configuration
        await self._wizard_step4_optional_settings()

        # Save configuration and finish
        current_config = json.dumps(self.state_manager.session.user_config, sort_keys=True)
        if initial_config != current_config:
            try:
                user_configuration.save_config(self.state_manager)
                await ui.panel(
                    "🎉 Setup Complete!",
                    f"Configuration saved to: [bold]{self.config_file}[/bold]\n\n"
                    "🚀 You're ready to start using TunaCode!\n"
                    "💡 Use [green]/quickstart[/green] anytime for a tutorial.",
                    border_style=UI_COLORS["success"],
                )
            except ConfigurationError as e:
                await ui.error(str(e))

    async def _wizard_step1_provider_selection(self):
        """Wizard step 1: Provider selection with detailed explanations."""
        provider_info = {
            "1": {
                "name": "OpenAI",
                "description": "GPT-4, GPT-3.5-turbo models",
                "signup": "https://platform.openai.com/signup",
                "key_name": "OPENAI_API_KEY",
            },
            "2": {
                "name": "Anthropic",
                "description": "Claude-3.5-sonnet, Claude-3 models",
                "signup": "https://console.anthropic.com/",
                "key_name": "ANTHROPIC_API_KEY",
            },
            "3": {
                "name": "OpenRouter",
                "description": "Access to multiple models (GPT-4, Claude, Gemini, etc.)",
                "signup": "https://openrouter.ai/",
                "key_name": "OPENROUTER_API_KEY",
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
        message += "\n💡 OpenRouter is recommended for beginners (access to all models)"

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

    async def _wizard_step2_api_key_setup(self):
        """Wizard step 2: API key setup with provider-specific guidance."""
        provider = self._wizard_selected_provider

        message = f"Enter your {provider['name']} API key:\n\n"
        message += f"📋 Get your key from: {provider['signup']}\n"
        message += "🔒 Your key will be stored securely in your local config"

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

    async def _wizard_step3_model_selection(self):
        """Wizard step 3: Model selection with smart recommendations."""
        provider = self._wizard_selected_provider

        # Provide smart recommendations based on provider
        recommendations = {
            "OpenAI": [
                ("openai:gpt-4o", "Latest GPT-4 model (recommended)"),
                ("openai:gpt-4-turbo", "Fast GPT-4 variant"),
                ("openai:gpt-3.5-turbo", "Cost-effective option"),
            ],
            "Anthropic": [
                ("anthropic:claude-3-5-sonnet-20241022", "Latest Claude model (recommended)"),
                ("anthropic:claude-3-opus-20240229", "Most capable Claude model"),
                ("anthropic:claude-3-haiku-20240307", "Fast and cost-effective"),
            ],
            "OpenRouter": [
                ("openrouter:anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet (recommended)"),
                ("openrouter:openai/gpt-4o", "GPT-4o via OpenRouter"),
                ("openrouter:google/gemini-2.0-flash-exp", "Google Gemini 2.0"),
            ],
            "Google": [
                ("google:gemini-2.0-flash-exp", "Latest Gemini model (recommended)"),
                ("google:gemini-1.5-pro", "Gemini 1.5 Pro"),
                ("google:gemini-1.5-flash", "Fast Gemini variant"),
            ],
        }

        models = recommendations.get(provider["name"], [])
        message = f"Choose your default {provider['name']} model:\n\n"

        for i, (model_id, description) in enumerate(models, 1):
            message += f"  {i} - {description}\n"

        message += "\n💡 You can change this later with [green]/model[/green]"

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

    async def _wizard_step4_optional_settings(self):
        """Wizard step 4: Optional settings configuration."""
        message = "Configure optional settings:\n\n"
        message += "• Tutorial: Enable interactive tutorial for new users\n"
        message += "• Streaming: Enable real-time response streaming\n"
        message += "\n⏭️  Skip this step to use recommended defaults"

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

        # Ask about streaming
        streaming_choice = await ui.input(
            "wizard_streaming",
            pretext="  Enable response streaming? [Y/n]: ",
            state_manager=self.state_manager,
        )

        enable_streaming = streaming_choice.strip().lower() not in ["n", "no", "false"]
        self.state_manager.session.user_config["streaming"] = enable_streaming

        await ui.info("Optional settings configured!")
