"""Message handling utilities for agent communication."""


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
