from __future__ import annotations

import os
from pathlib import Path

import pathspec

from tunacode.configuration.ignore_patterns import DEFAULT_IGNORE_PATTERNS
from tunacode.constants import AUTOCOMPLETE_MAX_DEPTH, AUTOCOMPLETE_RESULT_LIMIT


class FileFilter:
    """Gitignore-aware file filtering."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(".")
        self._spec = self._build_spec()

    def _build_spec(self) -> pathspec.PathSpec:
        patterns = list(DEFAULT_IGNORE_PATTERNS)
        gitignore = self.root / ".gitignore"
        if gitignore.exists():
            patterns.extend(gitignore.read_text().splitlines())
        return pathspec.PathSpec.from_lines("gitwildmatch", patterns)

    def is_ignored(self, path: Path) -> bool:
        try:
            rel = path.relative_to(self.root)
            return self._spec.match_file(str(rel))
        except ValueError:
            return False

    def _parse_prefix(self, prefix: str) -> tuple[Path, str]:
        """Parse prefix into search path and name filter."""
        if not prefix:
            return self.root, ""

        candidate = self.root / prefix

        if candidate.exists() and candidate.is_dir():
            return candidate, ""

        search_path = candidate.parent
        name_prefix = Path(prefix).name

        if not search_path.exists():
            return self.root, ""

        return search_path, name_prefix

    def _matches_prefix(self, path: Path, name_prefix: str, search_path: Path) -> bool:
        """Check if path matches name prefix filter."""
        if not name_prefix:
            return True

        prefix_lower = name_prefix.lower()

        if path.parent == search_path:
            return path.name.lower().startswith(prefix_lower)

        rel_path = path.relative_to(search_path)
        return any(prefix_lower in part.lower() for part in rel_path.parts)

    def complete(
        self,
        prefix: str = "",
        limit: int = AUTOCOMPLETE_RESULT_LIMIT,
        max_depth: int = AUTOCOMPLETE_MAX_DEPTH,
    ) -> list[str]:
        """Return filtered file paths matching prefix."""
        search_path, name_prefix = self._parse_prefix(prefix)

        if not search_path.exists():
            return []

        results_with_depth: list[tuple[int, str]] = []

        for root_dir, dirs, files in os.walk(str(search_path), topdown=True):
            root_path = Path(root_dir)
            rel_root = root_path.relative_to(search_path)
            current_depth = len(rel_root.parts)

            if current_depth >= max_depth:
                dirs[:] = []

            dirs[:] = sorted(d for d in dirs if not self.is_ignored(root_path / d))

            for d in dirs:
                dir_path = root_path / d
                if not self._matches_prefix(dir_path, name_prefix, search_path):
                    continue

                rel = dir_path.relative_to(self.root)
                results_with_depth.append((current_depth, f"{rel}/"))

                if len(results_with_depth) >= limit:
                    break

            for f in sorted(files):
                file_path = root_path / f
                if self.is_ignored(file_path):
                    continue
                if not self._matches_prefix(file_path, name_prefix, search_path):
                    continue

                rel = file_path.relative_to(self.root)
                results_with_depth.append((current_depth, str(rel)))

                if len(results_with_depth) >= limit:
                    break

            if len(results_with_depth) >= limit:
                break

        results_with_depth.sort(key=lambda x: (x[0], x[1]))
        return [path for _, path in results_with_depth[:limit]]
