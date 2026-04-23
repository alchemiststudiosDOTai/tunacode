"""Pure utility functions for the main agent module."""

from __future__ import annotations

from dataclasses import dataclass

from tinyagent.agent_types import (
    AgentToolResult,
    AssistantMessage,
    TextContent,
)

from tunacode.types import UsageMetrics

from tunacode.core.types.state_structures import RuntimeState

CONTEXT_OVERFLOW_PATTERNS: tuple[str, ...] = (
    "context_length_exceeded",
    "maximum context length",
)
CONTEXT_OVERFLOW_RETRY_NOTICE = "Context overflow detected. Compacting and retrying once..."
CONTEXT_OVERFLOW_FAILURE_NOTICE = (
    "Context is still too large after compaction. Use /compact or /clear and retry."
)


@dataclass(slots=True)
class _TinyAgentStreamState:
    runtime: RuntimeState
    baseline_message_count: int
    tool_start_times: dict[str, float]
    active_tool_call_ids: set[str]
    batch_tool_call_ids: set[str]
    last_assistant_message: AssistantMessage | None = None


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

