from __future__ import annotations

from typing import cast

from tunacode.types import UserSettings

from tunacode.infrastructure.cache import ManualStrategy, get_cache, register_cache

LIMITS_SETTINGS_CACHE_NAME = "tunacode.limits.settings"
LIMITS_SETTINGS_KEY = "settings"

register_cache(LIMITS_SETTINGS_CACHE_NAME, ManualStrategy())


def get_settings() -> UserSettings | None:
    cache = get_cache(LIMITS_SETTINGS_CACHE_NAME)
    cached = cache.get(LIMITS_SETTINGS_KEY)
    if cached is None:
        return None
    return cast(UserSettings, cached)


def set_settings(settings: UserSettings) -> None:
    get_cache(LIMITS_SETTINGS_CACHE_NAME).set(LIMITS_SETTINGS_KEY, settings)


def clear_settings_cache() -> None:
    get_cache(LIMITS_SETTINGS_CACHE_NAME).clear()
