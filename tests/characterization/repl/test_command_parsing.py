from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import tunacode.cli.repl as repl_mod


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "command,handle_result,should_restart",
    [
        ("/help", None, False),
        ("/restart", "restart", True),
    ],
)
async def test_repl_command_detection_and_handling(command, handle_result, should_restart):
    """Test that REPL detects commands, calls _handle_command, and handles 'restart'."""

    state_manager = MagicMock()
    state_manager.session.current_model = "gpt-test"
    state_manager.session.input_sessions = {}
    state_manager.session.show_thoughts = False
    state_manager.session.total_tokens = 100
    state_manager.session.user_config = {"context_window_size": 200000}

    # Patch UI and agent
    with (
        patch.object(repl_mod.ui, "muted", new=AsyncMock()),
        patch.object(repl_mod.ui, "success", new=AsyncMock()),
        patch.object(repl_mod.ui, "line", new=AsyncMock()),
        patch.object(repl_mod.agent, "get_or_create_agent") as get_agent,
        patch.object(repl_mod.ui, "info", new=AsyncMock()),
        patch.object(repl_mod.ui, "warning", new=AsyncMock()),
        patch.object(
            repl_mod, "_handle_command", new=AsyncMock(return_value=handle_result)
        ) as handle_cmd,
    ):
        agent_instance = MagicMock()
        # Create a proper async context manager mock
        mcp_context = AsyncMock()
        mcp_context.__aenter__ = AsyncMock(return_value=None)
        mcp_context.__aexit__ = AsyncMock(return_value=None)
        agent_instance.run_mcp_servers = MagicMock(return_value=mcp_context)
        get_agent.return_value = agent_instance

        # Simulate multiline_input yielding the command, then "exit" to end
        inputs = [command, "exit"]

        async def fake_multiline_input(*a, **kw):
            return inputs.pop(0)

        with (
            patch.object(repl_mod.ui, "multiline_input", new=fake_multiline_input),
            patch("tunacode.cli.repl.get_app") as get_app,
        ):
            bg_task = MagicMock()
            bg_task.done.return_value = True
            get_app.return_value.create_background_task = MagicMock(return_value=bg_task)

            await repl_mod.repl(state_manager)

            # _handle_command should be called for the command
            handle_cmd.assert_awaited_with(command, state_manager)
            # No background task should be created for commands
            assert get_app.return_value.create_background_task.call_count == 0
