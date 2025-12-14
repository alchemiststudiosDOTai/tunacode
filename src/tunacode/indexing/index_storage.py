"""Index storage and lookup operations for code indexing.

This module manages the in-memory data structures used for fast file lookups
and provides query operations against the index.
"""

from collections import defaultdict
from pathlib import Path


def _normalize_file_type(file_type: str | None) -> str | None:
    """Normalize file extension to include leading dot."""
    if file_type is None:
        return None
    if file_type.startswith("."):
        return file_type
    return "." + file_type


class IndexStorage:
    """In-memory storage for code index data.

    Provides fast lookups by basename, path, symbols, and imports.
    All paths are relative to the repository root.
    """

    def __init__(self) -> None:
        """Initialize empty index storage."""
        self._basename_to_paths: dict[str, list[Path]] = defaultdict(list)
        self._path_to_imports: dict[Path, set[str]] = {}
        self._all_files: set[Path] = set()
        self._class_definitions: dict[str, list[Path]] = defaultdict(list)
        self._function_definitions: dict[str, list[Path]] = defaultdict(list)

    def clear(self) -> None:
        """Clear all index data."""
        self._basename_to_paths.clear()
        self._path_to_imports.clear()
        self._all_files.clear()
        self._class_definitions.clear()
        self._function_definitions.clear()

    def add_file(
        self,
        relative_path: Path,
        imports: set[str] | None = None,
        classes: list[str] | None = None,
        functions: list[str] | None = None,
    ) -> None:
        """Add or update a file in the index (replace semantics).

        If the file already exists in the index, it will be removed first
        to prevent duplicate/stale entries.

        Args:
            relative_path: File path relative to repository root.
            imports: Set of top-level module imports (for Python files).
                     Pass empty set() to track Python files with no imports.
            classes: List of class names defined in the file.
            functions: List of function names defined in the file.
        """
        if relative_path in self._all_files:
            self.remove_file(relative_path)

        self._all_files.add(relative_path)
        self._basename_to_paths[relative_path.name].append(relative_path)

        if imports is not None:
            self._path_to_imports[relative_path] = imports

        if classes:
            for class_name in classes:
                self._class_definitions[class_name].append(relative_path)

        if functions:
            for func_name in functions:
                self._function_definitions[func_name].append(relative_path)

    def remove_file(self, relative_path: Path) -> None:
        """Remove a file from all indices.

        Args:
            relative_path: File path relative to repository root.
        """
        self._all_files.discard(relative_path)

        basename = relative_path.name
        if basename in self._basename_to_paths:
            self._basename_to_paths[basename] = [
                p for p in self._basename_to_paths[basename] if p != relative_path
            ]
            if not self._basename_to_paths[basename]:
                del self._basename_to_paths[basename]

        self._path_to_imports.pop(relative_path, None)

        for symbol_dict in [self._class_definitions, self._function_definitions]:
            for symbol, paths in list(symbol_dict.items()):
                symbol_dict[symbol] = [p for p in paths if p != relative_path]
                if not symbol_dict[symbol]:
                    del symbol_dict[symbol]

    def lookup(self, query: str, file_type: str | None = None) -> list[Path]:
        """Look up files matching a query.

        Searches across basenames, paths, and symbols (classes/functions).

        Args:
            query: Search query (basename, partial path, or symbol).
                   Empty string returns empty list.
            file_type: Optional file extension filter (e.g., '.py' or 'py').

        Returns:
            List of matching file paths, sorted by relevance.
        """
        if not query:
            return []

        results: set[Path] = set()
        normalized_type = _normalize_file_type(file_type)

        if query in self._basename_to_paths:
            results.update(self._basename_to_paths[query])

        query_lower = query.lower()
        for basename, paths in self._basename_to_paths.items():
            if query_lower in basename.lower():
                results.update(paths)

        for file_path in self._all_files:
            if query_lower in str(file_path).lower():
                results.add(file_path)

        if query in self._class_definitions:
            results.update(self._class_definitions[query])
        if query in self._function_definitions:
            results.update(self._function_definitions[query])

        if normalized_type:
            results = {p for p in results if p.suffix == normalized_type}

        return sorted(
            results,
            key=lambda p: (
                0 if p.name == query else 1,
                len(str(p)),
                str(p),
            ),
        )

    def get_all_files(self, file_type: str | None = None) -> list[Path]:
        """Get all indexed files.

        Args:
            file_type: Optional file extension filter (e.g., '.py' or 'py').

        Returns:
            List of all file paths, sorted alphabetically.
        """
        normalized_type = _normalize_file_type(file_type)

        if normalized_type:
            return sorted([p for p in self._all_files if p.suffix == normalized_type])

        return sorted(self._all_files)

    def find_imports(self, module_name: str) -> list[Path]:
        """Find files that import a specific module.

        Args:
            module_name: Name of the module to search for.

        Returns:
            List of file paths that import the module, sorted alphabetically.
        """
        results = []
        for file_path, imports in self._path_to_imports.items():
            if module_name in imports:
                results.append(file_path)

        return sorted(results)

    def get_stats(self) -> dict[str, int]:
        """Get index statistics.

        Returns:
            Dictionary with counts of indexed items.
        """
        return {
            "total_files": len(self._all_files),
            "unique_basenames": len(self._basename_to_paths),
            "python_files_indexed": len(self._path_to_imports),
            "classes_indexed": len(self._class_definitions),
            "functions_indexed": len(self._function_definitions),
        }
