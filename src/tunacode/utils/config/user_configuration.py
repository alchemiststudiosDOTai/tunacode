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

import hashlib


class ConfigLoader:
    """Handles loading and caching user configuration."""

    def __init__(self):
        self._fingerprint: str | None = None
        self._cache: UserConfig | None = None

    def load_config(self) -> UserConfig | None:
        """Load user config from file, using fingerprint fast path if available."""
        app_settings = ApplicationSettings()
        try:
            with open(app_settings.paths.config_file) as f:
                raw = f.read()
                loaded = json.loads(raw)
                new_fp = hashlib.sha1(raw.encode()).hexdigest()[:12]
                # If hash matches, return in-memory cached config object
                if new_fp == self._fingerprint and self._cache is not None:
                    return self._cache
                # else, update fast path
                self._fingerprint = new_fp
                self._cache = loaded

                # Initialize onboarding defaults for new configurations
                _ensure_onboarding_defaults(loaded)

                return loaded
        except FileNotFoundError:
            return None
        except JSONDecodeError as err:
            msg = f"Invalid JSON in config file at {app_settings.paths.config_file}"
            raise ConfigurationError(msg) from err
        except Exception as err:
            raise ConfigurationError(f"Failed to load configuration: {err}") from err


# Global instance for backward compatibility
_config_loader = ConfigLoader()


def load_config() -> UserConfig | None:
    """Load user config from file, using fingerprint fast path if available."""
    return _config_loader.load_config()


def save_config(state_manager: "StateManagerProtocol") -> bool:
    """Save user config to file"""
    app_settings = ApplicationSettings()
    try:
        # Ensure config directory exists
        app_settings.paths.config_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

        # Write config file
        with open(app_settings.paths.config_file, "w") as f:
            json.dump(state_manager.session.user_config, f, indent=4)
        return True
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


def set_default_model(model_name: ModelName, state_manager: "StateManagerProtocol") -> bool:
    """Set the default model in the user config and save"""
    state_manager.session.user_config["default_model"] = model_name
    try:
        save_config(state_manager)
        return True
    except ConfigurationError:
        # Re-raise ConfigurationError to be handled by caller
        raise


def _ensure_onboarding_defaults(config: UserConfig) -> None:
    """Ensure onboarding-related default settings are present in config."""
    if "settings" not in config:
        config["settings"] = {}
