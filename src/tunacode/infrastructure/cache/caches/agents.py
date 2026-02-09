from __future__ import annotations

from typing import cast

from tinyagent import Agent

from tunacode.types import ModelName

from tunacode.infrastructure.cache import ManualStrategy, get_cache, register_cache

AGENTS_CACHE_NAME = "tunacode.agents"

register_cache(AGENTS_CACHE_NAME, ManualStrategy())


def get_agent(model: ModelName, *, expected_version: int) -> Agent | None:
    """Return a cached agent when its cached version matches expected_version.

    If the cache contains an agent with a mismatched (or missing) version, the
    entry is invalidated and None is returned.
    """

    cache = get_cache(AGENTS_CACHE_NAME)

    cached = cache.get(model)
    if cached is None:
        return None

    cached_version = cache.get_metadata(model)
    if cached_version is None:
        cache.delete(model)
        return None

    if not isinstance(cached_version, int):
        raise TypeError(
            f"Agent cache version metadata must be int, got {type(cached_version).__name__}"
        )

    if cached_version != expected_version:
        cache.delete(model)
        return None

    if not isinstance(cached, Agent):
        raise TypeError(f"Agent cache value must be Agent, got {type(cached).__name__}")

    return cast(Agent, cached)


def set_agent(model: ModelName, *, agent: Agent, version: int) -> None:
    cache = get_cache(AGENTS_CACHE_NAME)
    cache.set(model, agent)
    cache.set_metadata(model, version)


def invalidate_agent(model: ModelName) -> bool:
    cache = get_cache(AGENTS_CACHE_NAME)
    return cache.delete(model)


def clear_agents() -> None:
    get_cache(AGENTS_CACHE_NAME).clear()
