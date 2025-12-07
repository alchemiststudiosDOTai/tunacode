#!/usr/bin/env python3
# Fail CI and pre-commit if any Python file exceeds MAX_LINES.
import sys
from pathlib import Path

MAX_LINES = 600
SKIP_DIRS = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "build",
    "dist",
    "__pycache__",
}
SKIP_GLOBS = {
    "**/migrations/**",
}
SKIP_FILES = {
    "src/tunacode/core/agents/main.py",  # Recently refactored
}


def should_skip(path: Path) -> bool:
    # Check if file is in skip list
    if str(path) in SKIP_FILES:
        return True
    parts = set(p.name for p in path.parents)
    if parts & SKIP_DIRS:
        return True
    return any(path.match(pat) for pat in SKIP_GLOBS)


errors = []

for file in Path(".").rglob("*.py"):
    if should_skip(file):
        continue
    try:
        with open(file, encoding="utf-8") as f:
            line_count = sum(1 for _ in f)
        if line_count > MAX_LINES:
            errors.append(f"{file} has {line_count} lines (max {MAX_LINES})")
    except (UnicodeDecodeError, OSError) as e:
        errors.append(f"Could not read {file}: {e}")

if errors:
    print("❌ File length check failed:")
    for err in errors:
        print("  -", err)
    sys.exit(1)

print("✅ File length check passed.")
