#!/usr/bin/env python3
"""Check that no Python file exceeds max-file-lines from pyproject.toml."""

import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

MAX_LINES = 500


def get_max_lines() -> int:
    """Read max-file-lines from pyproject.toml if it exists."""
    pyproject = Path("pyproject.toml")
    if pyproject.exists():
        config = tomllib.loads(pyproject.read_text())
        return config.get("tool", {}).get("lint", {}).get("max-file-lines", MAX_LINES)
    return MAX_LINES


def check_file_lengths(directory: str = ".") -> list[tuple[str, int]]:
    """Return list of (file, line_count) for files exceeding limit."""
    max_lines = get_max_lines()
    violations = []
    for path in Path(directory).rglob("*.py"):
        if any(skip in str(path) for skip in [".ruff_cache", "__pycache__", ".venv"]):
            continue
        line_count = len(path.read_text().splitlines())
        if line_count > max_lines:
            violations.append((str(path), line_count, max_lines))
    return sorted(violations, key=lambda x: -x[1])


def main() -> int:
    max_lines = get_max_lines()
    violations = check_file_lengths()
    if violations:
        print(f"Files exceeding {max_lines} lines:")
        for filepath, count, limit in violations:
            print(f"  {filepath}: {count} lines (+{count - limit})")
        return 1
    print(f"All files under {max_lines} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
