"""Shared formatting helpers."""

from __future__ import annotations

MAX_DIAGNOSTIC_MESSAGE_LENGTH = 80


def truncate_diagnostic_message(
    message: str, max_length: int = MAX_DIAGNOSTIC_MESSAGE_LENGTH
) -> str:
    """Truncate verbose diagnostic messages to essential info.

    Pyright often produces multi-line explanations. We keep only the first line
    (the actionable part), and cap it to max_length with an ellipsis suffix.
    """
    first_line = message.split("\n")[0].strip()
    if len(first_line) > max_length:
        return first_line[: max_length - 3] + "..."
    return first_line
