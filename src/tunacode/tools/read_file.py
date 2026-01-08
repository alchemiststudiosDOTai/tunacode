"""File reading tool for agent operations."""

import asyncio
import os

from tunacode.constants import (
    ERROR_FILE_TOO_LARGE,
    MAX_FILE_SIZE,
    MSG_FILE_SIZE_LIMIT,
)
from tunacode.core.limits import get_max_line_length, get_read_limit
from tunacode.exceptions import ToolExecutionError
from tunacode.tools.decorators import file_tool


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

    effective_limit = limit if limit is not None else get_read_limit()
    max_line_len = get_max_line_length()

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
