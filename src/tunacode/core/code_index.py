"""Fast in-memory code index for efficient file lookups."""

import logging
import os
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class CodeIndex:
    """Fast in-memory code index for repository file lookups.

    This index provides efficient file discovery without relying on
    grep searches that can timeout in large repositories.
    """

    # Singleton instance
    _instance: Optional["CodeIndex"] = None
    _instance_lock = threading.RLock()

    # Directories to ignore during indexing
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
        ".vscode",
        ".vs",
        "htmlcov",
        ".coverage",
        ".tox",
        ".eggs",
        "*.egg-info",
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

    # File extensions to index
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
        ".gitignore",
        ".env.example",
    }

    def __init__(self, root_dir: Optional[str] = None):
        """Initialize the code index.

        Args:
            root_dir: Root directory to index. Defaults to current directory.
        """
        self.root_dir = Path(root_dir or os.getcwd()).resolve()
        self._lock = threading.RLock()

        # Primary indices
        self._basename_to_paths: Dict[str, List[Path]] = defaultdict(list)
        self._path_to_imports: Dict[Path, Set[str]] = {}
        self._all_files: Set[Path] = set()

        # Symbol indices for common patterns
        self._class_definitions: Dict[str, List[Path]] = defaultdict(list)
        self._function_definitions: Dict[str, List[Path]] = defaultdict(list)

        # Cache for directory contents
        self._dir_cache: Dict[Path, List[Path]] = {}

        # Cache freshness tracking
        self._cache_timestamps: Dict[Path, float] = {}
        self._cache_ttl = 5.0  # 5 seconds TTL for directory cache

        self._indexed = False

    @classmethod
    def get_instance(cls, root_dir: Optional[str] = None) -> "CodeIndex":
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

    def get_directory_contents(self, path: Path) -> List[str]:
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

    def update_directory_cache(self, path: Path, entries: List[str]) -> None:
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

            logger.info(f"Building code index for {self.root_dir}")
            self._clear_indices()

            try:
                self._scan_directory(self.root_dir)
                self._indexed = True
                logger.info(f"Indexed {len(self._all_files)} files")
            except Exception as e:
                logger.error(f"Error building index: {e}")
                raise

    def _clear_indices(self) -> None:
        """Clear all indices."""
        self._basename_to_paths.clear()
        self._path_to_imports.clear()
        self._all_files.clear()
        self._class_definitions.clear()
        self._function_definitions.clear()
        self._dir_cache.clear()
        self._cache_timestamps.clear()

    def _should_ignore_path(self, path: Path) -> bool:
        """Check if a path should be ignored during indexing."""
        # Check against ignore patterns
        parts = path.parts
        for part in parts:
            if part in self.IGNORE_DIRS:
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
                elif entry.is_file():
                    if self._should_index_file(entry):
                        self._index_file(entry)
                        file_list.append(entry)

            # Cache directory contents with timestamp
            self._dir_cache[directory] = file_list
            self._cache_timestamps[directory] = time.time()

        except PermissionError:
            logger.debug(f"Permission denied: {directory}")
        except Exception as e:
            logger.warning(f"Error scanning {directory}: {e}")

    def _should_index_file(self, file_path: Path) -> bool:
        """Check if a file should be indexed."""
        # Check extension
        if file_path.suffix.lower() not in self.INDEXED_EXTENSIONS:
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
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            imports = set()

            # Quick regex-free parsing for common patterns
            for line in content.splitlines():
                line = line.strip()

                # Import statements
                if line.startswith("import ") or line.startswith("from "):
                    parts = line.split()
                    if len(parts) >= 2:
                        if parts[0] == "import":
                            imports.add(parts[1].split(".")[0])
                        elif parts[0] == "from" and len(parts) >= 3:
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

        except Exception as e:
            logger.debug(f"Error indexing Python file {file_path}: {e}")

    def lookup(self, query: str, file_type: Optional[str] = None) -> List[Path]:
        """Look up files matching a query.

        Args:
            query: Search query (basename, partial path, or symbol)
            file_type: Optional file extension filter (e.g., '.py')

        Returns:
            List of matching file paths relative to root directory.
        """
        with self._lock:
            if not self._indexed:
                self.build_index()

            results = set()

            # Exact basename match
            if query in self._basename_to_paths:
                results.update(self._basename_to_paths[query])

            # Partial basename match
            query_lower = query.lower()
            for basename, paths in self._basename_to_paths.items():
                if query_lower in basename.lower():
                    results.update(paths)

            # Path component match
            for file_path in self._all_files:
                if query_lower in str(file_path).lower():
                    results.add(file_path)

            # Symbol matches (classes and functions)
            if query in self._class_definitions:
                results.update(self._class_definitions[query])
            if query in self._function_definitions:
                results.update(self._function_definitions[query])

            # Filter by file type if specified
            if file_type:
                if not file_type.startswith("."):
                    file_type = "." + file_type
                results = {p for p in results if p.suffix == file_type}

            # Sort results by relevance
            sorted_results = sorted(
                results,
                key=lambda p: (
                    # Exact basename matches first
                    0 if p.name == query else 1,
                    # Then shorter paths
                    len(str(p)),
                    # Then alphabetically
                    str(p),
                ),
            )

            return sorted_results

    def get_all_files(self, file_type: Optional[str] = None) -> List[Path]:
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

    def find_imports(self, module_name: str) -> List[Path]:
        """Find files that import a specific module.

        Args:
            module_name: Name of the module to search for

        Returns:
            List of file paths that import the module.
        """
        with self._lock:
            if not self._indexed:
                self.build_index()

            results = []
            for file_path, imports in self._path_to_imports.items():
                if module_name in imports:
                    results.append(file_path)

            return sorted(results)

    def refresh(self, path: Optional[str] = None) -> None:
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

    def get_stats(self) -> Dict[str, int]:
        """Get indexing statistics.

        Returns:
            Dictionary with index statistics.
        """
        with self._lock:
            return {
                "total_files": len(self._all_files),
                "unique_basenames": len(self._basename_to_paths),
                "python_files": len(self._path_to_imports),
                "classes_indexed": len(self._class_definitions),
                "functions_indexed": len(self._function_definitions),
                "directories_cached": len(self._dir_cache),
            }
