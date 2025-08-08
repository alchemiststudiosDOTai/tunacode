"""Utilities for processing message history."""

from typing import Any


def get_message_content(message: Any) -> str:
    """Extracts the content from a message object of any type."""
    if isinstance(message, str):
        return message
    if isinstance(message, dict):
        if "content" in message:
            content = message["content"]
            # Handle nested content structures
            if isinstance(content, list):
                return " ".join(get_message_content(item) for item in content)
            return str(content)
        if "thought" in message:
            return str(message["thought"])
    if hasattr(message, "content"):
        content = message.content
        if isinstance(content, list):
            return " ".join(get_message_content(item) for item in content)
        return str(content)
    if hasattr(message, "parts"):
        parts = message.parts
        if isinstance(parts, list):
            return " ".join(get_message_content(part) for part in parts)
        return str(parts)
    return ""
