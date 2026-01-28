"""Message history sanitization for session resume.

Functions to clean up corrupt or inconsistent message history that can
occur from abort scenarios, preventing API errors on subsequent requests.

Key cleanup operations:
- Remove dangling tool calls (no matching tool return)
- Remove empty responses (abort during response generation)
- Remove consecutive requests (abort before model responds)
- Strip system prompts (pydantic-ai injects these automatically)
"""

from __future__ import annotations

from dataclasses import is_dataclass, replace
from typing import Any

from tunacode.types import ToolCallId
from tunacode.types.canonical import CanonicalMessage, MessageRole, SystemPromptPart
from tunacode.utils.messaging import (
    _get_attr,
    _get_parts,
    find_dangling_tool_calls,
    to_canonical_list,
)

from tunacode.core.logging import get_logger
from tunacode.core.types import ToolCallRegistry

PART_KIND_ATTR: str = "part_kind"
TOOL_CALL_ID_ATTR: str = "tool_call_id"
PARTS_ATTR: str = "parts"
TOOL_CALLS_ATTR: str = "tool_calls"
RUN_ID_ATTR: str = "run_id"

PART_KIND_SYSTEM_PROMPT: str = "system-prompt"

MAX_CLEANUP_ITERATIONS: int = 10
MIN_CONSECUTIVE_REQUEST_WINDOW: int = 2

REQUEST_ROLES: set[MessageRole] = {MessageRole.USER, MessageRole.SYSTEM}
RESPONSE_ROLES: set[MessageRole] = {MessageRole.ASSISTANT, MessageRole.TOOL}

__all__ = [
    "sanitize_history_for_resume",
    "run_cleanup_loop",
    "remove_dangling_tool_calls",
    "remove_empty_responses",
    "remove_consecutive_requests",
    "find_dangling_tool_call_ids",
    "PART_KIND_ATTR",
    "TOOL_CALL_ID_ATTR",
]


# -----------------------------------------------------------------------------
# Canonical helpers
# -----------------------------------------------------------------------------


def _canonicalize_messages(messages: list[Any]) -> list[CanonicalMessage]:
    """Convert message list to canonical messages."""
    return to_canonical_list(messages)


def _is_request_message(message: CanonicalMessage) -> bool:
    """Check if a canonical message is a request."""
    role = message.role
    return role in REQUEST_ROLES


def _is_response_message(message: CanonicalMessage) -> bool:
    """Check if a canonical message is a response."""
    role = message.role
    return role in RESPONSE_ROLES


# -----------------------------------------------------------------------------
# Message mutation helpers
# -----------------------------------------------------------------------------


def _normalize_list(value: Any) -> list[Any]:
    """Normalize optional list-like values to a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _get_message_tool_calls(message: Any) -> list[Any]:
    """Return tool_calls from a message as a list."""
    tool_calls_value = _get_attr(message, TOOL_CALLS_ATTR)
    return _normalize_list(tool_calls_value)


def _can_update_tool_calls(message: Any) -> bool:
    """Return True if tool_calls can be updated on the message."""
    if isinstance(message, dict):
        return True

    message_dict = getattr(message, "__dict__", {})
    return TOOL_CALLS_ATTR in message_dict


def _replace_message_fields(message: Any, updates: dict[str, Any]) -> Any:
    """Return a new message with updated fields."""
    if not updates:
        return message

    if isinstance(message, dict):
        new_message = message.copy()
        new_message.update(updates)
        return new_message

    if is_dataclass(message) and not isinstance(message, type):
        return replace(message, **updates)

    model_copy = getattr(message, "model_copy", None)
    if callable(model_copy):
        return model_copy(update=updates)

    copy_fn = getattr(message, "copy", None)
    if callable(copy_fn):
        return copy_fn(update=updates)

    message_type = type(message).__name__
    update_fields = ", ".join(sorted(updates))
    raise TypeError(f"Unsupported message type for updates: {message_type} ({update_fields})")


def _apply_message_updates(message: Any, updates: dict[str, Any]) -> Any:
    """Apply updates to a message, mutating when possible."""
    if not updates:
        return message

    if isinstance(message, dict):
        message.update(updates)
        return message

    update_keys = list(updates.keys())
    can_set_attrs = all(hasattr(message, key) for key in update_keys)
    if can_set_attrs:
        for key, value in updates.items():
            try:
                setattr(message, key, value)
            except (AttributeError, TypeError):
                can_set_attrs = False
                break

    if can_set_attrs:
        return message

    return _replace_message_fields(message, updates)


def _strip_system_prompt_parts(parts: list[Any]) -> tuple[list[Any], int]:
    """Remove system-prompt parts from a list of parts."""
    if not parts:
        return parts, 0

    filtered_parts: list[Any] = []
    stripped_count = 0

    for part in parts:
        part_kind = _get_attr(part, PART_KIND_ATTR)
        is_system_prompt_kind = part_kind == PART_KIND_SYSTEM_PROMPT
        is_system_prompt_part = isinstance(part, SystemPromptPart)
        if is_system_prompt_kind or is_system_prompt_part:
            stripped_count += 1
            continue
        filtered_parts.append(part)

    return filtered_parts, stripped_count


def _filter_parts_by_tool_call_id(
    parts: list[Any],
    dangling_tool_call_ids: set[ToolCallId],
    logger: Any,
) -> tuple[list[Any], bool]:
    """Remove parts referencing dangling tool call IDs."""
    if not parts:
        return parts, False

    filtered_parts: list[Any] = []
    removed_any = False

    for part in parts:
        tool_call_id = _get_attr(part, TOOL_CALL_ID_ATTR)
        has_tool_call_id = tool_call_id is not None
        if not has_tool_call_id:
            filtered_parts.append(part)
            continue

        is_dangling = tool_call_id in dangling_tool_call_ids
        if not is_dangling:
            filtered_parts.append(part)
            continue

        part_kind = _get_attr(part, PART_KIND_ATTR) or "unknown"
        tool_name = _get_attr(part, "tool_name") or "unknown"
        logger.debug(f"[PRUNED] {part_kind} part: tool={tool_name} id={tool_call_id}")
        removed_any = True

    return filtered_parts, removed_any


def _filter_tool_calls_by_tool_call_id(
    tool_calls: list[Any],
    dangling_tool_call_ids: set[ToolCallId],
    logger: Any,
) -> tuple[list[Any], bool]:
    """Remove tool_calls entries referencing dangling tool call IDs."""
    if not tool_calls:
        return tool_calls, False

    filtered_tool_calls: list[Any] = []
    removed_any = False

    for tool_call in tool_calls:
        tool_call_id = _get_attr(tool_call, TOOL_CALL_ID_ATTR)
        has_tool_call_id = tool_call_id is not None
        if not has_tool_call_id:
            filtered_tool_calls.append(tool_call)
            continue

        is_dangling = tool_call_id in dangling_tool_call_ids
        if not is_dangling:
            filtered_tool_calls.append(tool_call)
            continue

        tool_name = _get_attr(tool_call, "tool_name") or "unknown"
        logger.debug(f"[PRUNED] tool_calls entry: tool={tool_name} id={tool_call_id}")
        removed_any = True

    return filtered_tool_calls, removed_any


# -----------------------------------------------------------------------------
# Dangling tool call detection (delegates to adapter)
# -----------------------------------------------------------------------------


def find_dangling_tool_call_ids(messages: list[Any]) -> set[ToolCallId]:
    """Return tool_call_ids that never received a tool return."""
    return find_dangling_tool_calls(messages)


def remove_dangling_tool_calls(
    messages: list[Any],
    tool_registry: ToolCallRegistry,
    dangling_tool_call_ids: set[ToolCallId] | None = None,
) -> bool:
    """Remove tool calls that never received tool returns and prune the registry."""
    has_messages = bool(messages)
    if not has_messages:
        return False

    if dangling_tool_call_ids is None:
        dangling_tool_call_ids = find_dangling_tool_call_ids(messages)

    has_dangling_tool_calls = bool(dangling_tool_call_ids)
    if not has_dangling_tool_calls:
        return False

    logger = get_logger()
    removed_any = False
    remaining_messages: list[Any] = []

    for message in messages:
        parts = _get_parts(message)
        tool_calls = _get_message_tool_calls(message)

        filtered_parts, removed_parts = _filter_parts_by_tool_call_id(
            parts,
            dangling_tool_call_ids,
            logger,
        )
        filtered_tool_calls, removed_tool_calls = _filter_tool_calls_by_tool_call_id(
            tool_calls,
            dangling_tool_call_ids,
            logger,
        )

        removed_from_message = removed_parts or removed_tool_calls
        if removed_from_message:
            removed_any = True

        has_remaining_parts = bool(filtered_parts)
        has_remaining_tool_calls = bool(filtered_tool_calls)
        should_drop_message = removed_from_message and not (
            has_remaining_parts or has_remaining_tool_calls
        )
        if should_drop_message:
            continue

        updates: dict[str, Any] = {}
        if removed_parts:
            updates[PARTS_ATTR] = filtered_parts

        can_update_tool_calls = _can_update_tool_calls(message)
        if removed_tool_calls and can_update_tool_calls:
            updates[TOOL_CALLS_ATTR] = filtered_tool_calls

        updated_message = _apply_message_updates(message, updates)
        remaining_messages.append(updated_message)

    if not removed_any:
        return False

    messages[:] = remaining_messages
    tool_registry.remove_many(dangling_tool_call_ids)

    return True


# -----------------------------------------------------------------------------
# Empty response and consecutive request removal
# -----------------------------------------------------------------------------


def remove_empty_responses(messages: list[Any]) -> bool:
    """Remove response messages with zero parts."""
    has_messages = bool(messages)
    if not has_messages:
        return False

    canonical_messages = _canonicalize_messages(messages)
    indices_to_remove: list[int] = []

    for index, canonical_message in enumerate(canonical_messages):
        is_response = _is_response_message(canonical_message)
        has_parts = bool(canonical_message.parts)
        if not is_response:
            continue
        if has_parts:
            continue
        indices_to_remove.append(index)

    has_indices_to_remove = bool(indices_to_remove)
    if not has_indices_to_remove:
        return False

    logger = get_logger()
    for index in reversed(indices_to_remove):
        logger.debug(f"Removing empty response at index {index}")
        del messages[index]

    removed_count = len(indices_to_remove)
    logger.lifecycle(f"Removed {removed_count} empty response messages")
    return True


def remove_consecutive_requests(messages: list[Any]) -> bool:
    """Remove consecutive request messages, keeping only the last in each run."""
    message_count = len(messages)
    if message_count < MIN_CONSECUTIVE_REQUEST_WINDOW:
        return False

    canonical_messages = _canonicalize_messages(messages)
    indices_to_remove: list[int] = []

    last_index = message_count - 1
    current_index = 0

    while current_index < last_index:
        current_message = canonical_messages[current_index]
        is_request = _is_request_message(current_message)
        if not is_request:
            current_index += 1
            continue

        run_start = current_index
        run_end = current_index

        while run_end < last_index:
            next_message = canonical_messages[run_end + 1]
            next_is_request = _is_request_message(next_message)
            if not next_is_request:
                break
            run_end += 1

        has_run = run_end > run_start
        if has_run:
            indices_to_remove.extend(range(run_start, run_end))

        current_index = run_end + 1

    has_indices_to_remove = bool(indices_to_remove)
    if not has_indices_to_remove:
        return False

    logger = get_logger()
    for index in reversed(indices_to_remove):
        logger.debug(f"Removing consecutive request at index {index}")
        del messages[index]

    removed_count = len(indices_to_remove)
    logger.lifecycle(f"Removed {removed_count} consecutive request messages")
    return True


# -----------------------------------------------------------------------------
# System prompt stripping
# -----------------------------------------------------------------------------


def sanitize_history_for_resume(messages: list[Any]) -> list[Any]:
    """Sanitize message history to ensure compatibility with pydantic-ai."""
    if not messages:
        return []

    logger = get_logger()
    sanitized_messages: list[Any] = []
    system_prompts_stripped = 0

    for message in messages:
        parts = _get_parts(message)
        filtered_parts, stripped_count = _strip_system_prompt_parts(parts)
        system_prompts_stripped += stripped_count

        had_parts = bool(parts)
        has_filtered_parts = bool(filtered_parts)
        if had_parts and not has_filtered_parts:
            continue

        updates: dict[str, Any] = {}
        if stripped_count:
            updates[PARTS_ATTR] = filtered_parts

        supports_run_id = False
        if isinstance(message, dict):
            supports_run_id = RUN_ID_ATTR in message
        elif hasattr(message, RUN_ID_ATTR):
            supports_run_id = True

        if supports_run_id:
            updates[RUN_ID_ATTR] = None

        sanitized_message = _replace_message_fields(message, updates)
        sanitized_messages.append(sanitized_message)

    if system_prompts_stripped > 0:
        logger.lifecycle(f"Stripped {system_prompts_stripped} system-prompt parts from history")

    return sanitized_messages


# -----------------------------------------------------------------------------
# Cleanup orchestrator
# -----------------------------------------------------------------------------


def run_cleanup_loop(
    messages: list[Any],
    tool_registry: ToolCallRegistry,
) -> tuple[bool, set[ToolCallId]]:
    """Run iterative cleanup until message history stabilizes."""
    logger = get_logger()
    total_cleanup_applied = False
    dangling_tool_call_ids: set[ToolCallId] = set()

    last_iteration_index = MAX_CLEANUP_ITERATIONS - 1

    for cleanup_iteration in range(MAX_CLEANUP_ITERATIONS):
        any_cleanup = False

        dangling_tool_call_ids = find_dangling_tool_call_ids(messages)
        removed_dangling = remove_dangling_tool_calls(
            messages,
            tool_registry,
            dangling_tool_call_ids,
        )
        if removed_dangling:
            any_cleanup = True
            total_cleanup_applied = True
            logger.lifecycle("Cleaned up dangling tool calls")

        removed_empty_responses = remove_empty_responses(messages)
        if removed_empty_responses:
            any_cleanup = True
            total_cleanup_applied = True

        removed_consecutive_requests = remove_consecutive_requests(messages)
        if removed_consecutive_requests:
            any_cleanup = True
            total_cleanup_applied = True

        if not any_cleanup:
            break

        is_last_iteration = cleanup_iteration == last_iteration_index
        if is_last_iteration:
            logger.warning(
                f"Message cleanup did not stabilize after {MAX_CLEANUP_ITERATIONS} iterations"
            )

    return total_cleanup_applied, dangling_tool_call_ids
