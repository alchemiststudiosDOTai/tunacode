import asyncio
import importlib
import json
import logging
import os
import re
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

from tunacode.constants import (
    JSON_PARSE_BASE_DELAY,
    JSON_PARSE_MAX_DELAY,
    JSON_PARSE_MAX_RETRIES,
    READ_ONLY_TOOLS,
)
from tunacode.exceptions import ToolBatchingJSONError
from tunacode.types import (
    ErrorMessage,
    StateManager,
    ToolCallback,
    ToolCallId,
    ToolName,
)
from tunacode.ui import console as ui
from tunacode.utils.retry import retry_json_parse_async

logger = logging.getLogger(__name__)


# Lazy import for Agent and Tool
def get_agent_tool():
    pydantic_ai = importlib.import_module("pydantic_ai")
    return pydantic_ai.Agent, pydantic_ai.Tool


def get_model_messages():
    """
    Safely retrieve message-related classes from pydantic_ai.

    If the running environment (e.g. our test stubs) does not define
    SystemPromptPart we create a minimal placeholder so that the rest of the
    code can continue to work without depending on the real implementation.
    """
    messages = importlib.import_module("pydantic_ai.messages")

    # Create minimal fallbacks for missing message part classes
    # SystemPromptPart
    if not hasattr(messages, "SystemPromptPart"):

        class SystemPromptPart:  # type: ignore
            def __init__(self, content: str = "", role: str = "system", part_kind: str = ""):
                self.content = content
                self.role = role
                self.part_kind = part_kind

            def __repr__(self) -> str:  # pragma: no cover
                return f"SystemPromptPart(content={self.content!r})"

        SystemPromptPart.__module__ = messages.__name__
        setattr(messages, "SystemPromptPart", SystemPromptPart)

    # UserPromptPart
    if not hasattr(messages, "UserPromptPart"):

        class UserPromptPart:  # type: ignore
            def __init__(self, content: str = "", role: str = "user", part_kind: str = ""):
                self.content = content
                self.role = role
                self.part_kind = part_kind

            def __repr__(self) -> str:  # pragma: no cover
                return f"UserPromptPart(content={self.content!r})"

        UserPromptPart.__module__ = messages.__name__
        setattr(messages, "UserPromptPart", UserPromptPart)

    # Finally, return the relevant classes so callers can use them directly
    return messages.ModelRequest, messages.ToolReturnPart, messages.SystemPromptPart


async def execute_tools_parallel(
    tool_calls: list[tuple[Any, Any]], callback: ToolCallback, return_exceptions: bool = True
) -> list[Any]:
    """Execute multiple tool calls in parallel using asyncio.

    Args:
        tool_calls: List of (part, node) tuples
        callback: The tool callback function to execute
        return_exceptions: Whether to return exceptions or raise them

    Returns:
        List of results in the same order as input, with exceptions for failed calls
    """
    # Get max parallel from environment or default to CPU count
    max_parallel = int(os.environ.get("TUNACODE_MAX_PARALLEL", os.cpu_count() or 4))

    async def execute_with_error_handling(part, node):
        try:
            return await callback(part, node)
        except Exception as e:
            return e

    # If we have more tools than max_parallel, execute in batches
    if len(tool_calls) > max_parallel:
        results = []
        for i in range(0, len(tool_calls), max_parallel):
            batch = tool_calls[i : i + max_parallel]
            batch_tasks = [execute_with_error_handling(part, node) for part, node in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=return_exceptions)
            results.extend(batch_results)
        return results
    tasks = [execute_with_error_handling(part, node) for part, node in tool_calls]
    return await asyncio.gather(*tasks, return_exceptions=return_exceptions)


def batch_read_only_tools(tool_calls: list[Any]) -> Iterator[list[Any]]:
    """Batch tool calls so read-only tools can be executed in parallel.

    Yields batches where:
    - Read-only tools are grouped together
    - Write/execute tools are in their own batch (single item)
    - Order within each batch is preserved

    Args:
        tool_calls: List of tool call objects with 'tool' attribute

    Yields:
        Batches of tool calls
    """
    if not tool_calls:
        return

    current_batch = []

    for tool_call in tool_calls:
        tool_name = tool_call.tool_name if hasattr(tool_call, "tool_name") else None

        if tool_name in READ_ONLY_TOOLS:
            # Add to current batch
            current_batch.append(tool_call)
        else:
            # Yield any pending read-only batch
            if current_batch:
                yield current_batch
                current_batch = []

            # Yield write/execute tool as single-item batch
            yield [tool_call]

    # Yield any remaining read-only tools
    if current_batch:
        yield current_batch


async def create_buffering_callback(
    original_callback: ToolCallback, buffer: Any, state_manager: StateManager
) -> ToolCallback:
    """Create a callback wrapper that buffers read-only tools for parallel execution.

    Args:
        original_callback: The original tool callback
        buffer: ToolBuffer instance to store read-only tools
        state_manager: StateManager for UI access

    Returns:
        A wrapped callback function
    """

    async def buffering_callback(part, node):
        tool_name = getattr(part, "tool_name", None)

        if tool_name in READ_ONLY_TOOLS:
            # Buffer read-only tools
            buffer.add(part, node)
            # Don't execute yet - will be executed in parallel batch
            return None

        # Non-read-only tool encountered - flush buffer first
        if buffer.has_tasks():
            buffered_tasks = buffer.flush()

            # Execute buffered read-only tools in parallel
            if state_manager.session.show_thoughts:
                await ui.muted(f"Executing {len(buffered_tasks)} read-only tools in parallel")

            await execute_tools_parallel(buffered_tasks, original_callback)

        # Execute the non-read-only tool
        return await original_callback(part, node)

    return buffering_callback


async def parse_json_tool_calls(
    text: str, tool_callback: ToolCallback | None, state_manager: StateManager
):
    """Parse JSON tool calls from text when structured tool calling fails.
    Fallback for when API providers don't support proper tool calling.
    """
    if not tool_callback:
        return

    # Pattern for JSON tool calls: {"tool": "tool_name", "args": {...}}
    # Find potential JSON objects and parse them
    potential_jsons = []
    brace_count = 0
    start_pos = -1

    for i, char in enumerate(text):
        if char == "{":
            if brace_count == 0:
                start_pos = i
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0 and start_pos != -1:
                potential_json = text[start_pos : i + 1]
                try:
                    # Use retry logic for JSON parsing
                    parsed = await retry_json_parse_async(
                        potential_json,
                        max_retries=JSON_PARSE_MAX_RETRIES,
                        base_delay=JSON_PARSE_BASE_DELAY,
                        max_delay=JSON_PARSE_MAX_DELAY,
                    )
                    if isinstance(parsed, dict) and "tool" in parsed and "args" in parsed:
                        potential_jsons.append((parsed["tool"], parsed["args"]))
                except json.JSONDecodeError as e:
                    # After all retries failed
                    logger.error(f"JSON parsing failed after {JSON_PARSE_MAX_RETRIES} retries: {e}")
                    if state_manager.session.show_thoughts:
                        await ui.error(
                            f"Failed to parse tool JSON after {JSON_PARSE_MAX_RETRIES} retries"
                        )
                    # Raise custom exception for better error handling
                    raise ToolBatchingJSONError(
                        json_content=potential_json,
                        retry_count=JSON_PARSE_MAX_RETRIES,
                        original_error=e,
                    ) from e
                start_pos = -1

    matches = potential_jsons

    for tool_name, args in matches:
        try:
            # Create a mock tool call object
            class MockToolCall:
                def __init__(self, tool_name: str, args: dict):
                    self.tool_name = tool_name
                    self.args = args
                    self.tool_call_id = f"fallback_{datetime.now().timestamp()}"

            class MockNode:
                pass

            # Execute the tool through the callback
            mock_call = MockToolCall(tool_name, args)
            mock_node = MockNode()

            await tool_callback(mock_call, mock_node)

            if state_manager.session.show_thoughts:
                await ui.muted(f"FALLBACK: Executed {tool_name} via JSON parsing")

        except Exception as e:
            if state_manager.session.show_thoughts:
                await ui.error(f"Error executing fallback tool {tool_name}: {e!s}")


async def extract_and_execute_tool_calls(
    text: str, tool_callback: ToolCallback | None, state_manager: StateManager
):
    """Extract tool calls from text content and execute them.
    Supports multiple formats for maximum compatibility.
    """
    if not tool_callback:
        return

    # Format 2: Tool calls in code blocks
    code_block_pattern = r'```json\s*(\{(?:[^{}]|"[^"]*"|(?:\{[^}]*\}))*"tool"(?:[^{}]|"[^"]*"|(?:\{[^}]*\}))*\})\s*```'
    code_matches = re.findall(code_block_pattern, text, re.MULTILINE | re.DOTALL)
    remaining_text = re.sub(code_block_pattern, "", text)

    for match in code_matches:
        try:
            # Use retry logic for JSON parsing in code blocks
            tool_data = await retry_json_parse_async(
                match,
                max_retries=JSON_PARSE_MAX_RETRIES,
                base_delay=JSON_PARSE_BASE_DELAY,
                max_delay=JSON_PARSE_MAX_DELAY,
            )
            if "tool" in tool_data and "args" in tool_data:

                class MockToolCall:
                    def __init__(self, tool_name: str, args: dict):
                        self.tool_name = tool_name
                        self.args = args
                        self.tool_call_id = f"codeblock_{datetime.now().timestamp()}"

                class MockNode:
                    pass

                mock_call = MockToolCall(tool_data["tool"], tool_data["args"])
                mock_node = MockNode()

                await tool_callback(mock_call, mock_node)

                if state_manager.session.show_thoughts:
                    await ui.muted(f"FALLBACK: Executed {tool_data['tool']} from code block")

        except json.JSONDecodeError as e:
            # After all retries failed
            logger.error(
                f"Code block JSON parsing failed after {JSON_PARSE_MAX_RETRIES} retries: {e}"
            )
            if state_manager.session.show_thoughts:
                await ui.error(
                    f"Failed to parse code block tool JSON after {JSON_PARSE_MAX_RETRIES} retries"
                )
            # Raise custom exception for better error handling
            raise ToolBatchingJSONError(
                json_content=match,
                retry_count=JSON_PARSE_MAX_RETRIES,
                original_error=e,
            ) from e
        except (KeyError, Exception) as e:
            if state_manager.session.show_thoughts:
                await ui.error(f"Error parsing code block tool call: {e!s}")

    # Format 1: {"tool": "name", "args": {...}}
    await parse_json_tool_calls(remaining_text, tool_callback, state_manager)


def patch_tool_messages(
    error_message: ErrorMessage = "Tool operation failed",
    state_manager: StateManager = None,
):
    """Find any tool calls without responses and add synthetic error responses for them.
    Takes an error message to use in the synthesized tool response.

    Ignores tools that have corresponding retry prompts as the model is already
    addressing them.
    """
    if state_manager is None:
        raise ValueError("state_manager is required for patch_tool_messages")

    messages = state_manager.session.messages

    if not messages:
        return

    # Map tool calls to their tool returns
    tool_calls: dict[ToolCallId, ToolName] = {}  # tool_call_id -> tool_name
    tool_returns: set[ToolCallId] = set()  # set of tool_call_ids with returns
    retry_prompts: set[ToolCallId] = set()  # set of tool_call_ids with retry prompts

    for message in messages:
        if hasattr(message, "parts"):
            for part in message.parts:
                if (
                    hasattr(part, "part_kind")
                    and hasattr(part, "tool_call_id")
                    and part.tool_call_id
                ):
                    if part.part_kind == "tool-call":
                        tool_calls[part.tool_call_id] = part.tool_name
                    elif part.part_kind == "tool-return":
                        tool_returns.add(part.tool_call_id)
                    elif part.part_kind == "retry-prompt":
                        retry_prompts.add(part.tool_call_id)

    # Identify orphaned tools (those without responses and not being retried)
    for tool_call_id, tool_name in list(tool_calls.items()):
        if tool_call_id not in tool_returns and tool_call_id not in retry_prompts:
            # Import ModelRequest and ToolReturnPart lazily
            model_request_cls, tool_return_part_cls, _ = get_model_messages()
            messages.append(
                model_request_cls(
                    parts=[
                        tool_return_part_cls(
                            tool_name=tool_name,
                            content=error_message,
                            tool_call_id=tool_call_id,
                            timestamp=datetime.now(timezone.utc),
                            part_kind="tool-return",
                        )
                    ],
                    kind="request",
                )
            )
