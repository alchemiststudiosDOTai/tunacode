"""Tool execution helpers for the agent loop."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypedDict, cast

from .agent_types import (
    AgentMessage,
    AgentTool,
    AgentToolResult,
    AssistantMessage,
    EventStream,
    JsonObject,
    MessageEndEvent,
    MessageStartEvent,
    ToolCallContent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    ToolExecutionUpdateEvent,
    ToolResultMessage,
)


class ToolExecutionResult(TypedDict):
    tool_results: list[ToolResultMessage]
    steering_messages: list[AgentMessage] | None


def validate_tool_arguments(tool: AgentTool, tool_call: ToolCallContent) -> JsonObject:
    """Validate tool arguments against the tool's schema.

    Placeholder implementation: returns the arguments as-is.
    """

    return tool_call.get("arguments", {})


def _extract_tool_calls(assistant_message: AssistantMessage) -> list[ToolCallContent]:
    tool_calls: list[ToolCallContent] = []
    for content in assistant_message.get("content", []):
        if not content:
            continue
        if content.get("type") == "tool_call":
            tool_calls.append(cast(ToolCallContent, content))
    return tool_calls


def _find_tool(tools: list[AgentTool] | None, name: str) -> AgentTool | None:
    if not tools:
        return None
    for tool in tools:
        if tool.name == name:
            return tool
    return None


async def _execute_single_tool(
    tool: AgentTool | None,
    tool_call: ToolCallContent,
    signal: asyncio.Event | None,
    stream: EventStream,
) -> tuple[AgentToolResult, bool]:
    """Execute a single tool and return (result, is_error)."""

    tool_call_name = tool_call.get("name", "")
    tool_call_id = tool_call.get("id", "")
    tool_call_args = tool_call.get("arguments", {})

    if not tool:
        return (
            AgentToolResult(
                content=[{"type": "text", "text": f"Tool {tool_call_name} not found"}],
                details={},
            ),
            True,
        )
    if not tool.execute:
        error_text = f"Tool {tool_call_name} has no execute function"
        return (
            AgentToolResult(
                content=[{"type": "text", "text": error_text}],
                details={},
            ),
            True,
        )

    try:
        validated_args = validate_tool_arguments(tool, tool_call)

        def on_update(partial_result: AgentToolResult) -> None:
            stream.push(
                ToolExecutionUpdateEvent(
                    tool_call_id=tool_call_id,
                    tool_name=tool_call_name,
                    args=tool_call_args,
                    partial_result=partial_result,
                )
            )

        result = await tool.execute(tool_call_id, validated_args, signal, on_update)
        return (result, False)
    except Exception as exc:  # noqa: BLE001
        return (
            AgentToolResult(
                content=[{"type": "text", "text": str(exc)}],
                details={},
            ),
            True,
        )


def _create_tool_result_message(
    tool_call: ToolCallContent,
    result: AgentToolResult,
    is_error: bool,
) -> ToolResultMessage:
    return {
        "role": "tool_result",
        "tool_call_id": tool_call.get("id", ""),
        "tool_name": tool_call.get("name", ""),
        "content": result.content,
        "details": result.details,
        "is_error": is_error,
        "timestamp": int(asyncio.get_event_loop().time() * 1000),
    }


async def execute_tool_calls(
    tools: list[AgentTool] | None,
    assistant_message: AssistantMessage,
    signal: asyncio.Event | None,
    stream: EventStream,
    get_steering_messages: Callable[[], Awaitable[list[AgentMessage]]] | None = None,
) -> ToolExecutionResult:
    tool_calls = _extract_tool_calls(assistant_message)
    results: list[ToolResultMessage] = []
    steering_messages: list[AgentMessage] | None = None

    for index, tool_call in enumerate(tool_calls):
        tool_call_name = tool_call.get("name", "")
        tool_call_id = tool_call.get("id", "")
        tool_call_args = tool_call.get("arguments", {})
        tool = _find_tool(tools, tool_call_name)

        stream.push(
            ToolExecutionStartEvent(
                tool_call_id=tool_call_id,
                tool_name=tool_call_name,
                args=tool_call_args,
            )
        )

        result, is_error = await _execute_single_tool(tool, tool_call, signal, stream)

        stream.push(
            ToolExecutionEndEvent(
                tool_call_id=tool_call_id,
                tool_name=tool_call_name,
                result=result,
                is_error=is_error,
            )
        )

        tool_result_message = _create_tool_result_message(tool_call, result, is_error)
        results.append(tool_result_message)
        stream.push(MessageStartEvent(message=tool_result_message))
        stream.push(MessageEndEvent(message=tool_result_message))

        if get_steering_messages:
            steering = await get_steering_messages()
            if steering:
                steering_messages = steering
                for skipped in tool_calls[index + 1 :]:
                    results.append(skip_tool_call(skipped, stream))
                break

    return {"tool_results": results, "steering_messages": steering_messages}


def skip_tool_call(tool_call: ToolCallContent, stream: EventStream) -> ToolResultMessage:
    """Skip a tool call due to user interruption."""

    tool_call_name = tool_call.get("name", "")
    tool_call_id = tool_call.get("id", "")
    tool_call_args = tool_call.get("arguments", {})

    result = AgentToolResult(
        content=[{"type": "text", "text": "Skipped due to queued user message."}],
        details={},
    )

    stream.push(
        ToolExecutionStartEvent(
            tool_call_id=tool_call_id,
            tool_name=tool_call_name,
            args=tool_call_args,
        )
    )
    stream.push(
        ToolExecutionEndEvent(
            tool_call_id=tool_call_id,
            tool_name=tool_call_name,
            result=result,
            is_error=True,
        )
    )

    tool_result_message = _create_tool_result_message(tool_call, result, True)

    stream.push(MessageStartEvent(message=tool_result_message))
    stream.push(MessageEndEvent(message=tool_result_message))

    return tool_result_message
