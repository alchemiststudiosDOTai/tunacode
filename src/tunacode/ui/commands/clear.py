"""Clear command for resetting active agent working state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tunacode.core.ui_api.shared_types import UsageMetrics

from tunacode.ui.commands.base import Command

if TYPE_CHECKING:
    from tunacode.ui.app import TextualReplApp


class ClearCommand(Command):
    """Clear transient agent state used during command execution."""

    name = "clear"
    description = "Clear agent working state (UI, thoughts)"

    async def execute(self, app: TextualReplApp, args: str) -> None:
        session = app.state_manager.session

        app.rich_log.clear()

        # PRESERVE messages - needed for /resume
        # PRESERVE total_tokens - represents conversation size
        session.conversation.thoughts = []
        session.runtime.tool_registry.clear()
        session.conversation.files_in_context = set()

        session.runtime.iteration_count = 0
        session.runtime.current_iteration = 0
        session.runtime.consecutive_empty_responses = 0
        session.runtime.batch_counter = 0

        session.runtime.request_id = ""
        session.task.original_query = ""
        session.runtime.operation_cancelled = False

        session._debug_events = []
        session._debug_raw_stream_accum = ""

        session.usage.last_call_usage = UsageMetrics()
        # Keep session_total_usage - tracks lifetime session cost

        app.state_manager.reset_recursive_state()
        app.reset_context_panel_state()

        app._update_resource_bar()
        app.notify("Cleared agent state (messages preserved for /resume)")
        await app.state_manager.save_session()
