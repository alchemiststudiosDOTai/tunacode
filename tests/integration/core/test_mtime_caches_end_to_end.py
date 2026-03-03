from __future__ import annotations

import os
from pathlib import Path

import pytest

from tunacode.tools.ignore import get_ignore_manager

from tunacode.infrastructure.cache import clear_all

from tunacode.core.agents.agent_components.agent_config import load_tunacode_context

MTIME_INCREMENT_NS = 1_000_000_000


@pytest.fixture
def clean_cache_manager() -> None:
    """Ensure caches are empty without resetting the CacheManager singleton."""
    clear_all()
    yield
    clear_all()


def test_tunacode_context_cache_invalidates_on_mtime_ns(
    clean_cache_manager: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))

    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.chdir(project_root)

    agents_path = project_root / "AGENTS.md"
    agents_path.write_text("one\n", encoding="utf-8")

    original_mtime_ns = os.stat(agents_path).st_mtime_ns

    first = load_tunacode_context()
    second = load_tunacode_context()

    assert first == second
    assert "one" in first[0]

    agents_path.write_text("two\n", encoding="utf-8")

    new_mtime_ns = original_mtime_ns + MTIME_INCREMENT_NS
    os.utime(agents_path, ns=(new_mtime_ns, new_mtime_ns))
    assert os.stat(agents_path).st_mtime_ns == new_mtime_ns

    third = load_tunacode_context()

    assert third != first
    assert "two" in third[0]


def test_ignore_manager_cache_invalidates_on_mtime_ns(
    clean_cache_manager: None,
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()

    gitignore_path = root / ".gitignore"
    gitignore_path.write_text("ignored.txt\n", encoding="utf-8")

    original_mtime_ns = os.stat(gitignore_path).st_mtime_ns

    first = get_ignore_manager(root)
    second = get_ignore_manager(root)

    assert first is second

    gitignore_path.write_text("ignored2.txt\n", encoding="utf-8")

    new_mtime_ns = original_mtime_ns + MTIME_INCREMENT_NS
    os.utime(gitignore_path, ns=(new_mtime_ns, new_mtime_ns))
    assert os.stat(gitignore_path).st_mtime_ns == new_mtime_ns

    third = get_ignore_manager(root)

    assert third is not second
