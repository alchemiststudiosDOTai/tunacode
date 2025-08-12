"""
Module: tunacode.tools.list_dir

Directory listing tool for agent operations in the TunaCode application.
Provides efficient directory listing without using shell commands.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import List, Tuple

from tunacode.exceptions import ToolExecutionError
from tunacode.tools.base import FileBasedTool
from tunacode.types import FilePath, ToolResult

logger = logging.getLogger(__name__)


class ListDirTool(FileBasedTool):
    """Tool for listing directory contents without shell commands."""

    @property
    def tool_name(self) -> str:
        return "ListDir"

    async def _execute(
        self, directory: FilePath = ".", max_entries: int = 200, show_hidden: bool = False
    ) -> ToolResult:
        """List the contents of a directory.

        Args:
            directory: The path to the directory to list (defaults to current directory)
            max_entries: Maximum number of entries to return (default: 200)
            show_hidden: Whether to include hidden files/directories (default: False)

        Returns:
            ToolResult: Formatted list of files and directories

        Raises:
            Exception: Directory access errors
        """
        # Convert to Path object for easier handling
        dir_path = Path(directory).resolve()

        # Verify it's a directory
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")

        if not dir_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {dir_path}")

        # Try to use cached data from CodeIndex first
        try:
            from tunacode.core.code_index import CodeIndex

            index = CodeIndex.get_instance()
            cached_entries = index.get_directory_contents(dir_path)

            if cached_entries:
                # Filter cached entries based on show_hidden
                if not show_hidden:
                    cached_entries = [name for name in cached_entries if not name.startswith(".")]

                # Limit entries and format output
                limited_entries = cached_entries[:max_entries]

                # Return simple format for cached results (names only for speed)
                if limited_entries:
                    return f"Files in {dir_path}:\n" + "\n".join(
                        f"  {name}" for name in limited_entries
                    )
                else:
                    return f"Directory {dir_path} is empty"

        except Exception as e:
            # If CodeIndex fails, fall back to regular scanning
            logger.debug(f"CodeIndex cache miss for {dir_path}: {e}")

        # Fallback: Collect entries in a background thread to prevent blocking the event loop
        def _scan_directory(path: Path) -> List[Tuple[str, bool, str]]:
            """Synchronous helper that scans a directory and returns entry metadata."""
            collected: List[Tuple[str, bool, str]] = []
            try:
                with os.scandir(path) as scanner:
                    for entry in scanner:
                        # Skip hidden files if requested
                        if not show_hidden and entry.name.startswith("."):
                            continue

                        try:
                            is_directory = entry.is_dir(follow_symlinks=False)
                            is_symlink = entry.is_symlink()

                            # Determine type indicator
                            if is_symlink:
                                type_indicator = "@"  # Symlink
                            elif is_directory:
                                type_indicator = "/"  # Directory
                            elif entry.is_file():
                                # Check if executable
                                if os.access(entry.path, os.X_OK):
                                    type_indicator = "*"  # Executable
                                else:
                                    type_indicator = ""  # Regular file
                            else:
                                type_indicator = "?"  # Unknown type

                            collected.append((entry.name, is_directory, type_indicator))

                        except (OSError, PermissionError):
                            # If we can't stat the entry, include it with unknown type
                            collected.append((entry.name, False, "?"))
            except PermissionError:
                # Re-raise for the outer async context to handle uniformly
                raise

            return collected

        try:
            entries: List[Tuple[str, bool, str]] = await asyncio.to_thread(
                _scan_directory, dir_path
            )
        except PermissionError as e:
            raise PermissionError(f"Permission denied accessing directory: {dir_path}") from e

        # Sort entries: directories first, then files, both alphabetically
        entries.sort(key=lambda x: (not x[1], x[0].lower()))

        # Update CodeIndex cache with the fresh data
        try:
            from tunacode.core.code_index import CodeIndex

            index = CodeIndex.get_instance()
            # Extract just the names for cache storage
            entry_names = [name for name, _, _ in entries]
            index.update_directory_cache(dir_path, entry_names)
        except Exception as e:
            logger.debug(f"Failed to update CodeIndex cache for {dir_path}: {e}")

        # Apply limit after sorting to ensure consistent results
        total_entries = len(entries)
        if len(entries) > max_entries:
            entries = entries[:max_entries]

        # Format output
        if not entries:
            return f"Directory '{dir_path}' is empty"

        # Build formatted output
        lines = [f"Contents of '{dir_path}':"]
        lines.append("")

        # Determine column width for better formatting
        max_name_length = max(len(name) for name, _, _ in entries)
        col_width = min(max_name_length + 2, 50)  # Cap at 50 chars

        for name, is_dir, type_indicator in entries:
            # Truncate long names
            display_name = name
            if len(name) > 47:
                display_name = name[:44] + "..."

            # Add type indicator
            display_name += type_indicator

            # Add entry type description
            if is_dir:
                entry_type = "[DIR]"
            else:
                entry_type = "[FILE]"

            lines.append(f"  {display_name:<{col_width}} {entry_type}")

        # Add summary
        displayed_count = len(entries)
        dir_count = sum(1 for _, is_dir, _ in entries if is_dir)
        file_count = displayed_count - dir_count

        lines.append("")
        lines.append(
            f"Total: {displayed_count} entries ({dir_count} directories, {file_count} files)"
        )

        if total_entries > max_entries:
            lines.append(f"Note: Output limited to {max_entries} entries")

        return "\n".join(lines)

    def _format_args(self, directory: FilePath = ".", *args, **kwargs) -> str:
        """Format arguments for display."""
        all_args = [repr(str(directory))]

        # Add other keyword arguments if present
        for key, value in kwargs.items():
            if key not in ["max_entries", "show_hidden"]:
                continue
            all_args.append(f"{key}={repr(value)}")

        return ", ".join(all_args)

    def _get_error_context(self, directory: FilePath = None, *args, **kwargs) -> str:
        """Get error context including directory path."""
        if directory:
            return f"listing directory '{directory}'"
        return super()._get_error_context(*args, **kwargs)


# Create the function that maintains compatibility with pydantic-ai
async def list_dir(directory: str = ".", max_entries: int = 200, show_hidden: bool = False) -> str:
    """
    List the contents of a directory without using shell commands.

    Uses os.scandir for efficient directory listing with proper error handling.
    Results are sorted with directories first, then files, both alphabetically.

    Args:
        directory: The path to the directory to list (defaults to current directory)
        max_entries: Maximum number of entries to return (default: 200)
        show_hidden: Whether to include hidden files/directories (default: False)

    Returns:
        str: Formatted list of directory contents or error message
    """
    tool = ListDirTool(None)  # No UI for pydantic-ai compatibility
    try:
        return await tool.execute(directory, max_entries=max_entries, show_hidden=show_hidden)
    except ToolExecutionError as e:
        # Return error message for pydantic-ai compatibility
        return str(e)
