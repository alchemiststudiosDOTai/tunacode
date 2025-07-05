"""Utilities for processing message history."""


def get_message_content(message: any) -> str:
    """Extracts the content from a message object of any type."""
    if isinstance(message, str):
        return message
    if isinstance(message, dict):
        if "content" in message:
            return message["content"]
        if "thought" in message:
            return message["thought"]
    if hasattr(message, "content"):
        return message.content
    if hasattr(message, "parts"):
        return " ".join(get_message_content(part) for part in message.parts)
    return ""
