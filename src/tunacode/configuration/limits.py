"""Centralized limit configuration with cascading defaults.

Precedence: explicit setting > standard default

This allows:
- Users to override individual limits
- Big model users to set custom limits
"""

from tunacode.constants import (
    MAX_COMMAND_OUTPUT,
    MAX_FILES_IN_DIR,
)

from tunacode.infrastructure.cache.manager import CACHE_SETTINGS, get_cache_manager

_SETTINGS_KEY = "loaded_settings"


def _load_settings() -> dict:
    """Load and cache settings from user config via CacheManager."""
    cm = get_cache_manager()
    cache = cm.get_cache(CACHE_SETTINGS)

    if _SETTINGS_KEY in cache:
        return cache[_SETTINGS_KEY]

    # Import here to avoid circular imports
    from tunacode.configuration.user_config import load_config

    config = load_config()
    settings = config["settings"] if config and "settings" in config else {}
    cache[_SETTINGS_KEY] = settings
    return settings


def clear_cache() -> None:
    """Clear the settings cache. Call when config changes."""
    get_cache_manager().clear_cache(CACHE_SETTINGS)


def _get_limit(key: str, default: int) -> int:
    """Get a limit value with proper precedence.

    Precedence: explicit setting > standard default
    """
    settings = _load_settings()

    # If explicitly set, use that value
    if key in settings:
        return settings[key]

    return default


def get_command_limit() -> int:
    """Get max command output length for bash tool."""
    return _get_limit("max_command_output", MAX_COMMAND_OUTPUT)


def get_max_files_in_dir() -> int:
    """Get max files to list in list_dir tool."""
    return _get_limit("max_files_in_dir", MAX_FILES_IN_DIR)


def get_max_tokens() -> int | None:
    """Get max response tokens. Returns None if not set (no limit)."""
    settings = _load_settings()

    # Explicit setting takes precedence
    if "max_tokens" in settings:
        return settings["max_tokens"]

    return None
