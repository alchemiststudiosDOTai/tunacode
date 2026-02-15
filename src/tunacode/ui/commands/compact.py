"""Manual /compact command for context compaction."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from tinyagent.agent_types import AgentMessage

from tunacode.core.compaction.controller import (
    apply_compaction_messages,
    get_or_create_compaction_controller,
)
from tunacode.core.compaction.types import COMPACTION_STATUS_COMPACTED
from tunacode.core.ui_api.messaging import estimate_messages_tokens

from tunacode.ui.commands.base import Command

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp

COMPACT_USAGE_HINT = "Usage: /compact"
COMPACT_EMPTY_HISTORY_NOTICE = "Nothing to compact."
COMPACT_COMPLETE_TEMPLATE = "Compaction complete: {removed} messages, ~{tokens} tokens reclaimed"


class CompactCommand(Command):
    """Slash command that forces immediate context compaction."""

    name = "compact"
    description = "Summarize old context and keep recent messages"
    usage = "/compact"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        if args.strip():
            app.notify(COMPACT_USAGE_HINT, severity="warning")
            return

        session = app.state_manager.session
        conversation = session.conversation

        try:
            history = _coerce_history(conversation.messages)
        except TypeError as exc:
            app.notify(str(exc), severity="error")
            return

        if not history:
            app.notify(COMPACT_EMPTY_HISTORY_NOTICE)
            return

        controller = get_or_create_compaction_controller(app.state_manager)
        controller.reset_request_state()
        controller.set_status_callback(app._update_compaction_status)

        tokens_before = estimate_messages_tokens(history)
        compaction_outcome = await controller.force_compact(
            history,
            max_tokens=conversation.max_tokens,
            signal=None,
        )
        compacted_history = apply_compaction_messages(
            app.state_manager,
            compaction_outcome.messages,
        )

        app._update_compaction_status(False)
        app._update_resource_bar()
        await app.state_manager.save_session()

        if compaction_outcome.status != COMPACTION_STATUS_COMPACTED:
            app.notify(
                f"Compaction skipped: {compaction_outcome.reason}",
                severity="warning",
            )
            return

        removed_count = len(history) - len(compacted_history)
        tokens_after = estimate_messages_tokens(compacted_history)
        reclaimed_tokens = max(0, tokens_before - tokens_after)
        app.notify(
            COMPACT_COMPLETE_TEMPLATE.format(
                removed=removed_count,
                tokens=reclaimed_tokens,
            )
        )


def _coerce_history(messages: list[AgentMessage]) -> list[dict[str, Any]]:
    if all(isinstance(message, dict) for message in messages):
        return [cast(dict[str, Any], message) for message in messages]

    raise TypeError("Session history is not in tinyagent dict format")
