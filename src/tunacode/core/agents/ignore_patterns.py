"""
Agent ignore pattern system for filtering files and directories.

This module provides functionality for reading and applying ignore patterns
similar to .gitignore, specifically for the architect mode to avoid unnecessary
scanning of test directories and other irrelevant files.
"""

import fnmatch
import os
import re
from pathlib import Path
from typing import List


class IgnorePatterns:
    """Manages ignore patterns for filtering files and directories."""

    # Default patterns to ignore (can be overridden by .agentignore)
    DEFAULT_PATTERNS = [
        # Test directories
        "tests/**",
        "**/test_*",
        "**/*_test.py",
        "**/test/**",
        "**/tests/**",
        "__tests__/**",
        "spec/**",
        # Build and cache directories
        "build/**",
        "dist/**",
        "*.egg-info/**",
        "__pycache__/**",
        "*.pyc",
        ".pytest_cache/**",
        ".coverage",
        "htmlcov/**",
        # Version control
        ".git/**",
        ".svn/**",
        ".hg/**",
        # IDE and editor files
        ".vscode/**",
        ".idea/**",
        "*.swp",
        "*.swo",
        "*~",
        # Dependencies
        "node_modules/**",
        "venv/**",
        "env/**",
        ".env/**",
        "virtualenv/**",
        # Documentation builds
        "_build/**",
        "site/**",
        # OS files
        ".DS_Store",
        "Thumbs.db",
        # Large binary files
        "*.so",
        "*.dylib",
        "*.dll",
        "*.exe",
    ]

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.patterns: List[str] = []
        self._compiled_patterns: List[re.Pattern] = []
        self._load_patterns()

    def _load_patterns(self):
        """Load ignore patterns from .agentignore file or use defaults."""
        agentignore_path = self.project_root / ".agentignore"

        if agentignore_path.exists():
            # Load custom patterns from .agentignore
            try:
                with open(agentignore_path, "r") as f:
                    custom_patterns = [
                        line.strip()
                        for line in f
                        if line.strip() and not line.strip().startswith("#")
                    ]
                self.patterns = custom_patterns
            except Exception:
                # Fall back to defaults if can't read file
                self.patterns = self.DEFAULT_PATTERNS.copy()
        else:
            # Use default patterns
            self.patterns = self.DEFAULT_PATTERNS.copy()

        # Compile patterns for efficiency
        self._compile_patterns()

    def _compile_patterns(self):
        """Convert glob patterns to regex patterns."""
        self._compiled_patterns = []
        for pattern in self.patterns:
            # Convert glob pattern to regex
            if pattern.startswith("!"):
                # Negation patterns - handle separately
                continue

            # Handle ** for recursive matching
            regex_pattern = pattern.replace("**/", ".*/")
            regex_pattern = regex_pattern.replace("/**", "/.*")
            regex_pattern = fnmatch.translate(regex_pattern)

            try:
                self._compiled_patterns.append(re.compile(regex_pattern))
            except re.error:
                # Skip invalid patterns
                continue

    def should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored based on patterns."""
        # Convert to relative path from project root
        try:
            rel_path = path.relative_to(self.project_root)
        except ValueError:
            # Path is outside project root
            return True

        path_str = str(rel_path).replace(os.sep, "/")

        # Check against compiled patterns
        for pattern in self._compiled_patterns:
            if pattern.match(path_str):
                return True

        # Also check if any parent directory matches
        for parent in rel_path.parents:
            parent_str = str(parent).replace(os.sep, "/") + "/"
            for pattern in self._compiled_patterns:
                if pattern.match(parent_str):
                    return True

        return False

    def filter_paths(self, paths: List[Path]) -> List[Path]:
        """Filter a list of paths, removing ignored ones."""
        return [p for p in paths if not self.should_ignore(p)]

    def add_pattern(self, pattern: str):
        """Add a new ignore pattern."""
        if pattern not in self.patterns:
            self.patterns.append(pattern)
            self._compile_patterns()

    def remove_pattern(self, pattern: str):
        """Remove an ignore pattern."""
        if pattern in self.patterns:
            self.patterns.remove(pattern)
            self._compile_patterns()

    def get_patterns(self) -> List[str]:
        """Get current ignore patterns."""
        return self.patterns.copy()
