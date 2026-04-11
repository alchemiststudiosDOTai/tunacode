"""Shared ignore defaults and helpers for filesystem filtering."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Final

import pathspec

from tunacode.constants import ENV_FILE

GITIGNORE_FILE_NAME: Final[str] = ".gitignore"

DEFAULT_IGNORE_PATTERNS: Final[tuple[str, ...]] = (
    ".git/",
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

_WILDCARD_CHARS = ("*", "?", "[")

DEFAULT_EXCLUDE_DIRS: Final[frozenset[str]] = frozenset(
    p.rstrip("/")
    for p in DEFAULT_IGNORE_PATTERNS
    if p.endswith("/") and not any(c in p for c in _WILDCARD_CHARS)
)


def read_ignore_file_lines(filepath: Path) -> tuple[str, ...]:
    """Read raw ignore-file lines, returning an empty tuple when unreadable."""
    try:
        return tuple(filepath.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeDecodeError):
        return ()


def compile_ignore_spec(patterns: Iterable[str]) -> pathspec.PathSpec:
    """Compile gitignore-style patterns into a reusable matcher."""
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def merge_ignore_patterns(
    base_patterns: Iterable[str],
    extra_patterns: Iterable[str],
) -> tuple[str, ...]:
    """Append extra patterns onto a base pattern set, dropping blanks."""
    return tuple(base_patterns) + tuple(p for p in extra_patterns if p)
