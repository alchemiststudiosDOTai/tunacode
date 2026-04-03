"""UI adapter for file autocomplete filtering."""

from __future__ import annotations

from pathlib import Path

from tunacode.configuration.ignore_patterns import DEFAULT_IGNORE_PATTERNS
from tunacode.constants import AUTOCOMPLETE_MAX_DEPTH, AUTOCOMPLETE_RESULT_LIMIT

from tunacode.infrastructure.file_filter import FileFilter as InfrastructureFileFilter


class FileFilter(InfrastructureFileFilter):
    """UI-facing adapter that supplies default ignore patterns and limits."""

    def __init__(self, root: Path | None = None) -> None:
        super().__init__(
            ignore_patterns=DEFAULT_IGNORE_PATTERNS,
            result_limit=AUTOCOMPLETE_RESULT_LIMIT,
            max_depth=AUTOCOMPLETE_MAX_DEPTH,
            root=root,
        )
