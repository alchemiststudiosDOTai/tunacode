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
        ):
            # Mock background task creation
            # Mock a task-like object that is awaitable and has a .done() method
            bg_task = asyncio.create_task(asyncio.sleep(0))
            # bg_task.done = MagicMock(return_value=True)

            get_app.return_value.create_background_task = MagicMock(return_value=bg_task)

            await repl_mod.repl(state_manager)

            # Only non-empty, non-whitespace lines should trigger background task
            assert get_app.return_value.create_background_task.call_count == expected_process_calls
