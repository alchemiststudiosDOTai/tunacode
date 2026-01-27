"""Shared ignore logic for discovery tools."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pathspec

from tunacode.configuration.ignore_patterns import (
    DEFAULT_EXCLUDE_DIRS,
    DEFAULT_IGNORE_PATTERNS,
)

GITIGNORE_FILE_NAME = ".gitignore"
GITIGNORE_STYLE = "gitwildmatch"
PATH_SEPARATOR = "/"
MISSING_GITIGNORE_MTIME = 0.0
EMPTY_PATTERNS: tuple[str, ...] = ()
TEXT_ENCODING = "utf-8"
ROOT_NOT_FOUND_ERROR = "Ignore root not found: {root}."
ROOT_NOT_DIRECTORY_ERROR = "Ignore root is not a directory: {root}."
PATH_OUTSIDE_ROOT_ERROR = "Path '{path}' is outside ignore root '{root}'."


@dataclass(frozen=True)
class IgnoreCacheEntry:
    """Cached ignore manager with gitignore mtime tracking."""

    gitignore_mtime: float
    manager: IgnoreManager


IGNORE_MANAGER_CACHE: dict[Path, IgnoreCacheEntry] = {}


def _resolve_root(root: Path) -> Path:
    resolved_root = root.resolve()
    if not resolved_root.exists():
        message = ROOT_NOT_FOUND_ERROR.format(root=resolved_root)
        raise FileNotFoundError(message)
    if not resolved_root.is_dir():
        message = ROOT_NOT_DIRECTORY_ERROR.format(root=resolved_root)
        raise NotADirectoryError(message)
    return resolved_root


def _build_gitignore_path(root: Path) -> Path:
    return root / GITIGNORE_FILE_NAME


def _get_gitignore_mtime(gitignore_path: Path, gitignore_exists: bool) -> float:
    if not gitignore_exists:
        return MISSING_GITIGNORE_MTIME
    gitignore_stat = gitignore_path.stat()
    return gitignore_stat.st_mtime


def _read_gitignore_lines(gitignore_path: Path, gitignore_exists: bool) -> tuple[str, ...]:
    if not gitignore_exists:
        return EMPTY_PATTERNS
    gitignore_text = gitignore_path.read_text(encoding=TEXT_ENCODING)
    gitignore_lines = gitignore_text.splitlines()
    return tuple(gitignore_lines)


def _build_patterns(gitignore_lines: tuple[str, ...]) -> tuple[str, ...]:
    default_patterns = DEFAULT_IGNORE_PATTERNS
    return tuple(default_patterns) + gitignore_lines


def _compile_spec(patterns: tuple[str, ...]) -> pathspec.PathSpec:
    return pathspec.PathSpec.from_lines(GITIGNORE_STYLE, patterns)


def _normalize_extra_patterns(extra_patterns: Iterable[str]) -> tuple[str, ...]:
    filtered_patterns = tuple(pattern for pattern in extra_patterns if pattern)
    return filtered_patterns


class IgnoreManager:
    """Provides gitignore-aware file filtering for discovery tools."""

    def __init__(
        self,
        root: Path,
        patterns: Iterable[str],
        exclude_dirs: frozenset[str],
    ) -> None:
        """Precondition: root exists and is a directory."""
        self._root = root
        patterns_tuple = tuple(patterns)
        self._patterns = patterns_tuple
        self._exclude_dirs = exclude_dirs
        self._spec = _compile_spec(patterns_tuple)

    def should_ignore(self, path: Path) -> bool:
        """Return True when a file path matches ignore rules."""
        relative_path = self._normalize_path(path)
        is_fast_excluded = self._is_fast_excluded(relative_path)
        if is_fast_excluded:
            return True
        rel_posix = relative_path.as_posix()
        return self._spec.match_file(rel_posix)

    def should_ignore_dir(self, path: Path) -> bool:
        """Return True when a directory path matches ignore rules."""
        relative_path = self._normalize_path(path)
        is_fast_excluded = self._is_fast_excluded(relative_path)
        if is_fast_excluded:
            return True
        rel_posix = relative_path.as_posix()
        matches_file_rule = self._spec.match_file(rel_posix)
        if matches_file_rule:
            return True
        dir_path = f"{rel_posix}{PATH_SEPARATOR}"
        return self._spec.match_file(dir_path)

    def filter_paths(self, paths: Iterable[Path]) -> Iterator[Path]:
        """Yield only paths that are not ignored."""
        for path in paths:
            is_ignored = self.should_ignore(path)
            if is_ignored:
                continue
            yield path

    def with_additional_patterns(self, extra_patterns: Iterable[str]) -> IgnoreManager:
        """Return a new IgnoreManager with additional ignore patterns."""
        normalized_patterns = _normalize_extra_patterns(extra_patterns)
        if not normalized_patterns:
            return self
        combined_patterns = self._patterns + normalized_patterns
        return IgnoreManager(
            root=self._root,
            patterns=combined_patterns,
            exclude_dirs=self._exclude_dirs,
        )

    def _normalize_path(self, path: Path) -> Path:
        is_absolute = path.is_absolute()
        candidate_path = path if is_absolute else self._root / path
        try:
            relative_path = candidate_path.relative_to(self._root)
        except ValueError as exc:
            message = PATH_OUTSIDE_ROOT_ERROR.format(path=candidate_path, root=self._root)
            raise ValueError(message) from exc
        return relative_path

    def _is_fast_excluded(self, relative_path: Path) -> bool:
        path_parts = relative_path.parts
        exclude_dirs = self._exclude_dirs
        has_excluded_part = any(part in exclude_dirs for part in path_parts)
        return has_excluded_part


def get_ignore_manager(root: Path) -> IgnoreManager:
    """Get a cached IgnoreManager for the provided root."""
    resolved_root = _resolve_root(root)
    gitignore_path = _build_gitignore_path(resolved_root)
    gitignore_exists = gitignore_path.exists()
    gitignore_mtime = _get_gitignore_mtime(gitignore_path, gitignore_exists)
    cache_entry = IGNORE_MANAGER_CACHE.get(resolved_root)
    has_cache_entry = cache_entry is not None
    is_cache_fresh = has_cache_entry and cache_entry.gitignore_mtime == gitignore_mtime
    if is_cache_fresh:
        return cache_entry.manager
    gitignore_lines = _read_gitignore_lines(gitignore_path, gitignore_exists)
    ignore_patterns = _build_patterns(gitignore_lines)
    ignore_manager = IgnoreManager(resolved_root, ignore_patterns, DEFAULT_EXCLUDE_DIRS)
    IGNORE_MANAGER_CACHE[resolved_root] = IgnoreCacheEntry(gitignore_mtime, ignore_manager)
    return ignore_manager


__all__ = [
    "DEFAULT_EXCLUDE_DIRS",
    "DEFAULT_IGNORE_PATTERNS",
    "IgnoreManager",
    "get_ignore_manager",
]
