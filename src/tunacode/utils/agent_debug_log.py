"""Append-only NDJSON for agent timing when `session.debug_mode` is on (`/debug`)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Protocol

ENV_TUNACODE_AGENT_DEBUG_LOG = "TUNACODE_AGENT_DEBUG_LOG"
_DEFAULT_RELATIVE = Path("logs") / "agent-timing.ndjson"


class _SessionForAgentDebug(Protocol):
    debug_mode: bool
    session_id: str
    working_directory: str


class _StateManagerForAgentDebug(Protocol):
    @property
    def session(self) -> _SessionForAgentDebug: ...


def resolve_agent_debug_log_path(*, working_directory: str) -> Path:
    """Absolute path for agent timing NDJSON (used by `/debug` help text and writer)."""

    env_override = os.environ.get(ENV_TUNACODE_AGENT_DEBUG_LOG, "").strip()
    if env_override:
        return Path(env_override).expanduser().resolve()
    root = Path(working_directory).expanduser() if working_directory.strip() else Path.cwd()
    try:
        resolved = root.resolve()
    except OSError:
        resolved = Path.cwd()
    return resolved / _DEFAULT_RELATIVE


def write_agent_debug(state_manager: _StateManagerForAgentDebug, payload: dict[str, Any]) -> None:
    """Write one NDJSON line when debug_mode is True. No message bodies or secrets."""

    session = state_manager.session
    if not session.debug_mode:
        return
    log_path = resolve_agent_debug_log_path(working_directory=session.working_directory)
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        envelope = {
            **payload,
            "sessionId": str(session.session_id),
            "timestamp": int(time.time() * 1000),
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(envelope) + "\n")
    except OSError:
        pass
