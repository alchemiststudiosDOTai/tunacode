"""Tests for IgnoreManager."""

import os
import time
from pathlib import Path

from tunacode.tools.ignore import get_ignore_manager

DEFAULT_IGNORED_DIR_NAME = "node_modules"
DEFAULT_IGNORED_FILE_NAME = "index.js"
SOURCE_DIR_NAME = "src"
SOURCE_FILE_NAME = "main.py"
GITIGNORE_FILE_NAME = ".gitignore"
GITIGNORE_IGNORED_FILE = "ignored.txt"
GITIGNORE_IGNORED_DIR_NAME = "ignored_dir"
GITIGNORE_DIR_SUFFIX = "/"
GITIGNORE_LINE_SEPARATOR = "\n"
KEEP_FILE_NAME = "keep.txt"
MTIME_OFFSET_SECONDS = 10


def test_should_ignore_default_dirs(tmp_path: Path) -> None:
    """Default exclude directories should be ignored."""
    ignore_manager = get_ignore_manager(tmp_path)
    ignored_dir = tmp_path / DEFAULT_IGNORED_DIR_NAME
    ignored_file = ignored_dir / DEFAULT_IGNORED_FILE_NAME

    assert ignore_manager.should_ignore_dir(ignored_dir)
    assert ignore_manager.should_ignore(ignored_file)


def test_filter_paths_excludes_ignored(tmp_path: Path) -> None:
    """filter_paths should skip ignored paths."""
    ignore_manager = get_ignore_manager(tmp_path)
    keep_path = tmp_path / SOURCE_DIR_NAME / SOURCE_FILE_NAME
    ignored_path = tmp_path / DEFAULT_IGNORED_DIR_NAME / DEFAULT_IGNORED_FILE_NAME

    filtered_paths = list(ignore_manager.filter_paths([keep_path, ignored_path]))

    assert filtered_paths == [keep_path]


def test_cache_invalidation_on_mtime(tmp_path: Path) -> None:
    """Ignore manager cache should invalidate on .gitignore mtime change."""
    gitignore_path = tmp_path / GITIGNORE_FILE_NAME
    gitignore_path.write_text(GITIGNORE_IGNORED_FILE)

    first_manager = get_ignore_manager(tmp_path)
    second_manager = get_ignore_manager(tmp_path)

    assert first_manager is second_manager

    new_mtime = time.time() + MTIME_OFFSET_SECONDS
    os.utime(gitignore_path, (new_mtime, new_mtime))

    third_manager = get_ignore_manager(tmp_path)

    assert third_manager is not second_manager


def test_gitignore_patterns_loaded(tmp_path: Path) -> None:
    """Root .gitignore patterns should be loaded and applied."""
    gitignore_path = tmp_path / GITIGNORE_FILE_NAME
    gitignore_lines = [
        GITIGNORE_IGNORED_FILE,
        f"{GITIGNORE_IGNORED_DIR_NAME}{GITIGNORE_DIR_SUFFIX}",
    ]
    gitignore_content = GITIGNORE_LINE_SEPARATOR.join(gitignore_lines)
    gitignore_path.write_text(gitignore_content)

    ignore_manager = get_ignore_manager(tmp_path)
    ignored_file = tmp_path / GITIGNORE_IGNORED_FILE
    ignored_dir = tmp_path / GITIGNORE_IGNORED_DIR_NAME
    ignored_dir_file = ignored_dir / KEEP_FILE_NAME
    keep_file = tmp_path / KEEP_FILE_NAME

    assert ignore_manager.should_ignore(ignored_file)
    assert ignore_manager.should_ignore_dir(ignored_dir)
    assert ignore_manager.should_ignore(ignored_dir_file)
    assert not ignore_manager.should_ignore(keep_file)
