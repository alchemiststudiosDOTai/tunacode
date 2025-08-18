"""
Module: sidekick.utils.user_configuration

Provides user configuration file management.
Handles loading, saving, and updating user preferences including
model selection and MCP server settings.
"""

import json
from json import JSONDecodeError
from typing import TYPE_CHECKING, Optional

from tunacode.configuration.settings import ApplicationSettings
from tunacode.exceptions import ConfigurationError
from tunacode.types import MCPServers, ModelName, UserConfig

if TYPE_CHECKING:
    from tunacode.core.state import StateManager


import hashlib

_config_fingerprint = None
_config_cache = None


def compute_config_fingerprint(config_obj) -> str:
    """Returns a short hash/fingerprint for a config object/searchable for fastpath usage."""
    b = json.dumps(config_obj, sort_keys=True).encode()
    return hashlib.sha1(b).hexdigest()[:12]


def load_config() -> Optional[UserConfig]:
    """Load user config from file, using fingerprint fast path if available."""
    global _config_fingerprint, _config_cache
    app_settings = ApplicationSettings()
    try:
        with open(app_settings.paths.config_file, "r") as f:
            raw = f.read()
            loaded = json.loads(raw)
            new_fp = hashlib.sha1(raw.encode()).hexdigest()[:12]
            # If hash matches, return in-memory cached config object
            if new_fp == _config_fingerprint and _config_cache is not None:
                return _config_cache
            # else, update fast path
            _config_fingerprint = new_fp
            _config_cache = loaded

            # Initialize onboarding defaults for new configurations
            _ensure_onboarding_defaults(loaded)

            return loaded
    except FileNotFoundError:
        return None
    except JSONDecodeError:
        raise ConfigurationError(f"Invalid JSON in config file at {app_settings.paths.config_file}")
    except Exception as e:
        raise ConfigurationError(e)


def save_config(state_manager: "StateManager") -> bool:
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
        )
    except OSError as e:
        raise ConfigurationError(
            f"Failed to save configuration to {app_settings.paths.config_file}: {e}"
        )
    except Exception as e:
        raise ConfigurationError(f"Unexpected error saving configuration: {e}")


def get_mcp_servers(state_manager: "StateManager") -> MCPServers:
    """Retrieve MCP server configurations from user config"""
    return state_manager.session.user_config.get("mcpServers", [])


def set_default_model(model_name: ModelName, state_manager: "StateManager") -> bool:
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
    from datetime import datetime

    if "settings" not in config:
        config["settings"] = {}

    settings = config["settings"]

    # Set tutorial enabled by default for new users
    if "enable_tutorial" not in settings:
        settings["enable_tutorial"] = True

    # Set first installation date if not present (for new installs)
    if "first_installation_date" not in settings:
        settings["first_installation_date"] = datetime.now().isoformat()


def initialize_first_time_user(state_manager: "StateManager") -> None:
    """Initialize first-time user settings and save configuration."""
    from datetime import datetime

    # Ensure settings section exists
    if "settings" not in state_manager.session.user_config:
        state_manager.session.user_config["settings"] = {}

    settings = state_manager.session.user_config["settings"]

    # Only set installation date if it doesn't exist (true first-time)
    if "first_installation_date" not in settings:
        settings["first_installation_date"] = datetime.now().isoformat()
        settings["enable_tutorial"] = True

        # Save the updated configuration
        try:
            save_config(state_manager)
        except ConfigurationError:
            # Non-critical error, continue without failing
            pass
