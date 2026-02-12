"""Integration tests for context compaction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tunacode.core.compaction.controller import (
    CompactionController,
    apply_compaction_messages,
)
from tunacode.core.compaction.summarizer import ContextSummarizer
from tunacode.core.compaction.types import (
    COMPACTION_REASON_ALREADY_COMPACTED,
    COMPACTION_REASON_COMPACTED,
    COMPACTION_STATUS_COMPACTED,
    COMPACTION_STATUS_SKIPPED,
    CompactionRecord,
)
from tunacode.core.session import StateManager

KEEP_RECENT_TOKENS = 80
RESERVE_TOKENS = 40
MAX_TOKENS = 220

SUMMARY_TEXT = """## Goal
Keep the refactor moving.

## Constraints & Preferences
- Preserve tool context

## Progress
### Done
- [x] Compacted old messages
### In Progress
- [ ] Continue implementation

## Key Decisions
- **Use compaction**: Prevent context overflow

## Next Steps
1. Continue from retained context

## Files Touched
### Read
- src/tunacode/core/agents/main.py
### Modified
- src/tunacode/core/compaction/controller.py

## Critical Context
- Keep recent turns verbatim
"""


def _make_text_message(
    role: str,
    text: str,
    *,
    stop_reason: str | None = None,
) -> dict[str, object]:
    message: dict[str, object] = {
        "role": role,
        "content": [{"type": "text", "text": text}],
        "timestamp": None,
    }
    if stop_reason is not None:
        message["stop_reason"] = stop_reason
    return message


def _make_tool_call_message() -> dict[str, object]:
    return {
        "role": "assistant",
        "content": [
            {
                "type": "tool_call",
                "id": "tc-1",
                "name": "bash",
                "arguments": {"command": "ls -la"},
            }
        ],
        "stop_reason": "tool_calls",
        "timestamp": None,
    }


def _make_tool_result_message(tool_output: str) -> dict[str, object]:
    return {
        "role": "tool_result",
        "tool_call_id": "tc-1",
        "tool_name": "bash",
        "content": [{"type": "text", "text": tool_output}],
        "timestamp": None,
    }


@pytest.mark.asyncio
async def test_compaction_flow_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    state_manager = StateManager()
    session = state_manager.session
    session.project_id = "project-test"
    session.created_at = "2026-02-11T00:00:00+00:00"
    session.working_directory = "/tmp"

    conversation = session.conversation
    conversation.max_tokens = MAX_TOKENS

    tool_output = "x" * 700
    history: list[dict[str, object]] = [
        _make_text_message("user", "u" * 200),
        _make_text_message("assistant", "a" * 200, stop_reason="complete"),
        _make_tool_call_message(),
        _make_tool_result_message(tool_output),
        _make_text_message("assistant", "follow-up", stop_reason="complete"),
        _make_text_message("user", "recent-user" * 16),
        _make_text_message("assistant", "recent-assistant" * 10, stop_reason="complete"),
    ]
    conversation.messages = history

    captured_prompts: list[str] = []

    async def fake_summary_model(prompt: str, _signal: object) -> str:
        captured_prompts.append(prompt)
        return SUMMARY_TEXT

    summarizer = ContextSummarizer(fake_summary_model)
    controller = CompactionController(
        state_manager=state_manager,
        summarizer=summarizer,
        keep_recent_tokens=KEEP_RECENT_TOKENS,
        reserve_tokens=RESERVE_TOKENS,
    )

    assert controller.should_compact(history, max_tokens=MAX_TOKENS)

    boundary = summarizer.calculate_retention_boundary(history, KEEP_RECENT_TOKENS)
    serialized = summarizer.serialize_messages(history[:boundary])
    assert "[Tool Result]:" in serialized
    assert "...[truncated]" in serialized

    controller.reset_request_state()
    compaction_outcome = await controller.check_and_compact(
        history,
        max_tokens=MAX_TOKENS,
        signal=None,
    )

    assert compaction_outcome.status == COMPACTION_STATUS_COMPACTED
    assert compaction_outcome.reason == COMPACTION_REASON_COMPACTED

    compacted = compaction_outcome.messages
    assert compacted == history[boundary:]
    assert len(compacted) < len(history)
    assert captured_prompts, "summary model should have been called"

    # Controller compaction is side-effect free for conversation history mutation.
    assert conversation.messages == history
    apply_compaction_messages(state_manager, compacted)

    record = session.compaction
    assert record is not None
    assert isinstance(record, CompactionRecord)
    assert record.compacted_message_count == boundary
    assert "## Goal" in record.summary
    assert record.compaction_count == 1

    round_trip = CompactionRecord.from_dict(record.to_dict())
    assert round_trip == record

    second_outcome = await controller.check_and_compact(
        compacted,
        max_tokens=MAX_TOKENS,
        signal=None,
    )
    assert second_outcome.status == COMPACTION_STATUS_SKIPPED
    assert second_outcome.reason == COMPACTION_REASON_ALREADY_COMPACTED
    assert second_outcome.messages == compacted

    transformed = controller.inject_summary_message(compacted)
    assert transformed[0]["role"] == "user"
    assert transformed[0]["compaction_summary"] is True
    first_text = transformed[0]["content"][0]["text"]
    assert "## Goal" in first_text

    assert await state_manager.save_session()

    restored = StateManager()
    restored_loaded = await restored.load_session(session.session_id)
    assert restored_loaded
    assert restored.session.compaction is not None
    assert restored.session.compaction.summary == record.summary
    assert restored.session.compaction.compaction_count == record.compaction_count


@pytest.mark.asyncio
async def test_legacy_session_without_compaction_field_defaults_to_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    storage_dir = tmp_path / "tunacode" / "sessions"
    storage_dir.mkdir(parents=True, exist_ok=True)

    session_id = "legacy-session"
    legacy_path = storage_dir / f"legacy_{session_id}.json"
    legacy_payload = {
        "version": 1,
        "session_id": session_id,
        "project_id": "legacy",
        "created_at": "2026-02-11T00:00:00+00:00",
        "last_modified": "2026-02-11T00:00:00+00:00",
        "working_directory": "/tmp",
        "current_model": "openrouter:openai/gpt-4.1",
        "session_total_usage": {
            "input": 0,
            "output": 0,
            "cache_read": 0,
            "cache_write": 0,
            "total_tokens": 0,
            "cost": {
                "input": 0.0,
                "output": 0.0,
                "cache_read": 0.0,
                "cache_write": 0.0,
                "total": 0.0,
            },
        },
        "thoughts": [],
        "messages": [],
    }
    legacy_path.write_text(json.dumps(legacy_payload), encoding="utf-8")

    state_manager = StateManager()
    assert await state_manager.load_session(session_id)
    assert state_manager.session.compaction is None
