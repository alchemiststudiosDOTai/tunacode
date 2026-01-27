"""File reading tool for agent operations."""

import asyncio
import os

from tunacode.configuration.limits import get_max_line_length, get_read_limit
from tunacode.constants import (
    ERROR_FILE_TOO_LARGE,
    MAX_FILE_SIZE,
    MSG_FILE_SIZE_LIMIT,
)
from tunacode.exceptions import ToolExecutionError

from tunacode.tools.decorators import file_tool

DEFAULT_FILE_ENCODING = "utf-8"
LINE_NUMBER_PAD_WIDTH = 5
LINE_NUMBER_START = 1
LINE_NUMBER_SEPARATOR = "| "
TRUNCATION_SUFFIX = "..."
FILE_TAG_OPEN = "<file>"
FILE_TAG_CLOSE = "</file>"
MORE_LINES_MESSAGE = "(File has more lines. Use 'offset' to read beyond line {last_line})"
END_OF_FILE_MESSAGE = "(End of file - total {total_lines} lines)"


def _format_content_line(line: str, line_number: int, line_limit: int) -> str:
    line_text = line.rstrip("\n")
    needs_truncation = len(line_text) > line_limit
    truncated_line = line_text[:line_limit] + TRUNCATION_SUFFIX if needs_truncation else line_text
    padded_number = str(line_number).zfill(LINE_NUMBER_PAD_WIDTH)
    return f"{padded_number}{LINE_NUMBER_SEPARATOR}{truncated_line}"


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

    def _read_sync(path: str, line_limit: int, line_offset: int, line_count: int) -> str:
        content_lines: list[str] = []
        skipped_lines = 0

        with open(path, encoding=DEFAULT_FILE_ENCODING) as f:
            for _ in range(line_offset):
                line = f.readline()
                if not line:
                    break
                skipped_lines += 1

            for line_index in range(line_count):
                line = f.readline()
                if not line:
                    break
                line_number = skipped_lines + line_index + LINE_NUMBER_START
                formatted_line = _format_content_line(line, line_number, line_limit)
                content_lines.append(formatted_line)

            extra_line = f.readline()
            has_more_lines = bool(extra_line)

        last_line = skipped_lines + len(content_lines)

        output = f"{FILE_TAG_OPEN}\n"
        output += "\n".join(content_lines)

        if has_more_lines:
            output += f"\n\n{MORE_LINES_MESSAGE.format(last_line=last_line)}"
            output += f"\n{FILE_TAG_CLOSE}"
            return output

        total_lines = last_line
        output += f"\n\n{END_OF_FILE_MESSAGE.format(total_lines=total_lines)}"
        output += f"\n{FILE_TAG_CLOSE}"
        return output

    return await asyncio.to_thread(_read_sync, filepath, max_line_len, offset, effective_limit)
