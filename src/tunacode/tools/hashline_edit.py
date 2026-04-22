"""Native tinyagent hashline_edit tool."""

from __future__ import annotations

import asyncio
import difflib
from collections.abc import Callable
from pathlib import Path

from tinyagent.agent_types import (
    AgentTool,
    AgentToolResult,
    AgentToolUpdateCallback,
    JsonObject,
    TextContent,
)

from tunacode.exceptions import (
    ToolRetryError,
    UserAbortError,
)

from tunacode.tools.hashline import parse_line_ref
from tunacode.tools.line_cache import get as _cache_get
from tunacode.tools.line_cache import replace_range as _cache_replace_range
from tunacode.tools.line_cache import update_lines as _cache_update_lines
from tunacode.tools.utils.file_errors import translate_file_tool_errors

STALE_REF_MESSAGE = (
    "File has changed since last read — line {line} hash mismatch "
    "(expected '{expected}', cached '{actual}'). Re-read the file first."
)
UNCACHED_FILE_MESSAGE = "File '{filepath}' has no cached state. Read the file first with read_file."
LINE_NOT_CACHED_MESSAGE = (
    "Line {line} is not in the cached state for '{filepath}'. "
    "The file may have been read with an offset that skipped this line. "
    "Re-read the file to include this line."
)
FILE_NOT_FOUND_MESSAGE = "File '{filepath}' not found. Cannot edit."
DEFAULT_ENCODING = "utf-8"
INVALID_REF_MESSAGE = (
    "Invalid line reference '{ref}': {error}. Use '<line>:<hash>' from read_file output."
)

_HASHLINE_EDIT_DESCRIPTION = """Edit a file using hash-validated line references."""

_HASHLINE_EDIT_PARAMETERS: JsonObject = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "filepath": {"type": "string", "description": "Absolute path to the file to edit."},
        "operation": {
            "type": "string",
            "enum": ["replace", "replace_range", "insert_after"],
            "description": "Edit operation to apply.",
        },
        "line": {"type": "string", "description": "Line reference for replace."},
        "start": {"type": "string", "description": "Start line reference for replace_range."},
        "end": {"type": "string", "description": "End line reference for replace_range."},
        "after": {"type": "string", "description": "Line reference for insert_after."},
        "new": {"type": "string", "description": "Replacement or inserted text."},
    },
    "required": ["filepath", "operation"],
}


def _text_result(text: str) -> AgentToolResult:
    return AgentToolResult(content=[TextContent(text=text)], details={})


def _optional_string_arg(args: JsonObject, key: str) -> str | None:
    value = args.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ToolRetryError(
            f"Invalid arguments for tool 'hashline_edit': '{key}' must be a string."
        )
    return value


def _validate_ref(filepath: str, ref: str) -> int:
    try:
        line_number, expected_hash = parse_line_ref(ref)
    except ValueError as exc:
        raise ToolRetryError(INVALID_REF_MESSAGE.format(ref=ref, error=str(exc))) from exc

    cached = _cache_get(filepath)
    if cached is None:
        raise ToolRetryError(UNCACHED_FILE_MESSAGE.format(filepath=filepath))

    cached_line = cached.get(line_number)
    if cached_line is None:
        raise ToolRetryError(LINE_NOT_CACHED_MESSAGE.format(line=line_number, filepath=filepath))

    if cached_line.hash != expected_hash:
        raise ToolRetryError(
            STALE_REF_MESSAGE.format(
                line=line_number,
                expected=expected_hash,
                actual=cached_line.hash,
            )
        )

    return line_number


def _read_file_lines(filepath: str) -> tuple[list[str], bool]:
    with open(filepath, encoding=DEFAULT_ENCODING) as file_obj:
        content = file_obj.read()
    return content.splitlines(), content.endswith("\n")


def _write_file_lines(filepath: str, lines: list[str], preserve_trailing_newline: bool) -> None:
    serialized = "\n".join(lines)
    if preserve_trailing_newline:
        serialized += "\n"
    with open(filepath, "w", encoding=DEFAULT_ENCODING) as file_obj:
        file_obj.write(serialized)


def _make_diff(filepath: str, original_lines: list[str], new_lines: list[str]) -> str:
    diff = difflib.unified_diff(
        [line + "\n" for line in original_lines],
        [line + "\n" for line in new_lines],
        fromfile=f"a/{filepath}",
        tofile=f"b/{filepath}",
    )
    return "".join(diff)


def _apply_replace(
    filepath: str,
    lines: list[str],
    line_ref: str | None,
    new_content: str,
) -> tuple[list[str], str, Callable[[], None]]:
    if line_ref is None:
        raise ToolRetryError("The 'line' parameter is required for the 'replace' operation.")
    line_number = _validate_ref(filepath, line_ref)
    index = line_number - 1
    if index < 0 or index >= len(lines):
        raise ToolRetryError(f"Line {line_number} is out of range (file has {len(lines)} lines).")

    new_lines = list(lines)
    new_lines[index] = new_content

    def cache_mutation() -> None:
        _cache_update_lines(filepath, {line_number: new_content})

    return new_lines, f"File '{filepath}' updated: replaced line {line_number}.", cache_mutation


def _apply_replace_range(
    filepath: str,
    lines: list[str],
    start_ref: str | None,
    end_ref: str | None,
    new_content: str,
) -> tuple[list[str], str, Callable[[], None]]:
    if start_ref is None:
        raise ToolRetryError("The 'start' parameter is required for the 'replace_range' operation.")
    if end_ref is None:
        raise ToolRetryError("The 'end' parameter is required for the 'replace_range' operation.")
    start_line = _validate_ref(filepath, start_ref)
    end_line = _validate_ref(filepath, end_ref)

    if start_line > end_line:
        raise ToolRetryError(
            f"Start line ({start_line}) must not be greater than end line ({end_line})."
        )

    start_index = start_line - 1
    end_index = end_line
    if start_index < 0 or end_index > len(lines):
        raise ToolRetryError(
            f"Line range {start_line}-{end_line} is out of bounds (file has {len(lines)} lines)."
        )

    replacement_lines = new_content.splitlines() if new_content else []
    new_lines = lines[:start_index] + replacement_lines + lines[end_index:]

    def cache_mutation() -> None:
        _cache_replace_range(filepath, start_line, end_line, replacement_lines)

    return (
        new_lines,
        f"File '{filepath}' updated: replaced lines {start_line}-{end_line}.",
        cache_mutation,
    )


def _apply_insert_after(
    filepath: str,
    lines: list[str],
    after_ref: str | None,
    new_content: str,
) -> tuple[list[str], str, Callable[[], None]]:
    if after_ref is None:
        raise ToolRetryError("The 'after' parameter is required for the 'insert_after' operation.")
    after_line = _validate_ref(filepath, after_ref)
    insert_index = after_line
    if insert_index > len(lines):
        raise ToolRetryError(f"Line {after_line} is out of range (file has {len(lines)} lines).")

    insertion_lines = new_content.splitlines() if new_content else []
    new_lines = lines[:insert_index] + insertion_lines + lines[insert_index:]

    def cache_mutation() -> None:
        _cache_replace_range(filepath, after_line + 1, after_line, insertion_lines)

    return (
        new_lines,
        (
            f"File '{filepath}' updated: inserted {len(insertion_lines)} "
            f"line(s) after line {after_line}."
        ),
        cache_mutation,
    )


async def _run_hashline_edit(
    filepath: str,
    operation: str,
    line: str | None = None,
    start: str | None = None,
    end: str | None = None,
    after: str | None = None,
    new: str = "",
) -> str:
    path = Path(filepath)
    if not await asyncio.to_thread(path.exists):
        raise ToolRetryError(FILE_NOT_FOUND_MESSAGE.format(filepath=filepath))

    original_lines, had_trailing_newline = await asyncio.to_thread(_read_file_lines, filepath)
    if operation == "replace":
        new_lines, description, cache_mutation = _apply_replace(filepath, original_lines, line, new)
    elif operation == "replace_range":
        new_lines, description, cache_mutation = _apply_replace_range(
            filepath,
            original_lines,
            start,
            end,
            new,
        )
    elif operation == "insert_after":
        new_lines, description, cache_mutation = _apply_insert_after(
            filepath,
            original_lines,
            after,
            new,
        )
    else:
        raise ToolRetryError(
            f"Unknown operation '{operation}'. Use 'replace', 'replace_range', or 'insert_after'."
        )

    await asyncio.to_thread(_write_file_lines, filepath, new_lines, had_trailing_newline)
    cache_mutation()
    diff_text = _make_diff(filepath, original_lines, new_lines)
    output = f"{description}\n\n{diff_text}"
    return output


async def _execute_hashline_edit(  # noqa: C901
    tool_call_id: str,
    args: JsonObject,
    signal: asyncio.Event | None,
    on_update: AgentToolUpdateCallback,
) -> AgentToolResult:
    _ = (tool_call_id, on_update)
    if signal is not None and signal.is_set():
        raise UserAbortError("Tool execution aborted: hashline_edit")

    filepath = args.get("filepath")
    operation = args.get("operation")
    line = _optional_string_arg(args, "line")
    start = _optional_string_arg(args, "start")
    end = _optional_string_arg(args, "end")
    after = _optional_string_arg(args, "after")
    new = args.get("new", "")

    if not isinstance(filepath, str):
        raise ToolRetryError(
            "Invalid arguments for tool 'hashline_edit': 'filepath' must be a string."
        )
    if not isinstance(operation, str):
        raise ToolRetryError(
            "Invalid arguments for tool 'hashline_edit': 'operation' must be a string."
        )
    if not isinstance(new, str):
        raise ToolRetryError("Invalid arguments for tool 'hashline_edit': 'new' must be a string.")

    result = await translate_file_tool_errors(
        tool_name="hashline_edit",
        filepath=filepath,
        operation=_run_hashline_edit(
            filepath=filepath,
            operation=operation,
            line=line,
            start=start,
            end=end,
            after=after,
            new=new,
        ),
    )

    return _text_result(result)


hashline_edit = AgentTool(
    name="hashline_edit",
    label="hashline_edit",
    description=_HASHLINE_EDIT_DESCRIPTION,
    parameters=_HASHLINE_EDIT_PARAMETERS,
    execute=_execute_hashline_edit,
)
