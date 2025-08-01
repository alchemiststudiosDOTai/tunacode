import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import tunacode.cli.repl as repl_mod


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "inputs,expected_process_calls",
    [
        (["", "   ", "exit"], 1),  # Current behavior: empty is skipped but whitespace is processed
        (["hello", "exit"], 1),  # One valid input
        (["", "foo", "   ", "bar", "exit"], 3),  # Current behavior: whitespace counts as input
    ],
)
async def test_repl_input_validation(inputs, expected_process_calls):
    """Test that REPL ignores empty/whitespace and processes valid input."""

    state_manager = MagicMock()
    state_manager.session.current_model = "gpt-test"
    state_manager.session.input_sessions = {}
    state_manager.session.show_thoughts = False
    state_manager.session.user_config = {"context_window_size": 100000}
    state_manager.session.max_tokens = 100000
    state_manager.session.total_tokens = 0
    state_manager.session.update_token_count = MagicMock()
    state_manager.session._startup_shown = True
    state_manager.session.current_task = None
    state_manager.session.spinner = None
    state_manager.session.session_total_usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cost": 0.0,
    }
    state_manager.session.last_call_usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cost": 0.0,
    }

    # Patch UI and agent
    with (
        patch.object(repl_mod.ui, "muted", new=AsyncMock()),
        patch.object(repl_mod.ui, "success", new=AsyncMock()),
        patch.object(repl_mod.ui, "line", new=AsyncMock()),
        patch.object(repl_mod.agent, "get_or_create_agent") as get_agent,
        patch.object(repl_mod.ui, "info", new=AsyncMock()),
        patch.object(repl_mod.ui, "warning", new=AsyncMock()),
    ):
        agent_instance = MagicMock()
        mcp_context = AsyncMock()
        mcp_context.__aenter__ = AsyncMock(return_value=None)
        mcp_context.__aexit__ = AsyncMock(return_value=None)
        agent_instance.run_mcp_servers = MagicMock(return_value=mcp_context)
        get_agent.return_value = agent_instance

        # Track which input we're on
        input_index = [0]

        # Simulate multiline_input yielding from the inputs list
        async def fake_multiline_input(*a, **kw):
            if input_index[0] < len(inputs):
                val = inputs[input_index[0]]
                input_index[0] += 1
                # Give time for background tasks to complete
                await asyncio.sleep(0.01)
                return val
            else:
                raise Exception("No more inputs")

        # Mock process_request to prevent actual processing
        async def mock_process_request(text, state_manager, *args, **kwargs):
            try:
                await asyncio.sleep(0)  # Yield to event loop
            finally:
                # Mimic the real process_request clearing current_task
                state_manager.session.current_task = None

        with (
            patch.object(repl_mod.ui, "multiline_input", new=fake_multiline_input),
            patch("tunacode.cli.repl.get_app") as get_app,
            patch("tunacode.cli.repl.process_request", new=AsyncMock()),
        ):
            # Mock background task creation
            # Use AsyncMock to properly handle the coroutine passed to create_background_task
            def mock_create_background_task(coro):
                # Create a task that properly handles the coroutine to avoid RuntimeWarning
                task = asyncio.create_task(coro)
                return task

            get_app.return_value.create_background_task = MagicMock(
                side_effect=mock_create_background_task
            )

            await repl_mod.repl(state_manager)

            # Only non-empty, non-whitespace lines should trigger background task
            assert get_app.return_value.create_background_task.call_count == expected_process_calls
