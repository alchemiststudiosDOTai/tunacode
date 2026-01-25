from __future__ import annotations

from pydantic_ai.messages import UserPromptPart

from tunacode.types import ModelRequest, StateManagerProtocol, ToolConfirmationResponse, ToolName

MODEL_REQUEST_KIND: str = "request"
USER_PROMPT_PART_KIND: str = "user-prompt"


class ToolRejectionNotifier:
    """Handle agent notification when tool execution is rejected."""

    def notify_rejection(
        self,
        tool_name: ToolName,
        response: ToolConfirmationResponse,
        state: StateManagerProtocol,
    ) -> None:
        guidance = getattr(response, "instructions", "").strip()
        if guidance:
            guidance_section = f"User guidance:\n{guidance}"
        else:
            guidance_section = "User cancelled without additional instructions."

        cancellation_message = (
            f"Tool '{tool_name}' execution cancelled before running.\n"
            f"{guidance_section}\n"
            "Do not assume the operation succeeded; "
            "request updated guidance or offer alternatives."
        )

        user_prompt_part = UserPromptPart(
            content=cancellation_message,
            part_kind=USER_PROMPT_PART_KIND,
        )
        state.session.conversation.messages.append(
            ModelRequest(parts=[user_prompt_part], kind=MODEL_REQUEST_KIND)
        )
        state.session.update_token_count()
