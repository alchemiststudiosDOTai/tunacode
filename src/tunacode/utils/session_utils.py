"""
Lightweight session persistence utilities.

Saves and loads a minimal subset of SessionState to JSON using the
existing session directory pattern at ~/.tunacode/sessions/{session_id}.

Fail fast with explicit errors; avoid silent fallbacks.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple, cast

from tunacode.core.state import SessionState
from tunacode.types import SessionId
from tunacode.utils.system import get_session_dir, get_tunacode_home

# Symbolic constants to avoid magic strings
SESSION_FILENAME: str = "session_state.json"
ESSENTIAL_FIELDS: Tuple[str, ...] = (
    "session_id",
    "current_model",
    "user_config",
    "messages",
    "total_cost",
    "files_in_context",
    "session_total_usage",
)


def _is_safe_session_id(session_id: str) -> bool:
    """Validate session_id to prevent path traversal.

    Accept UUID-like identifiers with hex and dashes only.
    """
    return bool(re.fullmatch(r"[A-Fa-f0-9\-]{8,64}", session_id))


def _serialize_message(message: Any) -> Dict[str, Any]:
    """Best-effort message serialization.

    - If already JSON-serializable dict with 'role'/'content', keep minimal.
    - Otherwise, record minimal shape with extracted string content via str().
    """
    if isinstance(message, dict):
        result: Dict[str, Any] = {}
        if "role" in message:
            result["role"] = message.get("role")
        if "content" in message:
            result["content"] = message.get("content")
        if result:
            return result
        # Fallback: keep shallow copy of JSON-serializable items
        filtered: Dict[str, Any] = {}
        for k, v in message.items():
            try:
                json.dumps(v)
                filtered[k] = v
            except Exception:
                filtered[k] = str(v)
        return filtered

    # Simple primitives
    try:
        json.dumps(message)
        return cast(Dict[str, Any], message)
    except Exception:
        pass

    # Object fallback
    if hasattr(message, "role") or hasattr(message, "content"):
        return {
            "role": getattr(message, "role", None),
            "content": getattr(message, "content", None),
        }
    return {"content": str(message)}


def _collect_essential_state(state: SessionState) -> Dict[str, Any]:
    """Extract essential fields from SessionState for persistence."""
    # Dataclasses may appear nested; convert safely
    obj: Dict[str, Any]
    if is_dataclass(state):
        obj = asdict(state)
    else:
        # Fallback for unexpected types; store known attributes
        obj = {k: getattr(state, k, None) for k in ESSENTIAL_FIELDS}

    # Keep only essential fields in defined order
    essential: Dict[str, Any] = {k: obj.get(k) for k in ESSENTIAL_FIELDS}
    # Serialize messages minimally
    messages: List[Any] = cast(List[Any], essential.get("messages") or [])
    essential["messages"] = [_serialize_message(m) for m in messages]
    # Normalize set to list for JSON
    fic = essential.get("files_in_context")
    if isinstance(fic, set):
        essential["files_in_context"] = sorted(list(cast(set[str], fic)))
    elif isinstance(fic, list):
        essential["files_in_context"] = cast(List[str], fic)
    else:
        essential["files_in_context"] = []
    return essential


def save_session_state(state_manager: Any) -> Path:
    """Save essential session state to a JSON file.

    Returns the path to the saved file.
    """
    session_dir = get_session_dir(state_manager)
    session_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    data = _collect_essential_state(state_manager.session)
    out_path = session_dir / SESSION_FILENAME

    try:
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except PermissionError as e:
        raise PermissionError(f"Permission denied writing session file: {out_path}: {e}")
    except OSError as e:
        raise OSError(f"Failed to save session file: {out_path}: {e}")

    return out_path


def load_session_state(state_manager: Any, session_id: SessionId) -> bool:
    """Load session state from JSON and apply to the current session.

    Returns True on success, raises on fatal validation errors.
    """
    if not _is_safe_session_id(session_id):
        raise ValueError("Invalid session_id format")

    # Resolve session file path under ~/.tunacode/sessions/<id>/session_state.json
    home = get_tunacode_home()
    session_dir = home / "sessions" / session_id
    in_path = session_dir / SESSION_FILENAME

    if not in_path.exists():
        return False

    try:
        raw = in_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Corrupted session file: {in_path}: {e}")
    except OSError as e:
        raise OSError(f"Failed to read session file: {in_path}: {e}")

    # Apply essential fields to current live session
    session = state_manager.session
    if not isinstance(data, dict):
        raise ValueError("Session data must be a JSON object")

    # Restore explicit fields with defensive defaults
    session.session_id = cast(str, data.get("session_id") or session.session_id)
    session.current_model = cast(str, data.get("current_model") or session.current_model)
    session.total_cost = cast(float, data.get("total_cost") or 0.0)

    user_config = cast(Dict[str, Any], data.get("user_config") or {})
    if isinstance(user_config, dict):
        session.user_config = user_config

    files_in_context = cast(List[str], data.get("files_in_context") or [])
    if isinstance(files_in_context, list):
        session.files_in_context = set(files_in_context)

    usage = cast(Dict[str, Any], data.get("session_total_usage") or {})
    if isinstance(usage, dict):
        session.session_total_usage = usage

    # Messages: minimal dicts already; accept list
    msgs = cast(List[Any], data.get("messages") or [])
    if isinstance(msgs, list):
        session.messages = msgs

    return True
