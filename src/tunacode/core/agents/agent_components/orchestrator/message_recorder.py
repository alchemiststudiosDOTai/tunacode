"""Message recording helpers for agent node processing."""

from tunacode.core.state import SessionState


def record_thought(session: SessionState, thought: str) -> None:
    """Persist agent thoughts outside the conversation history."""
    session.thoughts.append(thought)
