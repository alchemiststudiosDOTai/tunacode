"""Message handling utilities for agent communication."""

from typing import Any


def get_model_messages() -> tuple[Any, Any, Any]:
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

        class SystemPromptPart:
            def __init__(self, content: str = "", role: str = "system", part_kind: str = ""):
                self.content = content
                self.role = role
                self.part_kind = part_kind

        system_prompt_part_cls: Any = SystemPromptPart
    else:
        system_prompt_part_cls = messages.SystemPromptPart

    return ModelRequest, ToolReturnPart, system_prompt_part_cls
