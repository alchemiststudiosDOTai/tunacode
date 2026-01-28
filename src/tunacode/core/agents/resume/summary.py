"""Rolling summary generation for long conversations.

Implements summary checkpoint mechanism to compress long conversation
history while preserving essential context. Based on OpenCode's compaction
strategy.

Summary checkpoints are special messages that:
1. Contain a condensed representation of conversation so far
2. Allow truncation of older messages
3. Include metadata about what was summarized
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from tunacode.utils.messaging import estimate_tokens

from tunacode.core.logging import get_logger

if TYPE_CHECKING:
    from pydantic_ai import Agent

# Summary generation threshold (tokens)
SUMMARY_THRESHOLD: int = 40_000

# Summary marker for detection
SUMMARY_MARKER: str = "[CONVERSATION_SUMMARY]"

__all__ = [
    "SummaryMessage",
    "is_summary_message",
    "should_compact",
    "generate_summary",
    "SUMMARY_THRESHOLD",
    "SUMMARY_MARKER",
]


@dataclass
class SummaryMessage:
    """Represents a summary checkpoint in conversation history.

    Attributes:
        content: The summary text
        timestamp: When the summary was generated
        source_range: Tuple of (start_index, end_index) of summarized messages
        token_count: Estimated tokens in the summary
    """

    content: str
    timestamp: datetime
    source_range: tuple[int, int]
    token_count: int

    def to_marker_text(self) -> str:
        """Format summary with marker for detection."""
        return f"{SUMMARY_MARKER}\n{self.content}"


def is_summary_message(message: Any) -> bool:
    """Check if a message is a summary checkpoint.

    Looks for the SUMMARY_MARKER in text parts of the message.

    Args:
        message: A pydantic-ai message or dict

    Returns:
        True if message contains a summary checkpoint
    """
    # Handle dict messages
    if isinstance(message, dict):
        content = message.get("content", "")
        if isinstance(content, str) and SUMMARY_MARKER in content:
            return True
        parts = message.get("parts", [])
        for part in parts:
            if isinstance(part, dict):
                part_content = part.get("content", "")
                if isinstance(part_content, str) and SUMMARY_MARKER in part_content:
                    return True
        return False

    # Handle pydantic-ai messages
    if hasattr(message, "parts"):
        for part in message.parts:
            content = getattr(part, "content", None)
            if isinstance(content, str) and SUMMARY_MARKER in content:
                return True

    return False


def should_compact(messages: list[Any], model_name: str) -> bool:
    """Check if conversation should trigger summary generation.

    Args:
        messages: Message history
        model_name: Model for token estimation

    Returns:
        True if token count exceeds threshold
    """
    if not messages:
        return False

    threshold = SUMMARY_THRESHOLD

    # Estimate total tokens in history
    total_tokens = 0
    for message in messages:
        if isinstance(message, dict):
            content = message.get("content", "")
            if isinstance(content, str):
                total_tokens += estimate_tokens(content, model_name)
        elif hasattr(message, "parts"):
            for part in message.parts:
                content = getattr(part, "content", None)
                if isinstance(content, str):
                    total_tokens += estimate_tokens(content, model_name)

    return total_tokens > threshold


async def generate_summary(
    agent: Agent[str],
    messages: list[Any],
    model_name: str,
    start_index: int = 0,
    end_index: int | None = None,
) -> SummaryMessage:
    """Generate a summary of conversation messages.

    Uses the agent to summarize a range of messages into a condensed form.

    Args:
        agent: The pydantic-ai agent to use for summarization
        messages: Full message history
        model_name: Model for token estimation
        start_index: First message index to summarize
        end_index: Last message index to summarize (None = last message)

    Returns:
        SummaryMessage containing the generated summary
    """
    logger = get_logger()

    if end_index is None:
        end_index = len(messages) - 1

    # Extract text content from messages to summarize
    content_parts: list[str] = []
    for i in range(start_index, min(end_index + 1, len(messages))):
        msg = messages[i]
        if isinstance(msg, dict):
            content = msg.get("content", "")
            if content:
                content_parts.append(str(content))
        elif hasattr(msg, "parts"):
            for part in msg.parts:
                content = getattr(part, "content", None)
                if content:
                    content_parts.append(str(content))

    conversation_text = "\n---\n".join(content_parts)

    # Prompt for summary generation
    summary_prompt = f"""Summarize the following conversation history into a concise summary.
Focus on:
1. Key decisions made
2. Important context established
3. Current state of the task
4. Any pending actions

Keep the summary under 500 words.

Conversation:
{conversation_text}

Summary:"""

    # Use agent to generate summary
    try:
        result = await agent.run(summary_prompt)
        summary_text = str(result.output)
    except Exception as e:
        logger.warning(f"Summary generation failed: {e}")
        # Fallback to truncated content
        retained_count = min(3, len(content_parts))
        summary_text = f"[Summary generation failed. Last {retained_count} messages retained.]"

    token_count = estimate_tokens(summary_text, model_name)

    return SummaryMessage(
        content=summary_text,
        timestamp=datetime.now(UTC),
        source_range=(start_index, end_index),
        token_count=token_count,
    )
