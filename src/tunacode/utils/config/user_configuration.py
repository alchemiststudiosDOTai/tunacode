"""
Module: tunacode.utils.user_configuration

Provides user configuration file management.
Handles loading, saving, and updating user preferences including model selection.
"""

import json
from json import JSONDecodeError
from typing import TYPE_CHECKING

from tunacode.configuration.settings import ApplicationSettings
from tunacode.exceptions import ConfigurationError
from tunacode.types import ModelName, UserConfig

if TYPE_CHECKING:
    from tunacode.types.state import StateManagerProtocol


def load_config() -> UserConfig | None:
    """Load user config from file.

    Returns None when the config file does not exist.
    Raises ConfigurationError for invalid JSON or other failures.
    """
    app_settings = ApplicationSettings()
    try:
        with open(app_settings.paths.config_file) as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except JSONDecodeError as err:
        msg = f"Invalid JSON in config file at {app_settings.paths.config_file}"
        raise ConfigurationError(msg) from err
    except Exception as err:
        raise ConfigurationError(f"Failed to load configuration: {err}") from err


def save_config(state_manager: "StateManagerProtocol") -> None:
    """Save user config to file."""
    app_settings = ApplicationSettings()
    try:
        app_settings.paths.config_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

        with open(app_settings.paths.config_file, "w") as f:
            json.dump(state_manager.session.user_config, f, indent=4)
    except PermissionError as e:
        raise ConfigurationError(
            f"Permission denied writing to {app_settings.paths.config_file}: {e}"
        ) from e
    except OSError as e:
        raise ConfigurationError(
            f"Failed to save configuration to {app_settings.paths.config_file}: {e}"
        ) from e
    except Exception as e:
        raise ConfigurationError(f"Unexpected error saving configuration: {e}") from e


def set_default_model(model_name: ModelName, state_manager: "StateManagerProtocol") -> None:
    """Set the default model in the user config and save."""
    state_manager.session.user_config["default_model"] = model_name
    save_config(state_manager)
