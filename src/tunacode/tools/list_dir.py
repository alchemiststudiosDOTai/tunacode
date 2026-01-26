"""Directory listing tool with recursive tree view for agent operations."""

import asyncio
import os
from pathlib import Path

from pydantic_ai.exceptions import ModelRetry

from tunacode.tools.decorators import base_tool
from tunacode.tools.ignore import (
    DEFAULT_IGNORE_PATTERNS,
    IgnoreManager,
    get_ignore_manager,
)

IGNORE_PATTERNS_COUNT = len(DEFAULT_IGNORE_PATTERNS)

LIMIT = 100


def _collect_files(
    root: Path,
    max_files: int,
    show_hidden: bool,
    ignore_manager: IgnoreManager,
) -> list[str]:
    """Recursively collect files up to limit, respecting ignore patterns."""
    files: list[str] = []
    root_str = str(root)

    for dirpath, dirnames, filenames in os.walk(root_str):
        dir_path = Path(dirpath)

        filtered_dirs: list[str] = []
        for name in dirnames:
            is_hidden_dir = name.startswith(".")
            should_skip_hidden_dir = is_hidden_dir and not show_hidden
            if should_skip_hidden_dir:
                continue
            candidate_dir = dir_path / name
            is_ignored_dir = ignore_manager.should_ignore_dir(candidate_dir)
            if is_ignored_dir:
                continue
            filtered_dirs.append(name)

        filtered_dirs.sort()
        dirnames[:] = filtered_dirs

        # Collect files
        for filename in sorted(filenames):
            is_hidden_file = filename.startswith(".")
            should_skip_hidden_file = is_hidden_file and not show_hidden
            if should_skip_hidden_file:
                continue

            file_path = dir_path / filename
            is_ignored_file = ignore_manager.should_ignore(file_path)
            if is_ignored_file:
                continue

            rel_path = file_path.relative_to(root)
            normalized_path = rel_path.as_posix()
            files.append(normalized_path)
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
        raise ModelRetry(f"Directory not found: {dir_path}. Check the path.")

    if not dir_path.is_dir():
        raise ModelRetry(f"Not a directory: {dir_path}. Provide a directory path.")

    ignore_manager = get_ignore_manager(dir_path)
    additional_count = len(ignore) if ignore else 0
    if ignore:
        ignore_manager = ignore_manager.with_additional_patterns(ignore)

    # Collect files in background thread
    files = await asyncio.to_thread(
        _collect_files, dir_path, max_files, show_hidden, ignore_manager
    )

    total_ignore_count = IGNORE_PATTERNS_COUNT + additional_count

    if not files:
        return f"0 files  0 dirs  {total_ignore_count} ignored\n{dir_path.name}/"

    tree_output, file_count, dir_count = _render_tree(dir_path.name, files)
    summary = f"{file_count} files  {dir_count} dirs  {total_ignore_count} ignored"

    if len(files) >= max_files:
        summary += " (truncated)"

    return f"{summary}\n{tree_output}"
