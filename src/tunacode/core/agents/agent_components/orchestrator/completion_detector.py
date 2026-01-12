"""Completion and truncation detection helpers."""

from dataclasses import dataclass

from ..task_completion import check_task_completion
from ..truncation_checker import check_for_truncation

PENDING_INTENTION_PHRASES = (
    "let me",
    "i'll check",
    "i will",
    "going to",
    "about to",
    "need to check",
    "let's check",
    "i should",
    "need to find",
    "let me see",
    "i'll look",
    "let me search",
    "let me find",
)
ACTION_ENDINGS = (
    "checking",
    "searching",
    "looking",
    "finding",
    "reading",
    "analyzing",
)


@dataclass(frozen=True, slots=True)
class CompletionResult:
    """Result from completion marker detection."""

    is_complete: bool
    cleaned_text: str
    can_transition: bool


def detect_completion(text: str, has_tool_calls: bool) -> CompletionResult:
    """Check for completion markers and return cleaned content."""
    is_complete, cleaned_text = check_task_completion(text)
    can_transition = is_complete and not has_tool_calls
    return CompletionResult(
        is_complete=is_complete,
        cleaned_text=cleaned_text,
        can_transition=can_transition,
    )


def detect_truncation(text: str) -> bool:
    """Detect whether the response text appears truncated."""
    return check_for_truncation(text)


def has_premature_intention(text: str) -> bool:
    """Detect intention phrases that suggest unfinished work."""
    normalized_text = text.lower()
    if any(phrase in normalized_text for phrase in PENDING_INTENTION_PHRASES):
        return True

    trimmed_text = normalized_text.rstrip()
    return any(trimmed_text.endswith(ending) for ending in ACTION_ENDINGS)
