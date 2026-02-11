"""Compaction data types for persisted session metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from tinyagent.agent_types import AgentMessage

KEY_SUMMARY = "summary"
KEY_COMPACTED_MESSAGE_COUNT = "compacted_message_count"
KEY_TOKENS_BEFORE = "tokens_before"
KEY_TOKENS_AFTER = "tokens_after"
KEY_COMPACTION_COUNT = "compaction_count"
KEY_PREVIOUS_SUMMARY = "previous_summary"
KEY_LAST_COMPACTED_AT = "last_compacted_at"

COMPACTION_STATUS_COMPACTED = "compacted"
COMPACTION_STATUS_SKIPPED = "skipped"
COMPACTION_STATUS_FAILED = "failed"

COMPACTION_REASON_COMPACTED = "compacted"
COMPACTION_REASON_ALREADY_COMPACTED = "already_compacted_this_request"
COMPACTION_REASON_THRESHOLD_NOT_ALLOWED = "threshold_compaction_not_allowed"
COMPACTION_REASON_AUTO_DISABLED = "auto_compaction_disabled"
COMPACTION_REASON_BELOW_THRESHOLD = "below_threshold"
COMPACTION_REASON_NO_VALID_BOUNDARY = "no_valid_boundary"
COMPACTION_REASON_NO_COMPACTABLE_MESSAGES = "no_compactable_messages"
COMPACTION_REASON_UNSUPPORTED_PROVIDER = "unsupported_provider"
COMPACTION_REASON_MISSING_API_KEY = "missing_api_key"
COMPACTION_REASON_SUMMARIZATION_FAILED = "summarization_failed"

COMPACTION_CAPABILITY_SKIP_REASONS: frozenset[str] = frozenset(
    {
        COMPACTION_REASON_UNSUPPORTED_PROVIDER,
        COMPACTION_REASON_MISSING_API_KEY,
    }
)

CompactionStatus = Literal[
    "compacted",
    "skipped",
    "failed",
]


__all__: list[str] = [
    "COMPACTION_CAPABILITY_SKIP_REASONS",
    "COMPACTION_REASON_ALREADY_COMPACTED",
    "COMPACTION_REASON_AUTO_DISABLED",
    "COMPACTION_REASON_BELOW_THRESHOLD",
    "COMPACTION_REASON_COMPACTED",
    "COMPACTION_REASON_MISSING_API_KEY",
    "COMPACTION_REASON_NO_COMPACTABLE_MESSAGES",
    "COMPACTION_REASON_NO_VALID_BOUNDARY",
    "COMPACTION_REASON_SUMMARIZATION_FAILED",
    "COMPACTION_REASON_THRESHOLD_NOT_ALLOWED",
    "COMPACTION_REASON_UNSUPPORTED_PROVIDER",
    "COMPACTION_STATUS_COMPACTED",
    "COMPACTION_STATUS_FAILED",
    "COMPACTION_STATUS_SKIPPED",
    "CompactionOutcome",
    "CompactionRecord",
]


@dataclass(slots=True)
class CompactionOutcome:
    """Result contract for a compaction attempt."""

    status: CompactionStatus
    reason: str
    detail: str | None
    messages: list[AgentMessage]

    @property
    def is_capability_skip(self) -> bool:
        """Return True when compaction skipped because summarization capability is unavailable."""

        return self.reason in COMPACTION_CAPABILITY_SKIP_REASONS


@dataclass(slots=True)
class CompactionRecord:
    """Persisted metadata describing the latest context compaction."""

    summary: str
    compacted_message_count: int
    tokens_before: int
    tokens_after: int
    compaction_count: int
    previous_summary: str | None
    last_compacted_at: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize the record to a JSON-friendly dictionary."""

        return {
            KEY_SUMMARY: self.summary,
            KEY_COMPACTED_MESSAGE_COUNT: self.compacted_message_count,
            KEY_TOKENS_BEFORE: self.tokens_before,
            KEY_TOKENS_AFTER: self.tokens_after,
            KEY_COMPACTION_COUNT: self.compaction_count,
            KEY_PREVIOUS_SUMMARY: self.previous_summary,
            KEY_LAST_COMPACTED_AT: self.last_compacted_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompactionRecord:
        """Deserialize a compaction record from persisted session JSON."""

        if not isinstance(data, dict):
            raise TypeError(f"Compaction record must be a dict, got {type(data).__name__}")

        summary = _coerce_string(data.get(KEY_SUMMARY), field_name=KEY_SUMMARY)
        compacted_message_count = _coerce_non_negative_int(
            data.get(KEY_COMPACTED_MESSAGE_COUNT),
            field_name=KEY_COMPACTED_MESSAGE_COUNT,
        )
        tokens_before = _coerce_non_negative_int(
            data.get(KEY_TOKENS_BEFORE),
            field_name=KEY_TOKENS_BEFORE,
        )
        tokens_after = _coerce_non_negative_int(
            data.get(KEY_TOKENS_AFTER),
            field_name=KEY_TOKENS_AFTER,
        )
        compaction_count = _coerce_positive_int(
            data.get(KEY_COMPACTION_COUNT),
            field_name=KEY_COMPACTION_COUNT,
        )

        previous_summary_value = data.get(KEY_PREVIOUS_SUMMARY)
        previous_summary = _coerce_optional_string(
            previous_summary_value,
            field_name=KEY_PREVIOUS_SUMMARY,
        )

        last_compacted_at = _coerce_string(
            data.get(KEY_LAST_COMPACTED_AT),
            field_name=KEY_LAST_COMPACTED_AT,
        )

        return cls(
            summary=summary,
            compacted_message_count=compacted_message_count,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            compaction_count=compaction_count,
            previous_summary=previous_summary,
            last_compacted_at=last_compacted_at,
        )


def _coerce_string(value: Any, *, field_name: str) -> str:
    if isinstance(value, str):
        return value
    raise TypeError(f"Compaction field '{field_name}' must be a string")


def _coerce_optional_string(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise TypeError(f"Compaction field '{field_name}' must be a string or null")


def _coerce_non_negative_int(value: Any, *, field_name: str) -> int:
    coerced = _coerce_int(value, field_name=field_name)
    if coerced < 0:
        raise ValueError(f"Compaction field '{field_name}' must be >= 0")
    return coerced


def _coerce_positive_int(value: Any, *, field_name: str) -> int:
    coerced = _coerce_int(value, field_name=field_name)
    if coerced <= 0:
        raise ValueError(f"Compaction field '{field_name}' must be > 0")
    return coerced


def _coerce_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"Compaction field '{field_name}' must be an int")
    if isinstance(value, int):
        return value
    raise TypeError(f"Compaction field '{field_name}' must be an int")
