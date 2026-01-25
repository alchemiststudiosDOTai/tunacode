"""Tests for ToolCallRegistry lifecycle behavior."""

from datetime import UTC, datetime

from tunacode.types.canonical import ToolCallStatus
from tunacode.types.tool_registry import ToolCallRegistry

TOOL_CALL_ID = "tool-call-1"
TOOL_NAME = "read_file"
TOOL_ARGS = {"file_path": "README.md"}
STARTED_AT = datetime(2024, 1, 1, tzinfo=UTC)
COMPLETED_AT = datetime(2024, 1, 2, tzinfo=UTC)
FAILURE_MESSAGE = "boom"


def test_tool_registry_tracks_lifecycle() -> None:
    registry = ToolCallRegistry()

    call = registry.register(TOOL_CALL_ID, TOOL_NAME, TOOL_ARGS)
    assert call.status == ToolCallStatus.PENDING

    registry.start(TOOL_CALL_ID, started_at=STARTED_AT)
    started_call = registry.get(TOOL_CALL_ID)
    assert started_call is not None
    assert started_call.status == ToolCallStatus.RUNNING
    assert started_call.started_at == STARTED_AT

    registry.complete(TOOL_CALL_ID, result="ok", completed_at=COMPLETED_AT)
    completed_call = registry.get(TOOL_CALL_ID)
    assert completed_call is not None
    assert completed_call.status == ToolCallStatus.COMPLETED
    assert completed_call.result == "ok"
    assert completed_call.completed_at == COMPLETED_AT


def test_tool_registry_fail_and_cancel() -> None:
    registry = ToolCallRegistry()
    registry.register(TOOL_CALL_ID, TOOL_NAME, TOOL_ARGS)

    registry.fail(TOOL_CALL_ID, error=FAILURE_MESSAGE, completed_at=COMPLETED_AT)
    failed_call = registry.get(TOOL_CALL_ID)
    assert failed_call is not None
    assert failed_call.status == ToolCallStatus.FAILED
    assert failed_call.error == FAILURE_MESSAGE
    assert failed_call.completed_at == COMPLETED_AT

    registry.cancel(TOOL_CALL_ID, reason="user", completed_at=COMPLETED_AT)
    cancelled_call = registry.get(TOOL_CALL_ID)
    assert cancelled_call is not None
    assert cancelled_call.status == ToolCallStatus.CANCELLED
    assert cancelled_call.error == "user"


def test_tool_registry_legacy_records_format() -> None:
    registry = ToolCallRegistry()
    registry.register(TOOL_CALL_ID, TOOL_NAME, TOOL_ARGS)
    registry.start(TOOL_CALL_ID, started_at=STARTED_AT)

    records = registry.to_legacy_records()
    assert len(records) == 1
    record = records[0]
    assert record["tool"] == TOOL_NAME
    assert record["args"] == TOOL_ARGS
    assert record["tool_call_id"] == TOOL_CALL_ID
    assert record["timestamp"] == STARTED_AT.isoformat()


def test_tool_registry_duplicate_registration_overwrites() -> None:
    registry = ToolCallRegistry()
    registry.register(TOOL_CALL_ID, TOOL_NAME, TOOL_ARGS)

    updated_args = {"file_path": "UPDATED.md"}
    registry.register(TOOL_CALL_ID, TOOL_NAME, updated_args)

    updated_call = registry.get(TOOL_CALL_ID)
    assert updated_call is not None
    assert updated_call.args == updated_args
