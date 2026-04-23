"""Native tinyagent write_file tool."""

from __future__ import annotations

import asyncio
import os

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

from tunacode.tools.utils.file_errors import translate_file_tool_errors

_WRITE_FILE_DESCRIPTION = """Write content to a new file. Fails if the file already exists."""

_WRITE_FILE_PARAMETERS: JsonObject = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "filepath": {"type": "string", "description": "Absolute path to the new file."},
        "content": {"type": "string", "description": "Content to write to the file."},
    },
    "required": ["filepath", "content"],
}


def _text_result(text: str) -> AgentToolResult:
    return AgentToolResult(content=[TextContent(text=text)], details={})


async def _run_write_file(filepath: str, content: str) -> str:
    if os.path.exists(filepath):
        raise ToolRetryError(
            f"File '{filepath}' already exists. "
            "Read the file first with `read_file`, then use `hashline_edit` to modify it."
        )

    dirpath = os.path.dirname(filepath)
    if dirpath and not os.path.exists(dirpath):
        os.makedirs(dirpath, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as file_obj:
        file_obj.write(content)

    result = f"Successfully wrote to new file: {filepath}"
    return result


async def _execute_write_file(
    tool_call_id: str,
    args: JsonObject,
    signal: asyncio.Event | None,
    on_update: AgentToolUpdateCallback,
) -> AgentToolResult:
    _ = (tool_call_id, on_update)
    if signal is not None and signal.is_set():
        raise UserAbortError("Tool execution aborted: write_file")

    filepath = args.get("filepath")
    content = args.get("content")
    if not isinstance(filepath, str):
        raise ToolRetryError(
            "Invalid arguments for tool 'write_file': 'filepath' must be a string."
        )
    if not isinstance(content, str):
        raise ToolRetryError("Invalid arguments for tool 'write_file': 'content' must be a string.")

    result = await translate_file_tool_errors(
        tool_name="write_file",
        filepath=filepath,
        operation=_run_write_file(filepath=filepath, content=content),
    )

    return _text_result(result)


write_file = AgentTool(
    name="write_file",
    label="write_file",
    description=_WRITE_FILE_DESCRIPTION,
    parameters=_WRITE_FILE_PARAMETERS,
    execute=_execute_write_file,
)
