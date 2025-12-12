#!/usr/bin/env python3
"""Check that Python source files do not exceed the maximum line count."""

import sys
from pathlib import Path

MAX_LINES = 600
SRC_DIR = Path("src")


def main() -> int:
    violations: list[tuple[Path, int]] = []

    if not SRC_DIR.exists():
        print(f"Source directory '{SRC_DIR}' not found")
        return 1

    for py_file in SRC_DIR.rglob("*.py"):
        line_count = len(py_file.read_text(encoding="utf-8").splitlines())
        if line_count > MAX_LINES:
            violations.append((py_file, line_count))

    if violations:
        print(f"Files exceeding {MAX_LINES} lines:")
        for path, count in sorted(violations, key=lambda x: -x[1]):
            print(f"  {path}: {count} lines")
        return 1

    print(f"All Python files are within the {MAX_LINES} line limit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
