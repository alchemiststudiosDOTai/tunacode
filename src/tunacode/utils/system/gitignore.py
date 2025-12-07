"""
Module: tunacode.utils.system.gitignore

Provides gitignore pattern matching and file listing with ignore support.
"""

import fnmatch
import os

from tunacode.constants import ENV_FILE

# Default ignore patterns if .gitignore is not found
DEFAULT_IGNORE_PATTERNS = {
    "node_modules/",
    "env/",
    "venv/",
    ".git/",
    "build/",
    "dist/",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".DS_Store",
    "Thumbs.db",
    ENV_FILE,
    ".venv",
    "*.egg-info",
    ".pytest_cache/",
    ".coverage",
    "htmlcov/",
    ".tox/",
    "coverage.xml",
    "*.cover",
    ".idea/",
    ".vscode/",
    "*.swp",
    "*.swo",
}


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
    patterns.add(".git/")
    return patterns


def _is_ignored(rel_path, name, patterns):
    """
    Checks if a given relative path or name matches any ignore patterns.
    Mimics basic .gitignore behavior using fnmatch.
    """
    if not patterns:
        return False

    if name == ".git" or rel_path.startswith(".git/") or "/.git/" in rel_path:
        return True

    path_parts = rel_path.split(os.sep)

    for pattern in patterns:
        is_dir_pattern = pattern.endswith("/")
        match_pattern = pattern.rstrip("/") if is_dir_pattern else pattern

        if match_pattern.startswith("/"):
            match_pattern = match_pattern.lstrip("/")
            if fnmatch.fnmatch(rel_path, match_pattern) or fnmatch.fnmatch(
                rel_path, match_pattern + "/*"
            ):
                if is_dir_pattern:
                    if rel_path == match_pattern or rel_path.startswith(match_pattern + os.sep):
                        return True
                else:
                    return True
            continue

        if fnmatch.fnmatch(name, match_pattern):
            if is_dir_pattern:
                pass
            else:
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
            if not _is_ignored(dir_rel_path, d, ignore_patterns):
                dirs.append(d)

        if current_depth <= max_depth:
            for f in files:
                file_rel_path = os.path.join(rel_root, f) if rel_root else f
                if not _is_ignored(file_rel_path, f, ignore_patterns):
                    file_list.append(file_rel_path.replace(os.sep, "/"))

    return sorted(file_list)
