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
        # Fast path: if config fingerprint matches last loaded and config is already present, skip reprocessing
        new_fp = None
        if loaded_config:
            b = json.dumps(loaded_config, sort_keys=True).encode()
            new_fp = hashlib.sha1(b).hexdigest()[:12]
        last_fp = getattr(self.state_manager, "_config_fingerprint", None)
        if (
            loaded_config
            and not force_setup
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

        if loaded_config and not force_setup:
            # Silent loading
            # Merge loaded config with defaults to ensure all required keys exist
            self.state_manager.session.user_config = self._merge_with_defaults(loaded_config)
        else:
            if force_setup:
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
                    await self._onboarding_wizard()
                else:
                    await self._onboarding()
            else:
                # No config found - offer interactive wizard or CLI usage
                from tunacode.ui.console import console

                console.print("\n[bold cyan]Welcome to TunaCode![/bold cyan]")
                console.print("\n[bold]First time setup needed.[/bold]")
                console.print("\n[yellow]Choose your setup method:[/yellow]")
                console.print("  [bold green]1[/bold green] → Interactive setup wizard (recommended)")
                console.print("  [bold blue]2[/bold blue] → Quick CLI setup")
                console.print("  [bold red]3[/bold red] → Exit and setup later")

                choice = await ui.input(
                    "setup_choice",
                    pretext="  → Your choice [1/2/3]: ",
                    state_manager=self.state_manager,
                )
                choice = choice.strip()

                if choice in ['1', 'wizard', 'interactive']:
                    # Run interactive wizard
                    self.state_manager.session.user_config = DEFAULT_USER_CONFIG.copy()
                    try:
                        user_configuration.save_config(self.state_manager)
                    except ConfigurationError as e:
                        await ui.error(str(e))
                        raise
                    await self._onboarding_wizard()
                elif choice in ['2', 'cli', 'quick']:
                    # Show CLI examples
                    console.print("\n[bold]Quick CLI Setup:[/bold]")
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

                    raise ConfigurationError(
                        "Please restart TunaCode with CLI flags to configure."
                    )
                else:
                    # Exit
                    console.print("\n[yellow]Setup cancelled. Run TunaCode again when ready to configure.[/yellow]\n")
                    raise ConfigurationError("Setup cancelled by user.")

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

    async def _onboarding_wizard(self):
        """Enhanced wizard-style onboarding with better guidance and explanations."""
        initial_config = json.dumps(self.state_manager.session.user_config, sort_keys=True)

        # Welcome and explanation
        message = (
            f"Welcome to {APP_NAME}! Let's get you set up quickly.\n\n"
            "This wizard will help you:\n"
            "• Choose and configure an AI provider\n"
            "• Set up your preferred model\n"
            "• Get you ready to start coding with AI assistance\n\n"
            "The whole process takes less than 2 minutes."
        )
        await ui.panel("🎯 Setup Wizard", message, border_style=UI_COLORS["primary"])

        # Step 1: Enhanced API key collection with provider guidance
        await self._wizard_step1_provider_selection()

        # Only continue if at least one API key was provided
        env = self.state_manager.session.user_config.get("env", {})
        has_api_key = (
            any(key.endswith("_API_KEY") and env.get(key) for key in env) if env else False
        )

        if has_api_key:
            # Step 2: Model selection with recommendations
            if not self.state_manager.session.user_config.get("default_model"):
                await self._wizard_step2_model_selection()

            # Step 3: Optional settings
            await self._wizard_step3_optional_settings()

            # Final setup completion
            current_config = json.dumps(self.state_manager.session.user_config, sort_keys=True)
            if initial_config != current_config:
                try:
                    user_configuration.save_config(self.state_manager)

                    # Success message with next steps
                    message = (
                        f"✅ Setup complete! Configuration saved to:\n"
                        f"   [bold]{self.config_file}[/bold]\n\n"
                        "🚀 Ready to start! Try these commands:\n"
                        "   • [green]/help[/green] - See all available commands\n"
                        "   • [green]/quickstart[/green] - Quick tutorial\n"
                        "   • Just type your coding question to get started!"
                    )
                    await ui.panel("🎉 Welcome to TunaCode!", message, border_style=UI_COLORS["success"])
                except ConfigurationError as e:
                    await ui.error(str(e))
        else:
            await ui.panel(
                "⚠️ Setup Incomplete",
                "At least one API key is required to use TunaCode.\n"
                "You can restart the setup anytime with: [green]tunacode --setup[/green]",
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

    async def _wizard_step1_provider_selection(self):
        """Wizard step 1: Enhanced provider selection with guidance."""
        providers_info = {
            "OpenAI": {
                "description": "Industry standard with GPT-4 models",
                "best_for": "General coding, balanced performance",
                "signup": "https://platform.openai.com/signup",
                "key_name": "OPENAI_API_KEY"
            },
            "Anthropic": {
                "description": "Advanced Claude models, excellent for coding",
                "best_for": "Complex reasoning, detailed explanations",
                "signup": "https://console.anthropic.com/",
                "key_name": "ANTHROPIC_API_KEY"
            },
            "Google": {
                "description": "Gemini models with fast responses",
                "best_for": "Quick iterations, code completion",
                "signup": "https://aistudio.google.com/",
                "key_name": "GEMINI_API_KEY"
            },
            "OpenRouter": {
                "description": "Access to multiple models via one API",
                "best_for": "Trying different models, cost optimization",
                "signup": "https://openrouter.ai/",
                "key_name": "OPENROUTER_API_KEY"
            }
        }

        message = (
            "🔑 Let's set up your AI provider. Choose one or more:\n\n"
            "Provider recommendations:\n"
        )
        for i, (provider, info) in enumerate(providers_info.items(), 1):
            message += f"  {i}. [bold]{provider}[/bold] - {info['description']}\n"
            message += f"     • {info['best_for']}\n"

        message += (
            "\nYou can configure multiple providers and switch between them later.\n"
            "We'll help you get API keys from your chosen provider(s)."
        )

        await ui.panel("🔑 Provider Setup", message, border_style=UI_COLORS["primary"])

        # Get provider selection
        choice = await ui.input(
            "provider_choice",
            pretext="  → Which provider(s)? [1,2,3,4 or names]: ",
            state_manager=self.state_manager,
        )

        selected_providers = []
        for part in choice.split(','):
            part = part.strip().lower()
            if part in ['1', 'openai']:
                selected_providers.append('OpenAI')
            elif part in ['2', 'anthropic', 'claude']:
                selected_providers.append('Anthropic')
            elif part in ['3', 'google', 'gemini']:
                selected_providers.append('Google')
            elif part in ['4', 'openrouter']:
                selected_providers.append('OpenRouter')

        if not selected_providers:
            selected_providers = ['OpenAI']  # Default fallback

        # Configure API keys for selected providers
        env_config = self.state_manager.session.user_config.get("env", {})

        for provider in selected_providers:
            info = providers_info[provider]

            message = (
                f"📋 Setting up {provider}\n\n"
                f"📖 {info['description']}\n"
                f"🎯 Best for: {info['best_for']}\n\n"
                f"Get your API key: [blue]{info['signup']}[/blue]\n"
                f"Once you have your key, paste it below:"
            )
            await ui.panel(f"🔧 {provider} Setup", message, border_style=UI_COLORS["primary"])

            api_key = await ui.input(
                f"{provider.lower()}_key",
                pretext=f"  {provider} API Key: ",
                is_password=True,
                state_manager=self.state_manager,
            )

            if api_key.strip():
                env_config[info['key_name']] = api_key.strip()
                await ui.success(f"✅ {provider} configured successfully!")
            else:
                await ui.muted(f"⏭️  Skipped {provider} setup")

        self.state_manager.session.user_config["env"] = env_config

    async def _wizard_step2_model_selection(self):
        """Wizard step 2: Enhanced model selection with recommendations."""
        message = (
            "🤖 Now let's choose your default model.\n\n"
            "Model recommendations based on your providers:\n"
        )

        # Get configured providers
        env = self.state_manager.session.user_config.get("env", {})
        available_providers = []

        if env.get("OPENAI_API_KEY"):
            available_providers.append("OpenAI")
            message += "  • [bold]openai:gpt-4o[/bold] - Latest GPT-4, great for coding\n"
            message += "  • [bold]openai:gpt-4o-mini[/bold] - Faster, more affordable\n"

        if env.get("ANTHROPIC_API_KEY"):
            available_providers.append("Anthropic")
            message += "  • [bold]anthropic:claude-3-5-sonnet-20241022[/bold] - Excellent for coding\n"
            message += "  • [bold]anthropic:claude-3-haiku-20240307[/bold] - Fast responses\n"

        if env.get("GEMINI_API_KEY"):
            available_providers.append("Google")
            message += "  • [bold]google-gla:gemini-2.0-flash[/bold] - Fast and capable\n"

        if env.get("OPENROUTER_API_KEY"):
            available_providers.append("OpenRouter")
            message += "  • [bold]openrouter:anthropic/claude-3.5-sonnet[/bold] - Top coding model\n"
            message += "  • [bold]openrouter:openai/gpt-4o[/bold] - Reliable performance\n"

        message += (
            "\nFormat: provider:model-name\n"
            "💡 Tip: You can change models anytime with [green]/model[/green] command"
        )

        await ui.panel("🤖 Model Selection", message, border_style=UI_COLORS["primary"])

        # Get model selection
        model_choice = await ui.input(
            "model_selection",
            pretext="  → Enter model name: ",
            state_manager=self.state_manager,
        )

        model_choice = model_choice.strip()

        # Validate provider prefix
        if ":" not in model_choice:
            await ui.warning("Adding provider prefix. Using: openai:gpt-4o")
            model_choice = "openai:gpt-4o"

        self.state_manager.session.user_config["default_model"] = model_choice
        await ui.success(f"✅ Default model set to: {model_choice}")

    async def _wizard_step3_optional_settings(self):
        """Wizard step 3: Optional settings configuration."""
        message = (
            "⚙️ Optional settings (recommended defaults):\n\n"
            "• Enable tutorial for first-time users? [Y/n]\n"
            "• Enable streaming responses? [Y/n]\n"
            "• Set context window size? [default: 200000]"
        )

        await ui.panel("⚙️ Optional Settings", message, border_style=UI_COLORS["primary"])

        # Tutorial setting
        tutorial_choice = await ui.input(
            "tutorial_setting",
            pretext="  → Enable tutorial? [Y/n]: ",
            state_manager=self.state_manager,
        )

        enable_tutorial = tutorial_choice.strip().lower() not in ['n', 'no', 'false']

        # Streaming setting
        streaming_choice = await ui.input(
            "streaming_setting",
            pretext="  → Enable streaming? [Y/n]: ",
            state_manager=self.state_manager,
        )

        enable_streaming = streaming_choice.strip().lower() not in ['n', 'no', 'false']

        # Update settings
        if "settings" not in self.state_manager.session.user_config:
            self.state_manager.session.user_config["settings"] = {}

        self.state_manager.session.user_config["settings"].update({
            "enable_tutorial": enable_tutorial,
            "enable_streaming": enable_streaming,
        })

        await ui.success("✅ Settings configured!")
