import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import tunacode.cli.repl as repl_mod


@pytest.mark.asyncio
async def test_repl_multiline_input_handling():
    """Test that REPL processes multiline input as a single message."""

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

        # Simulate multiline_input returning a multi-line string, then "exit"
        inputs = ["first line\nsecond line\nthird line", "exit"]

        async def fake_multiline_input(*a, **kw):
            return inputs.pop(0)

        with (
            patch.object(repl_mod.ui, "multiline_input", new=fake_multiline_input),
            patch("tunacode.cli.repl.get_app") as get_app,
            patch("tunacode.cli.repl.process_request", new=AsyncMock()),
        ):
            # Use AsyncMock to properly handle the coroutine passed to create_background_task
            def mock_create_background_task(coro):
                # Create a task that properly handles the coroutine to avoid RuntimeWarning
                task = asyncio.create_task(coro)
                return task

            get_app.return_value.create_background_task = MagicMock(
                side_effect=mock_create_background_task
            )

            await repl_mod.repl(state_manager)

            # The multi-line input should be processed as a single message
            get_app.return_value.create_background_task.assert_called_once()
