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

from dataclasses import replace
from typing import Any

from tunacode.core.logging import get_logger
from tunacode.types import ToolArgs, ToolCallId
from tunacode.utils.messaging import (
    _get_attr,
    _get_parts,
    find_dangling_tool_calls,
)

# Message part kind identifiers (kept for mutation functions)
PART_KIND_TOOL_CALL: str = "tool-call"
PART_KIND_SYSTEM_PROMPT: str = "system-prompt"
PART_KIND_ATTR: str = "part_kind"
PARTS_ATTR: str = "parts"
TOOL_CALLS_ATTR: str = "tool_calls"
TOOL_CALL_ID_ATTR: str = "tool_call_id"

MESSAGE_KIND_REQUEST: str = "request"
MESSAGE_KIND_RESPONSE: str = "response"

MAX_CLEANUP_ITERATIONS: int = 10

__all__ = [
    "sanitize_history_for_resume",
    "run_cleanup_loop",
    "remove_dangling_tool_calls",
    "remove_empty_responses",
    "remove_consecutive_requests",
    "find_dangling_tool_call_ids",
    # Constants for external use
    "PART_KIND_ATTR",
    "TOOL_CALL_ID_ATTR",
]


# -----------------------------------------------------------------------------
# Mutation helpers (kept for modifying messages)
# -----------------------------------------------------------------------------


def _set_message_parts(message: Any, parts: list[Any]) -> None:
    """Assign new parts to a message."""
    if isinstance(message, dict):
        message[PARTS_ATTR] = parts
        return
    if hasattr(message, PARTS_ATTR):
        setattr(message, PARTS_ATTR, parts)


def _set_message_tool_calls(message: Any, tool_calls: list[Any]) -> None:
    """Assign tool_calls to a message.

    Note: For pydantic-ai messages, tool_calls is a read-only property derived
    from parts. Setting parts is sufficient; this function only handles dict
    messages (e.g., serialized session data).
    """
    if isinstance(message, dict):
        message[TOOL_CALLS_ATTR] = tool_calls
        return
    # For pydantic-ai message objects, tool_calls is a computed property
    # derived from parts. We cannot set it directly - setting parts is enough.


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
    """Return tool_calls from a message as a list (for mutation functions)."""
    tool_calls_value = _get_attr(message, TOOL_CALLS_ATTR)
    return _normalize_list(tool_calls_value)


# -----------------------------------------------------------------------------
# Dangling tool call detection (delegates to adapter)
# -----------------------------------------------------------------------------


def find_dangling_tool_call_ids(messages: list[Any]) -> set[ToolCallId]:
    """Return tool_call_ids that never received a tool return.

    This is a thin wrapper around adapter.find_dangling_tool_calls() for
    backwards compatibility. The adapter handles all message format polymorphism.
    """
    return find_dangling_tool_calls(messages)


def _filter_dangling_tool_calls_from_parts(
    parts: list[Any],
    dangling_tool_call_ids: set[ToolCallId],
) -> tuple[list[Any], bool]:
    """Remove parts that reference dangling tool call IDs.

    This filters:
    - tool-call parts: the original tool invocation
    - tool-return parts: the result of the tool call
    - retry-prompt parts: pydantic-ai's error response for failed tool calls

    All of these have a tool_call_id attribute that must be pruned together.
    """
    if not parts:
        return parts, False

    logger = get_logger()
    filtered_parts: list[Any] = []
    removed_any = False

    for part in parts:
        tool_call_id = _get_attr(part, TOOL_CALL_ID_ATTR)

        # Parts without tool_call_id are never dangling
        if tool_call_id is None:
            filtered_parts.append(part)
            continue

        # Check if this part references a dangling tool call
        if tool_call_id in dangling_tool_call_ids:
            part_kind = _get_attr(part, PART_KIND_ATTR) or "unknown"
            tool_name = _get_attr(part, "tool_name") or "unknown"
            logger.debug(f"[PRUNED] {part_kind} part: tool={tool_name} id={tool_call_id}")
            removed_any = True
            continue

        filtered_parts.append(part)

    return filtered_parts, removed_any


def _filter_dangling_tool_calls_from_tool_calls(
    tool_calls: list[Any],
    dangling_tool_call_ids: set[ToolCallId],
) -> tuple[list[Any], bool]:
    """Remove dangling entries from tool_calls lists."""
    if not tool_calls:
        return tool_calls, False

    logger = get_logger()
    filtered_tool_calls: list[Any] = []
    removed_any = False

    for tool_call in tool_calls:
        tool_call_id = _get_attr(tool_call, TOOL_CALL_ID_ATTR)
        if tool_call_id is None:
            filtered_tool_calls.append(tool_call)
            continue

        if tool_call_id in dangling_tool_call_ids:
            tool_name = _get_attr(tool_call, "tool_name") or "unknown"
            logger.debug(f"[PRUNED] tool_calls entry: tool={tool_name} id={tool_call_id}")
            removed_any = True
            continue

        filtered_tool_calls.append(tool_call)

    return filtered_tool_calls, removed_any


def _strip_dangling_tool_calls_from_message(
    message: Any,
    dangling_tool_call_ids: set[ToolCallId],
) -> tuple[Any, bool, bool]:
    """Remove dangling tool calls from a message.

    Returns:
        Tuple of (modified_message, removed_any, should_drop)
        - modified_message: New message object (for pydantic) or same message (for dict)
        - removed_any: True if any tool calls were removed
        - should_drop: True if message should be dropped from history
    """
    parts = _get_parts(message)
    tool_calls = _get_message_tool_calls(message)

    filtered_parts, removed_from_parts = _filter_dangling_tool_calls_from_parts(
        parts,
        dangling_tool_call_ids,
    )
    filtered_tool_calls, removed_from_tool_calls = _filter_dangling_tool_calls_from_tool_calls(
        tool_calls,
        dangling_tool_call_ids,
    )

    removed_any = removed_from_parts or removed_from_tool_calls
    should_drop = removed_any and not filtered_parts and not filtered_tool_calls

    # If nothing removed, return original message
    if not removed_any:
        return message, False, False

    # For dict messages, mutate in place (backwards compat with serialized data)
    if isinstance(message, dict):
        if removed_from_parts:
            message[PARTS_ATTR] = filtered_parts
        if removed_from_tool_calls:
            message[TOOL_CALLS_ATTR] = filtered_tool_calls
        return message, removed_any, should_drop

    # For pydantic objects, use replace() to create new immutable object
    # Note: tool_calls is a computed property from parts, so only update parts
    try:
        modified_message = replace(message, parts=filtered_parts)
        return modified_message, removed_any, should_drop
    except Exception as e:
        logger = get_logger()
        logger.warning(f"Failed to replace message parts with dataclasses.replace: {e}")
        # Fallback: try setattr (may fail on frozen models, but worth trying)
        if removed_from_parts:
            _set_message_parts(message, filtered_parts)
        if removed_from_tool_calls:
            _set_message_tool_calls(message, filtered_tool_calls)
        return message, removed_any, should_drop


def remove_dangling_tool_calls(
    messages: list[Any],
    tool_call_args_by_id: dict[ToolCallId, ToolArgs],
    dangling_tool_call_ids: set[ToolCallId] | None = None,
) -> bool:
    """Remove tool calls that never received tool returns and clear cached args."""
    if not messages:
        return False

    if dangling_tool_call_ids is None:
        dangling_tool_call_ids = find_dangling_tool_call_ids(messages)
    if not dangling_tool_call_ids:
        return False

    removed_any = False
    remaining_messages: list[Any] = []

    for message in messages:
        (
            modified_message,
            removed_from_message,
            should_drop,
        ) = _strip_dangling_tool_calls_from_message(
            message,
            dangling_tool_call_ids,
        )
        if removed_from_message:
            removed_any = True
        if should_drop:
            removed_any = True
            continue
        # Use modified_message (which may be a new object for pydantic messages)
        remaining_messages.append(modified_message)

    if removed_any:
        messages[:] = remaining_messages
        for tool_call_id in dangling_tool_call_ids:
            tool_call_args_by_id.pop(tool_call_id, None)

    return removed_any


# -----------------------------------------------------------------------------
# Empty response and consecutive request removal
# -----------------------------------------------------------------------------


def remove_consecutive_requests(messages: list[Any]) -> bool:
    """Remove consecutive request messages, keeping only the last in each run.

    The API expects alternating request/response messages. When abort happens
    before model responds, we can end up with consecutive request messages.
    This function removes all but the last request in any consecutive run.

    Returns:
        True if any messages were removed, False otherwise.
    """
    if len(messages) < 2:
        return False

    logger = get_logger()
    indices_to_remove: list[int] = []
    i = 0

    while i < len(messages) - 1:
        current_kind = getattr(messages[i], "kind", None)

        if current_kind != MESSAGE_KIND_REQUEST:
            i += 1
            continue

        # Found a request - check if next message is also a request
        run_start = i
        while i < len(messages) - 1:
            next_kind = getattr(messages[i + 1], "kind", None)
            if next_kind != MESSAGE_KIND_REQUEST:
                break
            i += 1

        # If we advanced, we have consecutive requests from run_start to i
        # Keep only the last one (at index i), remove run_start to i-1
        if i > run_start:
            for idx in range(run_start, i):
                indices_to_remove.append(idx)

        i += 1

    if not indices_to_remove:
        return False

    # Remove in reverse order to preserve indices
    for idx in reversed(indices_to_remove):
        removed_msg = messages[idx]
        removed_kind = getattr(removed_msg, "kind", "unknown")
        removed_parts = len(getattr(removed_msg, "parts", []))
        logger.debug(
            f"Removing consecutive request at index {idx}: "
            f"kind={removed_kind} parts={removed_parts}"
        )
        del messages[idx]

    logger.lifecycle(f"Removed {len(indices_to_remove)} consecutive request messages")
    return True


def remove_empty_responses(messages: list[Any]) -> bool:
    """Remove response messages with zero parts.

    Empty responses (parts=0) can occur when abort happens after model starts
    responding but before any content is generated. These empty responses
    create invalid message sequences.

    Returns:
        True if any messages were removed, False otherwise.
    """
    if not messages:
        return False

    logger = get_logger()
    indices_to_remove: list[int] = []

    for i, message in enumerate(messages):
        msg_kind = getattr(message, "kind", None)
        if msg_kind != MESSAGE_KIND_RESPONSE:
            continue

        parts = getattr(message, "parts", [])
        if not parts:
            indices_to_remove.append(i)

    if not indices_to_remove:
        return False

    for idx in reversed(indices_to_remove):
        logger.debug(f"Removing empty response at index {idx}")
        del messages[idx]

    logger.lifecycle(f"Removed {len(indices_to_remove)} empty response messages")
    return True


# -----------------------------------------------------------------------------
# System prompt stripping
# -----------------------------------------------------------------------------


def _strip_system_prompt_parts(parts: list[Any]) -> list[Any]:
    """Remove system-prompt parts from a list of message parts.

    pydantic-ai injects the system prompt automatically via agent.system_prompt.
    If message_history contains system prompts from a previous run, we get
    duplicate system prompts which can confuse the model or cause hangs.
    """
    if not parts:
        return parts

    return [p for p in parts if _get_attr(p, PART_KIND_ATTR) != PART_KIND_SYSTEM_PROMPT]


def sanitize_history_for_resume(messages: list[Any]) -> list[Any]:
    """Sanitize message history to ensure compatibility with pydantic-ai.

    This function:
    1. Removes internal IDs (run_id) that bind messages to previous sessions
    2. Strips system-prompt parts (pydantic-ai injects these automatically)
    3. Removes empty messages that result from stripping

    Critical: pydantic-ai v1.21.0+ enforces that agent.iter() adds its own
    system prompt. If history contains system prompts, they will be duplicated.
    """
    if not messages:
        return []

    sanitized = []
    logger = get_logger()
    system_prompts_stripped = 0

    for msg in messages:
        # Handle dict messages (from serialization)
        if isinstance(msg, dict):
            msg_copy = msg.copy()
            if PARTS_ATTR in msg_copy and isinstance(msg_copy[PARTS_ATTR], list):
                original_count = len(msg_copy[PARTS_ATTR])
                msg_copy[PARTS_ATTR] = _strip_system_prompt_parts(msg_copy[PARTS_ATTR])
                system_prompts_stripped += original_count - len(msg_copy[PARTS_ATTR])
                # Skip empty messages
                if not msg_copy[PARTS_ATTR]:
                    continue
            sanitized.append(msg_copy)
            continue

        # Handle pydantic-ai message objects
        parts = _get_parts(msg)
        original_part_count = len(parts)
        filtered_parts = _strip_system_prompt_parts(parts)
        stripped_count = original_part_count - len(filtered_parts)
        system_prompts_stripped += stripped_count

        # Skip messages that become empty after stripping system prompts
        if original_part_count > 0 and not filtered_parts:
            continue

        # Clean run_id and update parts if needed
        try:
            if hasattr(msg, "run_id"):
                if stripped_count > 0:
                    clean_msg = replace(msg, run_id=None, parts=filtered_parts)
                else:
                    clean_msg = replace(msg, run_id=None)
                sanitized.append(clean_msg)
            elif stripped_count > 0:
                # No run_id but need to update parts
                clean_msg = replace(msg, parts=filtered_parts)
                sanitized.append(clean_msg)
            else:
                sanitized.append(msg)
        except Exception as e:
            logger.debug(f"Failed to sanitize message {type(msg).__name__}: {e}")
            sanitized.append(msg)

    if system_prompts_stripped > 0:
        logger.lifecycle(f"Stripped {system_prompts_stripped} system-prompt parts from history")

    return sanitized


# -----------------------------------------------------------------------------
# Cleanup orchestrator
# -----------------------------------------------------------------------------


def run_cleanup_loop(
    messages: list[Any],
    tool_call_args_by_id: dict[ToolCallId, ToolArgs],
) -> tuple[bool, set[ToolCallId]]:
    """Run iterative cleanup until message history stabilizes.

    Message cleanup is iterative because each pass can expose new issues:
    - Removing dangling tool calls may create consecutive requests
    - Removing consecutive requests may orphan tool returns, creating new dangling calls

    Args:
        messages: Message history list (mutated in place)
        tool_call_args_by_id: Tool call argument cache (mutated in place)

    Returns:
        Tuple of (any_cleanup_applied, final_dangling_tool_call_ids)
    """
    logger = get_logger()
    total_cleanup_applied = False
    dangling_tool_call_ids: set[ToolCallId] = set()

    for cleanup_iteration in range(MAX_CLEANUP_ITERATIONS):
        any_cleanup = False

        dangling_tool_call_ids = find_dangling_tool_call_ids(messages)
        if remove_dangling_tool_calls(
            messages,
            tool_call_args_by_id,
            dangling_tool_call_ids,
        ):
            any_cleanup = True
            total_cleanup_applied = True
            logger.lifecycle("Cleaned up dangling tool calls")

        # Remove empty response messages (abort during response generation)
        if remove_empty_responses(messages):
            any_cleanup = True
            total_cleanup_applied = True

        # Remove consecutive request messages (caused by abort before model responds)
        # Must run AFTER empty response removal since that can expose consecutive requests
        if remove_consecutive_requests(messages):
            any_cleanup = True
            total_cleanup_applied = True

        if not any_cleanup:
            break

        if cleanup_iteration == MAX_CLEANUP_ITERATIONS - 1:
            logger.warning(
                f"Message cleanup did not stabilize after {MAX_CLEANUP_ITERATIONS} iterations"
            )

    return total_cleanup_applied, dangling_tool_call_ids
