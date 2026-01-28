"""Tool output pruning for context window management.

Implements backward-scanning algorithm to replace old tool outputs with placeholders,
preserving conversation structure while freeing token budget.

Inspired by OpenCode's compaction strategy.
"""

from typing import Any

from tunacode.utils.messaging import estimate_tokens

# Pruning thresholds
PRUNE_PROTECT_TOKENS: int = 40_000  # Protect last 40k tokens
PRUNE_MINIMUM_THRESHOLD: int = 20_000  # Only prune if savings exceed 20k

PRUNE_MIN_USER_TURNS: int = 2  # Require at least 2 user turns before pruning
PRUNE_PLACEHOLDER: str = "[Old tool result content cleared]"

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


def estimate_part_tokens(part: Any, model_name: str) -> int:
    """Estimate token count for a message part's content.

    Args:
        part: Message part with content attribute
        model_name: Model identifier for heuristic estimation

    Returns:
        Estimated token count; 0 if content not extractable
    """
    if not hasattr(part, "content"):
        return 0

    content = part.content
    if not isinstance(content, str):
        # Non-string content, estimate based on repr
        content = repr(content)

    return estimate_tokens(content, model_name)


def prune_part_content(part: Any, model_name: str) -> int:
    """Replace a tool return part's content with placeholder.

    Mutates the part in-place. Returns tokens reclaimed.

    Args:
        part: Tool return part to prune
        model_name: Model for token estimation

    Returns:
        Number of tokens reclaimed (original - placeholder); 0 if cannot prune
    """
    if not hasattr(part, "content"):
        return 0

    content = part.content

    # Skip already-pruned content
    if content == PRUNE_PLACEHOLDER:
        return 0

    # Calculate original tokens
    if isinstance(content, str):
        original_tokens = estimate_tokens(content, model_name)
    else:
        original_tokens = estimate_tokens(repr(content), model_name)

    # Calculate placeholder tokens
    placeholder_tokens = estimate_tokens(PRUNE_PLACEHOLDER, model_name)

    # Try to replace content
    try:
        part.content = PRUNE_PLACEHOLDER
    except (AttributeError, TypeError):
        # Part is immutable, cannot prune
        return 0

    return max(0, original_tokens - placeholder_tokens)


def prune_old_tool_outputs(
    messages: list[Any],
    model_name: str,
) -> tuple[list[Any], int]:
    """Prune old tool output content from message history.

    Scans message history backwards, protecting the most recent tool outputs
    up to PRUNE_PROTECT_TOKENS, then replaces older tool output content
    with PRUNE_PLACEHOLDER.

    Args:
        messages: List of pydantic-ai message objects (ModelRequest, ModelResponse, dict)
        model_name: Model identifier for token estimation (e.g., "anthropic:claude-sonnet")

    Returns:
        Tuple of:
            - Modified message list (same list, mutated in-place)
            - Number of tokens reclaimed by pruning
    """
    if not messages:
        return (messages, 0)

    # Early exit: insufficient history
    user_turns = count_user_turns(messages)
    if user_turns < PRUNE_MIN_USER_TURNS:
        return (messages, 0)

    # Phase 1: Scan backwards, collect tool return parts with token counts
    # Each entry: (message_index, part_index, part, token_count)
    tool_parts: list[tuple[int, int, Any, int]] = []

    for msg_idx in range(len(messages) - 1, -1, -1):
        message = messages[msg_idx]
        if not hasattr(message, "parts"):
            continue

        parts = message.parts
        for part_idx in range(len(parts) - 1, -1, -1):
            part = parts[part_idx]
            if is_tool_return_part(part):
                tokens = estimate_part_tokens(part, model_name)
                tool_parts.append((msg_idx, part_idx, part, tokens))

    if not tool_parts:
        return (messages, 0)

    # Get pruning thresholds
    protect_tokens, minimum_threshold = get_prune_thresholds()

    # Phase 2: Determine pruning boundary
    accumulated_tokens = 0
    prune_start_index = -1

    for i, (_, _, _, tokens) in enumerate(tool_parts):
        accumulated_tokens += tokens
        if accumulated_tokens > protect_tokens:
            prune_start_index = i
            break

    # Early exit: nothing old enough to prune
    if prune_start_index < 0:
        return (messages, 0)

    # Phase 3: Calculate potential savings
    parts_to_prune = tool_parts[prune_start_index:]
    total_prunable_tokens = sum(tokens for _, _, _, tokens in parts_to_prune)

    # Early exit: savings below threshold
    if total_prunable_tokens < minimum_threshold:
        return (messages, 0)

    # Phase 4: Apply pruning
    total_reclaimed = 0
    for _, _, part, _ in parts_to_prune:
        reclaimed = prune_part_content(part, model_name)
        total_reclaimed += reclaimed

    return (messages, total_reclaimed)
