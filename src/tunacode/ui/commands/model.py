"""Model command for selecting and validating runtime model selection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tunacode.core.ui_api.configuration import ApplicationSettings

from tunacode.ui.commands.base import Command

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp


def _validate_provider_api_key_with_notification(
    model_string: str,
    user_config: dict,
    app: TextualReplApp,
    show_config_path: bool = False,
) -> bool:
    """Validate provider key and notify user if required.

    Returns True when valid or when no provider prefix exists.
    """

    from tunacode.core.ui_api.configuration import validate_provider_api_key

    if ":" not in model_string:
        return True

    provider_id = model_string.split(":")[0]
    is_valid, env_var = validate_provider_api_key(provider_id, user_config)

    if not is_valid:
        app.notify(f"Missing API key: {env_var}", severity="error")
        msg = f"[yellow]Set {env_var} in config for {provider_id}[/yellow]"
        if show_config_path:
            config_path = ApplicationSettings().paths.config_file
            msg += f"\n[dim]Config: {config_path}[/dim]"
        app.rich_log.write(msg)

    return is_valid


class ModelCommand(Command):
    """Switch model or open the model picker."""

    name = "model"
    description = "Open model picker or switch directly"
    usage = "/model [provider:model-name]"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        from tunacode.core.agents.agent_components.agent_config import (
            invalidate_agent_cache,
        )
        from tunacode.core.ui_api.configuration import (
            DEFAULT_USER_CONFIG,
            get_model_context_window,
            load_models_registry,
        )
        from tunacode.core.ui_api.user_configuration import load_config_with_defaults, save_config

        state_manager = app.state_manager
        session = state_manager.session
        default_user_config = DEFAULT_USER_CONFIG
        reloaded_user_config = load_config_with_defaults(default_user_config)
        session.user_config = reloaded_user_config

        if args:
            load_models_registry()
            model_name = args.strip()

            if not _validate_provider_api_key_with_notification(
                model_name,
                session.user_config,
                app,
                show_config_path=True,
            ):
                return

            session.current_model = model_name
            session.user_config["default_model"] = model_name
            session.conversation.max_tokens = get_model_context_window(model_name)
            save_config(state_manager)
            invalidate_agent_cache(model_name, state_manager)
            app._update_resource_bar()
            app.notify(f"Model: {model_name}")
        else:
            from tunacode.ui.screens.model_picker import (
                ModelPickerScreen,
                ProviderPickerScreen,
            )

            current_model = app.state_manager.session.current_model

            def on_model_selected(full_model: str | None) -> None:
                if full_model is None:
                    return

                if not _validate_provider_api_key_with_notification(
                    full_model,
                    session.user_config,
                    app,
                    show_config_path=False,
                ):
                    return

                session.current_model = full_model
                session.user_config["default_model"] = full_model
                session.conversation.max_tokens = get_model_context_window(full_model)
                save_config(state_manager)
                invalidate_agent_cache(full_model, state_manager)
                app._update_resource_bar()
                app.notify(f"Model: {full_model}")

            def on_provider_selected(provider_id: str | None) -> None:
                if provider_id is not None:
                    app.push_screen(
                        ModelPickerScreen(provider_id, current_model),
                        on_model_selected,
                    )

            app.push_screen(
                ProviderPickerScreen(current_model),
                on_provider_selected,
            )
