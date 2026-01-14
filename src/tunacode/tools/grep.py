"""
Parallel grep tool for TunaCode - Enhanced content search with parallel processing.

This tool provides sophisticated grep-like functionality with:
- Parallel file searching across multiple directories
- Multiple search strategies (literal, regex, fuzzy)
- Smart result ranking and deduplication
- Context-aware output formatting
- Timeout handling for overly broad patterns (3 second deadline for first match)

CLAUDE_ANCHOR[grep-module]: Fast parallel file search with 3-second deadline
"""

import asyncio
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from pydantic_ai.exceptions import ModelRetry

from tunacode.configuration.defaults import DEFAULT_USER_CONFIG
from tunacode.exceptions import TooBroadPatternError, ToolExecutionError
from tunacode.tools.decorators import base_tool
from tunacode.tools.grep_components import (
    FileFilter,
    PatternMatcher,
    SearchConfig,
    SearchResult,
)
from tunacode.tools.grep_components.result_formatter import ResultFormatter
from tunacode.tools.utils.ripgrep import RipgrepExecutor
from tunacode.tools.utils.ripgrep import metrics as ripgrep_metrics


class ParallelGrep:
    """Advanced parallel grep tool with multiple search strategies."""

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=8)
        self._file_filter = FileFilter()
        self._pattern_matcher = PatternMatcher()
        self._result_formatter = ResultFormatter()
        self._ripgrep_executor = RipgrepExecutor()
        self._config = self._load_ripgrep_config()

    def _load_ripgrep_config(self) -> dict[str, Any]:
        """Load ripgrep configuration from defaults."""
        default_ripgrep_config = {
            "timeout": 10,
            "max_buffer_size": 1048576,
            "max_results": 100,
            "enable_metrics": False,
            "debug": False,
        }
        settings = DEFAULT_USER_CONFIG.get("settings", {})
        if not isinstance(settings, dict):
            return default_ripgrep_config

        config = settings.get("ripgrep", default_ripgrep_config)
        if not isinstance(config, dict):
            return default_ripgrep_config

        merged = default_ripgrep_config | config
        return merged

    async def execute(
        self,
        pattern: str,
        directory: str = ".",
        case_sensitive: bool = False,
        use_regex: bool = False,
        include_files: str | None = None,
        exclude_files: str | None = None,
        max_results: int = 50,
        context_lines: int = 2,
        search_type: str = "smart",  # smart, ripgrep, python, hybrid
        return_format: str = "string",  # "string" (default) or "list" (legacy)
        output_mode: str = "content",  # content, files_with_matches, count, json
    ) -> str | list[str]:
        """
        Execute parallel grep search with fast-glob prefiltering and multiple strategies.

        Args:
            pattern: Search pattern (literal text or regex)
            directory: Directory to search (default: current)
            case_sensitive: Whether search is case sensitive
            use_regex: Whether pattern is a regular expression
            include_files: File patterns to include (e.g., "*.py", "*.{js,ts}")
            exclude_files: File patterns to exclude (e.g., "*.pyc", "node_modules/*")
            max_results: Maximum number of results to return
            context_lines: Number of context lines before/after matches
            search_type: Search strategy to use

        Returns:
            Formatted search results
        """
        try:
            # 0️⃣ Validate directory path before any file operations
            dir_path = Path(directory).resolve()
            if not dir_path.exists():
                raise ModelRetry(f"Directory not found: {directory}. Check the path.")
            if not dir_path.is_dir():
                raise ModelRetry(f"Not a directory: {directory}. Provide a directory path.")

            # 1️⃣ Fast-glob prefilter to find candidate files
            include_pattern = include_files or "*"
            exclude_pattern = exclude_files

            candidates = await asyncio.get_running_loop().run_in_executor(
                self._executor,
                self._file_filter.fast_glob,
                Path(directory),
                include_pattern,
                exclude_pattern,
            )

            if not candidates:
                if return_format == "list":
                    return []
                return f"No files found matching pattern: {include_pattern}"

            # 2️⃣ Smart strategy selection based on candidate count
            original_search_type = search_type
            if search_type == "smart":
                if len(candidates) <= 50:
                    # Small set - Python strategy more efficient (low startup cost)
                    search_type = "python"
                elif len(candidates) <= 1000:
                    # Medium set - Ripgrep optimal for this range
                    search_type = "ripgrep"
                else:
                    # Large set - Hybrid for best coverage and redundancy
                    search_type = "hybrid"

            # 3️⃣ Create search configuration
            # Note: include_patterns/exclude_patterns now only used for legacy compatibility
            include_patterns = (
                self._file_filter.parse_patterns(include_files) if include_files else ["*"]
            )
            exclude_patterns = (
                self._file_filter.parse_patterns(exclude_files) if exclude_files else []
            )
            config = SearchConfig(
                case_sensitive=case_sensitive,
                use_regex=use_regex,
                max_results=max_results,
                context_lines=context_lines,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
            )

            # 4️⃣ Execute chosen strategy with pre-filtered candidates
            # Execute search with pre-filtered candidates
            if search_type == "ripgrep":
                # Try ripgrep first for performance. If ripgrep is unavailable or
                # returns no results (e.g., binary missing), gracefully fallback to
                # the Python implementation so the tool still returns matches.
                results = await self._ripgrep_search_filtered(pattern, candidates, config)
                if not results:
                    # Fallback to python search when ripgrep produced no output
                    results = await self._python_search_filtered(pattern, candidates, config)
            elif search_type == "python":
                results = await self._python_search_filtered(pattern, candidates, config)
            elif search_type == "hybrid":
                results = await self._hybrid_search_filtered(pattern, candidates, config)
            else:
                raise ToolExecutionError(
                    tool_name="grep", message=f"Unknown search type: {search_type}"
                )

            # 5️⃣ Format and return results with strategy info
            strategy_info = (
                f"Strategy: {search_type} (was {original_search_type}), "
                f"Files: {len(candidates)}/{5000}"
            )
            formatted_results = self._result_formatter.format_results(
                results, pattern, config, output_mode=output_mode
            )

            if return_format == "list":
                # Legacy: return list of file paths with at least one match
                file_set = set()
                for r in results:
                    file_set.add(r.file_path)
                return list(file_set)
            else:
                # Add strategy info to results
                if formatted_results.startswith("Found"):
                    lines = formatted_results.split("\n")
                    lines[1] = (
                        f"Strategy: {search_type} | Candidates: {len(candidates)} files | "
                        + lines[1]
                    )
                    return "\n".join(lines)
                else:
                    return f"{formatted_results}\n\n{strategy_info}"

        except TooBroadPatternError:
            # Re-raise TooBroadPatternError without wrapping it
            raise
        except ModelRetry:
            # Re-raise ModelRetry for LLM self-correction
            raise
        except Exception as err:
            raise ToolExecutionError(
                tool_name="grep", message=f"Grep search failed: {err}"
            ) from err

    # ====== SEARCH METHODS ======

    async def _ripgrep_search_filtered(
        self, pattern: str, candidates: list[Path], config: SearchConfig
    ) -> list[SearchResult]:
        """
        Run ripgrep on pre-filtered file list using the enhanced RipgrepExecutor.
        """
        start_time = time.time()
        results: list[SearchResult] = []

        timeout_setting = self._config.get("timeout", 10)
        timeout = min(timeout_setting, config.timeout_seconds)

        if self._ripgrep_executor._use_python_fallback:
            return []

        try:
            # Use the enhanced executor with support for context lines
            # Note: Currently searching all files, not using candidates
            # This is a limitation that should be addressed in future enhancement
            search_results = await self._ripgrep_executor.search(
                pattern=pattern,
                path=".",  # Search in current directory
                timeout=timeout,
                max_matches=config.max_results,
                case_insensitive=not config.case_sensitive,
                context_before=config.context_lines,
                context_after=config.context_lines,
            )

            # Ripgrep doesn't provide timing info for first match, so we rely on
            # the overall timeout mechanism instead of first_match_deadline

            # Parse results
            for result_line in search_results:
                # Parse ripgrep output format "file:line:content"
                parts = result_line.split(":", 2)
                if len(parts) < 3:
                    continue

                # Filter to only include results from candidates
                file_path = Path(parts[0])
                if file_path not in candidates:
                    continue

                try:
                    line_content = parts[2]
                    search_result = SearchResult(
                        file_path=parts[0],
                        line_number=int(parts[1]),
                        line_content=line_content,
                        match_start=0,
                        match_end=len(line_content),
                        context_before=[],
                        context_after=[],
                        relevance_score=1.0,
                    )
                    results.append(search_result)

                    # Stop if we have enough results
                    if config.max_results and len(results) >= config.max_results:
                        break
                except (ValueError, IndexError):
                    continue

        except TooBroadPatternError:
            raise
        except Exception:
            # Return empty to trigger fallback
            return []

        if self._config.get("enable_metrics", False):
            total_time = time.time() - start_time
            ripgrep_metrics.record_search(
                duration=total_time, used_fallback=self._ripgrep_executor._use_python_fallback
            )

        return results

    async def _python_search_filtered(
        self, pattern: str, candidates: list[Path], config: SearchConfig
    ) -> list[SearchResult]:
        """
        Run Python parallel search on pre-filtered candidates with first match deadline.
        """
        # Prepare search pattern
        if config.use_regex:
            flags = 0 if config.case_sensitive else re.IGNORECASE
            regex_pattern = re.compile(pattern, flags)
        else:
            regex_pattern = None

        # Track search progress
        first_match_event = asyncio.Event()

        async def search_with_monitoring(file_path: Path):
            """Search a file and signal when first match is found."""
            try:
                file_results = await self._search_file(file_path, pattern, regex_pattern, config)
                if file_results and not first_match_event.is_set():
                    first_match_event.set()
                return file_results
            except Exception:
                return []

        # Create search tasks for candidates only
        search_tasks = []
        for file_path in candidates:
            task = search_with_monitoring(file_path)
            search_tasks.append(task)

        # Create a deadline task
        async def check_deadline():
            """Monitor for first match deadline."""
            await asyncio.sleep(config.first_match_deadline)
            if not first_match_event.is_set():
                # Cancel all pending tasks
                for task in search_tasks:
                    if not task.done():
                        task.cancel()
                raise TooBroadPatternError(pattern, config.first_match_deadline)

        deadline_task = asyncio.create_task(check_deadline())

        try:
            # Execute searches in parallel with deadline monitoring
            all_results = await asyncio.gather(*search_tasks, return_exceptions=True)

            # Cancel deadline task if we got results
            deadline_task.cancel()

            # Flatten results and filter out exceptions
            results = []
            for file_results in all_results:
                if isinstance(file_results, list):
                    results.extend(file_results)

            # Sort by relevance and limit results
            results.sort(key=lambda r: r.relevance_score, reverse=True)
            return results[: config.max_results]

        except asyncio.CancelledError:
            # Re-raise TooBroadPatternError if that's what caused the cancellation
            if deadline_task.done():
                try:
                    await deadline_task
                except TooBroadPatternError:
                    raise
            return []

    async def _hybrid_search_filtered(
        self, pattern: str, candidates: list[Path], config: SearchConfig
    ) -> list[SearchResult]:
        """
        Hybrid approach using multiple search methods concurrently on pre-filtered candidates.
        """

        # Run multiple search strategies in parallel
        tasks = [
            self._ripgrep_search_filtered(pattern, candidates, config),
            self._python_search_filtered(pattern, candidates, config),
        ]

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # Check if any task raised TooBroadPatternError
        too_broad_errors = [r for r in results_list if isinstance(r, TooBroadPatternError)]
        if too_broad_errors:
            # If both strategies timed out, raise the error
            valid_results = [r for r in results_list if isinstance(r, list)]
            if not valid_results:
                raise too_broad_errors[0]

        # Merge and deduplicate results
        all_results = []
        for results in results_list:
            if isinstance(results, list):
                all_results.extend(results)

        # Deduplicate by file path and line number
        seen = set()
        unique_results = []
        for result in all_results:
            key = (result.file_path, result.line_number)
            if key not in seen:
                seen.add(key)
                unique_results.append(result)

        # Sort and limit
        unique_results.sort(key=lambda r: r.relevance_score, reverse=True)
        return unique_results[: config.max_results]

    async def _search_file(
        self,
        file_path: Path,
        pattern: str,
        regex_pattern: re.Pattern | None,
        config: SearchConfig,
    ) -> list[SearchResult]:
        """Search a single file for the pattern."""

        def search_file_sync():
            return self._pattern_matcher.search_file(file_path, pattern, regex_pattern, config)

        return await asyncio.get_running_loop().run_in_executor(self._executor, search_file_sync)


@base_tool
async def grep(
    pattern: str,
    directory: str = ".",
    path: str | None = None,
    case_sensitive: bool = False,
    use_regex: bool = False,
    include_files: str | None = None,
    exclude_files: str | None = None,
    max_results: int = 50,
    context_lines: int = 2,
    search_type: str = "smart",
    return_format: str = "string",
    output_mode: str = "content",
) -> str | list[str]:
    """Advanced parallel grep search with multiple strategies.

    Args:
        pattern: Search pattern (literal text or regex).
        directory: Directory to search (default: current directory).
        path: Alias for directory.
        case_sensitive: Whether search is case sensitive.
        use_regex: Whether pattern is a regular expression.
        include_files: File patterns to include (e.g., "*.py,*.js").
        exclude_files: File patterns to exclude.
        max_results: Maximum number of results to return.
        context_lines: Number of context lines before/after matches.
        search_type: Search strategy (smart/ripgrep/python/hybrid).
        return_format: Output format (string or list).
        output_mode: Output mode (content, files_with_matches, count, json).

    Returns:
        Formatted search results with file paths, line numbers, and context.
    """
    if path is not None:
        directory = path

    tool = ParallelGrep()
    return await tool.execute(
        pattern=pattern,
        directory=directory,
        case_sensitive=case_sensitive,
        use_regex=use_regex,
        include_files=include_files,
        exclude_files=exclude_files,
        max_results=max_results,
        context_lines=context_lines,
        search_type=search_type,
        return_format=return_format,
        output_mode=output_mode,
    )
