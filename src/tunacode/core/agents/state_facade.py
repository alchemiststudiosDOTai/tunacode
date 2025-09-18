"""Shared state facade helpers for agent request coordination."""

from __future__ import annotations

from typing import Any, Dict

from tunacode.core.logging.logger import get_logger
from tunacode.core.state import StateManager

logger = get_logger(__name__)


class StateFacade:
    """Thin wrapper to centralize session mutations and reads."""

    def __init__(self, state_manager: StateManager) -> None:
        self.sm = state_manager

    # ---- safe getters ----
    def get_setting(self, dotted: str, default: Any) -> Any:
        cfg: Dict[str, Any] = getattr(self.sm.session, "user_config", {}) or {}
        node = cfg
        for key in dotted.split("."):
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    @property
    def show_thoughts(self) -> bool:
        return bool(getattr(self.sm.session, "show_thoughts", False))

    @property
    def messages(self) -> list:
        return list(getattr(self.sm.session, "messages", []))

    # ---- safe setters ----
    def set_request_id(self, req_id: str) -> None:
        try:
            self.sm.session.request_id = req_id
        except AttributeError:
            logger.warning("Session missing 'request_id' attribute; unable to set (req=%s)", req_id)

    def reset_for_new_request(self) -> None:
        """Reset/initialize fields needed for a new run."""
        setattr(self.sm.session, "current_iteration", 0)
        setattr(self.sm.session, "iteration_count", 0)
        setattr(self.sm.session, "tool_calls", [])
        if not hasattr(self.sm.session, "batch_counter"):
            setattr(self.sm.session, "batch_counter", 0)
        setattr(self.sm.session, "consecutive_empty_responses", 0)
        setattr(self.sm.session, "original_query", "")

    def set_original_query_once(self, q: str) -> None:
        if not getattr(self.sm.session, "original_query", None):
            setattr(self.sm.session, "original_query", q)

    # ---- progress helpers ----
    def set_iteration(self, i: int) -> None:
        setattr(self.sm.session, "current_iteration", i)
        setattr(self.sm.session, "iteration_count", i)

    def increment_empty_response(self) -> int:
        value = int(getattr(self.sm.session, "consecutive_empty_responses", 0)) + 1
        setattr(self.sm.session, "consecutive_empty_responses", value)
        return value

    def clear_empty_response(self) -> None:
        setattr(self.sm.session, "consecutive_empty_responses", 0)
