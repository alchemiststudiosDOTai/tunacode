"""Fast in-memory code index for efficient file lookups."""

import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

from tunacode.indexing.file_filters import (
    PRIORITY_DIRS,
    QUICK_INDEX_THRESHOLD,
    should_ignore_path,
    should_index_file,
)
from tunacode.indexing.index_storage import IndexStorage
from tunacode.indexing.python_parser import parse_python_file

logger = logging.getLogger(__name__)

# Cache time-to-live for directory listings (seconds)
CACHE_TTL_SECONDS = 5.0


class CodeIndex:
    """Fast in-memory code index for repository file lookups.

    This index provides efficient file discovery without relying on
    grep searches that can timeout in large repositories.
    """

    # Singleton instance
    _instance: Optional["CodeIndex"] = None
    _instance_lock = threading.RLock()

    def __init__(self, root_dir: str | None = None):
        """Initialize the code index.

        Args:
            root_dir: Root directory to index. Defaults to current directory.
        """
        self.root_dir = Path(root_dir or os.getcwd()).resolve()
        self._lock = threading.RLock()
        self._storage = IndexStorage()
        self._dir_cache: dict[Path, list[Path]] = {}
        self._cache_timestamps: dict[Path, float] = {}
        self._cache_ttl = CACHE_TTL_SECONDS

        self._indexed = False
        self._partial_indexed = False

    @classmethod
    def get_instance(cls, root_dir: str | None = None) -> "CodeIndex":
        """Get the singleton CodeIndex instance.

        Args:
            root_dir: Root directory to index. Only used on first call.

        Returns:
            The singleton CodeIndex instance.
        """
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls(root_dir)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        with cls._instance_lock:
            cls._instance = None

    def get_directory_contents(self, path: Path) -> list[str]:
        """Get cached directory contents if available and fresh.

        Args:
            path: Directory path to check

        Returns:
            List of filenames in directory, empty list if not cached/stale
        """
        with self._lock:
            if path not in self._dir_cache:
                return []

            if not self.is_cache_fresh(path):
                self._dir_cache.pop(path, None)
                self._cache_timestamps.pop(path, None)
                return []

            return [p.name for p in self._dir_cache[path]]

    def is_cache_fresh(self, path: Path) -> bool:
        """Check if cached directory data is still fresh.

        Args:
            path: Directory path to check

        Returns:
            True if cache is fresh, False if stale or missing
        """
        if path not in self._cache_timestamps:
            return False

        age = time.time() - self._cache_timestamps[path]
        return age < self._cache_ttl

    def update_directory_cache(self, path: Path, entries: list[str]) -> None:
        """Update the directory cache with fresh data.

        Args:
            path: Directory path
            entries: List of filenames in the directory
        """
        with self._lock:
            self._dir_cache[path] = [Path(path) / entry for entry in entries]
            self._cache_timestamps[path] = time.time()

    def build_index(self, force: bool = False) -> None:
        """Build the file index for the repository.

        Args:
            force: Force rebuild even if already indexed.
        """
        with self._lock:
            if self._indexed and not force:
                return

            self._clear_indices()

            self._scan_directory(self.root_dir)
            self._indexed = True

    def _clear_indices(self) -> None:
        """Clear all indices."""
        self._storage.clear()
        self._dir_cache.clear()
        self._cache_timestamps.clear()

    def quick_count(self) -> int:
        """Fast file count without full indexing.

        Uses os.scandir for speed and exits early at threshold.
        Does not acquire lock - read-only filesystem scan.

        Returns:
            File count, capped at QUICK_INDEX_THRESHOLD + 1.
        """
        count = 0
        stack = [self.root_dir]

        while stack and count <= QUICK_INDEX_THRESHOLD:
            current = stack.pop()
            try:
                for entry in os.scandir(current):
                    if entry.is_dir(follow_symlinks=False):
                        if not should_ignore_path(Path(entry.path)):
                            stack.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        file_path = Path(entry.path)
                        if should_index_file(file_path):
                            count += 1
                            if count > QUICK_INDEX_THRESHOLD:
                                break
            except OSError as e:
                logger.exception("Failed to scan directory %s: %s", current, e)
                continue

        return count

    def build_priority_index(self) -> int:
        """Build index for priority directories only.

        Indexes top-level files and PRIORITY_DIRS subdirectories.
        Sets _partial_indexed = True to indicate background expansion needed.

        Returns:
            Number of files indexed.
        """
        with self._lock:
            self._clear_indices()

            for entry in os.scandir(self.root_dir):
                if entry.is_file(follow_symlinks=False):
                    file_path = Path(entry.path)
                    if should_index_file(file_path):
                        self._index_file(file_path)

            for name in PRIORITY_DIRS:
                priority_path = self.root_dir / name
                if priority_path.is_dir():
                    self._scan_directory(priority_path)

            self._partial_indexed = True
            self._indexed = False
            return self._storage.get_stats()["total_files"]

    def expand_index(self) -> None:
        """Expand partial index to full index.

        Safe to call in background. Only runs if _partial_indexed is True.
        Scans remaining non-priority directories.
        """
        with self._lock:
            if not self._partial_indexed:
                return

            for entry in os.scandir(self.root_dir):
                if entry.is_dir(follow_symlinks=False):
                    dir_path = Path(entry.path)
                    if should_ignore_path(dir_path):
                        continue
                    if entry.name not in PRIORITY_DIRS:
                        self._scan_directory(dir_path)

            self._partial_indexed = False
            self._indexed = True

    def _scan_directory(self, directory: Path) -> None:
        """Recursively scan a directory and index files.

        Args:
            directory: Directory path to scan.
        """
        if should_ignore_path(directory):
            return

        try:
            entries = list(directory.iterdir())
            file_list = []

            for entry in entries:
                if entry.is_dir():
                    self._scan_directory(entry)
                elif entry.is_file() and should_index_file(entry):
                    self._index_file(entry)
                    file_list.append(entry)

            self._dir_cache[directory] = file_list
            self._cache_timestamps[directory] = time.time()

        except OSError as e:
            logger.warning("Failed to scan directory %s: %s", directory, e)

    def _index_file(self, file_path: Path) -> None:
        """Index a single file.

        Args:
            file_path: Absolute path to the file to index.
        """
        relative_path = file_path.relative_to(self.root_dir)

        if file_path.suffix == ".py":
            imports, classes, functions = parse_python_file(file_path)
            self._storage.add_file(relative_path, imports, classes, functions)
        else:
            self._storage.add_file(relative_path)

    def lookup(self, query: str, file_type: str | None = None) -> list[Path]:
        """Look up files matching a query.

        Args:
            query: Search query (basename, partial path, or symbol).
            file_type: Optional file extension filter (e.g., '.py').

        Returns:
            List of matching file paths relative to root directory.
        """
        with self._lock:
            if not self._indexed:
                self.build_index()

            return self._storage.lookup(query, file_type)

    def get_all_files(self, file_type: str | None = None) -> list[Path]:
        """Get all indexed files.

        Args:
            file_type: Optional file extension filter (e.g., '.py').

        Returns:
            List of all file paths relative to root directory.
        """
        with self._lock:
            if not self._indexed:
                self.build_index()

            return self._storage.get_all_files(file_type)

    def find_imports(self, module_name: str) -> list[Path]:
        """Find files that import a specific module.

        Args:
            module_name: Name of the module to search for.

        Returns:
            List of file paths that import the module.
        """
        with self._lock:
            if not self._indexed:
                self.build_index()

            return self._storage.find_imports(module_name)

    def refresh(self, path: str | None = None) -> None:
        """Refresh the index for a specific path or the entire repository.

        Args:
            path: Optional specific path to refresh. If None, refreshes everything.
        """
        with self._lock:
            if not path:
                self.build_index(force=True)
                return

            target_path = Path(path)
            if not target_path.is_absolute():
                target_path = self.root_dir / target_path

            if target_path.is_file():
                relative_path = target_path.relative_to(self.root_dir)
                self._storage.remove_file(relative_path)
                if should_index_file(target_path):
                    self._index_file(target_path)

            elif target_path.is_dir():
                prefix = str(target_path.relative_to(self.root_dir))
                all_files = self._storage.get_all_files()
                for p in all_files:
                    p_str = str(p)
                    if p_str == prefix or p_str.startswith(prefix + os.sep):
                        self._storage.remove_file(p)
                self._scan_directory(target_path)

    def get_stats(self) -> dict[str, int]:
        """Get indexing statistics.

        Returns:
            Dictionary with index statistics.
        """
        with self._lock:
            stats = self._storage.get_stats()
            stats["directories_cached"] = len(self._dir_cache)
            return stats
