"""Tests for timeout pause mechanism.

Verifies that the global timeout excludes time spent waiting for user input
(tool confirmations, plan approvals).
"""

import asyncio

import pytest

from tunacode.core.agents.main import wait_for_with_pause
from tunacode.core.agents.timeout_state import TimeoutPauseState


async def test_timeout_pause_state_basics():
    """Test TimeoutPauseState basic functionality."""
    state = TimeoutPauseState()
    assert not state.is_paused, "Initial state should not be paused"

    async with state.timeout_paused():
        assert state.is_paused, "State should be paused inside context"

    assert not state.is_paused, "State should not be paused after context"


async def test_timeout_pause_state_exception_cleanup():
    """Test that pause state is cleared even on exception."""
    state = TimeoutPauseState()

    with pytest.raises(ValueError):
        async with state.timeout_paused():
            assert state.is_paused
            raise ValueError("Test exception")

    assert not state.is_paused, "State should be cleared after exception"


async def test_wait_for_with_pause_extends_deadline():
    """Test that wait_for_with_pause extends deadline during pause."""
    pause_state = TimeoutPauseState()

    async def slow_operation():
        await asyncio.sleep(0.1)
        async with pause_state.timeout_paused():
            await asyncio.sleep(0.3)  # Simulate user taking time
        await asyncio.sleep(0.1)
        return "done"

    # Total time = 0.5s, timeout = 0.3s, but paused 0.3s doesn't count
    result = await wait_for_with_pause(slow_operation(), timeout=0.3, pause_state=pause_state)
    assert result == "done"


async def test_wait_for_with_pause_timeout_when_not_paused():
    """Test that wait_for_with_pause times out when not paused."""
    pause_state = TimeoutPauseState()

    async def slow_operation():
        await asyncio.sleep(0.5)
        return "done"

    # Should timeout because operation takes longer than timeout and no pause
    with pytest.raises(TimeoutError):
        await wait_for_with_pause(slow_operation(), timeout=0.2, pause_state=pause_state)


async def test_wait_for_with_pause_none_timeout():
    """Test that wait_for_with_pause works with None timeout."""
    pause_state = TimeoutPauseState()

    async def operation():
        await asyncio.sleep(0.1)
        return "done"

    # None timeout should work without waiting
    result = await wait_for_with_pause(operation(), timeout=None, pause_state=pause_state)
    assert result == "done"


async def test_wait_for_with_pause_pause_before_timeout():
    """Test that pause extends deadline even when started just before timeout."""
    pause_state = TimeoutPauseState()

    async def operation_with_late_pause():
        await asyncio.sleep(0.2)
        # Start pause just before the 0.3s timeout would expire
        async with pause_state.timeout_paused():
            await asyncio.sleep(0.2)
        await asyncio.sleep(0.1)
        return "done"

    # Without pause, would timeout at 0.3s. With pause, should complete.
    result = await wait_for_with_pause(operation_with_late_pause(), timeout=0.3, pause_state=pause_state)
    assert result == "done"
