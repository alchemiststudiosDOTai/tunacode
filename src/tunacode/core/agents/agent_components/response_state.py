"""Response state management for tracking agent processing state."""

from dataclasses import dataclass


@dataclass
class ResponseState:
    """Track state across agent response processing."""

    has_user_response: bool = False
    task_completed: bool = False
    awaiting_user_guidance: bool = False
    has_final_synthesis: bool = False
    stream_cancelled: bool = False
