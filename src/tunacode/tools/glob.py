"""Glob tool for fast file pattern matching."""

import asyncio
import fnmatch
import os
import re
from enum import Enum
from pathlib import Path

from pydantic_ai.exceptions import ModelRetry

from tunacode.indexing import CodeIndex

from tunacode.tools.decorators import base_tool
from tunacode.tools.ignore import IgnoreManager, get_ignore_manager

MAX_RESULTS = 5000
EXCLUDE_DIR_SUFFIX = "/"
EMPTY_EXCLUDE_DIR_PATTERNS: tuple[str, ...] = ()


class SortOrder(Enum):
    """Sorting options for glob results."""

    MODIFIED = "modified"
    SIZE = "size"
    ALPHABETICAL = "alphabetical"
    DEPTH = "depth"


@base_tool
async def glob(
    pattern: str,
    directory: str = ".",
    recursive: bool = True,
    include_hidden: bool = False,
    exclude_dirs: list[str] | None = None,
    max_results: int = MAX_RESULTS,
    sort_by: str = "modified",
    case_sensitive: bool = False,
) -> str:
    """Find files matching glob patterns.

    Args:
        pattern: Glob pattern to match (e.g., "*.py", "**/*.{js,ts}").
        directory: Directory to search in (default: current directory).
        recursive: Whether to search recursively (default: True).
        include_hidden: Whether to include hidden files/directories.
        exclude_dirs: Additional directories to exclude from search.
        max_results: Maximum number of results to return.
        sort_by: How to sort results (modified/size/alphabetical/depth).
        case_sensitive: Whether pattern matching is case-sensitive.

    Returns:
        Formatted list of matching file paths.
    """
    root_path = Path(directory).resolve()
    if not root_path.exists():
        raise ModelRetry(f"Directory not found: {directory}. Check the path.")
    if not root_path.is_dir():
        raise ModelRetry(f"Not a directory: {directory}. Provide a directory path.")

    ignore_manager = _build_ignore_manager(root_path, exclude_dirs)
    sort_order = _parse_sort_order(sort_by)
    patterns = _expand_brace_pattern(pattern)

    # Try CodeIndex for faster lookup
    code_index = _get_code_index(directory)
    source = "filesystem"

    has_code_index = code_index is not None
    should_use_index = has_code_index and not include_hidden and recursive
    if should_use_index:
        matches = await _glob_with_index(
            code_index, patterns, root_path, ignore_manager, max_results, case_sensitive
        )
        source = "index"
    else:
        matches = await _glob_filesystem(
            root_path,
            patterns,
            recursive,
            include_hidden,
            ignore_manager,
            max_results,
            case_sensitive,
        )

    if not matches:
        return f"[source:{source}]\nNo files found matching pattern: {pattern}"

    matches = await _sort_matches(matches, sort_order)
    return _format_output(pattern, matches, max_results, source)


def _parse_sort_order(sort_by: str) -> SortOrder:
    """Parse sort order string to enum."""
    try:
        return SortOrder(sort_by)
    except ValueError:
        return SortOrder.MODIFIED


def _build_ignore_manager(root: Path, exclude_dirs: list[str] | None) -> IgnoreManager:
    ignore_manager = get_ignore_manager(root)
    exclude_patterns = _normalize_exclude_dir_patterns(exclude_dirs)
    if not exclude_patterns:
        return ignore_manager
    return ignore_manager.with_additional_patterns(exclude_patterns)


def _normalize_exclude_dir_patterns(exclude_dirs: list[str] | None) -> tuple[str, ...]:
    if not exclude_dirs:
        return EMPTY_EXCLUDE_DIR_PATTERNS
    patterns: list[str] = []
    for name in exclude_dirs:
        stripped_name = name.strip()
        if not stripped_name:
            continue
        has_suffix = stripped_name.endswith(EXCLUDE_DIR_SUFFIX)
        pattern = stripped_name if has_suffix else f"{stripped_name}{EXCLUDE_DIR_SUFFIX}"
        patterns.append(pattern)
    return tuple(patterns)


def _get_code_index(directory: str) -> CodeIndex | None:
    """Get CodeIndex instance if searching from project root."""
    if directory != "." and directory != os.getcwd():
        return None
    try:
        index = CodeIndex.get_instance()
        index.build_index()
        return index
    except Exception:
        return None


def _expand_brace_pattern(pattern: str) -> list[str]:
    """Expand brace patterns like "*.{py,js,ts}" into multiple patterns."""
    if "{" not in pattern or "}" not in pattern:
        return [pattern]

    expanded = []
    stack = [pattern]

    while stack:
        current = stack.pop()
        start = -1
        depth = 0

        for i, char in enumerate(current):
            if char == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0 and start != -1:
                    prefix = current[:start]
                    suffix = current[i + 1 :]
                    options = current[start + 1 : i].split(",")

                    for option in options:
                        new_pattern = prefix + option.strip() + suffix
                        if "{" in new_pattern:
                            stack.append(new_pattern)
                        else:
                            expanded.append(new_pattern)
                    break
        else:
            expanded.append(current)

    return expanded


async def _glob_with_index(
    code_index: CodeIndex,
    patterns: list[str],
    root: Path,
    ignore_manager: IgnoreManager,
    max_results: int,
    case_sensitive: bool,
) -> list[str]:
    """Use CodeIndex for faster file matching."""
    all_files = code_index.get_all_files()
    matches = []

    for file_path in all_files:
        abs_path = code_index.root_dir / file_path

        for pattern in patterns:
            path_matches = _match_pattern(str(file_path), pattern, case_sensitive)
            if not path_matches:
                continue
            is_ignored = ignore_manager.should_ignore(file_path)
            if is_ignored:
                break
            matches.append(str(abs_path))
            if len(matches) >= max_results:
                return matches
            break

    return matches


def _match_pattern(path: str, pattern: str, case_sensitive: bool) -> bool:
    """Match a path against a glob pattern."""
    if "**" in pattern:
        if pattern.startswith("**/"):
            suffix = pattern[3:]
            if case_sensitive:
                if fnmatch.fnmatch(path, suffix):
                    return True
            else:
                if fnmatch.fnmatch(path.lower(), suffix.lower()):
                    return True

        regex_pat = pattern.replace("**", "__STARSTAR__")
        regex_pat = fnmatch.translate(regex_pat)
        regex_pat = regex_pat.replace("__STARSTAR__", ".*")
        flags = 0 if case_sensitive else re.IGNORECASE
        return bool(re.match(regex_pat, path, flags))
    else:
        if case_sensitive:
            return fnmatch.fnmatch(path, pattern)
        return fnmatch.fnmatch(path.lower(), pattern.lower())


async def _glob_filesystem(
    root: Path,
    patterns: list[str],
    recursive: bool,
    include_hidden: bool,
    ignore_manager: IgnoreManager,
    max_results: int,
    case_sensitive: bool,
) -> list[str]:
    """Perform glob search using os.scandir."""

    def search_sync():
        matches = []
        stack = [root]
        flags = 0 if case_sensitive else re.IGNORECASE

        compiled = []
        for pat in patterns:
            if "**" in pat:
                regex_pat = pat.replace("**", "__STARSTAR__")
                regex_pat = fnmatch.translate(regex_pat)
                regex_pat = regex_pat.replace("__STARSTAR__", ".*")
                compiled.append((pat, re.compile(regex_pat, flags)))
            else:
                compiled.append((pat, re.compile(fnmatch.translate(pat), flags)))

        while stack and len(matches) < max_results:
            current = stack.pop()

            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        is_hidden_entry = entry.name.startswith(".")
                        should_skip_hidden = is_hidden_entry and not include_hidden
                        if should_skip_hidden:
                            continue

                        entry_path = Path(entry.path)

                        if entry.is_dir(follow_symlinks=False):
                            if not recursive:
                                continue
                            is_ignored_dir = ignore_manager.should_ignore_dir(entry_path)
                            if is_ignored_dir:
                                continue
                            stack.append(entry_path)
                            continue

                        if not entry.is_file(follow_symlinks=False):
                            continue

                        is_ignored_file = ignore_manager.should_ignore(entry_path)
                        if is_ignored_file:
                            continue

                        rel_path = os.path.relpath(entry.path, root)

                        for orig, comp in compiled:
                            if "**" in orig:
                                if orig.startswith("**/") and not recursive:
                                    suffix = orig[3:]
                                    if fnmatch.fnmatch(entry.name, suffix):
                                        matches.append(entry.path)
                                        break
                                elif comp.match(rel_path):
                                    matches.append(entry.path)
                                    break
                                elif orig.startswith("**/"):
                                    suffix = orig[3:]
                                    if fnmatch.fnmatch(entry.name, suffix):
                                        matches.append(entry.path)
                                        break
                            else:
                                if comp.match(entry.name):
                                    matches.append(entry.path)
                                    break

                        if len(matches) >= max_results:
                            break

            except (PermissionError, OSError):
                continue

        return matches[:max_results]

    return await asyncio.to_thread(search_sync)


async def _sort_matches(matches: list[str], sort_by: SortOrder) -> list[str]:
    """Sort matches based on the specified order."""
    if not matches:
        return matches

    def sort_sync():
        if sort_by == SortOrder.MODIFIED:
            return sorted(matches, key=lambda p: os.path.getmtime(p), reverse=True)
        elif sort_by == SortOrder.SIZE:
            return sorted(matches, key=lambda p: os.path.getsize(p), reverse=True)
        elif sort_by == SortOrder.DEPTH:
            return sorted(matches, key=lambda p: (p.count(os.sep), p))
        return sorted(matches)

    return await asyncio.to_thread(sort_sync)


def _format_output(pattern: str, matches: list[str], max_results: int, source: str) -> str:
    """Format glob results with source marker and header for rich panel parsing.

    Args:
        pattern: The glob pattern used.
        matches: List of matching file paths.
        max_results: Maximum results limit.
        source: "index" or "filesystem" to indicate cache hit/miss.

    Returns:
        Formatted output with source marker and file count header.
    """
    parts = [f"[source:{source}]"]
    file_count = len(matches)
    file_word = "file" if file_count == 1 else "files"
    parts.append(f"Found {file_count} {file_word} matching pattern: {pattern}")

    if matches:
        parts.append("")  # Blank line
        parts.extend(matches)

    if file_count == max_results:
        parts.append(f"(truncated at {max_results})")

    return "\n".join(parts)
