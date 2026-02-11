"""Retention, serialization, and summarization logic for context compaction."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from tinyagent.agent_types import AgentMessage

from tunacode.utils.messaging import estimate_message_tokens, get_content

from tunacode.core.compaction.prompts import (
    FRESH_SUMMARY_PROMPT,
    ITERATIVE_SUMMARY_PROMPT,
    SUMMARY_OUTPUT_FORMAT,
)

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_TOOL_RESULT = "tool_result"

CONTENT_TYPE_TOOL_CALL = "tool_call"

TOOL_RESULT_TRUNCATION_LIMIT = 500
TOOL_RESULT_TRUNCATION_SUFFIX = "...[truncated]"

SERIALIZED_USER_PREFIX = "[User]:"
SERIALIZED_ASSISTANT_PREFIX = "[Assistant]:"
SERIALIZED_TOOL_CALL_PREFIX = "[Tool Call]:"
SERIALIZED_TOOL_RESULT_PREFIX = "[Tool Result]:"

SummaryGenerator = Callable[[str, asyncio.Event | None], Awaitable[str]]


class ContextSummarizer:
    """Compaction helper for retention boundaries and summary generation."""

    def __init__(self, summary_generator: SummaryGenerator) -> None:
        self._summary_generator = summary_generator

    def calculate_retention_boundary(
        self,
        messages: list[AgentMessage],
        keep_recent_tokens: int,
    ) -> int:
        """Return boundary index where older messages should be compacted.

        Boundary semantics:
            - messages[:boundary] are compacted/summarized
            - messages[boundary:] are retained verbatim
        """

        if keep_recent_tokens < 0:
            raise ValueError("keep_recent_tokens must be >= 0")

        if not messages:
            return 0

        threshold_index = self._find_threshold_index(messages, keep_recent_tokens)
        if threshold_index is None:
            return 0

        return self._snap_to_valid_boundary(messages, threshold_index)

    def serialize_messages(self, messages: list[AgentMessage]) -> str:
        """Serialize messages into compact text for LLM summarization."""

        lines: list[str] = []

        for index, raw_message in enumerate(messages):
            message = _coerce_message_dict(raw_message, index=index)
            role = _coerce_role(message, index=index)

            if role == ROLE_USER:
                user_lines = _serialize_user_message(message)
                lines.extend(user_lines)
                continue

            if role == ROLE_ASSISTANT:
                assistant_lines = _serialize_assistant_message(message)
                lines.extend(assistant_lines)
                continue

            if role == ROLE_TOOL_RESULT:
                tool_result_lines = _serialize_tool_result_message(message)
                lines.extend(tool_result_lines)
                continue

            raise ValueError(f"Unsupported message role for compaction serialization: {role!r}")

        return "\n".join(lines)

    async def summarize(
        self,
        messages: list[AgentMessage],
        *,
        previous_summary: str | None,
        signal: asyncio.Event | None,
    ) -> str:
        """Generate (or update) a structured compaction summary."""

        serialized_messages = self.serialize_messages(messages)
        if not serialized_messages.strip():
            raise ValueError("Cannot summarize an empty message transcript")

        prompt = self._build_summary_prompt(
            serialized_messages=serialized_messages,
            previous_summary=previous_summary,
        )

        summary = await self._summary_generator(prompt, signal)
        normalized_summary = summary.strip()
        if not normalized_summary:
            raise RuntimeError("Summary model returned an empty summary")

        return normalized_summary

    def _build_summary_prompt(
        self,
        *,
        serialized_messages: str,
        previous_summary: str | None,
    ) -> str:
        if previous_summary is None:
            return FRESH_SUMMARY_PROMPT.format(
                summary_output_format=SUMMARY_OUTPUT_FORMAT,
                serialized_messages=serialized_messages,
            )

        previous_summary_text = previous_summary.strip()
        if not previous_summary_text:
            return FRESH_SUMMARY_PROMPT.format(
                summary_output_format=SUMMARY_OUTPUT_FORMAT,
                serialized_messages=serialized_messages,
            )

        return ITERATIVE_SUMMARY_PROMPT.format(
            summary_output_format=SUMMARY_OUTPUT_FORMAT,
            previous_summary=previous_summary_text,
            serialized_messages=serialized_messages,
        )

    def _find_threshold_index(
        self,
        messages: list[AgentMessage],
        keep_recent_tokens: int,
    ) -> int | None:
        accumulated_tokens = 0
        for index in range(len(messages) - 1, -1, -1):
            accumulated_tokens += estimate_message_tokens(messages[index])
            if accumulated_tokens < keep_recent_tokens:
                continue
            return index
        return None

    def _snap_to_valid_boundary(self, messages: list[AgentMessage], threshold_index: int) -> int:
        for boundary in range(threshold_index, 0, -1):
            if self._is_valid_boundary(messages, boundary):
                return boundary
        return 0

    def _is_valid_boundary(self, messages: list[AgentMessage], boundary: int) -> bool:
        if boundary <= 0:
            return False

        if boundary > len(messages):
            return False

        previous = _coerce_message_dict(messages[boundary - 1], index=boundary - 1)
        if not _is_boundary_after_message(previous):
            return False

        if boundary == len(messages):
            return True

        next_message = _coerce_message_dict(messages[boundary], index=boundary)
        return not _is_tool_result_message(next_message)


def _coerce_message_dict(raw_message: AgentMessage, *, index: int) -> dict[str, Any]:
    if isinstance(raw_message, dict):
        return raw_message

    message_type = type(raw_message).__name__
    raise TypeError(f"Compaction expects dict messages; got {message_type} at index {index}")


def _coerce_role(message: dict[str, Any], *, index: int) -> str:
    role = message.get("role")
    if isinstance(role, str):
        return role
    raise TypeError(f"Message at index {index} is missing a valid 'role' string")


def _is_boundary_after_message(message: dict[str, Any]) -> bool:
    role = message.get("role")

    if role == ROLE_USER:
        return True

    if role != ROLE_ASSISTANT:
        return False

    return message.get("stop_reason") is not None


def _is_tool_result_message(message: dict[str, Any]) -> bool:
    return message.get("role") == ROLE_TOOL_RESULT


def _serialize_user_message(message: dict[str, Any]) -> list[str]:
    content = get_content(message).strip()
    if not content:
        return []
    return [f"{SERIALIZED_USER_PREFIX} {content}"]


def _serialize_assistant_message(message: dict[str, Any]) -> list[str]:
    lines: list[str] = []

    assistant_text = get_content(message).strip()
    if assistant_text:
        lines.append(f"{SERIALIZED_ASSISTANT_PREFIX} {assistant_text}")

    content_items = _coerce_content_items(message)
    for item in content_items:
        tool_call_line = _serialize_tool_call_item(item)
        if tool_call_line is None:
            continue
        lines.append(tool_call_line)

    return lines


def _serialize_tool_result_message(message: dict[str, Any]) -> list[str]:
    content = get_content(message).strip()
    truncated_content = _truncate_tool_result(content)
    if not truncated_content:
        return []
    return [f"{SERIALIZED_TOOL_RESULT_PREFIX} {truncated_content}"]


def _coerce_content_items(message: dict[str, Any]) -> list[Any]:
    content = message.get("content")
    if content is None:
        return []

    if isinstance(content, list):
        return content

    raise TypeError(f"Message 'content' must be a list, got {type(content).__name__}")


def _serialize_tool_call_item(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None

    item_type = item.get("type")
    if item_type != CONTENT_TYPE_TOOL_CALL:
        return None

    tool_name = item.get("name")
    if not isinstance(tool_name, str) or not tool_name:
        raise TypeError("tool_call item missing non-empty 'name'")

    arguments_raw = item.get("arguments", {})
    if not isinstance(arguments_raw, dict):
        raise TypeError("tool_call item 'arguments' must be a dict")

    serialized_args = json.dumps(arguments_raw, sort_keys=True)
    return f"{SERIALIZED_TOOL_CALL_PREFIX} {tool_name}({serialized_args})"


def _truncate_tool_result(content: str) -> str:
    if len(content) <= TOOL_RESULT_TRUNCATION_LIMIT:
        return content

    return content[:TOOL_RESULT_TRUNCATION_LIMIT] + TOOL_RESULT_TRUNCATION_SUFFIX
