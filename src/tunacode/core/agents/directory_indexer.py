"""
Directory indexer for efficient project structure discovery.

This module provides intelligent directory indexing with support for
ignore patterns, shallow scanning, and parallel operations.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .context_provider import ContextProvider
from .ignore_patterns import IgnorePatterns


@dataclass
class FileInfo:
    """Information about a file."""

    path: Path
    size: int
    extension: str
    is_source_file: bool


@dataclass
class DirectoryInfo:
    """Information about a directory."""

    path: Path
    file_count: int
    total_size: int
    has_source_files: bool
    subdirectories: List[str]


class DirectoryIndexer:
    """Indexes project directories efficiently with ignore support."""

    # Common source file extensions
    SOURCE_EXTENSIONS = {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".cpp",
        ".c",
        ".h",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".cs",
        ".swift",
        ".kt",
        ".scala",
        ".ml",
        ".hs",
        ".clj",
        ".ex",
        ".elm",
        ".vue",
        ".svelte",
    }

    def __init__(self, context_provider: ContextProvider):
        self.context = context_provider
        self.ignore_patterns = context_provider.ignore_patterns

        # Index cache
        self._index: Dict[Path, DirectoryInfo] = {}
        self._source_files: List[FileInfo] = []
        self._interesting_dirs: Set[Path] = set()

    async def build_index(self, root: Path = None, max_depth: int = 3) -> Dict[Path, DirectoryInfo]:
        """Build directory index with shallow scanning."""
        if root is None:
            root = self.context.project_root

        # Reset index
        self._index.clear()
        self._source_files.clear()
        self._interesting_dirs.clear()

        # Start indexing
        await self._index_directory(root, depth=0, max_depth=max_depth)

        # Identify interesting directories
        self._identify_interesting_dirs()

        return self._index

    async def _index_directory(self, directory: Path, depth: int, max_depth: int):
        """Recursively index a directory."""
        if depth > max_depth:
            return

        # Get shallow snapshot
        snapshot = await self.context.get_shallow_snapshot(directory)

        # Analyze files
        file_count = 0
        total_size = 0
        has_source_files = False

        for file_path in snapshot.files:
            metadata = await self.context.get_file_metadata(file_path)
            if not metadata:
                continue

            file_count += 1
            total_size += metadata.size

            extension = file_path.suffix.lower()
            is_source = extension in self.SOURCE_EXTENSIONS

            if is_source:
                has_source_files = True
                self._source_files.append(
                    FileInfo(
                        path=file_path, size=metadata.size, extension=extension, is_source_file=True
                    )
                )

        # Create directory info
        dir_info = DirectoryInfo(
            path=directory,
            file_count=file_count,
            total_size=total_size,
            has_source_files=has_source_files,
            subdirectories=[d.name for d in snapshot.subdirs],
        )

        self._index[directory] = dir_info

        # Index subdirectories in parallel (if not too deep)
        if depth < max_depth and snapshot.subdirs:
            tasks = []
            for subdir in snapshot.subdirs:
                tasks.append(self._index_directory(subdir, depth + 1, max_depth))

            # Limit parallelism
            for i in range(0, len(tasks), 5):
                batch = tasks[i : i + 5]
                await asyncio.gather(*batch, return_exceptions=True)

    def _identify_interesting_dirs(self):
        """Identify directories that are likely interesting for development."""
        for path, info in self._index.items():
            # Directory is interesting if it has source files
            if info.has_source_files:
                self._interesting_dirs.add(path)
                continue

            # Also interesting if it has certain names
            dir_name = path.name.lower()
            if any(name in dir_name for name in ["src", "lib", "app", "core", "api", "components"]):
                self._interesting_dirs.add(path)

    async def get_relevant_files(self, query: str = None) -> List[FileInfo]:
        """Get files relevant to a query or task."""
        if not self._source_files:
            await self.build_index()

        relevant_files = []

        if query:
            # Filter by query terms
            query_terms = query.lower().split()

            for file_info in self._source_files:
                file_name = file_info.path.name.lower()
                file_path_str = str(file_info.path).lower()

                # Check if any query term matches
                if any(term in file_name or term in file_path_str for term in query_terms):
                    relevant_files.append(file_info)
        else:
            # Return all source files if no query
            relevant_files = self._source_files.copy()

        # Sort by relevance (simple heuristic: shorter paths first)
        relevant_files.sort(key=lambda f: len(str(f.path)))

        return relevant_files[:50]  # Limit results

    async def get_project_structure(self, simplified: bool = True) -> Dict[str, List[str]]:
        """Get a simplified project structure."""
        if not self._index:
            await self.build_index()

        structure = {}

        for path, info in self._index.items():
            if simplified and path not in self._interesting_dirs:
                continue

            rel_path = path.relative_to(self.context.project_root)
            path_str = str(rel_path) if str(rel_path) != "." else "root"

            if info.has_source_files or info.subdirectories:
                structure[path_str] = {
                    "files": info.file_count,
                    "subdirs": info.subdirectories,
                    "has_source": info.has_source_files,
                }

        return structure

    async def find_entry_points(self) -> List[Path]:
        """Find likely entry points in the project."""
        entry_points = []

        # Common entry point names
        entry_names = {
            "main.py",
            "app.py",
            "index.js",
            "index.ts",
            "main.js",
            "main.ts",
            "server.py",
            "server.js",
            "api.py",
            "cli.py",
            "__main__.py",
            "index.html",
            "main.go",
            "main.rs",
            "main.cpp",
            "main.c",
        }

        for file_info in self._source_files:
            if file_info.path.name.lower() in entry_names:
                entry_points.append(file_info.path)

        return entry_points

    def get_statistics(self) -> Dict[str, any]:
        """Get indexing statistics."""
        return {
            "total_directories": len(self._index),
            "interesting_directories": len(self._interesting_dirs),
            "source_files": len(self._source_files),
            "total_size": sum(info.total_size for info in self._index.values()),
            "extensions": list(set(f.extension for f in self._source_files)),
        }
