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


def _render_tree(base_name: str, files: list[str]) -> str:
    """Build tree structure from file list."""
    dirs: set[str] = set()
    files_by_dir: dict[str, list[str]] = {}

    for file in files:
        dir_path = os.path.dirname(file)
        parts = dir_path.split("/") if dir_path else []

        # Add all parent directories
        for i in range(len(parts) + 1):
            parent = "/".join(parts[:i]) if i > 0 else "."
            dirs.add(parent)

        # Group files by directory
        key = dir_path if dir_path else "."
        if key not in files_by_dir:
            files_by_dir[key] = []
        files_by_dir[key].append(os.path.basename(file))

    def render_dir(dir_path: str, depth: int) -> str:
        indent = "  " * depth
        output = ""

        if depth > 0:
            output += f"{indent}{os.path.basename(dir_path)}/\n"

        child_indent = "  " * (depth + 1)

        # Get child directories (handle root "." specially)
        parent_match = "" if dir_path == "." else dir_path
        children = sorted(d for d in dirs if d != dir_path and os.path.dirname(d) == parent_match)

        # Render subdirectories first
        for child in children:
            output += render_dir(child, depth + 1)

        # Render files
        for filename in sorted(files_by_dir.get(dir_path, [])):
            output += f"{child_indent}{filename}\n"

        return output

    return f"{base_name}/\n" + render_dir(".", 0)


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
        return f"{dir_path.name}/ (empty)"

    output = _render_tree(dir_path.name, files)

    if len(files) >= max_files:
        output += f"\n(truncated at {max_files} files)"

    return output
