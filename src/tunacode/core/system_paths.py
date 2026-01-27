"""Core facade for system path helpers."""

from __future__ import annotations

from tunacode.configuration.paths import (
    check_for_updates as _check_for_updates,
)
from tunacode.configuration.paths import (
    delete_session_file as _delete_session_file,
)
from tunacode.configuration.paths import (
    get_project_id as _get_project_id,
)

__all__: list[str] = ["check_for_updates", "delete_session_file", "get_project_id"]


def get_project_id() -> str:
    """Return the hashed project identifier for the current working directory."""
    return _get_project_id()


def delete_session_file(project_id: str, session_id: str) -> bool:
    """Delete a persisted session file.

    Args:
        project_id: Project identifier.
        session_id: Session identifier.

    Returns:
        True when deletion succeeds, False otherwise.
    """
    return _delete_session_file(project_id, session_id)


def check_for_updates() -> tuple[bool, str]:
    """Check whether a newer TunaCode version is available."""
    return _check_for_updates()
