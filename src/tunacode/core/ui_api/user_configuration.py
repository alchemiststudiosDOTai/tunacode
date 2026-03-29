"""Core user configuration facade."""

from __future__ import annotations

from tunacode.configuration.user_config import (
    UserConfigStateManager,
)
from tunacode.configuration.user_config import (
    get_recent_models as _get_recent_models,
)
from tunacode.configuration.user_config import (
    load_config_with_defaults as _load_config_with_defaults,
)
from tunacode.configuration.user_config import (
    record_recent_model as _record_recent_model,
)
from tunacode.configuration.user_config import (
    save_config as _save_config,
)
from tunacode.types import UserConfig


def load_config_with_defaults(default_config: UserConfig) -> UserConfig:
    """Load user config from disk, or fall back to the default config.

    Args:
        default_config: Full default configuration to use when no config file exists.

    Returns:
        The validated user configuration.
    """
    return _load_config_with_defaults(default_config)


def save_config(state_manager: UserConfigStateManager) -> None:
    """Persist the current user configuration to disk."""
    _save_config(state_manager)


def get_recent_models(
    user_config: UserConfig,
    *,
    available_models: set[str] | None = None,
) -> list[str]:
    """Return normalized recent models from user configuration."""
    return _get_recent_models(user_config, available_models=available_models)


def record_recent_model(user_config: UserConfig, model_name: str) -> list[str]:
    """Promote a model to the front of the recent-model MRU list."""
    return _record_recent_model(user_config, model_name)
