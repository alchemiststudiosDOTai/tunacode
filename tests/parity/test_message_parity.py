"""Parity tests against real session artifacts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tunacode.configuration.paths import get_session_storage_dir
from tunacode.utils.messaging.adapter import (
    from_canonical_list,
    get_content,
    get_tool_call_ids,
    get_tool_return_ids,
    to_canonical_list,
)

SESSION_DIR_ENV: str = "TUNACODE_SESSION_DIR"
SESSION_FILE_GLOB: str = "*.json"
MAX_PARITY_SESSIONS: int = 25


def _resolve_session_dir() -> Path:
    """Resolve session directory for parity testing."""
    override_dir = os.environ.get(SESSION_DIR_ENV)
    if override_dir:
        return Path(override_dir)
    return get_session_storage_dir()


def _load_session_messages(session_path: Path) -> list[dict[str, Any]]:
    """Load session messages from a session artifact."""
    with session_path.open() as handle:
        data = json.load(handle)

    messages = data.get("messages", [])
    if not isinstance(messages, list):
        message_type = type(messages).__name__
        raise TypeError(f"Session messages must be a list, got {message_type}: {session_path}")

    return messages


def test_real_session_message_parity() -> None:
    """Ensure canonical adapter parity against historical session files."""
    session_dir = _resolve_session_dir()
    session_files = sorted(session_dir.glob(SESSION_FILE_GLOB))
    if not session_files:
        pytest.skip(f"No session artifacts found in {session_dir}")

    selected_sessions = session_files[:MAX_PARITY_SESSIONS]

    for session_path in selected_sessions:
        session_name = session_path.name
        messages = _load_session_messages(session_path)
        if not messages:
            continue

        canonical_messages = to_canonical_list(messages)
        roundtrip_messages = from_canonical_list(canonical_messages)

        assert len(roundtrip_messages) == len(messages), (
            f"Round-trip message count mismatch in {session_name}"
        )

        for index, (original, roundtrip) in enumerate(
            zip(messages, roundtrip_messages, strict=False)
        ):
            original_content = get_content(original)
            roundtrip_content = get_content(roundtrip)

            assert roundtrip_content == original_content, (
                f"Round-trip content mismatch in {session_name} message {index}"
            )

            original_call_ids = get_tool_call_ids(original)
            roundtrip_call_ids = get_tool_call_ids(roundtrip)
            assert original_call_ids == roundtrip_call_ids, (
                f"Tool call ID mismatch in {session_name} message {index}"
            )

            original_return_ids = get_tool_return_ids(original)
            roundtrip_return_ids = get_tool_return_ids(roundtrip)
            assert original_return_ids == roundtrip_return_ids, (
                f"Tool return ID mismatch in {session_name} message {index}"
            )
