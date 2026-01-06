"""
File filtering functionality for the grep tool.
"""

import fnmatch
import os
import re
from pathlib import Path

import pathspec

# Fast-Glob Prefilter Configuration
MAX_GLOB = 5_000  # Hard cap - protects memory & tokens
GLOB_BATCH = 500  # Streaming batch size

# Always exclude these directories (baseline, even without .gitignore)
EXCLUDE_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "target",
}


class FileFilter:
    """Handles file filtering and globbing for the grep tool."""

    @staticmethod
    def load_gitignore(root: Path) -> pathspec.PathSpec | None:
        """Load .gitignore patterns from root directory."""
        gitignore_path = root / ".gitignore"
        if not gitignore_path.exists():
            return None
        try:
            with open(gitignore_path) as f:
                return pathspec.PathSpec.from_lines("gitwildmatch", f)
        except OSError:
            return None

    @staticmethod
    def fast_glob(root: Path, include: str, exclude: str | None = None) -> list[Path]:
        """
        Lightning-fast filename filtering using os.scandir.

        Respects both hardcoded EXCLUDE_DIRS and .gitignore patterns.

        Args:
            root: Directory to search
            include: Include pattern (e.g., "*.py", "*.{js,ts}")
            exclude: Exclude pattern (optional)

        Returns:
            List of matching file paths (bounded by MAX_GLOB)
        """
        matches: list[Path] = []
        stack = [(root, "")]  # (path, relative_path_from_root)

        # Load .gitignore patterns
        gitignore_spec = FileFilter.load_gitignore(root)

        # Handle multiple extensions in include pattern like "*.{py,js,ts}"
        if "{" in include and "}" in include:
            # Convert *.{py,js,ts} to multiple patterns
            base, ext_part = include.split("{", 1)
            ext_part = ext_part.split("}", 1)[0]
            extensions = ext_part.split(",")
            include_patterns = [base + ext.strip() for ext in extensions]
            include_regexes = [
                re.compile(fnmatch.translate(pat), re.IGNORECASE) for pat in include_patterns
            ]
        else:
            include_regexes = [re.compile(fnmatch.translate(include), re.IGNORECASE)]

        exclude_rx = re.compile(fnmatch.translate(exclude), re.IGNORECASE) if exclude else None

        while stack and len(matches) < MAX_GLOB:
            current_dir, rel_prefix = stack.pop()

            try:
                with os.scandir(current_dir) as entries:
                    for entry in entries:
                        rel_path = f"{rel_prefix}/{entry.name}" if rel_prefix else entry.name

                        # Skip common irrelevant directories
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name in EXCLUDE_DIRS:
                                continue
                            # Check gitignore (directories need trailing slash)
                            if gitignore_spec and gitignore_spec.match_file(rel_path + "/"):
                                continue
                            stack.append((Path(entry.path), rel_path))

                        # Check file matches
                        elif entry.is_file(follow_symlinks=False):
                            # Check gitignore
                            if gitignore_spec and gitignore_spec.match_file(rel_path):
                                continue

                            # Check against any include pattern
                            matches_include = any(
                                regex.match(entry.name) for regex in include_regexes
                            )

                            if matches_include and (
                                not exclude_rx or not exclude_rx.match(entry.name)
                            ):
                                matches.append(Path(entry.path))

            except (PermissionError, OSError):
                continue  # Skip inaccessible directories

        return matches[:MAX_GLOB]

    @staticmethod
    def parse_patterns(patterns: str) -> list[str]:
        """Parse comma-separated file patterns."""
        return [p.strip() for p in patterns.split(",") if p.strip()]
