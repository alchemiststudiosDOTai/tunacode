"""Pure utility functions for the main agent module."""

from __future__ import annotations

from typing import Any, cast

from tunacode.types import UsageMetrics

CONTEXT_OVERFLOW_PATTERNS: tuple[str, ...] = (
    "context_length_exceeded",
    "maximum context length",
)
CONTEXT_OVERFLOW_RETRY_NOTICE = "Context overflow detected. Compacting and retrying once..."
CONTEXT_OVERFLOW_FAILURE_NOTICE = (
    "Context is still too large after compaction. Use /compact or /clear and retry."
)


def coerce_error_text(value: object) -> str:
    if isinstance(value, str):
        return value
    return ""


def is_context_overflow_error(error_text: str) -> bool:
    if not error_text:
        return False
    normalized_error = error_text.lower()
    return any(pattern in normalized_error for pattern in CONTEXT_OVERFLOW_PATTERNS)


def parse_canonical_usage(raw_usage: object) -> UsageMetrics:
    """Parse canonical tinyagent usage payload into UsageMetrics."""
    if not isinstance(raw_usage, dict):
        raise RuntimeError("Assistant message missing usage payload")
    try:
        return UsageMetrics.from_dict(raw_usage)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Assistant message usage contract violation: {exc}") from exc


def is_tinyagent_message(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    role = value.get("role")
    return role in {"user", "assistant", "tool_result"}


def coerce_tinyagent_history(messages: list[Any]) -> list[dict[str, Any]]:
    if not messages:
        return []
    if all(is_tinyagent_message(m) for m in messages):
        return [cast(dict[str, Any], m) for m in messages]
    raise TypeError(
        "Session history contains non-tinyagent messages. "
        "Back-compat for pydantic-ai sessions has been removed. "
        "Start a new session or delete the persisted session file."
    )


def extract_assistant_text(message: dict[str, Any] | None) -> str:
    if not message:
        return ""
    if message.get("role") != "assistant":
        return ""
    content = message.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "text":
            continue
        text = item.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def extract_tool_result_text(result: Any) -> str | None:
    if result is None:
        return None
    content = getattr(result, "content", None)
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "text":
            continue
        text = item.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts) if parts else None
