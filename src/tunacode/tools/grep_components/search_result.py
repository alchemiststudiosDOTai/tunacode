"""
Search result and configuration data structures for the grep tool.
"""

from dataclasses import dataclass


@dataclass
class SearchResult:
    """Represents a single search match with context."""

    file_path: str
    line_number: int
    line_content: str
    match_start: int
    match_end: int
    context_before: list[str]
    context_after: list[str]
    relevance_score: float = 0.0


@dataclass
class SearchConfig:
    """Configuration for search operations."""

    case_sensitive: bool = False
    use_regex: bool = False
    max_results: int = 50
    context_lines: int = 2
    include_patterns: list[str] | None = None
    exclude_patterns: list[str] | None = None
    max_file_size: int = 1024 * 1024  # 1MB
    timeout_seconds: int = 30
    first_match_deadline: float = 3.0  # Timeout for finding first match
