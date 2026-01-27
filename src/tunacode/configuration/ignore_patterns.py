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


def is_ignored(rel_path: str, name: str, patterns: Iterable[str]) -> bool:
    """Check if a relative path or name matches ignore patterns."""
    if not patterns:
        return False

    git_dir_prefix = GIT_DIR_PATTERN
    git_dir_marker = f"/{git_dir_prefix}"
    if name == GIT_DIR_NAME or rel_path.startswith(git_dir_prefix) or git_dir_marker in rel_path:
        return True

    path_parts = rel_path.split(os.sep)

    for pattern in patterns:
        is_dir_pattern = pattern.endswith("/")
        match_pattern = pattern.rstrip("/") if is_dir_pattern else pattern

        if match_pattern.startswith("/"):
            match_pattern = match_pattern.lstrip("/")
            if fnmatch.fnmatch(rel_path, match_pattern) or fnmatch.fnmatch(
                rel_path, f"{match_pattern}/*"
            ):
                if is_dir_pattern:
                    if rel_path == match_pattern or rel_path.startswith(match_pattern + os.sep):
                        return True
                else:
                    return True
            continue

        if fnmatch.fnmatch(name, match_pattern) and not is_dir_pattern:
            return True

        if fnmatch.fnmatch(rel_path, match_pattern):
            return True

        if is_dir_pattern or "/" not in pattern:
            limit = len(path_parts) if is_dir_pattern else len(path_parts) - 1
            for i in range(limit):
                if fnmatch.fnmatch(path_parts[i], match_pattern):
                    return True
            if name == path_parts[-1] and fnmatch.fnmatch(name, match_pattern):
                return True

    return False
