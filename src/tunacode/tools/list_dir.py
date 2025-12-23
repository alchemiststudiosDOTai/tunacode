"""Directory listing tool with recursive tree view for agent operations."""

import asyncio
import os
from pathlib import Path

from tunacode.tools.decorators import base_tool

IGNORE_PATTERNS = [
    "node_modules/",
    "__pycache__/",
    ".git/",
    "dist/",
    "build/",
    "target/",
    "vendor/",
    "bin/",
    "obj/",
    ".idea/",
    ".vscode/",
    ".zig-cache/",
    "zig-out/",
    ".coverage/",
    "coverage/",
    "tmp/",
    "temp/",
    ".cache/",
    "cache/",
    "logs/",
    ".venv/",
    "venv/",
    "env/",
    ".ruff_cache/",
    ".pytest_cache/",
    ".mypy_cache/",
    "*.egg-info/",
    ".eggs/",
]

IGNORE_PATTERNS_COUNT = len(IGNORE_PATTERNS)

LIMIT = 100


def _should_ignore(path: str, ignore_patterns: list[str]) -> bool:
    """Check if path matches any ignore pattern."""
    for pattern in ignore_patterns:
        if pattern.endswith("/"):
            # Directory pattern
            dir_name = pattern.rstrip("/")
            if f"/{dir_name}/" in f"/{path}/" or path.startswith(f"{dir_name}/"):
                return True
        elif "*" in pattern:
            # Glob pattern (simple suffix match)
            suffix = pattern.replace("*", "")
            if path.endswith(suffix):
                return True
    return False


def _collect_files(
    root: Path,
    max_files: int,
    show_hidden: bool,
    ignore_patterns: list[str],
) -> list[str]:
    """Recursively collect files up to limit, respecting ignore patterns."""
    files: list[str] = []
    root_str = str(root)

    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root_str)
        if rel_dir == ".":
            rel_dir = ""

        # Filter directories in-place to prevent descending into ignored dirs
        dirnames[:] = [
            d
            for d in dirnames
            if (show_hidden or not d.startswith("."))
            and not _should_ignore(f"{rel_dir}/{d}".lstrip("/") + "/", ignore_patterns)
        ]
        dirnames.sort()

        # Collect files
        for filename in sorted(filenames):
            if not show_hidden and filename.startswith("."):
                continue

            rel_path = f"{rel_dir}/{filename}".lstrip("/") if rel_dir else filename
            if _should_ignore(rel_path, ignore_patterns):
                continue

            files.append(rel_path)
            if len(files) >= max_files:
                return files

    return files


TREE_BRANCH = "├── "
TREE_LAST = "└── "
TREE_PIPE = "│   "
TREE_SPACE = "    "


def _render_tree(base_name: str, files: list[str]) -> tuple[str, int, int]:
    """Build tree structure with connectors from file list.

    Returns: (tree_output, file_count, dir_count)
    """
    dirs: set[str] = set()
    files_by_dir: dict[str, list[str]] = {}

    for file in files:
        dir_path = os.path.dirname(file)
        parts = dir_path.split("/") if dir_path else []

        for i in range(len(parts) + 1):
            parent = "/".join(parts[:i]) if i > 0 else "."
            dirs.add(parent)

        key = dir_path if dir_path else "."
        if key not in files_by_dir:
            files_by_dir[key] = []
        files_by_dir[key].append(os.path.basename(file))

    file_count = len(files)
    dir_count = len(dirs) - 1  # exclude root "."

    def render_dir(dir_path: str, prefix: str) -> str:
        output = ""
        parent_match = "" if dir_path == "." else dir_path
        child_dirs = sorted(d for d in dirs if d != dir_path and os.path.dirname(d) == parent_match)
        child_files = sorted(files_by_dir.get(dir_path, []))

        items: list[tuple[str, bool]] = []  # (name, is_dir)
        for d in child_dirs:
            items.append((os.path.basename(d), True))
        for f in child_files:
            items.append((f, False))

        for i, (name, is_dir) in enumerate(items):
            is_last = i == len(items) - 1
            connector = TREE_LAST if is_last else TREE_BRANCH
            child_prefix = prefix + (TREE_SPACE if is_last else TREE_PIPE)

            if is_dir:
                full_path = f"{parent_match}/{name}".lstrip("/") if parent_match else name
                output += f"{prefix}{connector}{name}/\n"
                output += render_dir(full_path, child_prefix)
            else:
                output += f"{prefix}{connector}{name}\n"

        return output

    return f"{base_name}/\n" + render_dir(".", ""), file_count, dir_count


@base_tool
async def list_dir(
    directory: str = ".",
    max_files: int = LIMIT,
    show_hidden: bool = False,
    ignore: list[str] | None = None,
) -> str:
    """List directory contents as a recursive tree.

    Args:
        directory: The path to the directory to list (defaults to current directory).
        max_files: Maximum number of files to return (default: 100).
        show_hidden: Whether to include hidden files/directories (default: False).
        ignore: Additional glob patterns to ignore (default: None).

    Returns:
        Compact tree view of directory contents.
    """
    dir_path = Path(directory).resolve()

    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {dir_path}")

    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {dir_path}")

    # Combine default and custom ignore patterns
    ignore_patterns = list(IGNORE_PATTERNS)
    if ignore:
        ignore_patterns.extend(ignore)

    # Collect files in background thread
    files = await asyncio.to_thread(
        _collect_files, dir_path, max_files, show_hidden, ignore_patterns
    )

    if not files:
        return f"{dir_path.name}/\n0 files  0 dirs"

    tree_output, file_count, dir_count = _render_tree(dir_path.name, files)
    summary = f"{file_count} files  {dir_count} dirs"

    if len(files) >= max_files:
        summary += " (truncated)"

    return f"{summary}\n{tree_output}"
