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
from tunacode.core.setup.config_wizard import ConfigWizard
from tunacode.core.state import StateManager
from tunacode.exceptions import ConfigurationError
from tunacode.types import ConfigFile, ConfigPath, UserConfig
from tunacode.ui import console as ui
from tunacode.utils import system, user_configuration
from tunacode.utils.api_key_validation import (
    get_required_api_key_for_model,
    validate_api_key_for_model,
)
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

        # Set the loaded config to session BEFORE initializing first-time user
        if loaded_config:
            self.state_manager.session.user_config = loaded_config

        # Initialize first-time user settings if needed
        user_configuration.initialize_first_time_user(self.state_manager)

        # Fast path: if config fingerprint matches last loaded and config is already present,
        # skip reprocessing
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
                    wizard = ConfigWizard(self.state_manager, self.model_registry, self.config_file)
                    await wizard.run_onboarding()
                else:
                    await self._onboarding()
            else:
                # No config found - show CLI usage and continue with safe defaults (no crash)
                from tunacode.ui.console import console

                console.print(
                    "\n[bold yellow]No configuration found — using safe defaults.[/bold yellow]"
                )
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

                # Initialize in-memory defaults so we don't crash
                self.state_manager.session.user_config = DEFAULT_USER_CONFIG.copy()
                # Mark config as not fully validated for the fast path
                setattr(self.state_manager, "_config_valid", False)

        if not self.state_manager.session.user_config.get("default_model"):
            # Gracefully apply default model instead of crashing
            self.state_manager.session.user_config["default_model"] = DEFAULT_USER_CONFIG[
                "default_model"
            ]
            await ui.warning(
                "No default model set in config; applying safe default "
                f"'{self.state_manager.session.user_config['default_model']}'."
            )

        # Validate API key exists for the selected model
        model = self.state_manager.session.user_config["default_model"]
        is_valid, error_msg = validate_api_key_for_model(
            model, self.state_manager.session.user_config
        )
        if not is_valid:
            # Try to pick a fallback model based on whichever provider has a key configured
            fallback = self._pick_fallback_model(self.state_manager.session.user_config)
            if fallback and fallback != model:
                await ui.warning(
                    "API key missing for selected model; switching to configured provider: "
                    f"'{fallback}'."
                )
                self.state_manager.session.user_config["default_model"] = fallback
                model = fallback
            else:
                # No suitable fallback; continue without crashing but mark invalid
                await ui.warning(
                    (error_msg or "API key missing for model")
                    + "\nContinuing without provider initialization; run 'tunacode --setup' later."
                )
                setattr(self.state_manager, "_config_valid", False)

        self.state_manager.session.current_model = model

    def _pick_fallback_model(self, user_config: UserConfig) -> str | None:
        """Select a reasonable fallback model based on configured API keys."""
        env = (user_config or {}).get("env", {})

        # Preference order: OpenAI → Anthropic → Google → OpenRouter
        if env.get("OPENAI_API_KEY", "").strip():
            return "openai:gpt-4o"
        if env.get("ANTHROPIC_API_KEY", "").strip():
            return "anthropic:claude-sonnet-4"
        if env.get("GEMINI_API_KEY", "").strip():
            return "google:gemini-2.5-flash"
        if env.get("OPENROUTER_API_KEY", "").strip():
            # Use the project default when OpenRouter is configured
            return DEFAULT_USER_CONFIG.get("default_model", "openrouter:openai/gpt-4.1")

        return None

    async def validate(self) -> bool:
        """Validate that configuration is properly set up."""
        # Check that we have a user config
        valid = True
        if not self.state_manager.session.user_config:
            valid = False
        elif not self.state_manager.session.user_config.get("default_model"):
            valid = False
        else:
            # Validate API key exists for the selected model
            model = self.state_manager.session.user_config.get("default_model")
            is_valid, error_msg = validate_api_key_for_model(
                model, self.state_manager.session.user_config
            )
            if not is_valid:
                valid = False
                # Store error message for later use
                setattr(self.state_manager, "_config_error", error_msg)

                # Provide actionable guidance for manual setup
                required_key, provider_name = get_required_api_key_for_model(model)
                setup_hint = (
                    f"Missing API key for {provider_name}.\n"
                    f"Either run 'tunacode --wizard' (recommended) or add it manually to: "
                    f"{self.config_file}\n\n"
                    "Example snippet (add under 'env'):\n"
                    '  "env": {\n'
                    f'    "{required_key or "PROVIDER_API_KEY"}": "your-key-here"\n'
                    "  }\n"
                )
                await ui.error(setup_hint)

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
