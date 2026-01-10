"""
Timeout pause state for coordinating timeout pauses during user interaction.

When the agent is waiting for user input (tool confirmation, plan approval),
the global timeout clock should pause. This module provides the shared state
and context manager for coordinating this pause behavior between the agent
and UI layers.
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass


@dataclass
class TimeoutPauseState:
    """
    Shared state for tracking whether the global timeout should be paused.

    The UI layer sets is_paused=True when waiting for user input.
    The agent layer checks is_paused and extends the timeout deadline while True.

    Thread-safety: Uses asyncio.Event for safe async coordination.
    """

    _event: asyncio.Event = None

    def __post_init__(self) -> None:
        self._event = asyncio.Event()

    @property
    def is_paused(self) -> bool:
        """Check if timeout is currently paused."""
        return self._event.is_set()

    @asynccontextmanager
    async def timeout_paused(self):
        """
        Context manager that pauses timeout while inside.

        Usage:
            async with pause_state.timeout_paused():
                # Code here doesn't count toward global timeout
                await user_input_future

        The pause flag is automatically cleared on exit, even if an
        exception is raised.
        """
        self._event.set()
        try:
            yield
        finally:
            self._event.clear()
