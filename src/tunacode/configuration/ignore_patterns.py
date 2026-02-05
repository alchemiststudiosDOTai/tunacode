"""Shared ignore patterns and matching helpers for filesystem tools and utilities."""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Iterable

from tunacode.constants import ENV_FILE

GIT_DIR_NAME = ".git"
GIT_DIR_PATTERN = f"{GIT_DIR_NAME}/"
WILDCARD_CHARS = ("*", "?", "[")

DEFAULT_IGNORE_PATTERNS = (
    GIT_DIR_PATTERN,
    ".hg/",
    ".svn/",
    ".bzr/",
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    "node_modules/",
    "bower_components/",
    ".venv/",
    "venv/",
    "env/",
    ".env/",
    "build/",
    "dist/",
    "_build/",
    "target/",
    ".idea/",
    ".vscode/",
    ".vs/",
    "htmlcov/",
    ".coverage",
    ".tox/",
    ".eggs/",
    "*.egg-info/",
    ".bundle/",
    "vendor/",
    ".terraform/",
    ".serverless/",
    ".next/",
    ".nuxt/",
    "coverage/",
    "tmp/",
    "temp/",
    ".cache/",
    "cache/",
    "logs/",
    "bin/",
    "obj/",
    ".zig-cache/",
    "zig-out/",
    "coverage.xml",
    "*.cover",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.swp",
    "*.swo",
    ".DS_Store",
    "Thumbs.db",
    ENV_FILE,
)


def _is_literal_dir_pattern(pattern: str) -> bool:
    return pattern.endswith("/") and not any(char in pattern for char in WILDCARD_CHARS)


def _extract_exclude_dirs(patterns: Iterable[str]) -> frozenset[str]:
    return frozenset(
        pattern.rstrip("/") for pattern in patterns if _is_literal_dir_pattern(pattern)
    )


DEFAULT_EXCLUDE_DIRS = _extract_exclude_dirs(DEFAULT_IGNORE_PATTERNS)


def _is_git_path(rel_path: str, name: str) -> bool:
    """Check if path is within a .git directory."""
    if name == GIT_DIR_NAME:
        return True
    if rel_path.startswith(GIT_DIR_PATTERN):
        return True
    git_dir_marker = f"/{GIT_DIR_PATTERN}"
    return git_dir_marker in rel_path


def _matches_rooted_pattern(rel_path: str, match_pattern: str, is_dir_pattern: bool) -> bool:
    """Check if rel_path matches a root-anchored pattern (leading /)."""
    clean_pattern = match_pattern.lstrip("/")
    path_matches = fnmatch.fnmatch(rel_path, clean_pattern) or fnmatch.fnmatch(
        rel_path, f"{clean_pattern}/*"
    )
    if not path_matches:
        return False
    if not is_dir_pattern:
        return True
    return rel_path == clean_pattern or rel_path.startswith(clean_pattern + os.sep)


def _matches_path_components(
    path_parts: list[str],
    name: str,
    match_pattern: str,
    is_dir_pattern: bool,
) -> bool:
    """Check if any path component matches the pattern."""
    limit = len(path_parts) if is_dir_pattern else len(path_parts) - 1
    for i in range(limit):
        if fnmatch.fnmatch(path_parts[i], match_pattern):
            return True
    return name == path_parts[-1] and fnmatch.fnmatch(name, match_pattern)


def _matches_pattern(
    rel_path: str,
    name: str,
    path_parts: list[str],
    pattern: str,
) -> bool:
    """Check if a path matches a single ignore pattern."""
    is_dir_pattern = pattern.endswith("/")
    match_pattern = pattern.rstrip("/") if is_dir_pattern else pattern

    if match_pattern.startswith("/"):
        return _matches_rooted_pattern(rel_path, match_pattern, is_dir_pattern)

    if fnmatch.fnmatch(name, match_pattern) and not is_dir_pattern:
        return True

    if fnmatch.fnmatch(rel_path, match_pattern):
        return True

    if not (is_dir_pattern or "/" not in pattern):
        return False

    return _matches_path_components(path_parts, name, match_pattern, is_dir_pattern)


def is_ignored(rel_path: str, name: str, patterns: Iterable[str]) -> bool:
    """Check if a relative path or name matches ignore patterns."""
    if not patterns:
        return False

    if _is_git_path(rel_path, name):
        return True

    path_parts = rel_path.split(os.sep)
    return any(_matches_pattern(rel_path, name, path_parts, p) for p in patterns)
