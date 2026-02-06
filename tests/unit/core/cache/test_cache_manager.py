"""Tests for CacheManager singleton."""

import tempfile
from pathlib import Path

import pytest

from tunacode.infrastructure.cache.manager import (
    CACHE_AGENTS,
    CacheManager,
    ManualStrategy,
    MtimeStrategy,
    get_cache_manager,
)


@pytest.fixture(autouse=True)
def reset_cache_manager():
    """Ensure fresh CacheManager for each test."""
    CacheManager.reset_instance()
    yield
    CacheManager.reset_instance()


class TestSingleton:
    def test_get_instance_returns_same_object(self):
        a = CacheManager.get_instance()
        b = CacheManager.get_instance()
        assert a is b

    def test_reset_instance_creates_new_object(self):
        a = CacheManager.get_instance()
        CacheManager.reset_instance()
        b = CacheManager.get_instance()
        assert a is not b

    def test_get_cache_manager_convenience(self):
        mgr = get_cache_manager()
        assert mgr is CacheManager.get_instance()


class TestNamedCaches:
    def test_get_cache_returns_dict(self):
        mgr = get_cache_manager()
        cache = mgr.get_cache(CACHE_AGENTS)
        assert isinstance(cache, dict)
        assert len(cache) == 0

    def test_get_cache_returns_same_dict(self):
        mgr = get_cache_manager()
        a = mgr.get_cache("test")
        b = mgr.get_cache("test")
        assert a is b

    def test_get_cache_lazy_registers(self):
        mgr = get_cache_manager()
        cache = mgr.get_cache("lazy")
        cache["key"] = "value"
        assert mgr.get_cache("lazy")["key"] == "value"

    def test_register_cache_idempotent(self):
        mgr = get_cache_manager()
        mgr.register_cache("x")
        cache = mgr.get_cache("x")
        cache["a"] = 1
        mgr.register_cache("x")  # should not clear
        assert cache["a"] == 1

    def test_clear_cache_by_name(self):
        mgr = get_cache_manager()
        cache = mgr.get_cache("test")
        cache["a"] = 1
        cache["b"] = 2
        mgr.clear_cache("test")
        assert len(cache) == 0

    def test_clear_cache_unknown_name_is_noop(self):
        mgr = get_cache_manager()
        mgr.clear_cache("nonexistent")  # should not raise

    def test_clear_all(self):
        mgr = get_cache_manager()
        c1 = mgr.get_cache("one")
        c2 = mgr.get_cache("two")
        c1["a"] = 1
        c2["b"] = 2
        mgr.clear_all()
        assert len(c1) == 0
        assert len(c2) == 0


class TestManualStrategy:
    def test_is_never_stale(self):
        strategy = ManualStrategy()
        assert strategy.is_stale("key", {}) is False
        assert strategy.is_stale("key", {"whatever": True}) is False


class TestMtimeStrategy:
    def test_stale_when_no_path(self):
        strategy = MtimeStrategy()
        assert strategy.is_stale("key", {}) is True

    def test_stale_when_no_mtime(self):
        strategy = MtimeStrategy()
        assert strategy.is_stale("key", {"path": "/tmp/nonexistent"}) is True

    def test_stale_when_file_missing(self):
        strategy = MtimeStrategy()
        assert strategy.is_stale("key", {"path": "/tmp/no_such_file_abc123", "mtime": 1.0}) is True

    def test_not_stale_when_mtime_matches(self):
        strategy = MtimeStrategy()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp_path = Path(f.name)
            f.write(b"data")
        try:
            mtime = tmp_path.stat().st_mtime
            assert strategy.is_stale("key", {"path": str(tmp_path), "mtime": mtime}) is False
        finally:
            tmp_path.unlink()

    def test_stale_when_mtime_differs(self):
        strategy = MtimeStrategy()
        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp_path = Path(f.name)
            f.write(b"data")
        try:
            assert strategy.is_stale("key", {"path": str(tmp_path), "mtime": 0.0}) is True
        finally:
            tmp_path.unlink()


class TestMetadata:
    def test_set_and_get_metadata(self):
        mgr = get_cache_manager()
        mgr.register_cache("test")
        mgr.set_metadata("test", "key1", {"path": "/tmp/foo", "mtime": 123.0})
        meta = mgr.get_metadata("test", "key1")
        assert meta == {"path": "/tmp/foo", "mtime": 123.0}

    def test_get_metadata_missing_returns_none(self):
        mgr = get_cache_manager()
        assert mgr.get_metadata("missing", "key") is None


class TestInvalidateStale:
    def test_invalidate_stale_removes_entries(self):
        mgr = get_cache_manager()
        mgr.register_cache("mtime_cache", MtimeStrategy())
        cache = mgr.get_cache("mtime_cache")
        cache["gone"] = "value"
        mgr.set_metadata("mtime_cache", "gone", {"path": "/no/such/file", "mtime": 1.0})
        removed = mgr.invalidate_stale()
        assert removed == 1
        assert "gone" not in cache

    def test_invalidate_stale_keeps_fresh(self):
        mgr = get_cache_manager()
        mgr.register_cache("manual_cache", ManualStrategy())
        cache = mgr.get_cache("manual_cache")
        cache["kept"] = "value"
        removed = mgr.invalidate_stale()
        assert removed == 0
        assert "kept" in cache

    def test_clear_cache_also_clears_metadata(self):
        mgr = get_cache_manager()
        mgr.register_cache("test")
        mgr.set_metadata("test", "k", {"x": 1})
        mgr.clear_cache("test")
        assert mgr.get_metadata("test", "k") is None
