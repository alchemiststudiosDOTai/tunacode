"""Message history sanitization for session resume."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, cast

from tinyagent.agent_types import JsonObject

from tunacode.types import ToolCallId
from tunacode.utils.messaging import adapter

from tunacode.core.logging import get_logger

ROLE_USER = "user"
ROLE_SYSTEM = "system"
ROLE_ASSISTANT = "assistant"
ROLE_TOOL_RESULT = "tool_result"

REQUEST_ROLES: set[str] = {ROLE_USER, ROLE_SYSTEM}
MAX_CLEANUP_ITERATIONS = 10
MIN_CONSECUTIVE_REQUEST_WINDOW = 2

CONTENT_TEXT = "text"
CONTENT_THINKING = "thinking"
CONTENT_TOOL_CALL = "tool_call"
CONTENT_IMAGE = "image"


@dataclass(frozen=True, slots=True)
class TextContentItem:
    text: str


@dataclass(frozen=True, slots=True)
class ThinkingContentItem:
    thinking: str


@dataclass(frozen=True, slots=True)
class ImageContentItem:
    url: str | None = None


@dataclass(frozen=True, slots=True)
class ToolCallContentItem:
    tool_call_id: ToolCallId
    tool_name: str
    arguments: dict[str, object]
    partial_json: str


RequestContentItem = TextContentItem | ImageContentItem
AssistantContentItem = (
    TextContentItem | ThinkingContentItem | ImageContentItem | ToolCallContentItem
)
ToolResultContentItem = TextContentItem | ThinkingContentItem | ImageContentItem


@dataclass(frozen=True, slots=True)
class UserResumeMessage:
    content: list[RequestContentItem] | None = None
    role: Literal["user"] = "user"


@dataclass(frozen=True, slots=True)
class SystemResumeMessage:
    content: list[RequestContentItem] | None = None
    role: Literal["system"] = "system"


@dataclass(frozen=True, slots=True)
class AssistantResumeMessage:
    content: list[AssistantContentItem] | None = None
    role: Literal["assistant"] = "assistant"


@dataclass(frozen=True, slots=True)
class ToolResultResumeMessage:
    tool_call_id: ToolCallId
    content: list[ToolResultContentItem]
    details: dict[str, object]
    is_error: bool
    role: Literal["tool_result"] = "tool_result"


ResumeMessage = (
    UserResumeMessage | SystemResumeMessage | AssistantResumeMessage | ToolResultResumeMessage
)


def _coerce_dict(value: object, *, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{context} must be a dict, got {type(value).__name__}")
    if not all(isinstance(key, str) for key in value):
        raise TypeError(f"{context} keys must be strings")
    return value


def _coerce_content_items(message: dict[str, object]) -> list[object]:
    raw_content = message.get("content", [])
    if raw_content is None:
        return []
    if not isinstance(raw_content, list):
        raise TypeError(f"message 'content' must be a list, got {type(raw_content).__name__}")
    return list(raw_content)


def _coerce_string(value: object) -> str:
    return value if isinstance(value, str) else str(value)


def _coerce_str_dict(value: object, *, field_name: str) -> dict[str, object]:
    return _coerce_dict(value, context=field_name)


def _parse_request_item(raw_item: object) -> RequestContentItem:
    item = _coerce_dict(raw_item, context="request content item")
    item_type = item.get("type")
    if item_type == CONTENT_TEXT:
        return TextContentItem(text=_coerce_string(item.get("text")))
    if item_type == CONTENT_IMAGE:
        url = item.get("url")
        return ImageContentItem(url=url if isinstance(url, str) and url else None)
    raise ValueError(f"Unsupported request content type: {item_type!r}")


def _parse_assistant_item(raw_item: object) -> AssistantContentItem:
    item = _coerce_dict(raw_item, context="assistant content item")
    item_type = item.get("type")
    if item_type == CONTENT_TEXT:
        return TextContentItem(text=_coerce_string(item.get("text")))
    if item_type == CONTENT_THINKING:
        return ThinkingContentItem(thinking=_coerce_string(item.get("thinking")))
    if item_type == CONTENT_IMAGE:
        url = item.get("url")
        return ImageContentItem(url=url if isinstance(url, str) and url else None)
    if item_type == CONTENT_TOOL_CALL:
        tool_call_id = item.get("id")
        if not isinstance(tool_call_id, str) or not tool_call_id:
            raise TypeError("tool_call content item missing non-empty 'id'")
        tool_name = item.get("name")
        if not isinstance(tool_name, str) or not tool_name:
            raise TypeError("tool_call content item missing non-empty 'name'")
        partial_json = item.get("partial_json", "")
        if not isinstance(partial_json, str):
            raise TypeError("tool_call 'partial_json' must be a string")
        return ToolCallContentItem(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            arguments=_coerce_str_dict(item.get("arguments", {}), field_name="arguments"),
            partial_json=partial_json,
        )
    raise ValueError(f"Unsupported assistant content type: {item_type!r}")


def _parse_tool_result_item(raw_item: object) -> ToolResultContentItem:
    item = _coerce_dict(raw_item, context="tool_result content item")
    item_type = item.get("type")
    if item_type == CONTENT_TEXT:
        return TextContentItem(text=_coerce_string(item.get("text")))
    if item_type == CONTENT_THINKING:
        return ThinkingContentItem(thinking=_coerce_string(item.get("thinking")))
    if item_type == CONTENT_IMAGE:
        url = item.get("url")
        return ImageContentItem(url=url if isinstance(url, str) and url else None)
    raise ValueError(f"Unsupported tool_result content type: {item_type!r}")


def _parse_request_content(raw_content: list[object]) -> list[RequestContentItem]:
    return [_parse_request_item(item) for item in raw_content if item is not None]


def _parse_assistant_content(raw_content: list[object]) -> list[AssistantContentItem]:
    return [_parse_assistant_item(item) for item in raw_content if item is not None]


def _parse_tool_result_content(raw_content: list[object]) -> list[ToolResultContentItem]:
    return [_parse_tool_result_item(item) for item in raw_content if item is not None]


def _parse_message(raw_message: object) -> ResumeMessage:
    adapter.to_canonical(cast(JsonObject, raw_message))
    message = _coerce_dict(raw_message, context="resume message")
    role = message.get("role")
    raw_content = _coerce_content_items(message)

    if role == ROLE_USER:
        return UserResumeMessage(content=_parse_request_content(raw_content))
    if role == ROLE_SYSTEM:
        return SystemResumeMessage(content=_parse_request_content(raw_content))
    if role == ROLE_ASSISTANT:
        return AssistantResumeMessage(content=_parse_assistant_content(raw_content))
    if role == ROLE_TOOL_RESULT:
        tool_call_id = message.get("tool_call_id")
        if not isinstance(tool_call_id, str) or not tool_call_id:
            raise TypeError("tool_result message missing non-empty 'tool_call_id'")
        details = _coerce_str_dict(message.get("details", {}), field_name="details")
        is_error = message.get("is_error", False)
        if not isinstance(is_error, bool):
            raise TypeError(f"is_error must be a bool, got {type(is_error).__name__}")
        return ToolResultResumeMessage(
            tool_call_id=tool_call_id,
            content=_parse_tool_result_content(raw_content),
            details=details,
            is_error=is_error,
        )
    raise ValueError(f"Unsupported resume message role: {role!r}")


def _parse_messages(messages: list[object]) -> list[ResumeMessage]:
    return [_parse_message(message) for message in messages]


def _serialize_request_item(item: RequestContentItem) -> dict[str, object]:
    if isinstance(item, TextContentItem):
        return {"type": CONTENT_TEXT, "text": item.text, "text_signature": None}
    image_item: dict[str, object] = {"type": CONTENT_IMAGE}
    if item.url:
        image_item["url"] = item.url
    return image_item


def _serialize_assistant_item(item: AssistantContentItem) -> dict[str, object]:
    if isinstance(item, TextContentItem):
        return {"type": CONTENT_TEXT, "text": item.text, "text_signature": None}
    if isinstance(item, ThinkingContentItem):
        return {
            "type": CONTENT_THINKING,
            "thinking": item.thinking,
            "thinking_signature": None,
        }
    if isinstance(item, ImageContentItem):
        image_item: dict[str, object] = {"type": CONTENT_IMAGE}
        if item.url:
            image_item["url"] = item.url
        return image_item
    return {
        "type": CONTENT_TOOL_CALL,
        "id": item.tool_call_id,
        "name": item.tool_name,
        "arguments": item.arguments,
        "partial_json": item.partial_json,
    }


def _serialize_tool_result_item(item: ToolResultContentItem) -> dict[str, object]:
    if isinstance(item, TextContentItem):
        return {"type": CONTENT_TEXT, "text": item.text, "text_signature": None}
    if isinstance(item, ThinkingContentItem):
        return {
            "type": CONTENT_THINKING,
            "thinking": item.thinking,
            "thinking_signature": None,
        }
    image_item: dict[str, object] = {"type": CONTENT_IMAGE}
    if item.url:
        image_item["url"] = item.url
    return image_item


def _serialize_message(message: ResumeMessage) -> dict[str, object]:
    if isinstance(message, UserResumeMessage):
        return {
            "role": ROLE_USER,
            "content": [_serialize_request_item(item) for item in message.content or []],
        }
    if isinstance(message, SystemResumeMessage):
        return {
            "role": ROLE_SYSTEM,
            "content": [_serialize_request_item(item) for item in message.content or []],
        }
    if isinstance(message, AssistantResumeMessage):
        return {
            "role": ROLE_ASSISTANT,
            "content": [_serialize_assistant_item(item) for item in message.content or []],
        }
    return {
        "role": ROLE_TOOL_RESULT,
        "tool_call_id": message.tool_call_id,
        "content": [_serialize_tool_result_item(item) for item in message.content],
        "details": message.details,
        "is_error": message.is_error,
    }


def _serialize_messages(messages: Sequence[ResumeMessage]) -> list[dict[str, object]]:
    return [_serialize_message(message) for message in messages]


def _assistant_tool_call_ids(message: AssistantResumeMessage) -> set[ToolCallId]:
    return {
        item.tool_call_id for item in message.content or [] if isinstance(item, ToolCallContentItem)
    }


def _find_dangling_ids(messages: list[ResumeMessage]) -> set[ToolCallId]:
    tool_call_ids: set[ToolCallId] = set()
    tool_return_ids: set[ToolCallId] = set()
    for message in messages:
        if isinstance(message, AssistantResumeMessage):
            tool_call_ids.update(_assistant_tool_call_ids(message))
        elif isinstance(message, ToolResultResumeMessage):
            tool_return_ids.add(message.tool_call_id)
    return tool_call_ids - tool_return_ids


def _remove_dangling_tool_calls(
    messages: list[ResumeMessage],
    dangling_tool_call_ids: set[ToolCallId],
) -> tuple[bool, list[ResumeMessage]]:
    logger = get_logger()
    removed_any = False
    kept_messages: list[ResumeMessage] = []

    for message in messages:
        if not isinstance(message, AssistantResumeMessage):
            kept_messages.append(message)
            continue

        kept_content: list[AssistantContentItem] = []
        for item in message.content or []:
            if (
                not isinstance(item, ToolCallContentItem)
                or item.tool_call_id not in dangling_tool_call_ids
            ):
                kept_content.append(item)
                continue
            removed_any = True
            logger.debug(
                f"[PRUNED] tool_call content: tool={item.tool_name!r} id={item.tool_call_id}"
            )

        if kept_content:
            kept_messages.append(AssistantResumeMessage(content=kept_content))

    return removed_any, kept_messages


def _remove_empty_responses(messages: list[ResumeMessage]) -> bool:
    indices_to_remove = [
        index
        for index, message in enumerate(messages)
        if isinstance(message, AssistantResumeMessage) and not message.content
    ]
    if not indices_to_remove:
        return False

    logger = get_logger()
    for index in reversed(indices_to_remove):
        logger.debug(f"Removing empty assistant message at index {index}")
        del messages[index]
    logger.lifecycle(f"Removed {len(indices_to_remove)} empty assistant messages")
    return True


def _remove_consecutive_requests(messages: list[ResumeMessage]) -> bool:
    if len(messages) < MIN_CONSECUTIVE_REQUEST_WINDOW:
        return False

    indices_to_remove: list[int] = []
    current_index = 0
    last_index = len(messages) - 1

    while current_index < last_index:
        if messages[current_index].role not in REQUEST_ROLES:
            current_index += 1
            continue

        run_start = current_index
        run_end = current_index
        while run_end < last_index and messages[run_end + 1].role in REQUEST_ROLES:
            run_end += 1
        if run_end > run_start:
            indices_to_remove.extend(range(run_start, run_end))
        current_index = run_end + 1

    if not indices_to_remove:
        return False

    logger = get_logger()
    for index in reversed(indices_to_remove):
        logger.debug(f"Removing consecutive request at index {index}")
        del messages[index]
    logger.lifecycle(f"Removed {len(indices_to_remove)} consecutive request messages")
    return True


def find_dangling_tool_call_ids(messages: list[object]) -> set[ToolCallId]:
    """Return tool_call_ids that never received a tool_result message."""
    return _find_dangling_ids(_parse_messages(messages))


def remove_dangling_tool_calls(
    messages: list[object],
    dangling_tool_call_ids: set[ToolCallId] | None = None,
) -> bool:
    """Remove dangling tool calls from assistant content."""
    typed_messages = _parse_messages(messages)
    resolved_dangling_ids = dangling_tool_call_ids or _find_dangling_ids(typed_messages)
    if not resolved_dangling_ids:
        return False

    removed_any, kept_messages = _remove_dangling_tool_calls(typed_messages, resolved_dangling_ids)
    if not removed_any:
        return False

    messages[:] = _serialize_messages(kept_messages)
    return True


def remove_empty_responses(messages: list[object]) -> bool:
    """Remove assistant messages with no content items."""
    typed_messages = _parse_messages(messages)
    changed = _remove_empty_responses(typed_messages)
    if changed:
        messages[:] = _serialize_messages(typed_messages)
    return changed


def remove_consecutive_requests(messages: list[object]) -> bool:
    """Remove consecutive user/system messages, keeping only the last in each run."""
    typed_messages = _parse_messages(messages)
    changed = _remove_consecutive_requests(typed_messages)
    if changed:
        messages[:] = _serialize_messages(typed_messages)
    return changed


def sanitize_history_for_resume(messages: list[object]) -> list[dict[str, object]]:
    """Return a sanitized copy of message history suitable for tinyagent resume."""
    sanitized_messages = [
        message
        for message in _parse_messages(messages)
        if not isinstance(message, SystemResumeMessage)
    ]
    return _serialize_messages(sanitized_messages)


def run_cleanup_loop(
    messages: list[object],
) -> tuple[bool, set[ToolCallId]]:
    """Run iterative cleanup until message history stabilizes."""
    logger = get_logger()
    typed_messages = _parse_messages(messages)
    total_cleanup_applied = False
    dangling_tool_call_ids: set[ToolCallId] = set()

    for iteration in range(MAX_CLEANUP_ITERATIONS):
        any_cleanup = False
        dangling_tool_call_ids = _find_dangling_ids(typed_messages)

        removed_dangling, typed_messages = _remove_dangling_tool_calls(
            typed_messages,
            dangling_tool_call_ids,
        )
        if removed_dangling:
            any_cleanup = True
            total_cleanup_applied = True
            logger.lifecycle("Cleaned up dangling tool calls")

        if _remove_empty_responses(typed_messages):
            any_cleanup = True
            total_cleanup_applied = True

        if _remove_consecutive_requests(typed_messages):
            any_cleanup = True
            total_cleanup_applied = True

        if not any_cleanup:
            break

        if iteration == MAX_CLEANUP_ITERATIONS - 1:
            logger.warning(
                f"Message cleanup did not stabilize after {MAX_CLEANUP_ITERATIONS} iterations"
            )

    messages[:] = _serialize_messages(typed_messages)
    return total_cleanup_applied, dangling_tool_call_ids
