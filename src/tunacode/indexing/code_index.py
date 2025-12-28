"""Fast in-memory code index for efficient file lookups."""

import os
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

from tunacode.indexing.constants import (
    IGNORE_DIRS,
    INDEXED_EXTENSIONS,
    PRIORITY_DIRS,
    QUICK_INDEX_THRESHOLD,
)


class CodeIndex:
    """Fast in-memory code index for repository file lookups.

    This index provides efficient file discovery without relying on
    grep searches that can timeout in large repositories.
    """

    _instance: Optional["CodeIndex"] = None
    _instance_lock = threading.RLock()

    def __init__(self, root_dir: str | None = None):
        """Initialize the code index.

        Args:
            root_dir: Root directory to index. Defaults to current directory.
        """
        self.root_dir = Path(root_dir or os.getcwd()).resolve()
        self._lock = threading.RLock()

        # Primary indices
        self._basename_to_paths: dict[str, list[Path]] = defaultdict(list)
        self._path_to_imports: dict[Path, set[str]] = {}
        self._all_files: set[Path] = set()

        # Symbol indices for common patterns
        self._class_definitions: dict[str, list[Path]] = defaultdict(list)
        self._function_definitions: dict[str, list[Path]] = defaultdict(list)

        # Cache for directory contents
        self._dir_cache: dict[Path, list[Path]] = {}

        # Cache freshness tracking
        self._cache_timestamps: dict[Path, float] = {}
        self._cache_ttl = 5.0  # 5 seconds TTL for directory cache

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
                # Remove stale entry
                self._dir_cache.pop(path, None)
                self._cache_timestamps.pop(path, None)
                return []

            # Return just the filenames, not Path objects
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
            # Convert filenames back to Path objects for internal storage
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
        self._basename_to_paths.clear()
        self._path_to_imports.clear()
        self._all_files.clear()
        self._class_definitions.clear()
        self._function_definitions.clear()
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
                        if entry.name not in IGNORE_DIRS and not entry.name.startswith("."):
                            stack.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        ext = Path(entry.name).suffix.lower()
                        if ext in INDEXED_EXTENSIONS:
                            count += 1
                            if count > QUICK_INDEX_THRESHOLD:
                                break
            except (PermissionError, OSError):
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

            # Index top-level files only (not subdirectories)
            for entry in os.scandir(self.root_dir):
                if entry.is_file(follow_symlinks=False):
                    file_path = Path(entry.path)
                    if self._should_index_file(file_path):
                        self._index_file(file_path)

            # Index priority subdirectories fully
            for name in PRIORITY_DIRS:
                priority_path = self.root_dir / name
                if priority_path.is_dir():
                    self._scan_directory(priority_path)

            self._partial_indexed = True
            self._indexed = False
            return len(self._all_files)

    def expand_index(self) -> None:
        """Expand partial index to full index.

        Safe to call in background. Only runs if _partial_indexed is True.
        Scans remaining non-priority directories.
        """
        with self._lock:
            if not self._partial_indexed:
                return

            # Scan remaining directories (non-priority)
            for entry in os.scandir(self.root_dir):
                if entry.is_dir(follow_symlinks=False):
                    dir_name = entry.name
                    if dir_name in IGNORE_DIRS or dir_name.startswith("."):
                        continue
                    if dir_name not in PRIORITY_DIRS:
                        self._scan_directory(Path(entry.path))

            self._partial_indexed = False
            self._indexed = True

    def _should_ignore_path(self, path: Path) -> bool:
        """Check if a path should be ignored during indexing."""
        # Check against ignore patterns
        parts = path.parts
        for part in parts:
            if part in IGNORE_DIRS:
                return True
            if part.startswith(".") and part != ".":
                # Skip hidden directories except current directory
                return True

        return False

    def _scan_directory(self, directory: Path) -> None:
        """Recursively scan a directory and index files."""
        if self._should_ignore_path(directory):
            return

        try:
            entries = list(directory.iterdir())
            file_list = []

            for entry in entries:
                if entry.is_dir():
                    self._scan_directory(entry)
                elif entry.is_file() and self._should_index_file(entry):
                    self._index_file(entry)
                    file_list.append(entry)

            # Cache directory contents with timestamp
            self._dir_cache[directory] = file_list
            self._cache_timestamps[directory] = time.time()

        except PermissionError:
            pass
        except Exception:
            pass

    def _should_index_file(self, file_path: Path) -> bool:
        """Check if a file should be indexed."""
        # Check extension
        if file_path.suffix.lower() not in INDEXED_EXTENSIONS:
            # Also index files with no extension if they might be scripts
            if file_path.suffix == "":
                # Check for shebang or common script names
                name = file_path.name.lower()
                if name in {"makefile", "dockerfile", "jenkinsfile", "rakefile"}:
                    return True
                # Try to detect shebang
                try:
                    with open(file_path, "rb") as f:
                        first_bytes = f.read(2)
                        if first_bytes == b"#!":
                            return True
                except Exception:
                    pass
            return False

        # Skip very large files
        try:
            if file_path.stat().st_size > 10 * 1024 * 1024:  # 10MB
                return False
        except Exception:
            return False

        return True

    def _index_file(self, file_path: Path) -> None:
        """Index a single file."""
        relative_path = file_path.relative_to(self.root_dir)

        # Add to all files set
        self._all_files.add(relative_path)

        # Index by basename
        basename = file_path.name
        self._basename_to_paths[basename].append(relative_path)

        # For Python files, extract additional information
        if file_path.suffix == ".py":
            self._index_python_file(file_path, relative_path)

    def _index_python_file(self, file_path: Path, relative_path: Path) -> None:
        """Extract Python-specific information from a file."""
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            imports = set()

            # Quick regex-free parsing for common patterns
            for line in content.splitlines():
                line = line.strip()

                # Import statements
                if line.startswith("import ") or line.startswith("from "):
                    parts = line.split()
                    if len(parts) >= 2:  # noqa: SIM102
                        if parts[0] == "import" or parts[0] == "from" and len(parts) >= 3:
                            imports.add(parts[1].split(".")[0])

                # Class definitions
                if line.startswith("class ") and ":" in line:
                    class_name = line[6:].split("(")[0].split(":")[0].strip()
                    if class_name:
                        self._class_definitions[class_name].append(relative_path)

                # Function definitions
                if line.startswith("def ") and "(" in line:
                    func_name = line[4:].split("(")[0].strip()
                    if func_name:
                        self._function_definitions[func_name].append(relative_path)

            if imports:
                self._path_to_imports[relative_path] = imports

        except Exception:
            pass

    def get_all_files(self, file_type: str | None = None) -> list[Path]:
        """Get all indexed files.

        Args:
            file_type: Optional file extension filter (e.g., '.py')

        Returns:
            List of all file paths relative to root directory.
        """
        with self._lock:
            if not self._indexed:
                self.build_index()

            if file_type:
                if not file_type.startswith("."):
                    file_type = "." + file_type
                return sorted([p for p in self._all_files if p.suffix == file_type])

            return sorted(self._all_files)

    def refresh(self, path: str | None = None) -> None:
        """Refresh the index for a specific path or the entire repository.

        Args:
            path: Optional specific path to refresh. If None, refreshes everything.
        """
        with self._lock:
            if path:
                # Refresh a specific file or directory
                target_path = Path(path)
                if not target_path.is_absolute():
                    target_path = self.root_dir / target_path

                if target_path.is_file():
                    # Re-index single file
                    relative_path = target_path.relative_to(self.root_dir)

                    # Remove from indices
                    self._remove_from_indices(relative_path)

                    # Re-index if it should be indexed
                    if self._should_index_file(target_path):
                        self._index_file(target_path)

                elif target_path.is_dir():
                    # Remove all files under this directory
                    prefix = str(target_path.relative_to(self.root_dir))
                    to_remove = [p for p in self._all_files if str(p).startswith(prefix)]
                    for p in to_remove:
                        self._remove_from_indices(p)

                    # Re-scan directory
                    self._scan_directory(target_path)
            else:
                # Full refresh
                self.build_index(force=True)

    def _remove_from_indices(self, relative_path: Path) -> None:
        """Remove a file from all indices."""
        # Remove from all files
        self._all_files.discard(relative_path)

        # Remove from basename index
        basename = relative_path.name
        if basename in self._basename_to_paths:
            self._basename_to_paths[basename] = [
                p for p in self._basename_to_paths[basename] if p != relative_path
            ]
            if not self._basename_to_paths[basename]:
                del self._basename_to_paths[basename]

        # Remove from import index
        if relative_path in self._path_to_imports:
            del self._path_to_imports[relative_path]

        # Remove from symbol indices
        for symbol_dict in [self._class_definitions, self._function_definitions]:
            for symbol, paths in list(symbol_dict.items()):
                symbol_dict[symbol] = [p for p in paths if p != relative_path]
                if not symbol_dict[symbol]:
                    del symbol_dict[symbol]
