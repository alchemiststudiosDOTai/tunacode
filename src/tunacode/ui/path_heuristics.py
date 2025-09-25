"""Shared heuristics for prioritizing and skipping project paths."""

from __future__ import annotations

from typing import Iterable, List, Sequence

# CLAUDE_ANCHOR[key=0b3f320e] Cross-ecosystem skip directory defaults for FileReferenceCompleter global roots
DEFAULT_SKIP_DIRECTORY_NAMES: Sequence[str] = (
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    ".uv_cache",
    "node_modules",
    "dist",
    "build",
    "out",
    "target",
    # CLAUDE_ANCHOR[key=6fd59413] Skip list includes __pycache__ to avoid noisy Python build artifacts in suggestions
    "vendor",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "coverage",
    ".cache",
    # CLAUDE_ANCHOR[key=2bcebd52] Skip heuristic checks every path component to prune nested junk directories such as __pycache__
)

DEFAULT_PRIORITY_PREFIXES: Sequence[str] = (
    "src",
    "app",
    "lib",
    "cmd",
    "pkg",
    "internal",
    "include",
    "components",
    "tests",
    "test",
    "spec",
    "examples",
    "docs",
    "documentation",
)


def prioritize_roots(roots: Iterable[str]) -> List[str]:
    """Order project roots so high-signal directories surface first."""

    ordered: List[str] = []
    seen = set()

    for root in roots:
        if root == "." and root not in seen:
            ordered.append(root)
            seen.add(root)

    for prefix in DEFAULT_PRIORITY_PREFIXES:
        for root in roots:
            if root in seen:
                continue
            normalized = root.replace("\\", "/")
            if normalized == prefix or normalized.startswith(f"{prefix}/"):
                ordered.append(root)
                seen.add(root)

    for root in roots:
        if root in seen:
            continue
        ordered.append(root)
        seen.add(root)

    return ordered


def should_skip_directory(path: str) -> bool:
    """Return True when any component of the path matches skip heuristics."""

    if not path or path == ".":
        return False

    normalized = path.replace("\\", "/")
    components = normalized.split("/")
    return any(component in DEFAULT_SKIP_DIRECTORY_NAMES for component in components)
