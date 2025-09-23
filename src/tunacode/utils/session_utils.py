"""
Lightweight session persistence utilities.

Saves and loads a minimal subset of SessionState to JSON using the
existing session directory pattern at ~/.tunacode/sessions/{session_id}.

Fail fast with explicit errors; avoid silent fallbacks.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from tunacode.constants import SESSIONS_SUBDIR
from tunacode.core.state import SessionState
from tunacode.types import SessionId
from tunacode.utils.session_id_generator import generate_user_friendly_session_id
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

# Sensitive fields to exclude from serialization
SENSITIVE_FIELDS: Tuple[str, ...] = (
    "api_key",
    "token",
    "password",
    "secret",
    "auth",
    "credential",
    "private_key",
)




def _is_sensitive_field(field_name: str) -> bool:
    """Check if a field name contains sensitive information."""
    field_lower = field_name.lower()
    return any(sensitive in field_lower for sensitive in SENSITIVE_FIELDS)


def _serialize_tool_calls(tool_calls: Any) -> List[Dict[str, Any]]:
    """Serialize tool calls preserving essential information."""
    if not tool_calls:
        return []

    if not isinstance(tool_calls, list):
        tool_calls = [tool_calls]

    serialized = []
    for call in tool_calls:
        if isinstance(call, dict):
            # Already a dict, filter sensitive fields
            filtered_call = {}
            for k, v in call.items():
                if not _is_sensitive_field(k):
                    try:
                        json.dumps(v)
                        filtered_call[k] = v
                    except Exception:
                        filtered_call[k] = str(v)
            serialized.append(filtered_call)
        elif hasattr(call, "tool_name"):
            # Object with tool call attributes
            call_dict = {
                "tool_name": getattr(call, "tool_name", None),
                "tool_call_id": getattr(call, "tool_call_id", None),
            }
            if hasattr(call, "args"):
                call_dict["args"] = getattr(call, "args", {})
            if hasattr(call, "timestamp"):
                call_dict["timestamp"] = getattr(call, "timestamp", None)
            serialized.append(call_dict)

    return serialized


def _serialize_message_part(part: Any) -> Optional[Dict[str, Any]]:
    """Serialize a message part (from pydantic-ai messages or dict)."""
    if not part:
        return None

    # Handle dict parts (already serialized)
    if isinstance(part, dict):
        result = dict(part)  # Copy the dict
        # Filter sensitive data from args if present
        if "args" in result and isinstance(result["args"], dict):
            filtered_args = {}
            for k, v in result["args"].items():
                if not _is_sensitive_field(k):
                    try:
                        json.dumps(v)
                        filtered_args[k] = v
                    except Exception:
                        filtered_args[k] = str(v)
            result["args"] = filtered_args
        return result

    result: Dict[str, Any] = {}

    # Preserve part type and basic info
    if hasattr(part, "part_kind"):
        result["part_kind"] = getattr(part, "part_kind")

    # Handle different part types
    part_kind = result.get("part_kind", "")

    if part_kind == "user-prompt" or part_kind == "text":
        # User input or text content
        if hasattr(part, "content"):
            result["content"] = getattr(part, "content")
        if hasattr(part, "role"):
            result["role"] = getattr(part, "role", "user")

    elif part_kind == "tool-call":
        # Tool call information
        result["tool_name"] = getattr(part, "tool_name", None)
        result["tool_call_id"] = getattr(part, "tool_call_id", None)
        if hasattr(part, "args"):
            args = getattr(part, "args")
            # Filter sensitive data from args
            if isinstance(args, dict):
                filtered_args = {}
                for k, v in args.items():
                    if not _is_sensitive_field(k):
                        try:
                            json.dumps(v)
                            filtered_args[k] = v
                        except Exception:
                            filtered_args[k] = str(v)
                result["args"] = filtered_args
            else:
                result["args"] = args

    elif part_kind == "tool-return":
        # Tool response
        result["tool_name"] = getattr(part, "tool_name", None)
        result["tool_call_id"] = getattr(part, "tool_call_id", None)
        if hasattr(part, "content"):
            content = getattr(part, "content")
            # Truncate very long tool outputs
            if isinstance(content, str) and len(content) > 1000:
                result["content"] = content[:997] + "..."
            else:
                result["content"] = content

    else:
        # Generic part - preserve basic content
        if hasattr(part, "content"):
            result["content"] = getattr(part, "content")
        if hasattr(part, "role"):
            result["role"] = getattr(part, "role")

    # Add timestamp if available
    if hasattr(part, "timestamp"):
        result["timestamp"] = getattr(part, "timestamp")

    return result if result else None


def _is_safe_session_id(session_id: str) -> bool:
    """Validate session_id to prevent path traversal.

    Accept both UUID-like identifiers and new timestamp-based format.
    New format: YYYY-MM-DD_HH-MM_description (alphanumeric, dashes, underscores)
    """
    # Accept UUID format (backward compatibility)
    if re.fullmatch(r"[A-Fa-f0-9\-]{8,64}", session_id):
        return True

    # Accept new timestamp-based format
    return bool(re.fullmatch(r"[A-Za-z0-9\-_]{10,80}", session_id))


def _serialize_message(message: Any) -> Dict[str, Any]:
    """Enhanced message serialization preserving tool calls and context.

    Preserves:
    - User queries and agent responses (role/content)
    - Tool calls with basic structure (tool_name, args, tool_call_id)
    - Message timestamps and types (part_kind)
    - Message structure (parts for complex messages)

    Excludes:
    - API keys and sensitive data
    - Complex internal state objects
    - Non-serializable objects
    """
    # Handle dict-based messages (simple format and enhanced format)
    if isinstance(message, dict):
        # Handle dict messages that already have parts structure (enhanced format)
        if "parts" in message:
            result = dict(message)  # Copy the dict
            # Re-serialize parts to ensure consistency
            if isinstance(result["parts"], list):
                result["parts"] = [_serialize_message_part(part) for part in result["parts"] if part]
            return result

        # Handle simple dict format
        result: Dict[str, Any] = {}

        # Preserve basic message fields
        for field in ["role", "content", "kind", "timestamp"]:
            if field in message:
                result[field] = message[field]

        # Preserve tool call information if present
        if "tool_calls" in message:
            result["tool_calls"] = _serialize_tool_calls(message["tool_calls"])

        if result:
            return result

        # Fallback: keep shallow copy of JSON-serializable items
        filtered: Dict[str, Any] = {}
        for k, v in message.items():
            if _is_sensitive_field(k):
                continue
            try:
                json.dumps(v)
                filtered[k] = v
            except Exception:
                filtered[k] = str(v)
        return filtered

    # Handle pydantic-ai message objects with parts
    if hasattr(message, "parts") and hasattr(message, "kind"):
        result = {
            "kind": getattr(message, "kind", "unknown"),
            "parts": []
        }

        # Add timestamp if available
        if hasattr(message, "timestamp"):
            result["timestamp"] = getattr(message, "timestamp", None)

        # Serialize each part
        for part in message.parts:
            serialized_part = _serialize_message_part(part)
            if serialized_part:
                result["parts"].append(serialized_part)

        return result

    # Simple primitives
    try:
        json.dumps(message)
        return cast(Dict[str, Any], message)
    except Exception:
        pass

    # Object fallback
    if hasattr(message, "role") or hasattr(message, "content"):
        result = {}
        if hasattr(message, "role"):
            result["role"] = getattr(message, "role", None)
        if hasattr(message, "content"):
            result["content"] = getattr(message, "content", None)
        return result

    return {"content": str(message)}


def _collect_essential_state(state: SessionState) -> Dict[str, Any]:
    """Extract essential fields from SessionState for persistence."""
    # SessionState is a dataclass; convert safely
    obj: Dict[str, Any] = asdict(state)

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

    Regenerates session ID with auto-description from current messages.
    Returns the path to the saved file.
    """
    # Regenerate session ID with current messages for better description
    if state_manager.session.messages:
        # Extract serialized messages for description generation
        serialized_messages = [_serialize_message(m) for m in state_manager.session.messages]
        new_session_id = generate_user_friendly_session_id(serialized_messages)
        state_manager.session.session_id = new_session_id

    # Get session directory after potential ID update
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
    session_dir = home / SESSIONS_SUBDIR / session_id
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


def list_saved_sessions(limit: int = 50) -> List[Dict[str, Any]]:
    """List saved sessions by last modified time (desc).

    Returns a list of entries: {session_id, path, mtime, model, message_count}.
    Ignores corrupted JSON entries without failing.
    """
    base = get_tunacode_home() / SESSIONS_SUBDIR
    if not base.exists():
        return []

    entries: List[Dict[str, Any]] = []
    for child in base.iterdir():
        if not child.is_dir():
            continue
        sid = child.name
        state_file = child / SESSION_FILENAME
        if not state_file.exists():
            continue
        try:
            st = state_file.stat()
            model = None
            message_count = None
            last_preview: Optional[str] = None
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    model = data.get("current_model")
                    msgs = data.get("messages")
                    if isinstance(msgs, list):
                        message_count = len(msgs)
                        if msgs:
                            last = msgs[-1]
                            if isinstance(last, dict) and "content" in last:
                                raw = last.get("content")
                            else:
                                raw = last
                            text = str(raw) if raw is not None else ""
                            # Collapse whitespace and trim
                            text = " ".join(text.split())
                            if len(text) > 80:
                                text = text[:77] + "..."
                            last_preview = text or None
            except Exception:
                # Skip metadata extraction but still list the session
                pass
            entries.append(
                {
                    "session_id": sid,
                    "path": str(state_file),
                    "mtime": st.st_mtime,
                    "model": model,
                    "message_count": message_count,
                    "last_message": last_preview,
                }
            )
        except OSError:
            # Skip unreadable entries
            continue

    # Sort by most recent first
    entries.sort(key=lambda e: cast(float, e.get("mtime", 0.0)), reverse=True)
    return entries[: max(0, limit)]
