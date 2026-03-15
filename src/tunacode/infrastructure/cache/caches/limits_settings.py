from __future__ import annotations

from typing import cast

from tunacode.infrastructure.cache import ManualStrategy, get_cache, register_cache

LIMITS_SETTINGS_CACHE_NAME = "tunacode.limits.settings"
LIMITS_SETTINGS_KEY = "settings"

register_cache(LIMITS_SETTINGS_CACHE_NAME, ManualStrategy())


def get_settings() -> dict[str, object] | None:
    cache = get_cache(LIMITS_SETTINGS_CACHE_NAME)
    cached = cache.get(LIMITS_SETTINGS_KEY)
    if cached is None:
        return None
    if not isinstance(cached, dict):
        raise TypeError(f"Limits settings cache value must be dict, got {type(cached).__name__}")
    return cast(dict[str, object], cached)


def set_settings(settings: dict[str, object]) -> None:
    get_cache(LIMITS_SETTINGS_CACHE_NAME).set(LIMITS_SETTINGS_KEY, settings)


def clear_settings_cache() -> None:
    get_cache(LIMITS_SETTINGS_CACHE_NAME).clear()
