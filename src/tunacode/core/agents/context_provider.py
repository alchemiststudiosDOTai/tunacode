"""
Context provider for efficient file and directory access with caching.

This module manages file context with lazy loading, caching, and Git integration
to minimize unnecessary file reads and improve performance.
"""

import asyncio
import hashlib
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .ignore_patterns import IgnorePatterns


@dataclass
class FileMetadata:
    """Cached metadata for a file."""

    path: Path
    size: int
    mtime: float
    content_hash: Optional[str] = None
    content: Optional[str] = None
    last_accessed: float = field(default_factory=time.time)


@dataclass
class DirectorySnapshot:
    """Shallow snapshot of a directory."""

    path: Path
    files: List[Path]
    subdirs: List[Path]
    scan_time: float = field(default_factory=time.time)


class ContextProvider:
    """Provides efficient access to file and directory context."""

    def __init__(self, project_root: Path, cache_ttl: int = 300):
        self.project_root = project_root
        self.cache_ttl = cache_ttl  # Cache time-to-live in seconds
        self.ignore_patterns = IgnorePatterns(project_root)

        # Caches
        self._file_cache: Dict[Path, FileMetadata] = {}
        self._dir_cache: Dict[Path, DirectorySnapshot] = {}
        self._git_status_cache: Optional[Dict[str, str]] = None
        self._git_status_time: float = 0

        # Stats
        self.cache_hits = 0
        self.cache_misses = 0
        self.files_read = 0
        self.dirs_scanned = 0

    async def get_shallow_snapshot(self, directory: Path = None) -> DirectorySnapshot:
        """Get a shallow snapshot of a directory (non-recursive)."""
        if directory is None:
            directory = self.project_root

        # Check cache
        if directory in self._dir_cache:
            snapshot = self._dir_cache[directory]
            if time.time() - snapshot.scan_time < self.cache_ttl:
                self.cache_hits += 1
                return snapshot

        self.cache_misses += 1
        self.dirs_scanned += 1

        # Perform shallow scan
        files = []
        subdirs = []

        try:
            for item in directory.iterdir():
                # Skip if ignored
                if self.ignore_patterns.should_ignore(item):
                    continue

                if item.is_file():
                    files.append(item)
                elif item.is_dir():
                    subdirs.append(item)
        except (PermissionError, OSError):
            # Handle inaccessible directories
            pass

        snapshot = DirectorySnapshot(path=directory, files=sorted(files), subdirs=sorted(subdirs))

        # Cache the snapshot
        self._dir_cache[directory] = snapshot
        return snapshot

    async def get_file_metadata(self, file_path: Path) -> Optional[FileMetadata]:
        """Get file metadata with caching."""
        # Check if file should be ignored
        if self.ignore_patterns.should_ignore(file_path):
            return None

        # Check cache
        if file_path in self._file_cache:
            metadata = self._file_cache[file_path]

            # Check if file has been modified
            try:
                stat = file_path.stat()
                if stat.st_mtime == metadata.mtime:
                    self.cache_hits += 1
                    metadata.last_accessed = time.time()
                    return metadata
            except (OSError, IOError):
                # File might have been deleted
                del self._file_cache[file_path]
                return None

        self.cache_misses += 1

        # Get fresh metadata
        try:
            stat = file_path.stat()
            metadata = FileMetadata(path=file_path, size=stat.st_size, mtime=stat.st_mtime)
            self._file_cache[file_path] = metadata
            return metadata
        except (OSError, IOError):
            return None

    async def read_file_lazy(self, file_path: Path) -> Optional[str]:
        """Read file content lazily with caching."""
        metadata = await self.get_file_metadata(file_path)
        if not metadata:
            return None

        # Check if content is already cached
        if metadata.content is not None:
            self.cache_hits += 1
            return metadata.content

        # Read file content
        try:
            self.files_read += 1
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Update metadata with content and hash
            metadata.content = content
            metadata.content_hash = hashlib.md5(content.encode()).hexdigest()

            return content
        except (OSError, IOError, UnicodeDecodeError):
            return None

    async def batch_read_files(
        self, file_paths: List[Path], max_workers: int = 8
    ) -> Dict[Path, Optional[str]]:
        """Read multiple files in parallel for efficient batch operations."""
        from concurrent.futures import ThreadPoolExecutor

        async def read_single_file(file_path: Path) -> Tuple[Path, Optional[str]]:
            """Read a single file and return path with content."""
            content = await self.read_file_lazy(file_path)
            return (file_path, content)

        # Filter out ignored files first
        valid_paths = [p for p in file_paths if not self.ignore_patterns.should_ignore(p)]

        # Read files in parallel
        tasks = [read_single_file(path) for path in valid_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build result dictionary
        file_contents = {}
        for result in results:
            if isinstance(result, tuple):
                path, content = result
                file_contents[path] = content
            else:
                # Exception occurred, skip this file
                pass

        return file_contents

    async def get_files_matching_patterns(
        self, patterns: List[str], directory: Path = None
    ) -> List[Path]:
        """Get files matching glob patterns with caching and filtering."""
        import fnmatch

        if directory is None:
            directory = self.project_root

        matching_files = []

        # Use shallow snapshots to find files
        async def scan_directory(dir_path: Path, depth: int = 0, max_depth: int = 5):
            if depth > max_depth:
                return

            snapshot = await self.get_shallow_snapshot(dir_path)

            # Check files in this directory
            for file_path in snapshot.files:
                file_name = file_path.name
                for pattern in patterns:
                    if fnmatch.fnmatch(file_name, pattern):
                        matching_files.append(file_path)
                        break

            # Recursively scan subdirectories
            scan_tasks = []
            for subdir in snapshot.subdirs:
                if not self.ignore_patterns.should_ignore(subdir):
                    scan_tasks.append(scan_directory(subdir, depth + 1, max_depth))

            if scan_tasks:
                await asyncio.gather(*scan_tasks, return_exceptions=True)

        await scan_directory(directory)
        return matching_files

    async def get_git_status(self) -> Dict[str, str]:
        """Get Git status with caching."""
        # Check cache
        if self._git_status_cache is not None:
            if time.time() - self._git_status_time < 5:  # 5 second cache
                return self._git_status_cache

        try:
            # Run git status
            result = subprocess.run(
                ["git", "status", "--porcelain", "-uall"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                return {}

            # Parse git status output
            status_map = {}
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                status = line[:2]
                file_path = line[3:]
                status_map[file_path] = status

            self._git_status_cache = status_map
            self._git_status_time = time.time()
            return status_map

        except (subprocess.TimeoutExpired, OSError):
            return {}

    async def get_modified_files(self) -> List[Path]:
        """Get list of modified files according to Git."""
        git_status = await self.get_git_status()

        modified_files = []
        for file_path, status in git_status.items():
            # Check if file is modified (M), added (A), or renamed (R)
            if any(s in status for s in ["M", "A", "R"]):
                full_path = self.project_root / file_path
                if not self.ignore_patterns.should_ignore(full_path):
                    modified_files.append(full_path)

        return modified_files

    async def invalidate_cache(self, path: Optional[Path] = None):
        """Invalidate cache for a specific path or all caches."""
        if path is None:
            # Clear all caches
            self._file_cache.clear()
            self._dir_cache.clear()
            self._git_status_cache = None
        else:
            # Clear specific path
            if path in self._file_cache:
                del self._file_cache[path]
            if path in self._dir_cache:
                del self._dir_cache[path]

            # Also invalidate parent directory
            parent = path.parent
            if parent in self._dir_cache:
                del self._dir_cache[parent]

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "files_read": self.files_read,
            "dirs_scanned": self.dirs_scanned,
            "cached_files": len(self._file_cache),
            "cached_dirs": len(self._dir_cache),
        }

    async def prefetch_directory(self, directory: Path, max_depth: int = 2):
        """Prefetch directory structure up to a certain depth."""
        if max_depth <= 0:
            return

        snapshot = await self.get_shallow_snapshot(directory)

        # Prefetch subdirectories in parallel
        if max_depth > 1:
            tasks = []
            for subdir in snapshot.subdirs[:10]:  # Limit parallel prefetches
                tasks.append(self.prefetch_directory(subdir, max_depth - 1))

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
