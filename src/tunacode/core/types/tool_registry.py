"""Tool call registry for lifecycle tracking."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from tunacode.types.base import ToolArgs, ToolCallId, ToolName, ToolResult

ERROR_TOOL_CALL_ID_REQUIRED = "tool_call_id is required"
ERROR_TOOL_CALL_NOT_FOUND = "Tool call not registered: {tool_call_id}"

TOOL_RECORD_KEY_ARGS = "args"
TOOL_RECORD_KEY_COMPLETED_AT = "completed_at"
TOOL_RECORD_KEY_ERROR = "error"
TOOL_RECORD_KEY_RESULT = "result"
TOOL_RECORD_KEY_STARTED_AT = "started_at"
TOOL_RECORD_KEY_TOOL = "tool"
TOOL_RECORD_KEY_TIMESTAMP = "timestamp"
TOOL_RECORD_KEY_TOOL_CALL_ID = "tool_call_id"
ToolCallEntry = dict[str, object]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _format_timestamp(timestamp: datetime | None) -> str | None:
    if timestamp is None:
        return None
    return timestamp.isoformat()


@dataclass(slots=True)
class ToolCallRegistry:
    """Single source of truth for tool call lifecycle."""

    _calls: dict[ToolCallId, ToolCallEntry] = field(default_factory=dict)
    _order: list[ToolCallId] = field(default_factory=list)

    def register(self, tool_call_id: ToolCallId, tool_name: ToolName, args: ToolArgs) -> None:
        """Register a new tool call."""
        if not tool_call_id:
            raise ValueError(ERROR_TOOL_CALL_ID_REQUIRED)
        existing_call = self._calls.get(tool_call_id)
        if existing_call is not None:
            existing_call[TOOL_RECORD_KEY_TOOL] = tool_name
            existing_call[TOOL_RECORD_KEY_ARGS] = args
            return

        self._calls[tool_call_id] = {
            TOOL_RECORD_KEY_TOOL_CALL_ID: tool_call_id,
            TOOL_RECORD_KEY_TOOL: tool_name,
            TOOL_RECORD_KEY_ARGS: args,
            TOOL_RECORD_KEY_STARTED_AT: None,
            TOOL_RECORD_KEY_COMPLETED_AT: None,
            TOOL_RECORD_KEY_RESULT: None,
            TOOL_RECORD_KEY_ERROR: None,
        }
        self._order.append(tool_call_id)

    def start(self, tool_call_id: ToolCallId, started_at: datetime | None = None) -> None:
        """Mark a tool call as running."""
        resolved_started_at = started_at or _utc_now()
        self._update_call(tool_call_id, TOOL_RECORD_KEY_STARTED_AT, resolved_started_at)

    def complete(
        self,
        tool_call_id: ToolCallId,
        result: ToolResult | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        """Mark a tool call as completed."""
        resolved_completed_at = completed_at or _utc_now()
        self._update_call(tool_call_id, TOOL_RECORD_KEY_RESULT, result)
        self._update_call(tool_call_id, TOOL_RECORD_KEY_COMPLETED_AT, resolved_completed_at)

    def fail(
        self,
        tool_call_id: ToolCallId,
        error: str | None,
        result: ToolResult | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        """Mark a tool call as failed."""
        resolved_completed_at = completed_at or _utc_now()
        self._update_call(tool_call_id, TOOL_RECORD_KEY_ERROR, error)
        self._update_call(tool_call_id, TOOL_RECORD_KEY_RESULT, result)
        self._update_call(tool_call_id, TOOL_RECORD_KEY_COMPLETED_AT, resolved_completed_at)

    def cancel(
        self,
        tool_call_id: ToolCallId,
        reason: str | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        """Mark a tool call as cancelled."""
        resolved_completed_at = completed_at or _utc_now()
        self._update_call(tool_call_id, TOOL_RECORD_KEY_ERROR, reason)
        self._update_call(tool_call_id, TOOL_RECORD_KEY_COMPLETED_AT, resolved_completed_at)

    def get(self, tool_call_id: ToolCallId) -> ToolCallEntry | None:
        """Return a tool call by ID."""
        return self._calls.get(tool_call_id)

    def get_args(self, tool_call_id: ToolCallId) -> ToolArgs:
        """Return stored args for a tool call."""
        call = self._calls.get(tool_call_id)
        if call is None:
            raise ValueError(ERROR_TOOL_CALL_NOT_FOUND.format(tool_call_id=tool_call_id))
        args = call[TOOL_RECORD_KEY_ARGS]
        if not isinstance(args, dict):
            raise TypeError(f"Stored tool args must be a dict, got {type(args).__name__}")
        return args

    def list_calls(self) -> list[ToolCallEntry]:
        """Return tool calls in registration order."""
        return [self._calls[tool_call_id] for tool_call_id in self._order]

    def latest_call(self) -> ToolCallEntry | None:
        """Return the most recently registered tool call."""
        if not self._order:
            return None
        last_tool_call_id = self._order[-1]
        return self._calls.get(last_tool_call_id)

    def recent_calls(self, limit: int) -> list[ToolCallEntry]:
        """Return the most recent tool calls."""
        call_ids = self._order[-limit:] if limit > 0 else []
        return [self._calls[tool_call_id] for tool_call_id in call_ids]

    def remove(self, tool_call_id: ToolCallId) -> bool:
        """Remove a tool call from the registry."""
        call = self._calls.pop(tool_call_id, None)
        if call is None:
            return False
        self._order.remove(tool_call_id)
        return True

    def remove_many(self, tool_call_ids: Iterable[ToolCallId]) -> int:
        """Remove multiple tool calls, returning the count removed."""
        removed_count = 0
        for tool_call_id in tool_call_ids:
            if self.remove(tool_call_id):
                removed_count += 1
        return removed_count

    def clear(self) -> None:
        """Clear the registry."""
        self._calls.clear()
        self._order.clear()

    def to_legacy_records(self) -> list[dict[str, object]]:
        """Return tool call records in the legacy list-of-dicts format."""
        records: list[dict[str, object]] = []
        for call in self.list_calls():
            started_at = call[TOOL_RECORD_KEY_STARTED_AT]
            timestamp_value = _format_timestamp(
                started_at if isinstance(started_at, datetime) else None
            )
            record = {
                TOOL_RECORD_KEY_TOOL: call[TOOL_RECORD_KEY_TOOL],
                TOOL_RECORD_KEY_ARGS: call[TOOL_RECORD_KEY_ARGS],
                TOOL_RECORD_KEY_TIMESTAMP: timestamp_value,
                TOOL_RECORD_KEY_TOOL_CALL_ID: call[TOOL_RECORD_KEY_TOOL_CALL_ID],
            }
            records.append(record)
        return records

    def _update_call(self, tool_call_id: ToolCallId, key: str, value: object) -> None:
        call = self._calls.get(tool_call_id)
        if call is None:
            raise ValueError(ERROR_TOOL_CALL_NOT_FOUND.format(tool_call_id=tool_call_id))
        call[key] = value
