"""
Extended result formatter with multiple output modes for flexible presentation.
Result formatting functionality for the grep tool.
"""


from .search_result import SearchConfig, SearchResult


class ResultFormatter:
    """Handles formatting of search results for display with multiple output modes."""

    @staticmethod
    def format_results(
        results: list[SearchResult],
        pattern: str,
        config: SearchConfig,
        output_mode: str = "content",
    ) -> str:
        """Format search results for display.

        Args:
            results: List of search results
            pattern: Search pattern
            config: Search configuration
            output_mode: Output format mode:
                - "content": Show matching lines with context (default)
                - "files_with_matches": Show only file paths
                - "count": Show match counts per file
                - "json": JSON format for programmatic use

        Returns:
            Formatted string based on output mode
        """
        if not results:
            return f"No matches found for pattern: {pattern}"

        if output_mode == "files_with_matches":
            return ResultFormatter._format_files_only(results, pattern)
        elif output_mode == "count":
            return ResultFormatter._format_count(results, pattern)
        elif output_mode == "json":
            return ResultFormatter._format_json(results, pattern)
        else:  # Default to "content"
            return ResultFormatter._format_content(results, pattern, config)

    @staticmethod
    def _format_content(results: list[SearchResult], pattern: str, config: SearchConfig) -> str:
        """Format results with content grouped by file."""
        output = [f"Found {len(results)} matches"]

        current_file = ""
        for result in results:
            if current_file != result.file_path:
                if current_file:
                    output.append("")
                current_file = result.file_path
                output.append(f"{result.file_path}:")

            output.append(f"  {result.line_number}: {result.line_content}")

        return "\n".join(output)

    @staticmethod
    def _format_files_only(results: list[SearchResult], pattern: str) -> str:
        """Format results showing only file paths."""
        files = sorted(set(r.file_path for r in results))
        return "\n".join(files)

    @staticmethod
    def _format_count(results: list[SearchResult], pattern: str) -> str:
        """Format results showing match counts per file."""
        file_counts: dict[str, int] = {}
        for result in results:
            file_counts[result.file_path] = file_counts.get(result.file_path, 0) + 1

        sorted_counts = sorted(file_counts.items(), key=lambda x: (-x[1], x[0]))
        return "\n".join(f"{count} {path}" for path, count in sorted_counts)

    @staticmethod
    def _format_json(results: list[SearchResult], pattern: str) -> str:
        """Format results as JSON."""
        import json

        json_results = [
            {"file": r.file_path, "line": r.line_number, "content": r.line_content} for r in results
        ]
        return json.dumps(json_results)
