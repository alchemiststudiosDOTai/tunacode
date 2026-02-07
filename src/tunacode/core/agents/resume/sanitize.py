"""Message history sanitization for session resume.

TunaCode stores message history as tinyagent-style dict messages.
This module removes common abort/corruption artifacts so the next request can
resume cleanly.

Cleanup operations:
- Remove dangling tool calls (assistant tool_call content with no tool_result)
- Remove empty assistant messages
- Remove consecutive user/system messages (keep only the last in each run)
- Strip system messages (system prompt is injected separately)

Legacy pydantic-ai message formats are intentionally **not** supported.
"""

from __future__ import annotations

from typing import Any, cast

from tunacode.types import ToolCallId
from tunacode.utils.messaging import find_dangling_tool_calls, to_canonical

from tunacode.core.logging import get_logger
from tunacode.core.types import ToolCallRegistry

# -----------------------------------------------------------------------------
# tinyagent message constants
# -----------------------------------------------------------------------------

KEY_ROLE: str = "role"
KEY_CONTENT: str = "content"
KEY_TYPE: str = "type"

ROLE_USER: str = "user"
ROLE_SYSTEM: str = "system"
ROLE_ASSISTANT: str = "assistant"
ROLE_TOOL_RESULT: str = "tool_result"

REQUEST_ROLES: set[str] = {ROLE_USER, ROLE_SYSTEM}
RESPONSE_ROLES: set[str] = {ROLE_ASSISTANT, ROLE_TOOL_RESULT}

CONTENT_TYPE_TEXT: str = "text"
CONTENT_TYPE_THINKING: str = "thinking"
CONTENT_TYPE_TOOL_CALL: str = "tool_call"
CONTENT_TYPE_IMAGE: str = "image"

KEY_TOOL_CALL_ID: str = "tool_call_id"
KEY_ID: str = "id"

MAX_CLEANUP_ITERATIONS: int = 10
MIN_CONSECUTIVE_REQUEST_WINDOW: int = 2

__all__ = [
    "sanitize_history_for_resume",
    "run_cleanup_loop",
    "remove_dangling_tool_calls",
    "remove_empty_responses",
    "remove_consecutive_requests",
    "find_dangling_tool_call_ids",
]


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _coerce_message_dict(message: Any) -> dict[str, Any]:
    if not isinstance(message, dict):
        raise TypeError(
            "sanitize expects tinyagent dict messages only; got "
            f"{type(message).__name__}"
        )
    return cast(dict[str, Any], message)


def _get_role(message: dict[str, Any]) -> str:
    role = message.get(KEY_ROLE)
    return role if isinstance(role, str) else ""


def _get_content_items(message: dict[str, Any]) -> list[Any]:
    content = message.get(KEY_CONTENT)
    if content is None:
        return []
    if isinstance(content, list):
        return content
    raise TypeError(f"Message '{KEY_CONTENT}' must be a list, got {type(content).__name__}")


def _is_empty_assistant_message(message: dict[str, Any]) -> bool:
    role = _get_role(message)
    if role != ROLE_ASSISTANT:
        return False

    content_items = _get_content_items(message)
    for item in content_items:
        if item is None:
            continue
        if not isinstance(item, dict):
            raise TypeError(f"Assistant content item must be a dict, got {type(item).__name__}")

        item_type = item.get(KEY_TYPE)
        if item_type in {
            CONTENT_TYPE_TEXT,
            CONTENT_TYPE_THINKING,
            CONTENT_TYPE_TOOL_CALL,
            CONTENT_TYPE_IMAGE,
        }:
            return False

        raise ValueError(f"Unsupported assistant content type: {item_type!r}")

    return True


def _filter_assistant_tool_calls(
    message: dict[str, Any],
    dangling_tool_call_ids: set[ToolCallId],
    logger: Any,
) -> tuple[dict[str, Any], bool]:
    role = _get_role(message)
    if role != ROLE_ASSISTANT:
        return message, False

    content_items = _get_content_items(message)
    if not content_items:
        return message, False

    filtered: list[Any] = []
    removed_any = False

    for item in content_items:
        if item is None:
            filtered.append(item)
            continue

        if not isinstance(item, dict):
            raise TypeError(f"Assistant content item must be a dict, got {type(item).__name__}")

        item_type = item.get(KEY_TYPE)
        if item_type != CONTENT_TYPE_TOOL_CALL:
            filtered.append(item)
            continue

        tool_call_id = item.get(KEY_ID)
        if not isinstance(tool_call_id, str) or not tool_call_id:
            raise TypeError("tool_call content item missing non-empty 'id'")

        if tool_call_id not in dangling_tool_call_ids:
            filtered.append(item)
            continue

        removed_any = True
        tool_name = item.get("name")
        logger.debug(
            f"[PRUNED] tool_call content: tool={tool_name!r} id={tool_call_id}",
        )

    if not removed_any:
        return message, False

    return {**message, KEY_CONTENT: filtered}, True


# -----------------------------------------------------------------------------
# Dangling tool call cleanup
# -----------------------------------------------------------------------------


def find_dangling_tool_call_ids(messages: list[Any]) -> set[ToolCallId]:
    """Return tool_call_ids that never received a tool_result message."""

    dangling = find_dangling_tool_calls(messages)
    return {cast(ToolCallId, tool_call_id) for tool_call_id in dangling}


def remove_dangling_tool_calls(
    messages: list[Any],
    tool_registry: ToolCallRegistry,
    dangling_tool_call_ids: set[ToolCallId] | None = None,
) -> bool:
    """Remove dangling tool calls from assistant content, and prune the registry."""

    if not messages:
        return False

    dangling_tool_call_ids = (
        find_dangling_tool_call_ids(messages)
        if dangling_tool_call_ids is None
        else dangling_tool_call_ids
    )
    if not dangling_tool_call_ids:
        return False

    logger = get_logger()
    removed_any = False
    kept: list[Any] = []

    for raw_message in messages:
        message = _coerce_message_dict(raw_message)

        updated, removed_from_message = _filter_assistant_tool_calls(
            message,
            dangling_tool_call_ids,
            logger,
        )
        if removed_from_message:
            removed_any = True

        role = _get_role(updated)
        content_items = _get_content_items(updated)
        if role == ROLE_ASSISTANT and not content_items:
            # Only tool calls were present and they were pruned.
            continue

        kept.append(updated)

    if not removed_any:
        return False

    messages[:] = kept
    tool_registry.remove_many(dangling_tool_call_ids)

    return True


# -----------------------------------------------------------------------------
# Empty response cleanup
# -----------------------------------------------------------------------------


def remove_empty_responses(messages: list[Any]) -> bool:
    """Remove assistant messages with no content items."""

    if not messages:
        return False

    logger = get_logger()
    indices_to_remove: list[int] = []

    for idx, raw_message in enumerate(messages):
        message = _coerce_message_dict(raw_message)
        if not _is_empty_assistant_message(message):
            continue
        indices_to_remove.append(idx)

    if not indices_to_remove:
        return False

    for idx in reversed(indices_to_remove):
        logger.debug(f"Removing empty assistant message at index {idx}")
        del messages[idx]

    logger.lifecycle(f"Removed {len(indices_to_remove)} empty assistant messages")
    return True


# -----------------------------------------------------------------------------
# Consecutive request cleanup
# -----------------------------------------------------------------------------


def _is_request_message(message: Any) -> bool:
    canonical = to_canonical(message)
    return canonical.role.value in REQUEST_ROLES


def remove_consecutive_requests(messages: list[Any]) -> bool:
    """Remove consecutive user/system messages, keeping only the last in each run."""

    if len(messages) < MIN_CONSECUTIVE_REQUEST_WINDOW:
        return False

    indices_to_remove: list[int] = []

    last_index = len(messages) - 1
    current_index = 0

    while current_index < last_index:
        if not _is_request_message(messages[current_index]):
            current_index += 1
            continue

        run_start = current_index
        run_end = current_index

        while run_end < last_index and _is_request_message(messages[run_end + 1]):
            run_end += 1

        if run_end > run_start:
            indices_to_remove.extend(range(run_start, run_end))

        current_index = run_end + 1

    if not indices_to_remove:
        return False

    logger = get_logger()
    for idx in reversed(indices_to_remove):
        logger.debug(f"Removing consecutive request at index {idx}")
        del messages[idx]

    logger.lifecycle(f"Removed {len(indices_to_remove)} consecutive request messages")
    return True


# -----------------------------------------------------------------------------
# System message stripping
# -----------------------------------------------------------------------------


def sanitize_history_for_resume(messages: list[Any]) -> list[Any]:
    """Return a sanitized copy of message history suitable for tinyagent resume."""

    if not messages:
        return []

    sanitized: list[Any] = []
    for raw_message in messages:
        message = _coerce_message_dict(raw_message)
        role = _get_role(message)
        if role == ROLE_SYSTEM:
            continue
        sanitized.append(message)

    return sanitized


# -----------------------------------------------------------------------------
# Cleanup loop
# -----------------------------------------------------------------------------


def run_cleanup_loop(
    messages: list[Any],
    tool_registry: ToolCallRegistry,
) -> tuple[bool, set[ToolCallId]]:
    """Run iterative cleanup until message history stabilizes."""

    logger = get_logger()
    total_cleanup_applied = False
    dangling_tool_call_ids: set[ToolCallId] = set()

    for iteration in range(MAX_CLEANUP_ITERATIONS):
        any_cleanup = False

        dangling_tool_call_ids = find_dangling_tool_call_ids(messages)

        if remove_dangling_tool_calls(messages, tool_registry, dangling_tool_call_ids):
            any_cleanup = True
            total_cleanup_applied = True
            logger.lifecycle("Cleaned up dangling tool calls")

        if remove_empty_responses(messages):
            any_cleanup = True
            total_cleanup_applied = True

        if remove_consecutive_requests(messages):
            any_cleanup = True
            total_cleanup_applied = True

        if not any_cleanup:
            break

        is_last_iteration = iteration == MAX_CLEANUP_ITERATIONS - 1
        if is_last_iteration:
            logger.warning(
                f"Message cleanup did not stabilize after {MAX_CLEANUP_ITERATIONS} iterations"
            )

    return total_cleanup_applied, dangling_tool_call_ids
