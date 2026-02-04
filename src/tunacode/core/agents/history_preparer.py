"""Message history preparation for agent requests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tunacode.core.agents.resume import log_message_history_debug, prune_old_tool_outputs
from tunacode.core.agents.resume.sanitize import (
    run_cleanup_loop,
    sanitize_history_for_resume,
)

from .request_logger import (
    log_history_state,
    log_sanitized_history_state,
)

if TYPE_CHECKING:
    from tunacode.types import ModelName

    from tunacode.core.types import StateManagerProtocol


class HistoryPreparer:
    """Prepares and sanitizes message history for agent runs."""

    def __init__(
        self,
        state_manager: StateManagerProtocol,
        model: ModelName,
        message: str,
    ) -> None:
        self.state_manager = state_manager
        self.model = model
        self.message = message

    def prepare(self, logger: Any) -> tuple[list[Any], bool, int]:
        """Prepare and sanitize message history for the next agent run.

        Returns:
            Tuple of (message_history, debug_mode, baseline_message_count)
        """
        session = self.state_manager.session
        conversation = session.conversation
        runtime = session.runtime

        session_messages = conversation.messages
        tool_registry = runtime.tool_registry

        self._log_pruned_tool_outputs(session_messages, logger)

        debug_mode = bool(getattr(session, "debug_mode", False))

        _, dangling_tool_call_ids = run_cleanup_loop(session_messages, tool_registry)

        self._drop_trailing_request_if_needed(session_messages, logger)

        if debug_mode:
            log_message_history_debug(
                session_messages,
                self.message,
                dangling_tool_call_ids,
            )

        baseline_message_count = len(session_messages)
        log_history_state(session_messages, baseline_message_count, logger)

        message_history = sanitize_history_for_resume(session_messages)
        log_sanitized_history_state(message_history, debug_mode, logger)

        return message_history, debug_mode, baseline_message_count

    def _log_pruned_tool_outputs(self, session_messages: list[Any], logger: Any) -> None:
        """Prune old tool outputs and log reclaimed tokens."""
        _, tokens_reclaimed = prune_old_tool_outputs(session_messages, self.model)
        if tokens_reclaimed <= 0:
            return
        logger.lifecycle(f"History pruned ({tokens_reclaimed} tokens reclaimed)")

    def _drop_trailing_request_if_needed(
        self,
        session_messages: list[Any],
        logger: Any,
    ) -> bool:
        """Remove a trailing request if we are about to enqueue a new one."""
        if not session_messages or not self.message:
            return False

        last_msg = session_messages[-1]
        last_kind = getattr(last_msg, "kind", None)
        if isinstance(last_msg, dict):
            last_kind = last_msg.get("kind")

        if last_kind != "request":
            return False

        logger.lifecycle("Dropping trailing request to avoid consecutive requests")
        session_messages.pop()
        return True
