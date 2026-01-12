"""Message recording helpers for agent node processing."""

from typing import Any

from tunacode.core.state import SessionState

THOUGHT_MESSAGE_KEY = "thought"


def record_request(session: SessionState, request: Any) -> None:
    """Append the request message to session history."""
    session.messages.append(request)


def record_thought(session: SessionState, thought: str) -> None:
    """Append the assistant thought to session history."""
    thought_message = {THOUGHT_MESSAGE_KEY: thought}
    session.messages.append(thought_message)


def record_model_response(session: SessionState, response: Any) -> None:
    """Append the model response to session history."""
    session.messages.append(response)
