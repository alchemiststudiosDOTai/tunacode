"""Pure extraction functions for response node data.

These functions extract data from response nodes without side effects.
Each function takes an input and returns structured data.
"""

from dataclasses import dataclass
from typing import Any

PART_KIND_TEXT = "text"
CONTENT_JOINER = " "


@dataclass(frozen=True, slots=True)
class ExtractedThought:
    """A thought extracted from a node."""

    content: str


@dataclass(frozen=True, slots=True)
class ExtractedUsage:
    """Usage data extracted from a model response."""

    usage: Any  # The raw usage object from pydantic-ai
    model_name: str


@dataclass(frozen=True, slots=True)
class ExtractedContent:
    """Text content extracted from response parts."""

    parts: list[str]
    has_non_empty: bool

    @property
    def combined(self) -> str:
        """Return combined content string."""
        return CONTENT_JOINER.join(self.parts).strip()


def extract_thought(node: Any) -> ExtractedThought | None:
    """Extract thought from a node if present."""
    thought = getattr(node, "thought", None)
    if not thought:
        return None
    return ExtractedThought(content=thought)


def extract_usage(node: Any, model_name: str) -> ExtractedUsage | None:
    """Extract usage data from a node's model response."""
    model_response = getattr(node, "model_response", None)
    if model_response is None:
        return None

    usage = getattr(model_response, "usage", None)
    if usage is None:
        return None

    return ExtractedUsage(usage=usage, model_name=model_name)


def extract_content(response_parts: list[Any]) -> ExtractedContent:
    """Extract text content from response parts."""
    content_parts: list[str] = []
    has_non_empty = False

    for part in response_parts:
        content = getattr(part, "content", None)
        if not isinstance(content, str):
            continue

        if content.strip():
            has_non_empty = True
            content_parts.append(content)

    return ExtractedContent(parts=content_parts, has_non_empty=has_non_empty)


def extract_request(node: Any) -> Any | None:
    """Extract request object from node."""
    return getattr(node, "request", None)


def extract_model_response(node: Any) -> Any | None:
    """Extract model response from node."""
    return getattr(node, "model_response", None)


def extract_response_parts(model_response: Any) -> list[Any]:
    """Extract parts list from model response."""
    return getattr(model_response, "parts", [])


def extract_result_output(node: Any) -> Any | None:
    """Extract result output from node if present."""
    result = getattr(node, "result", None)
    if result is None:
        return None
    return getattr(result, "output", None)
