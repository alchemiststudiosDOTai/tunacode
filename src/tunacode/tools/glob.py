"""
Glob tool for fast file pattern matching.

This tool provides filesystem pattern matching capabilities using glob patterns,
complementing the grep tool's content search with fast filename-based searching.
"""

import asyncio
import fnmatch
import os
import re
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from tunacode.core.code_index import CodeIndex
from tunacode.exceptions import ToolExecutionError
from tunacode.tools.base import BaseTool
from tunacode.tools.xml_helper import load_parameters_schema_from_xml, load_prompt_from_xml

# Configuration
MAX_RESULTS = 5000  # Maximum files to return
EXCLUDE_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "target",
    ".next",
    ".nuxt",
    "coverage",
    ".coverage",
}


class SortOrder(Enum):
    """Sorting options for glob results."""

    MODIFIED = "modified"  # Sort by modification time (newest first)
    SIZE = "size"  # Sort by file size (largest first)
    ALPHABETICAL = "alphabetical"  # Sort alphabetically
    DEPTH = "depth"  # Sort by path depth (shallow first)


class GlobTool(BaseTool):
    """Fast file pattern matching tool using glob patterns."""

    def __init__(self):
        """Initialize the glob tool."""
        super().__init__()
        self._code_index: Optional[CodeIndex] = None
        self._gitignore_patterns: Optional[Set[str]] = None

    @property
    def tool_name(self) -> str:
        return "glob"

    @lru_cache(maxsize=1)
    def _get_base_prompt(self) -> str:
        """Load and return the base prompt from XML file.

        Returns:
            str: The loaded prompt from XML or a default prompt
        """
        # Try to load from XML helper
        prompt = load_prompt_from_xml("glob")
        if prompt:
            return prompt

        # Fallback to default prompt
        return """Fast file pattern matching tool

- Supports glob patterns like "**/*.js" or "src/**/*.ts"
- Returns matching file paths sorted by modification time
- Use this tool when you need to find files by name patterns"""

    @lru_cache(maxsize=1)
    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get the parameters schema for the glob tool."""
        # Try to load from XML helper
        schema = load_parameters_schema_from_xml("glob")
        if schema:
            return schema

        # Fallback to hardcoded schema
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match (e.g., '*.py', '**/*.{js,ts}')",
                },
                "directory": {
                    "type": "string",
                    "description": "Directory to search in",
                    "default": ".",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to search recursively",
                    "default": True,
                },
                "include_hidden": {
                    "type": "boolean",
                    "description": "Whether to include hidden files/directories",
                    "default": False,
                },
                "exclude_dirs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional directories to exclude from search",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 5000,
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["modified", "size", "alphabetical", "depth"],
                    "description": "How to sort results",
                    "default": "modified",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Whether pattern matching is case-sensitive",
                    "default": False,
                },
                "use_gitignore": {
                    "type": "boolean",
                    "description": "Whether to respect .gitignore patterns",
                    "default": True,
                },
            },
            "required": ["pattern"],
        }

    def _get_code_index(self, directory: str) -> Optional[CodeIndex]:
        """Get the CodeIndex instance if available and appropriate."""
        # Only use CodeIndex if we're searching from the project root
        if directory != "." and directory != os.getcwd():
            return None

        if self._code_index is None:
            try:
                self._code_index = CodeIndex.get_instance()
                # Ensure index is built
                self._code_index.build_index()
            except Exception:
                # CodeIndex not available, fall back to filesystem traversal
                self._code_index = None
        return self._code_index

    async def _execute(
        self,
        pattern: str,
        directory: str = ".",
        recursive: bool = True,
        include_hidden: bool = False,
        exclude_dirs: Optional[List[str]] = None,
        max_results: int = MAX_RESULTS,
        sort_by: Union[str, SortOrder] = SortOrder.MODIFIED,
        case_sensitive: bool = False,
        use_gitignore: bool = True,
    ) -> str:
        """
        Find files matching glob patterns.

        Args:
            pattern: Glob pattern to match (e.g., "*.py", "**/*.{js,ts}", "src/**/test_*.py")
            directory: Directory to search in (default: current directory)
            recursive: Whether to search recursively (default: True)
            include_hidden: Whether to include hidden files/directories (default: False)
            exclude_dirs: Additional directories to exclude from search
            max_results: Maximum number of results to return (default: 5000)
            sort_by: How to sort results (modified/size/alphabetical/depth)
            case_sensitive: Whether pattern matching is case-sensitive (default: False)
            use_gitignore: Whether to respect .gitignore patterns (default: True)

        Returns:
            List of matching file paths as a formatted string

        Examples:
            glob("*.py")                    # All Python files in current directory
            glob("**/*.py", recursive=True) # All Python files recursively
            glob("*.{js,ts,jsx,tsx}")       # Multiple extensions
            glob("src/**/test_*.py")        # Test files in src directory
            glob("docs/**/*.md")            # All markdown files in docs
        """
        try:
            # Parse the directory path
            root_path = Path(directory).resolve()
            if not root_path.exists():
                return f"Error: Directory '{directory}' does not exist"
            if not root_path.is_dir():
                return f"Error: '{directory}' is not a directory"

            # Combine default and custom exclude directories
            all_exclude_dirs = EXCLUDE_DIRS.copy()
            if exclude_dirs:
                all_exclude_dirs.update(exclude_dirs)

            # Convert sort_by to enum if string
            if isinstance(sort_by, str):
                try:
                    sort_by = SortOrder(sort_by)
                except ValueError:
                    sort_by = SortOrder.MODIFIED

            # Handle multiple extensions pattern like "*.{py,js,ts}"
            patterns = self._expand_brace_pattern(pattern)

            # Load gitignore patterns if requested
            if use_gitignore:
                await self._load_gitignore_patterns(root_path)

            # Try to use CodeIndex for faster lookup if available
            code_index = self._get_code_index(directory)
            if code_index and not include_hidden and recursive:
                # Use CodeIndex for common cases
                matches = await self._glob_search_with_index(
                    code_index, patterns, root_path, all_exclude_dirs, max_results, case_sensitive
                )
            else:
                # Fall back to filesystem traversal
                matches = await self._glob_search(
                    root_path,
                    patterns,
                    recursive,
                    include_hidden,
                    all_exclude_dirs,
                    max_results,
                    case_sensitive,
                )

            # Format results
            if not matches:
                return f"No files found matching pattern: {pattern}"

            # Sort matches based on sort_by parameter
            matches = await self._sort_matches(matches, sort_by)

            # Create formatted output
            output = []
            output.append(f"Found {len(matches)} files matching pattern: {pattern}")
            if len(matches) == max_results:
                output.append(f"(Results limited to {max_results} files)")
            output.append("=" * 60)

            # Group files by directory for better readability
            current_dir = None
            for match in matches:
                match_dir = os.path.dirname(match)
                if match_dir != current_dir:
                    if current_dir is not None:
                        output.append("")  # Empty line between directories
                    output.append(f"📁 {match_dir}/")
                    current_dir = match_dir

                filename = os.path.basename(match)
                output.append(f"  - {filename}")

            return "\n".join(output)

        except Exception as e:
            raise ToolExecutionError(f"Glob search failed: {str(e)}")

    def _expand_brace_pattern(self, pattern: str) -> List[str]:
        """
        Expand brace patterns like "*.{py,js,ts}" into multiple patterns.
        Also supports extended patterns like "?(pattern)" for optional matching.

        Args:
            pattern: Pattern that may contain braces

        Returns:
            List of expanded patterns
        """
        if "{" not in pattern or "}" not in pattern:
            return [pattern]

        # Handle nested braces recursively
        expanded = []
        stack = [pattern]

        while stack:
            current = stack.pop()

            # Find the innermost brace expression
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
                        # Found a complete brace expression
                        prefix = current[:start]
                        suffix = current[i + 1 :]
                        options = current[start + 1 : i].split(",")

                        # Generate all combinations
                        for option in options:
                            new_pattern = prefix + option.strip() + suffix
                            if "{" in new_pattern:
                                stack.append(new_pattern)
                            else:
                                expanded.append(new_pattern)
                        break
            else:
                # No more braces to expand
                expanded.append(current)

        return expanded

    async def _load_gitignore_patterns(self, root: Path) -> None:
        """Load .gitignore patterns from the repository."""
        if self._gitignore_patterns is not None:
            return

        self._gitignore_patterns = set()

        # Look for .gitignore, .ignore, and .rgignore files
        ignore_files = [".gitignore", ".ignore", ".rgignore"]

        for ignore_file in ignore_files:
            ignore_path = root / ignore_file
            if ignore_path.exists():
                try:
                    with open(ignore_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#"):
                                self._gitignore_patterns.add(line)
                except Exception:
                    pass

    async def _glob_search_with_index(
        self,
        code_index: CodeIndex,
        patterns: List[str],
        root: Path,
        exclude_dirs: set,
        max_results: int,
        case_sensitive: bool,
    ) -> List[str]:
        """Use CodeIndex for faster file matching."""
        # Get all files from index
        all_files = code_index.get_all_files()

        matches = []
        for file_path in all_files:
            # Convert to absolute path
            abs_path = code_index.root_dir / file_path

            # Check against patterns
            for pattern in patterns:
                if self._match_pattern(str(file_path), pattern, case_sensitive):
                    # Check if in excluded directories
                    skip = False
                    for exclude_dir in exclude_dirs:
                        if exclude_dir in file_path.parts:
                            skip = True
                            break

                    if not skip:
                        matches.append(str(abs_path))
                        if len(matches) >= max_results:
                            return matches
                    break

        return matches

    def _match_pattern(self, path: str, pattern: str, case_sensitive: bool) -> bool:
        """Match a path against a glob pattern."""
        # Handle ** for recursive matching
        if "**" in pattern:
            # Special case: **/*.ext should match both root files and nested files
            if pattern.startswith("**/"):
                # Match the pattern after **/ directly and also with any prefix
                suffix_pattern = pattern[3:]  # Remove **/
                if case_sensitive:
                    # Check if path matches the suffix directly (root files)
                    if fnmatch.fnmatch(path, suffix_pattern):
                        return True
                else:
                    if fnmatch.fnmatch(path.lower(), suffix_pattern.lower()):
                        return True

            # Full recursive pattern matching
            regex_pat = pattern.replace("**", "__STARSTAR__")
            regex_pat = fnmatch.translate(regex_pat)
            regex_pat = regex_pat.replace("__STARSTAR__", ".*")
            flags = 0 if case_sensitive else re.IGNORECASE
            return bool(re.match(regex_pat, path, flags))
        else:
            # Simple pattern matching
            if case_sensitive:
                return fnmatch.fnmatch(path, pattern)
            else:
                return fnmatch.fnmatch(path.lower(), pattern.lower())

    async def _glob_search(
        self,
        root: Path,
        patterns: List[str],
        recursive: bool,
        include_hidden: bool,
        exclude_dirs: set,
        max_results: int,
        case_sensitive: bool = False,
    ) -> List[str]:
        """
        Perform the actual glob search using os.scandir for speed.

        Args:
            root: Root directory to search
            patterns: List of glob patterns to match
            recursive: Whether to search recursively
            include_hidden: Whether to include hidden files
            exclude_dirs: Set of directory names to exclude
            max_results: Maximum results to return

        Returns:
            List of matching file paths
        """

        def search_sync():
            matches = []
            stack = [root]

            # Compile patterns to regex for faster matching
            compiled_patterns = []
            flags = 0 if case_sensitive else re.IGNORECASE

            for pat in patterns:
                # Handle ** for recursive matching
                if "**" in pat:
                    # Convert ** to match any path depth
                    regex_pat = pat.replace("**", "__STARSTAR__")
                    regex_pat = fnmatch.translate(regex_pat)
                    regex_pat = regex_pat.replace("__STARSTAR__", ".*")
                    compiled_patterns.append((pat, re.compile(regex_pat, flags)))
                else:
                    compiled_patterns.append((pat, re.compile(fnmatch.translate(pat), flags)))

            while stack and len(matches) < max_results:
                current_dir = stack.pop()

                try:
                    with os.scandir(current_dir) as entries:
                        for entry in entries:
                            # Skip hidden files/dirs if not included
                            if not include_hidden and entry.name.startswith("."):
                                continue

                            if entry.is_dir(follow_symlinks=False):
                                # Check if directory should be excluded
                                if entry.name not in exclude_dirs and recursive:
                                    stack.append(Path(entry.path))
                            elif entry.is_file(follow_symlinks=False):
                                # Check against patterns
                                rel_path = os.path.relpath(entry.path, root)

                                for original_pat, compiled_pat in compiled_patterns:
                                    # For ** patterns, match against full relative path
                                    if "**" in original_pat:
                                        # Special handling for **/*.ext patterns
                                        if original_pat.startswith("**/") and not recursive:
                                            # In non-recursive mode, match only filename
                                            suffix_pat = original_pat[3:]
                                            if fnmatch.fnmatch(entry.name, suffix_pat):
                                                matches.append(entry.path)
                                                break
                                        elif compiled_pat.match(rel_path):
                                            matches.append(entry.path)
                                            break
                                        # Also check if filename matches the pattern after **/
                                        elif original_pat.startswith("**/"):
                                            suffix_pat = original_pat[3:]
                                            if fnmatch.fnmatch(entry.name, suffix_pat):
                                                matches.append(entry.path)
                                                break
                                    else:
                                        # For simple patterns, match against filename only
                                        if compiled_pat.match(entry.name):
                                            matches.append(entry.path)
                                            break

                                if len(matches) >= max_results:
                                    break

                except (PermissionError, OSError):
                    # Skip directories we can't read
                    continue

            return matches[:max_results]

        # Run the synchronous search in the thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, search_sync)

    async def _sort_matches(self, matches: List[str], sort_by: SortOrder) -> List[str]:
        """Sort matches based on the specified order."""
        if not matches:
            return matches

        def sort_sync():
            if sort_by == SortOrder.MODIFIED:
                # Sort by modification time (newest first)
                return sorted(matches, key=lambda p: os.path.getmtime(p), reverse=True)
            elif sort_by == SortOrder.SIZE:
                # Sort by file size (largest first)
                return sorted(matches, key=lambda p: os.path.getsize(p), reverse=True)
            elif sort_by == SortOrder.DEPTH:
                # Sort by path depth (shallow first), then alphabetically
                return sorted(matches, key=lambda p: (p.count(os.sep), p))
            else:  # SortOrder.ALPHABETICAL
                # Sort alphabetically
                return sorted(matches)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sort_sync)


# Create the tool function for pydantic-ai
async def glob(
    pattern: str,
    directory: str = ".",
    recursive: bool = True,
    include_hidden: bool = False,
    exclude_dirs: Optional[List[str]] = None,
    max_results: int = MAX_RESULTS,
    sort_by: str = "modified",
    case_sensitive: bool = False,
    use_gitignore: bool = True,
) -> str:
    """
    Find files matching glob patterns with fast filesystem traversal.

    Args:
        pattern: Glob pattern to match (e.g., "*.py", "**/*.{js,ts}", "src/**/test_*.py")
        directory: Directory to search in (default: current directory)
        recursive: Whether to search recursively (default: True)
        include_hidden: Whether to include hidden files/directories (default: False)
        exclude_dirs: Additional directories to exclude from search
                         (default: common build/cache dirs)
        max_results: Maximum number of results to return (default: 5000)
        sort_by: How to sort results - "modified", "size", "alphabetical", or "depth"
                 (default: "modified")
        case_sensitive: Whether pattern matching is case-sensitive (default: False)
        use_gitignore: Whether to respect .gitignore patterns (default: True)

    Returns:
        Formatted list of matching file paths grouped by directory

    Examples:
        glob("*.py")                         # All Python files in current directory
        glob("**/*.py")                      # All Python files recursively
        glob("*.{js,ts,jsx,tsx}")            # Multiple extensions
        glob("src/**/test_*.py")             # Test files in src directory
        glob("**/*.md", include_hidden=True) # Include hidden directories
        glob("*.py", sort_by="size")        # Sort by file size
    """
    tool = GlobTool()
    return await tool._execute(
        pattern=pattern,
        directory=directory,
        recursive=recursive,
        include_hidden=include_hidden,
        exclude_dirs=exclude_dirs,
        max_results=max_results,
        sort_by=sort_by,
        case_sensitive=case_sensitive,
        use_gitignore=use_gitignore,
    )
