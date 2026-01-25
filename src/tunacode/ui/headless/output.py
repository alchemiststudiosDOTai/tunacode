"""Output extraction for headless mode."""

from typing import Any

from pydantic_ai.messages import ModelResponse

from tunacode.utils.messaging import get_content

TEXT_ATTRIBUTES: tuple[str, ...] = ("output", "text", "content", "message")


def _normalize(value: str | None) -> str | None:
    """Strip whitespace and return None for empty strings."""
    if value is None:
        return None

    stripped = value.strip()
    return stripped if stripped else None


def _extract_from_attributes(obj: object) -> str | None:
    """Extract text from common result attributes."""
    for attr in TEXT_ATTRIBUTES:
        value = getattr(obj, attr, None)
        if isinstance(value, str):
            normalized = _normalize(value)
            if normalized is not None:
                return normalized
    return None


def _extract_from_result(agent_run: object) -> str | None:
    """Extract text from agent_run.result."""
    result = getattr(agent_run, "result", None)
    if result is None:
        return None

    if isinstance(result, str):
        return _normalize(result)

    return _extract_from_attributes(result)


def _extract_from_messages(messages: list[Any]) -> str | None:
    """Extract text from the latest ModelResponse in messages."""
    for message in reversed(messages):
        if not isinstance(message, ModelResponse):
            continue

        content = get_content(message)
        normalized = _normalize(content)
        if normalized is not None:
            return normalized

    return None


def resolve_output(agent_run: object, messages: list[Any]) -> str | None:
    """Resolve headless output from agent run or messages.

    Priority:
    1. agent_run.result (direct result)
    2. Latest ModelResponse content (fallback)

    Returns:
        Extracted text or None if no output found.
    """
    result = _extract_from_result(agent_run)
    if result is not None:
        return result

    return _extract_from_messages(messages)
