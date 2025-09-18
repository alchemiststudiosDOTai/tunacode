"""Validation utilities for ensuring tool-call/return consistency."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from tunacode.core.agents.agent_components.message_handler import patch_tool_messages
from tunacode.core.logging.logger import get_logger
from tunacode.core.state import StateManager

logger = get_logger(__name__)


@dataclass(frozen=True)
class OrphanToolCall:
    """Snapshot of a tool call that lacks a corresponding return."""

    tool_call_id: str
    tool_name: str


class ToolExecutionValidator:
    """Detect and optionally reconcile orphaned tool calls."""

    def __init__(self, state_manager: StateManager) -> None:
        self._state_manager = state_manager

    def find_orphaned_calls(self) -> List[OrphanToolCall]:
        """Return orphaned tool calls present in the session history."""
        session = self._state_manager.session
        messages = getattr(session, "messages", [])
        if not messages:
            return []

        seen_calls: dict[str, str] = {}
        returns: set[str] = set()
        retry_prompts: set[str] = set()

        for message in messages:
            parts: Iterable[object] = getattr(message, "parts", []) or []
            for part in parts:
                part_kind = getattr(part, "part_kind", "")
                tool_call_id = getattr(part, "tool_call_id", None)
                if not tool_call_id:
                    continue

                if part_kind == "tool-call":
                    seen_calls[tool_call_id] = getattr(part, "tool_name", "tool")
                elif part_kind == "tool-return":
                    returns.add(tool_call_id)
                elif part_kind == "retry-prompt":
                    retry_prompts.add(tool_call_id)

        orphaned: List[OrphanToolCall] = []
        for tool_call_id, tool_name in seen_calls.items():
            if tool_call_id not in returns and tool_call_id not in retry_prompts:
                orphaned.append(OrphanToolCall(tool_call_id=tool_call_id, tool_name=tool_name))

        return orphaned

    def reconcile_orphans(
        self,
        *,
        origin: str,
        error_message: Optional[str] = None,
    ) -> Tuple[bool, List[OrphanToolCall]]:
        """
        Ensure orphaned tool calls have synthetic responses.

        Returns:
            A tuple of (patched, orphaned_calls) where patched indicates whether synthetic
            responses were generated.
        """

        orphaned_calls = self.find_orphaned_calls()
        if not orphaned_calls:
            return False, []

        message = error_message or (
            "Buffered tool execution did not produce a return before retry; "
            "responding with synthetic error (origin: {origin})."
        ).format(origin=origin)

        logger.warning(
            "Orphaned tool calls detected (origin=%s): %s",
            origin,
            ", ".join(str(call.tool_call_id) for call in orphaned_calls),
        )

        patch_tool_messages(message, state_manager=self._state_manager)
        return True, orphaned_calls
