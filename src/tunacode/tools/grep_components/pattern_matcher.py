"""
Pattern matching functionality for the grep tool.
"""

import re
from pathlib import Path
from typing import Any

from .search_result import SearchConfig, SearchResult


class SimpleMatch:
    """Simple match object for non-regex searches."""

    def __init__(self, start_pos: int, end_pos: int):
        self._start = start_pos
        self._end = end_pos

    def start(self) -> int:
        return self._start

    def end(self) -> int:
        return self._end


class PatternMatcher:
    """Handles pattern matching and relevance scoring for search results."""

    @staticmethod
    def search_file(
        file_path: Path,
        pattern: str,
        regex_pattern: re.Pattern | None,
        config: SearchConfig,
    ) -> list[SearchResult]:
        """Search a single file for the pattern."""
        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            results = []
            for i, line in enumerate(lines):
                line = line.rstrip("\n\r")

                # Search for pattern
                if regex_pattern:
                    matches = list(regex_pattern.finditer(line))
                else:
                    # Simple string search
                    search_line = line if config.case_sensitive else line.lower()
                    search_pattern = pattern if config.case_sensitive else pattern.lower()

                    matches = []
                    start = 0
                    while True:
                        pos = search_line.find(search_pattern, start)
                        if pos == -1:
                            break

                        match = SimpleMatch(pos, pos + len(search_pattern))
                        matches.append(match)
                        start = pos + 1

                # Create results for each match
                for match in matches:
                    # Get context lines
                    context_start = max(0, i - config.context_lines)
                    context_end = min(len(lines), i + config.context_lines + 1)

                    context_before = [lines[j].rstrip("\n\r") for j in range(context_start, i)]
                    context_after = [lines[j].rstrip("\n\r") for j in range(i + 1, context_end)]

                    # Calculate relevance score
                    relevance = PatternMatcher.calculate_relevance(
                        str(file_path), line, pattern, match
                    )

                    result = SearchResult(
                        file_path=str(file_path),
                        line_number=i + 1,
                        line_content=line,
                        match_start=match.start() if hasattr(match, "start") else match.start(),
                        match_end=match.end() if hasattr(match, "end") else match.end(),
                        context_before=context_before,
                        context_after=context_after,
                        relevance_score=relevance,
                    )
                    results.append(result)

            return results

        except Exception:
            return []

    @staticmethod
    def calculate_relevance(file_path: str, line: str, pattern: str, match: Any) -> float:
        """Calculate relevance score for a search result."""
        score = 0.0

        # Base score
        score += 1.0

        # Boost for exact matches
        if pattern.lower() in line.lower():
            score += 0.5

        # Boost for matches at word boundaries
        if match.start() == 0 or not line[match.start() - 1].isalnum():
            score += 0.3

        # Boost for certain file types
        if file_path.endswith((".py", ".js", ".ts", ".java", ".cpp", ".c")):
            score += 0.2

        # Boost for matches in comments or docstrings
        stripped_line = line.strip()
        if stripped_line.startswith(("#", "//", "/*", '"""', "'''")):
            score += 0.1

        return score

    @staticmethod
    def parse_ripgrep_output(output: str) -> list[SearchResult]:
        """Parse ripgrep JSON output into SearchResult objects."""
        import json

        results = []
        for line in output.strip().split("\n"):
            if not line:
                continue

            try:
                data = json.loads(line)
                if data.get("type") != "match":
                    continue

                match_data = data["data"]
                result = SearchResult(
                    file_path=match_data["path"]["text"],
                    line_number=match_data["line_number"],
                    line_content=match_data["lines"]["text"].rstrip("\n\r"),
                    match_start=match_data["submatches"][0]["start"],
                    match_end=match_data["submatches"][0]["end"],
                    context_before=[],  # Ripgrep context handling would go here
                    context_after=[],
                    relevance_score=1.0,
                )
                results.append(result)
            except (json.JSONDecodeError, KeyError):
                continue

        return results
