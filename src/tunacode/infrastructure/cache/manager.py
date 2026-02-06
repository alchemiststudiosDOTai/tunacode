"""CacheManager singleton for unified cache management.

Follows the LogManager singleton pattern from core/logging/manager.py:
thread-safe singleton with double-checked locking.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Invalidation strategies
# ---------------------------------------------------------------------------


@runtime_checkable
class InvalidationStrategy(Protocol):
    """Protocol for cache invalidation strategies."""

    def is_stale(self, key: str, metadata: dict[str, Any]) -> bool: ...


class ManualStrategy:
    """Invalidation only via explicit clear_cache() calls.

    Used for: agents, settings, models registry, xml prompts, ripgrep utils.
    """

    def is_stale(self, key: str, metadata: dict[str, Any]) -> bool:
        return False


class MtimeStrategy:
    """Invalidation based on file modification time.

    Used for: prompt cache (AGENTS.md), gitignore cache.
    Metadata must contain 'path' (str) and 'mtime' (float).
    """

    def is_stale(self, key: str, metadata: dict[str, Any]) -> bool:
        path_str = metadata.get("path")
        cached_mtime = metadata.get("mtime")
        if path_str is None or cached_mtime is None:
            return True
        path = Path(path_str)
        if not path.exists():
            return True
        return path.stat().st_mtime != cached_mtime


# ---------------------------------------------------------------------------
# CacheManager singleton
# ---------------------------------------------------------------------------

# Symbolic constants for registered cache names
CACHE_AGENTS = "agents"
CACHE_AGENT_VERSIONS = "agent_versions"
CACHE_PROMPTS = "prompts"
CACHE_SETTINGS = "settings"
CACHE_MODELS_REGISTRY = "models_registry"
CACHE_GITIGNORE = "gitignore"
CACHE_XML_PROMPTS = "xml_prompts"
CACHE_RIPGREP_PLATFORM = "ripgrep_platform"
CACHE_RIPGREP_BINARY = "ripgrep_binary"


class CacheManager:
    """Singleton manager for all application caches.

    Thread-safe singleton that provides named cache dictionaries
    with pluggable invalidation strategies.
    """

    _instance: CacheManager | None = None
    _instance_lock = threading.RLock()

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._caches: dict[str, dict[str, Any]] = {}
        self._strategies: dict[str, InvalidationStrategy] = {}
        self._metadata: dict[str, dict[str, dict[str, Any]]] = {}

    @classmethod
    def get_instance(cls) -> CacheManager:
        """Get the singleton CacheManager instance."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        with cls._instance_lock:
            cls._instance = None

    def register_cache(
        self,
        name: str,
        strategy: InvalidationStrategy | None = None,
    ) -> None:
        """Register a named cache with an invalidation strategy.

        Args:
            name: Unique cache name.
            strategy: Invalidation strategy. Defaults to ManualStrategy.
        """
        with self._lock:
            if name not in self._caches:
                self._caches[name] = {}
                self._strategies[name] = strategy or ManualStrategy()
                self._metadata[name] = {}

    def get_cache(self, name: str) -> dict[str, Any]:
        """Return the dict backing a named cache.

        Lazily registers with ManualStrategy if not yet registered.
        """
        with self._lock:
            if name not in self._caches:
                self.register_cache(name)
            return self._caches[name]

    def set_metadata(self, cache_name: str, key: str, metadata: dict[str, Any]) -> None:
        """Store metadata for a specific cache entry (e.g. mtime)."""
        with self._lock:
            if cache_name not in self._metadata:
                self._metadata[cache_name] = {}
            self._metadata[cache_name][key] = metadata

    def get_metadata(self, cache_name: str, key: str) -> dict[str, Any] | None:
        """Retrieve metadata for a specific cache entry."""
        with self._lock:
            return self._metadata.get(cache_name, {}).get(key)

    def clear_cache(self, name: str) -> None:
        """Clear all entries in a named cache."""
        with self._lock:
            if name in self._caches:
                self._caches[name].clear()
            if name in self._metadata:
                self._metadata[name].clear()

    def clear_all(self) -> None:
        """Clear every registered cache."""
        with self._lock:
            for cache in self._caches.values():
                cache.clear()
            for meta in self._metadata.values():
                meta.clear()

    def invalidate_stale(self) -> int:
        """Check all entries and remove stale ones. Returns count invalidated."""
        removed = 0
        with self._lock:
            for name, cache in self._caches.items():
                strategy = self._strategies.get(name)
                if strategy is None:
                    continue
                meta_store = self._metadata.get(name, {})
                stale_keys = [
                    key
                    for key in list(cache.keys())
                    if strategy.is_stale(key, meta_store.get(key, {}))
                ]
                for key in stale_keys:
                    del cache[key]
                    meta_store.pop(key, None)
                    removed += 1
        return removed


def get_cache_manager() -> CacheManager:
    """Get the global CacheManager instance."""
    return CacheManager.get_instance()
