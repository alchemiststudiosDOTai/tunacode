"""Compaction data types for persisted session metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

KEY_SUMMARY = "summary"
KEY_COMPACTED_MESSAGE_COUNT = "compacted_message_count"
KEY_TOKENS_BEFORE = "tokens_before"
KEY_TOKENS_AFTER = "tokens_after"
KEY_COMPACTION_COUNT = "compaction_count"
KEY_PREVIOUS_SUMMARY = "previous_summary"
KEY_LAST_COMPACTED_AT = "last_compacted_at"


__all__: list[str] = ["CompactionRecord"]


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
