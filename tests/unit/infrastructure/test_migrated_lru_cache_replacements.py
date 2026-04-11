from __future__ import annotations

from pathlib import Path

import pytest

from tunacode.configuration.models import get_cached_models_registry, load_models_registry

from tunacode.tools.utils.ripgrep import get_ripgrep_binary_path

from tunacode.infrastructure.cache import clear_all


@pytest.fixture
def clean_caches() -> None:
    clear_all()
    yield
    clear_all()


def test_models_registry_cache_clears_via_clear_all(clean_caches: None) -> None:
    assert get_cached_models_registry() is None

    loaded = load_models_registry()
    assert isinstance(loaded, dict)
    assert get_cached_models_registry() is not None

    clear_all()

    assert get_cached_models_registry() is None


def test_ripgrep_binary_path_cache_clears_via_clear_all(
    clean_caches: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_rg = tmp_path / "rg-first"
    second_rg = tmp_path / "rg-second"
    first_rg.write_text("", encoding="utf-8")
    second_rg.write_text("", encoding="utf-8")

    monkeypatch.setenv("TUNACODE_RIPGREP_PATH", str(first_rg))
    first = get_ripgrep_binary_path()
    assert first == first_rg

    monkeypatch.setenv("TUNACODE_RIPGREP_PATH", str(second_rg))
    second = get_ripgrep_binary_path()

    # Cached.
    assert second == first_rg

    clear_all()

    third = get_ripgrep_binary_path()
    assert third == second_rg
