"""Shared session metadata initialization for UI surfaces."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from tunacode.core.types.state import StateManagerProtocol
from tunacode.core.ui_api.system_paths import get_project_id


def initialize_session_metadata(state_manager: StateManagerProtocol) -> None:
    """Populate persisted session metadata needed for save/load flows."""
    session = state_manager.session
    session.project_id = get_project_id()
    session.working_directory = os.getcwd()
    if session.created_at:
        return
    session.created_at = datetime.now(UTC).isoformat()
