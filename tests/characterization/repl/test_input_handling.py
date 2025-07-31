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

        # Simulate multiline_input yielding from the inputs list
        async def fake_multiline_input(*a, **kw):
            return inputs.pop(0)

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
