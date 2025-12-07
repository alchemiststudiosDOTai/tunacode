"""Message handling utilities for agent communication."""

from datetime import UTC, datetime

from tunacode.core.state import StateManager

ToolCallId = str
ToolName = str
ErrorMessage = str | None


def get_model_messages():
    """
    Safely retrieve message-related classes from pydantic_ai.

    If the running environment (e.g. our test stubs) does not define
    SystemPromptPart we create a minimal placeholder so that the rest of the
    code can continue to work without depending on the real implementation.
    """
    import importlib

    messages = importlib.import_module("pydantic_ai.messages")

    # Get the required classes
    ModelRequest = messages.ModelRequest
    ToolReturnPart = messages.ToolReturnPart

    # Create minimal fallback for SystemPromptPart if it doesn't exist
    if not hasattr(messages, "SystemPromptPart"):

        class SystemPromptPart:  # type: ignore
            def __init__(self, content: str = "", role: str = "system", part_kind: str = ""):
                self.content = content
                self.role = role
                self.part_kind = part_kind
    else:
        SystemPromptPart = messages.SystemPromptPart

    return ModelRequest, ToolReturnPart, SystemPromptPart


def patch_tool_messages(
    error_message: ErrorMessage = "Tool operation failed",
    state_manager: StateManager = None,
):
    """
    Find any tool calls without responses and add synthetic error responses for them.
    Takes an error message to use in the synthesized tool response.

    Ignores tools that have corresponding retry prompts as the model is already
    addressing them.
    """
    if state_manager is None:
        raise ValueError("state_manager is required for patch_tool_messages")

    messages = state_manager.session.messages

    if not messages:
        return

    # Map tool calls to their tool returns
    tool_calls: dict[ToolCallId, ToolName] = {}  # tool_call_id -> tool_name
    tool_returns: set[ToolCallId] = set()  # set of tool_call_ids with returns
    retry_prompts: set[ToolCallId] = set()  # set of tool_call_ids with retry prompts

    for message in messages:
        if hasattr(message, "parts"):
            for part in message.parts:
                if (
                    hasattr(part, "part_kind")
                    and hasattr(part, "tool_call_id")
                    and part.tool_call_id
                ):
                    if part.part_kind == "tool-call":
                        tool_calls[part.tool_call_id] = part.tool_name
                    elif part.part_kind == "tool-return":
                        tool_returns.add(part.tool_call_id)
                    elif part.part_kind == "retry-prompt":
                        retry_prompts.add(part.tool_call_id)

    # Identify orphaned tools (those without responses and not being retried)
    for tool_call_id, tool_name in list(tool_calls.items()):
        if tool_call_id not in tool_returns and tool_call_id not in retry_prompts:
            # Import ModelRequest and ToolReturnPart lazily
            ModelRequest, ToolReturnPart, _ = get_model_messages()
            messages.append(
                ModelRequest(
                    parts=[
                        ToolReturnPart(
                            tool_name=tool_name,
                            content=error_message,
                            tool_call_id=tool_call_id,
                            timestamp=datetime.now(UTC),
                            part_kind="tool-return",
                        )
                    ],
                    kind="request",
                )
            )
