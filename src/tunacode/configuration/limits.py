"""Centralized limit configuration with cascading defaults.

Precedence: explicit setting > standard default

This allows:
- Users to override individual limits
- Big model users to set custom limits
"""

from __future__ import annotations

from tunacode.configuration.defaults import DEFAULT_USER_CONFIG
from tunacode.types import UserSettings

from tunacode.infrastructure.cache.caches import limits_settings as limits_settings_cache


def _load_settings() -> UserSettings:
    """Load and cache settings from user config."""

    cached = limits_settings_cache.get_settings()
    if cached is not None:
        return cached

    # Import here to avoid circular imports.
    from tunacode.configuration.user_config import load_config

    config = load_config()
    settings = config["settings"] if config is not None else DEFAULT_USER_CONFIG["settings"]

    limits_settings_cache.set_settings(settings)
    return settings


def get_command_limit() -> int:
    """Get max command output length for bash tool."""
    return _load_settings()["max_command_output"]


def get_max_tokens() -> int | None:
    """Get max response tokens. Returns None if not set (no limit)."""
    return _load_settings()["max_tokens"]
