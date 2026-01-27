"""
Module: tunacode.utils.system.gitignore

Provides gitignore pattern matching and file listing with ignore support.
"""

import os

from tunacode.configuration.ignore_patterns import (
    DEFAULT_IGNORE_PATTERNS,
    GIT_DIR_PATTERN,
    is_ignored,
)


def _load_gitignore_patterns(filepath=".gitignore"):
    """Loads patterns from a .gitignore file."""
    patterns = set()
    try:
        with open(filepath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.add(line)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None
    patterns.add(GIT_DIR_PATTERN)
    return patterns


def list_cwd(max_depth=3):
    """
    Lists files in the current working directory up to a specified depth,
    respecting .gitignore rules or a default ignore list.

    Args:
        max_depth (int): Maximum directory depth to traverse.
                         0: only files in the current directory.
                         1: includes files in immediate subdirectories.
                         ... Default is 3.

    Returns:
        list: A sorted list of relative file paths.
    """
    ignore_patterns = _load_gitignore_patterns()
    if ignore_patterns is None:
        ignore_patterns = DEFAULT_IGNORE_PATTERNS

    file_list = []
    start_path = "."
    max_depth = max(0, max_depth)

    for root, dirs, files in os.walk(start_path, topdown=True):
        rel_root = os.path.relpath(root, start_path)
        if rel_root == ".":
            rel_root = ""
            current_depth = 0
        else:
            current_depth = rel_root.count(os.sep) + 1

        if current_depth >= max_depth:
            dirs[:] = []

        original_dirs = list(dirs)
        dirs[:] = []
        for d in original_dirs:
            dir_rel_path = os.path.join(rel_root, d) if rel_root else d
            if not is_ignored(dir_rel_path, d, ignore_patterns):
                dirs.append(d)

        if current_depth <= max_depth:
            for f in files:
                file_rel_path = os.path.join(rel_root, f) if rel_root else f
                if not is_ignored(file_rel_path, f, ignore_patterns):
                    file_list.append(file_rel_path.replace(os.sep, "/"))

    return sorted(file_list)
