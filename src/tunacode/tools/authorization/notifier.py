from __future__ import annotations

from typing import TYPE_CHECKING

from tunacode.constants import ToolName
from tunacode.types import ToolConfirmationResponse

if TYPE_CHECKING:
    from tunacode.core.state import StateManager


class ToolRejectionNotifier:
    """Handle agent notification when tool execution is rejected."""

    def notify_rejection(
        self,
        tool_name: ToolName,
        response: ToolConfirmationResponse,
        state: StateManager,
    ) -> None:
        from tunacode.core.agents.agent_components.agent_helpers import create_user_message

        guidance = getattr(response, "instructions", "").strip()
        if guidance:
            guidance_section = f"User guidance:\n{guidance}"
        else:
            guidance_section = "User cancelled without additional instructions."

        message = (
            f"Tool '{tool_name}' execution cancelled before running.\n"
            f"{guidance_section}\n"
            "Do not assume the operation succeeded; "
            "request updated guidance or offer alternatives."
        )

        create_user_message(message, state)
