"""Core user configuration facade."""

from __future__ import annotations

from tunacode.configuration.user_config import (
    UserConfigStateManager,
)
from tunacode.configuration.user_config import (
    load_config_with_defaults as _load_config_with_defaults,
)
from tunacode.configuration.user_config import (
    save_config as _save_config,
)
from tunacode.types import UserConfig

__all__: list[str] = ["load_config_with_defaults", "save_config"]


def load_config_with_defaults(default_config: UserConfig) -> UserConfig:
    """Load user config from disk and merge with defaults.

    Args:
        default_config: Default configuration to merge against.

    Returns:
        The merged user configuration.
    """
    return _load_config_with_defaults(default_config)


def save_config(state_manager: UserConfigStateManager) -> None:
    """Persist the current user configuration to disk."""
    _save_config(state_manager)
