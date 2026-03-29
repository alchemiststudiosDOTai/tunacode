"""Model command for selecting and validating runtime model selection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tunacode.core.ui_api.configuration import ApplicationSettings

from tunacode.ui.commands.base import Command

if TYPE_CHECKING:
    from tunacode.types import UserConfig

    from tunacode.ui.app import TextualReplApp


PROVIDER_MODEL_DELIMITER = ":"


def _validate_provider_api_key_with_notification(
    model_string: str,
    user_config: UserConfig,
    app: TextualReplApp,
    show_config_path: bool = False,
) -> bool:
    """Validate provider key and notify user if required.

    Returns True when valid or when no provider prefix exists.
    """

    from tunacode.core.ui_api.configuration import validate_provider_api_key

    if PROVIDER_MODEL_DELIMITER not in model_string:
        return True

    provider_id = model_string.split(PROVIDER_MODEL_DELIMITER, 1)[0]
    is_valid, env_var = validate_provider_api_key(provider_id, user_config)

    if not is_valid:
        app.notify(f"Missing API key: {env_var}", severity="error")
        msg = f"[yellow]Set {env_var} in config for {provider_id}[/yellow]"
        if show_config_path:
            config_path = ApplicationSettings().paths.config_file
            msg += f"\n[dim]Config: {config_path}[/dim]"
        app.chat_container.write(msg)

    return is_valid


class ModelCommand(Command):
    """Switch model or open the model picker."""

    name = "model"
    description = "Open model picker or switch directly"
    usage = "/model [provider:model-name]"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        from tunacode.core.ui_api.configuration import DEFAULT_USER_CONFIG
        from tunacode.core.ui_api.user_configuration import (
            get_recent_models,
            load_config_with_defaults,
        )

        session = app.state_manager.session
        session.user_config = load_config_with_defaults(DEFAULT_USER_CONFIG)
        session.user_config["recent_models"] = get_recent_models(session.user_config)

        if args:
            self._handle_direct_model_selection(app, args.strip())
            return

        self._open_model_picker(app)

    def _handle_direct_model_selection(self, app: TextualReplApp, model_name: str) -> None:
        session = app.state_manager.session

        if _validate_provider_api_key_with_notification(
            model_name,
            session.user_config,
            app,
            show_config_path=True,
        ):
            self._apply_model_selection(app, model_name)
            return

        if PROVIDER_MODEL_DELIMITER not in model_name:
            return

        from tunacode.ui.screens.api_key_entry import ApiKeyEntryScreen

        provider_id = model_name.split(PROVIDER_MODEL_DELIMITER, 1)[0]

        def on_api_key_entry_result(result: bool | None) -> None:
            if result is not True:
                return
            self._apply_model_selection(app, model_name)

        app.push_screen(
            ApiKeyEntryScreen(provider_id, app.state_manager),
            on_api_key_entry_result,
        )

    def _apply_model_selection(self, app: TextualReplApp, full_model: str) -> None:
        import copy

        from tunacode.core.agents.agent_components.agent_config import invalidate_agent_cache
        from tunacode.core.ui_api.configuration import get_model_context_window
        from tunacode.core.ui_api.user_configuration import record_recent_model, save_config

        state_manager = app.state_manager
        session = state_manager.session
        old_model = session.current_model
        old_default = session.user_config["default_model"]
        old_recent_models = copy.deepcopy(session.user_config["recent_models"])
        old_max_tokens = session.conversation.max_tokens
        new_max_tokens = get_model_context_window(full_model)

        try:
            session.current_model = full_model
            session.user_config["default_model"] = full_model
            record_recent_model(session.user_config, full_model)
            session.conversation.max_tokens = new_max_tokens
            save_config(state_manager)
            invalidate_agent_cache(full_model, state_manager)
            app._update_resource_bar()
            app.notify(f"Model: {full_model}")
        except Exception:
            session.current_model = old_model
            session.user_config["default_model"] = old_default
            session.user_config["recent_models"] = old_recent_models
            session.conversation.max_tokens = old_max_tokens
            raise

    def _open_model_picker(self, app: TextualReplApp) -> None:
        from tunacode.core.ui_api.user_configuration import get_recent_models

        from tunacode.ui.screens.api_key_entry import ApiKeyEntryScreen
        from tunacode.ui.screens.model_picker import ModelPickerScreen

        state_manager = app.state_manager
        session = state_manager.session
        current_model = session.current_model
        recent_models = get_recent_models(session.user_config)

        def on_model_selected(full_model: str | None) -> None:
            if full_model is None:
                return

            if _validate_provider_api_key_with_notification(
                full_model,
                session.user_config,
                app,
                show_config_path=True,
            ):
                self._apply_model_selection(app, full_model)
                return

            provider_id = full_model.split(PROVIDER_MODEL_DELIMITER, 1)[0]

            def on_api_key_entry_result(result: bool | None) -> None:
                if result is not True:
                    return

                self._apply_model_selection(app, full_model)

            app.push_screen(
                ApiKeyEntryScreen(provider_id, state_manager),
                on_api_key_entry_result,
            )

        app.push_screen(
            ModelPickerScreen(current_model, recent_models),
            on_model_selected,
        )
