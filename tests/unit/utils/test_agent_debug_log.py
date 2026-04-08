"""Tests for gated agent-timing NDJSON sink."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tunacode.utils.agent_debug_log import (
    ENV_TUNACODE_AGENT_DEBUG_LOG,
    resolve_agent_debug_log_path,
    write_agent_debug,
)

from tunacode.core.session import StateManager


@pytest.fixture
def state_manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> StateManager:
    monkeypatch.chdir(tmp_path)
    sm = StateManager()
    sm.session.working_directory = str(tmp_path)
    return sm


def test_write_agent_debug_no_op_when_debug_mode_off(
    state_manager: StateManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "custom.ndjson"
    monkeypatch.setenv(ENV_TUNACODE_AGENT_DEBUG_LOG, str(out))
    state_manager.session.debug_mode = False
    write_agent_debug(state_manager, {"message": "x"})
    assert not out.exists()


def test_write_agent_debug_appends_when_debug_mode_on(
    state_manager: StateManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out.ndjson"
    monkeypatch.setenv(ENV_TUNACODE_AGENT_DEBUG_LOG, str(out))
    state_manager.session.debug_mode = True
    sid = state_manager.session.session_id
    write_agent_debug(state_manager, {"message": "a"})
    write_agent_debug(state_manager, {"message": "b"})
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["message"] == "a"
    assert first["sessionId"] == sid
    assert "timestamp" in first


def test_resolve_agent_debug_log_path_default_under_logs_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ENV_TUNACODE_AGENT_DEBUG_LOG, raising=False)
    resolved = resolve_agent_debug_log_path(working_directory=str(tmp_path))
    assert resolved == tmp_path / "logs" / "agent-timing.ndjson"
