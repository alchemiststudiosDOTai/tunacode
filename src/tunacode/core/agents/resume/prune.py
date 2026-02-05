"""Tool output pruning for context window management.

Implements backward-scanning algorithm to replace old tool outputs with placeholders,
preserving conversation structure while freeing token budget.

Inspired by OpenCode's compaction strategy.
"""

from contextlib import suppress
from typing import Any

from tunacode.utils.messaging import estimate_tokens

# Pruning thresholds
PRUNE_PROTECT_TOKENS: int = 40_000  # Protect last 40k tokens
PRUNE_MINIMUM_THRESHOLD: int = 20_000  # Only prune if savings exceed 20k

PRUNE_MIN_USER_TURNS: int = 2  # Require at least 2 user turns before pruning
PRUNE_PLACEHOLDER: str = "[Old tool result content cleared]"
PRUNE_PLACEHOLDER_TOKENS: int = estimate_tokens(PRUNE_PLACEHOLDER)

__all__ = [
    "prune_old_tool_outputs",
    "get_prune_thresholds",
    "PRUNE_PLACEHOLDER",
]


def get_prune_thresholds() -> tuple[int, int]:
    """Get pruning thresholds.

    Returns:
        Tuple of (protect_tokens, minimum_threshold)
    """
    return (PRUNE_PROTECT_TOKENS, PRUNE_MINIMUM_THRESHOLD)


# Message part kind identifiers
PART_KIND_TOOL_RETURN: str = "tool-return"
PART_KIND_USER_PROMPT: str = "user-prompt"


def is_tool_return_part(part: Any) -> bool:
    """Check if a message part is a tool return with content.

    Args:
        part: A message part object

    Returns:
        True if part has part_kind == "tool-return" and content attribute
    """
    if not hasattr(part, "part_kind"):
        return False
    if part.part_kind != PART_KIND_TOOL_RETURN:
        return False
    if not hasattr(part, "content"):  # noqa: SIM103
        return False
    return True


def is_user_prompt_part(part: Any) -> bool:
    """Check if a message part is a user prompt.

    Args:
        part: A message part object

    Returns:
        True if part has part_kind == "user-prompt"
    """
    if not hasattr(part, "part_kind"):
        return False
    return bool(part.part_kind == PART_KIND_USER_PROMPT)


def count_user_turns(messages: list[Any]) -> int:
    """Count the number of user message turns in history.

    Counts messages containing UserPromptPart or dict messages with user content.

    Args:
        messages: Message history list

    Returns:
        Integer count of user turns
    """
    count = 0
    for message in messages:
        # Check for pydantic-ai message with parts
        if hasattr(message, "parts"):
            for part in message.parts:
                if is_user_prompt_part(part):
                    count += 1
                    break  # Count each message only once
        # Check for dict-style user message
        elif isinstance(message, dict) and "content" in message:
            role = message.get("role", "")
            if role == "user":
                count += 1
    return count


def get_part_content_text(part: Any) -> str | None:
    """Get content from a part as text.

    Args:
        part: Message part with content attribute

    Returns:
        String content for token estimation or None when unavailable
    """
    if not hasattr(part, "content"):
        return None

    content = part.content
    if isinstance(content, str):
        return content

    return repr(content)


def estimate_part_tokens(part: Any, model_name: str) -> int:
    """Estimate token count for a message part's content.

    Args:
        part: Message part with content attribute
        model_name: Model identifier for heuristic estimation

    Returns:
        Estimated token count; 0 if content not extractable
    """
    content_text = get_part_content_text(part)
    if content_text is None:
        return 0

    return estimate_tokens(content_text)


def prune_part_content(
    part: Any,
    model_name: str,
    *,
    original_tokens: int | None = None,
    placeholder_tokens: int = PRUNE_PLACEHOLDER_TOKENS,
) -> int:
    """Replace a tool return part's content with placeholder.

    Mutates the part in-place. Returns tokens reclaimed.

    Args:
        part: Tool return part to prune
        model_name: Model for token estimation
        original_tokens: Precomputed token count for the original content
        placeholder_tokens: Token count for the placeholder content

    Returns:
        Number of tokens reclaimed (original - placeholder); 0 if cannot prune
    """
    content_text = get_part_content_text(part)
    if content_text is None:
        return 0

    # Skip already-pruned content
    if content_text == PRUNE_PLACEHOLDER:
        return 0

    if original_tokens is None:
        original_tokens = estimate_tokens(content_text)

    # Try to replace content
    try:
        part.content = PRUNE_PLACEHOLDER
    except (AttributeError, TypeError):
        # Part is immutable, cannot prune
        return 0

    return max(0, original_tokens - placeholder_tokens)


ToolPartEntry = tuple[int, int, Any, int | None]

NO_PRUNING_RESULT = -1


def _scan_tool_parts_backwards(
    messages: list[Any],
    model_name: str,
    protect_tokens: int,
    stop_estimation_threshold: int,
) -> tuple[list[ToolPartEntry], int, bool]:
    """Scan messages backwards, collecting tool return parts with token counts.

    Returns:
        Tuple of (collected tool parts, prune_start_index, stop_estimating_reached).
        prune_start_index is NO_PRUNING_RESULT when protection threshold not reached.
    """
    tool_parts: list[ToolPartEntry] = []
    accumulated_tokens = 0
    prune_start_index = NO_PRUNING_RESULT
    stop_estimating = False

    for msg_idx in range(len(messages) - 1, -1, -1):
        message = messages[msg_idx]
        if not hasattr(message, "parts"):
            continue

        parts = message.parts
        for part_idx in range(len(parts) - 1, -1, -1):
            part = parts[part_idx]
            if not is_tool_return_part(part):
                continue

            if stop_estimating:
                tool_parts.append((msg_idx, part_idx, part, None))
                continue

            tokens = estimate_part_tokens(part, model_name)
            accumulated_tokens += tokens
            tool_parts.append((msg_idx, part_idx, part, tokens))

            if prune_start_index < 0 and accumulated_tokens > protect_tokens:
                prune_start_index = len(tool_parts) - 1

            if accumulated_tokens > stop_estimation_threshold:
                stop_estimating = True

    return tool_parts, prune_start_index, stop_estimating


def _has_sufficient_savings(
    parts_to_prune: list[ToolPartEntry],
    minimum_threshold: int,
    stop_estimation_threshold_reached: bool,
) -> bool:
    """Check if prunable parts exceed minimum savings threshold."""
    if stop_estimation_threshold_reached:
        return True
    total_prunable_tokens = sum(
        tokens for _, _, _, tokens in parts_to_prune if tokens is not None
    )
    return total_prunable_tokens >= minimum_threshold


def _apply_pruning(
    parts_to_prune: list[ToolPartEntry],
    model_name: str,
) -> int:
    """Replace tool return content with placeholders. Returns tokens reclaimed."""
    placeholder_tokens = PRUNE_PLACEHOLDER_TOKENS
    total_reclaimed = 0

    for _, _, part, tokens in parts_to_prune:
        if tokens is None:
            content_text = get_part_content_text(part)
            if content_text is None or content_text == PRUNE_PLACEHOLDER:
                continue
            with suppress(AttributeError, TypeError):
                part.content = PRUNE_PLACEHOLDER
            continue

        reclaimed = prune_part_content(
            part,
            model_name,
            original_tokens=tokens,
            placeholder_tokens=placeholder_tokens,
        )
        total_reclaimed += reclaimed

    return total_reclaimed


def prune_old_tool_outputs(
    messages: list[Any],
    model_name: str,
) -> tuple[list[Any], int]:
    """Prune old tool output content from message history.

    Scans message history backwards, protecting the most recent tool outputs
    up to PRUNE_PROTECT_TOKENS, then replaces older tool output content
    with PRUNE_PLACEHOLDER.

    Returns:
        Tuple of (modified message list, tokens reclaimed).
    """
    if not messages:
        return (messages, 0)

    user_turns = count_user_turns(messages)
    if user_turns < PRUNE_MIN_USER_TURNS:
        return (messages, 0)

    protect_tokens, minimum_threshold = get_prune_thresholds()
    stop_estimation_threshold = protect_tokens + minimum_threshold

    tool_parts, prune_start_index, stop_threshold_reached = _scan_tool_parts_backwards(
        messages, model_name, protect_tokens, stop_estimation_threshold
    )

    if not tool_parts or prune_start_index == NO_PRUNING_RESULT:
        return (messages, 0)

    parts_to_prune = tool_parts[prune_start_index:]

    if not _has_sufficient_savings(parts_to_prune, minimum_threshold, stop_threshold_reached):
        return (messages, 0)

    total_reclaimed = _apply_pruning(parts_to_prune, model_name)
    return (messages, total_reclaimed)
