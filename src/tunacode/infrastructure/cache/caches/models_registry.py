from __future__ import annotations

from typing import cast

from tunacode.infrastructure.cache import ManualStrategy, get_cache, register_cache

MODELS_REGISTRY_CACHE_NAME = "tunacode.models.registry"
MODELS_REGISTRY_KEY = "registry"

register_cache(MODELS_REGISTRY_CACHE_NAME, ManualStrategy())


def get_registry() -> dict[str, object] | None:
    cache = get_cache(MODELS_REGISTRY_CACHE_NAME)
    cached = cache.get(MODELS_REGISTRY_KEY)
    if cached is None:
        return None
    if not isinstance(cached, dict):
        raise TypeError(f"Models registry cache value must be dict, got {type(cached).__name__}")
    return cast(dict[str, object], cached)


def set_registry(registry: dict[str, object]) -> None:
    get_cache(MODELS_REGISTRY_CACHE_NAME).set(MODELS_REGISTRY_KEY, registry)


def clear_registry_cache() -> None:
    get_cache(MODELS_REGISTRY_CACHE_NAME).clear()
