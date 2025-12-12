"""File filtering logic for code indexing.

This module handles decisions about which files and directories should be
indexed based on patterns, extensions, and file attributes.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".bzr",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    "bower_components",
    ".venv",
    "venv",
    "env",
    ".env",
    "build",
    "dist",
    "_build",
    "target",
    ".idea",
    ".vs",
    "htmlcov",
    ".coverage",
    ".tox",
    ".eggs",
    ".bundle",
    "vendor",
    ".terraform",
    ".serverless",
    ".next",
    ".nuxt",
    "coverage",
    "tmp",
    "temp",
}

IGNORE_DIR_SUFFIXES = {".egg-info"}

ALLOW_DOT_DIRS = {".github", ".devcontainer", ".vscode", ".circleci", ".gitlab"}

INDEXED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".c",
    ".cpp",
    ".cc",
    ".cxx",
    ".h",
    ".hpp",
    ".rs",
    ".go",
    ".rb",
    ".php",
    ".cs",
    ".swift",
    ".kt",
    ".scala",
    ".sh",
    ".bash",
    ".zsh",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",
    ".md",
    ".rst",
    ".txt",
    ".html",
    ".css",
    ".scss",
    ".sass",
    ".sql",
    ".graphql",
    ".dockerfile",
    ".containerfile",
}

INDEXED_DOTFILES = {".gitignore", ".dockerignore", ".editorconfig", ".env.example"}

SPECIAL_FILENAMES = {"makefile", "dockerfile", "jenkinsfile", "rakefile"}

PRIORITY_DIRS = {"src", "lib", "app", "packages", "core", "internal"}
QUICK_INDEX_THRESHOLD = 1000
MAX_FILE_SIZE = 10 * 1024 * 1024


def _is_ignored_dot_dir(part: str) -> bool:
    """Check if a dot-prefixed directory should be ignored."""
    if not part.startswith("."):
        return False
    if part == ".":
        return False
    return part not in ALLOW_DOT_DIRS


def _has_ignored_suffix(part: str) -> bool:
    """Check if a directory name ends with an ignored suffix."""
    return any(part.endswith(suffix) for suffix in IGNORE_DIR_SUFFIXES)


def should_ignore_path(path: Path) -> bool:
    """Check if a path should be ignored during indexing.

    Args:
        path: Path to check for ignore patterns.

    Returns:
        True if the path should be ignored, False otherwise.
    """
    for part in path.parts:
        if part in IGNORE_DIRS:
            return True
        if _is_ignored_dot_dir(part):
            return True
        if _has_ignored_suffix(part):
            return True
    return False


def _check_file_size(file_path: Path) -> bool:
    """Check if file is within size limit. Returns False if file exceeds limit or on error."""
    try:
        size = file_path.stat().st_size
        if size > MAX_FILE_SIZE:
            logger.debug("File exceeds size limit: %s (%d bytes)", file_path, size)
            return False
        return True
    except OSError as e:
        logger.warning("Cannot stat file %s: %s", file_path, e)
        return False


def _is_shebang_file(file_path: Path) -> bool:
    """Check if file starts with shebang (#!)."""
    try:
        with open(file_path, "rb") as f:
            return f.read(2) == b"#!"
    except OSError as e:
        logger.warning("Cannot read file for shebang check %s: %s", file_path, e)
        return False


def should_index_file(file_path: Path) -> bool:
    """Check if a file should be indexed.

    Args:
        file_path: Path to the file to check.

    Returns:
        True if the file should be indexed, False otherwise.
    """
    if not _check_file_size(file_path):
        return False

    name = file_path.name.lower()
    suffix = file_path.suffix.lower()

    if suffix in INDEXED_EXTENSIONS:
        return True

    if name in INDEXED_DOTFILES:
        return True

    if name in SPECIAL_FILENAMES:
        return True

    return suffix == "" and _is_shebang_file(file_path)
