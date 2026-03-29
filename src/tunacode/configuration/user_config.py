"""User configuration file management.

Handles loading, saving, and updating user preferences including model selection.
"""

import copy
import json
from json import JSONDecodeError
from typing import Protocol

from tunacode.configuration.defaults import DEFAULT_USER_CONFIG
from tunacode.configuration.settings import ApplicationSettings
from tunacode.constants import MODEL_PICKER_RECENT_LIMIT
from tunacode.exceptions import ConfigurationError
from tunacode.types import (
    EnvConfig,
    LspSettings,
    ModelName,
    RipgrepSettings,
    UserConfig,
    UserSettings,
)


class UserConfigSession(Protocol):
    """Minimal session interface for user config persistence."""

    user_config: UserConfig


class UserConfigStateManager(Protocol):
    """State manager interface needed for config persistence."""

    @property
    def session(self) -> UserConfigSession:
        """Return the session containing user config."""


def _merge_config_value(default_value: object, override_value: object) -> object:
    """Recursively merge persisted config onto defaults."""
    if isinstance(default_value, dict) and isinstance(override_value, dict):
        merged_value = copy.deepcopy(default_value)
        for key, value in override_value.items():
            if key in merged_value:
                merged_value[key] = _merge_config_value(merged_value[key], value)
            else:
                merged_value[key] = copy.deepcopy(value)
        return merged_value
    return copy.deepcopy(override_value)


def load_config(default_config: UserConfig | None = None) -> UserConfig | None:
    """Load user config from file.

    Returns None when the config file does not exist.
    Raises ConfigurationError for invalid JSON or other failures.
    """
    app_settings = ApplicationSettings()
    config_defaults = default_config or DEFAULT_USER_CONFIG
    try:
        with open(app_settings.paths.config_file) as f:
            raw_config = json.load(f)
        merged_config = _merge_config_value(config_defaults, raw_config)
        return validate_user_config(merged_config)
    except FileNotFoundError:
        return None
    except JSONDecodeError as err:
        msg = f"Invalid JSON in config file at {app_settings.paths.config_file}"
        raise ConfigurationError(msg) from err
    except (KeyError, TypeError, ValueError) as err:
        raise ConfigurationError(
            f"Invalid user config at {app_settings.paths.config_file}: {err}"
        ) from err
    except Exception as err:
        raise ConfigurationError(f"Failed to load configuration: {err}") from err


def _require_mapping(value: object, *, path: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{path} must be an object, got {type(value).__name__}")
    if not all(isinstance(key, str) for key in value):
        raise TypeError(f"{path} keys must be strings")
    return value


def _require_str(value: object, *, path: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{path} must be a string, got {type(value).__name__}")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{path} must be a non-empty string")
    return stripped


def _require_int(value: object, *, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{path} must be an integer, got {type(value).__name__}")
    return value


def _require_optional_int(value: object, *, path: str) -> int | None:
    if value is None:
        return None
    return _require_int(value, path=path)


def _require_float(value: object, *, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{path} must be a float, got {type(value).__name__}")
    return float(value)


def _require_bool(value: object, *, path: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{path} must be a bool, got {type(value).__name__}")
    return value


def _validate_env(value: object) -> EnvConfig:
    raw_env = _require_mapping(value, path="env")
    env: EnvConfig = {}
    for key, raw_item in raw_env.items():
        if not isinstance(raw_item, str):
            raise TypeError(f"env.{key} must be a string, got {type(raw_item).__name__}")
        env[key] = raw_item
    return env


def _validate_recent_models(value: object) -> list[ModelName]:
    if not isinstance(value, list):
        raise TypeError(f"recent_models must be a list, got {type(value).__name__}")

    recent_models: list[ModelName] = []
    for index, raw_model in enumerate(value):
        recent_models.append(_require_str(raw_model, path=f"recent_models[{index}]"))
    return recent_models


def _validate_ripgrep_settings(value: object) -> RipgrepSettings:
    raw_ripgrep = _require_mapping(value, path="settings.ripgrep")
    return RipgrepSettings(
        timeout=_require_int(raw_ripgrep["timeout"], path="settings.ripgrep.timeout"),
        max_results=_require_int(
            raw_ripgrep["max_results"],
            path="settings.ripgrep.max_results",
        ),
        enable_metrics=_require_bool(
            raw_ripgrep["enable_metrics"],
            path="settings.ripgrep.enable_metrics",
        ),
    )


def _validate_lsp_settings(value: object) -> LspSettings:
    raw_lsp = _require_mapping(value, path="settings.lsp")
    return LspSettings(
        enabled=_require_bool(raw_lsp["enabled"], path="settings.lsp.enabled"),
        timeout=_require_float(raw_lsp["timeout"], path="settings.lsp.timeout"),
    )


def _validate_settings(value: object) -> UserSettings:
    raw_settings = _require_mapping(value, path="settings")
    return UserSettings(
        max_retries=_require_int(raw_settings["max_retries"], path="settings.max_retries"),
        max_iterations=_require_int(
            raw_settings["max_iterations"],
            path="settings.max_iterations",
        ),
        request_delay=_require_float(
            raw_settings["request_delay"],
            path="settings.request_delay",
        ),
        global_request_timeout=_require_float(
            raw_settings["global_request_timeout"],
            path="settings.global_request_timeout",
        ),
        tool_strict_validation=_require_bool(
            raw_settings["tool_strict_validation"],
            path="settings.tool_strict_validation",
        ),
        theme=_require_str(raw_settings["theme"], path="settings.theme"),
        stream_agent_text=_require_bool(
            raw_settings["stream_agent_text"],
            path="settings.stream_agent_text",
        ),
        max_command_output=_require_int(
            raw_settings["max_command_output"],
            path="settings.max_command_output",
        ),
        max_tokens=_require_optional_int(
            raw_settings["max_tokens"],
            path="settings.max_tokens",
        ),
        ripgrep=_validate_ripgrep_settings(raw_settings["ripgrep"]),
        lsp=_validate_lsp_settings(raw_settings["lsp"]),
    )


def validate_user_config(value: object) -> UserConfig:
    raw_config = _require_mapping(value, path="user_config")
    return UserConfig(
        default_model=_require_str(raw_config["default_model"], path="default_model"),
        recent_models=_validate_recent_models(raw_config["recent_models"]),
        env=_validate_env(raw_config["env"]),
        settings=_validate_settings(raw_config["settings"]),
    )


def load_config_with_defaults(default_config: UserConfig) -> UserConfig:
    """Load user config from file, or return a full default config when missing."""
    user_config = load_config(default_config)
    if user_config is None:
        return copy.deepcopy(default_config)
    return user_config


def get_recent_models(
    user_config: UserConfig,
    *,
    available_models: set[str] | None = None,
    limit: int = MODEL_PICKER_RECENT_LIMIT,
) -> list[str]:
    """Return normalized recent models, optionally filtered to known entries."""
    if limit <= 0:
        return []

    raw_recent_models = user_config["recent_models"]

    normalized_recent_models: list[str] = []
    seen_models: set[str] = set()

    for raw_model in raw_recent_models:
        if not isinstance(raw_model, str):
            raise TypeError("recent model entries must be strings")

        model_name = raw_model.strip()
        if not model_name:
            raise ValueError("recent model entries must be non-empty strings")

        if available_models is not None and model_name not in available_models:
            continue

        if model_name in seen_models:
            continue

        seen_models.add(model_name)
        normalized_recent_models.append(model_name)

        if len(normalized_recent_models) >= limit:
            break

    return normalized_recent_models


def record_recent_model(user_config: UserConfig, model_name: ModelName) -> list[str]:
    """Promote a model to the front of the recent-model MRU list."""
    normalized_model_name = model_name.strip()
    if not normalized_model_name:
        return get_recent_models(user_config)

    recent_models = get_recent_models(user_config)
    recent_models = [
        recent_model for recent_model in recent_models if recent_model != normalized_model_name
    ]
    recent_models.insert(0, normalized_model_name)
    user_config["recent_models"] = recent_models[:MODEL_PICKER_RECENT_LIMIT]
    return user_config["recent_models"]


def save_config(state_manager: UserConfigStateManager) -> None:
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


def set_default_model(model_name: ModelName, state_manager: UserConfigStateManager) -> None:
    """Set the default model in the user config and save."""
    state_manager.session.user_config["default_model"] = model_name
    save_config(state_manager)
