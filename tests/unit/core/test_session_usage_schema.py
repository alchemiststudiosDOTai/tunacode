from __future__ import annotations

import json
from pathlib import Path

import pytest

from tunacode.configuration.paths import get_session_storage_dir

from tunacode.core.session import StateManager

PROJECT_ID = "project-test"
SESSION_ID_CANONICAL = "session-canonical"
SESSION_ID_LEGACY = "session-legacy"
MODEL_ID = "openrouter:openai/gpt-4.1"


def _write_session_payload(file_path: Path, payload: dict[str, object]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.asyncio
async def test_load_session_accepts_canonical_usage_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    state_manager = StateManager()
    storage_dir = get_session_storage_dir()
    session_file = storage_dir / f"{PROJECT_ID}_{SESSION_ID_CANONICAL}.json"

    payload = {
        "session_id": SESSION_ID_CANONICAL,
        "project_id": PROJECT_ID,
        "created_at": "2026-02-12T00:00:00+00:00",
        "last_modified": "2026-02-12T00:00:00+00:00",
        "working_directory": "/tmp",
        "current_model": MODEL_ID,
        "session_total_usage": {
            "input": 12,
            "output": 7,
            "cache_read": 3,
            "cache_write": 1,
            "total_tokens": 19,
            "cost": {
                "input": 0.01,
                "output": 0.02,
                "cache_read": 0.003,
                "cache_write": 0.001,
                "total": 0.034,
            },
        },
        "thoughts": [],
        "messages": [],
    }
    _write_session_payload(session_file, payload)

    loaded = await state_manager.load_session(SESSION_ID_CANONICAL)

    assert loaded is True
    usage = state_manager.session.usage.session_total_usage
    assert usage.input == 12
    assert usage.output == 7
    assert usage.cache_read == 3
    assert usage.cache_write == 1
    assert usage.total_tokens == 19
    assert usage.cost.total == pytest.approx(0.034)


@pytest.mark.asyncio
async def test_load_session_rejects_legacy_usage_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    state_manager = StateManager()
    storage_dir = get_session_storage_dir()
    session_file = storage_dir / f"{PROJECT_ID}_{SESSION_ID_LEGACY}.json"

    payload = {
        "session_id": SESSION_ID_LEGACY,
        "project_id": PROJECT_ID,
        "created_at": "2026-02-12T00:00:00+00:00",
        "last_modified": "2026-02-12T00:00:00+00:00",
        "working_directory": "/tmp",
        "current_model": MODEL_ID,
        "session_total_usage": {
            "prompt_tokens": 12,
            "completion_tokens": 7,
            "cached_tokens": 3,
            "cost": 0.02,
        },
        "thoughts": [],
        "messages": [],
    }
    _write_session_payload(session_file, payload)

    loaded = await state_manager.load_session(SESSION_ID_LEGACY)

    assert loaded is False
