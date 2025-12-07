"""
File filtering functionality for the grep tool.
"""

import fnmatch
import os
import re
from pathlib import Path

# Fast-Glob Prefilter Configuration
MAX_GLOB = 5_000  # Hard cap - protects memory & tokens
GLOB_BATCH = 500  # Streaming batch size
EXCLUDE_DIRS = {  # Common directories to skip
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
    def fast_glob(root: Path, include: str, exclude: str | None = None) -> list[Path]:
        """
        Lightning-fast filename filtering using os.scandir.

        Args:
            root: Directory to search
            include: Include pattern (e.g., "*.py", "*.{js,ts}")
            exclude: Exclude pattern (optional)

        Returns:
            List of matching file paths (bounded by MAX_GLOB)
        """
        matches: list[Path] = []
        stack = [root]

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
            current_dir = stack.pop()

            try:
                with os.scandir(current_dir) as entries:
                    for entry in entries:
                        # Skip common irrelevant directories
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name not in EXCLUDE_DIRS:
                                stack.append(Path(entry.path))

                        # Check file matches
                        elif entry.is_file(follow_symlinks=False):
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
