"""File reading tool for agent operations."""

import asyncio
import os

from tunacode.constants import (
    DEFAULT_READ_LIMIT,
    ERROR_FILE_TOO_LARGE,
    LOCAL_DEFAULT_READ_LIMIT,
    LOCAL_MAX_LINE_LENGTH,
    MAX_FILE_SIZE,
    MAX_LINE_LENGTH,
    MSG_FILE_SIZE_LIMIT,
)
from tunacode.exceptions import ToolExecutionError
from tunacode.tools.decorators import file_tool
from tunacode.utils.config.user_configuration import load_config


def _get_limits() -> tuple[int, int]:
    """Get read limits based on local_mode setting."""
    config = load_config()
    if config and config.get("settings", {}).get("local_mode", False):
        return (LOCAL_DEFAULT_READ_LIMIT, LOCAL_MAX_LINE_LENGTH)
    return (DEFAULT_READ_LIMIT, MAX_LINE_LENGTH)


@file_tool
async def read_file(
    filepath: str,
    offset: int = 0,
    limit: int | None = None,
) -> str:
    """Read the contents of a file with line limiting and truncation.

    Args:
        filepath: The absolute path to the file to read.
        offset: The line number to start reading from (0-based). Defaults to 0.
        limit: The number of lines to read. Defaults to DEFAULT_READ_LIMIT (2000).

    Returns:
        The formatted file contents with line numbers.
    """
    if os.path.getsize(filepath) > MAX_FILE_SIZE:
        raise ToolExecutionError(
            tool_name="read_file",
            message=ERROR_FILE_TOO_LARGE.format(filepath=filepath) + MSG_FILE_SIZE_LIMIT,
        )

    default_limit, max_line_len = _get_limits()
    effective_limit = limit if limit is not None else default_limit

    def _read_sync(path: str, line_limit: int) -> str:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()

        total_lines = len(lines)
        raw = lines[offset : offset + effective_limit]

        content_lines = []
        for i, line in enumerate(raw):
            line = line.rstrip("\n")
            if len(line) > line_limit:
                line = line[:line_limit] + "..."
            line_num = str(i + offset + 1).zfill(5)
            content_lines.append(f"{line_num}| {line}")

        output = "<file>\n"
        output += "\n".join(content_lines)

        last_line = offset + len(content_lines)
        if total_lines > last_line:
            output += f"\n\n(File has more lines. Use 'offset' to read beyond line {last_line})"
        else:
            output += f"\n\n(End of file - total {total_lines} lines)"
        output += "\n</file>"

        return output

    return await asyncio.to_thread(_read_sync, filepath, max_line_len)
