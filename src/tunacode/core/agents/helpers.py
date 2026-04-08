"""Pure utility functions for the main agent module."""

from __future__ import annotations

from tinyagent.agent_types import (
    AgentToolResult,
    ImageContent,
    JsonObject,
    JsonValue,
    TextContent,
)

from tunacode.types import UsageMetrics
from tunacode.types.canonical import (
    CanonicalToolResult,
    ToolResultImagePart,
    ToolResultTextPart,
)

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


def extract_tool_result_text(result: AgentToolResult | None) -> str | None:
    if result is None:
        return None

    parts: list[str] = []
    for item in result.content:
        if not isinstance(item, TextContent):
            continue
        if isinstance(item.text, str):
            parts.append(item.text)

    return "".join(parts) if parts else None


def _coerce_json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list):
        return [_coerce_json_value(item) for item in value]
    if isinstance(value, dict):
        coerced: JsonObject = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise RuntimeError("Tool result details contract violation: non-string detail key")
            coerced[key] = _coerce_json_value(item)
        return coerced
    raise RuntimeError(
        "Tool result details contract violation: details must contain JSON-serializable values"
    )


def _coerce_tool_result_details(raw_details: object) -> JsonObject:
    if not isinstance(raw_details, dict):
        raise RuntimeError("Tool result details contract violation: details must be an object")

    details: JsonObject = {}
    for key, value in raw_details.items():
        if not isinstance(key, str):
            raise RuntimeError("Tool result details contract violation: non-string detail key")
        details[key] = _coerce_json_value(value)
    return details


def canonicalize_tool_result(
    result: AgentToolResult | None,
    *,
    tool_name: str | None,
    is_error: bool,
) -> CanonicalToolResult | None:
    """Convert a native tinyagent tool result into TunaCode's canonical shape."""
    if result is None:
        return None

    content_parts: list[ToolResultTextPart | ToolResultImagePart] = []
    for item in result.content:
        if isinstance(item, TextContent):
            content_parts.append(
                ToolResultTextPart(
                    text=item.text,
                    text_signature=item.text_signature,
                )
            )
            continue

        if isinstance(item, ImageContent):
            content_parts.append(
                ToolResultImagePart(
                    url=item.url,
                    mime_type=item.mime_type,
                )
            )

    return CanonicalToolResult(
        tool_name=tool_name,
        content=tuple(content_parts),
        details=_coerce_tool_result_details(result.details),
        is_error=is_error,
    )
