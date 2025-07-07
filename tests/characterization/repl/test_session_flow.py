from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import tunacode.cli.repl as repl_mod


@pytest.mark.asyncio
async def test_repl_agent_busy_message():
    """Test that REPL shows 'Agent is busy' and skips input when current_task is running."""

    state_manager = MagicMock()
    state_manager.session.current_model = "gpt-test"
    state_manager.session.input_sessions = {}
    state_manager.session.show_thoughts = False
    state_manager.session.total_tokens = 100
    state_manager.session.user_config = {"context_window_size": 200000}

    # Simulate a running background task
    busy_task = MagicMock()
    busy_task.done.return_value = False
    state_manager.session.current_task = busy_task

    with (
        patch("tunacode.ui.console.muted", new=AsyncMock()) as muted,
        patch("tunacode.ui.console.success", new=AsyncMock()),
        patch("tunacode.ui.console.line", new=AsyncMock()),
        patch.object(repl_mod.agent, "get_or_create_agent") as get_agent,
        patch("tunacode.ui.console.info", new=AsyncMock()),
        patch("tunacode.ui.console.warning", new=AsyncMock()),
    ):
        agent_instance = MagicMock()
        mcp_context = AsyncMock()
        mcp_context.__aenter__ = AsyncMock(return_value=None)
        mcp_context.__aexit__ = AsyncMock(return_value=None)
        agent_instance.run_mcp_servers = MagicMock(return_value=mcp_context)
        get_agent.return_value = agent_instance

        # Simulate input: valid input (should be skipped), then "exit"
        inputs = ["do something", "exit"]

        async def fake_multiline_input(*a, **kw):
            return inputs.pop(0)

        with (
            patch("tunacode.ui.console.multiline_input", new=fake_multiline_input),
            patch("tunacode.cli.repl.get_app") as get_app,
        ):
            bg_task = MagicMock()
            bg_task.done.return_value = True
            get_app.return_value.create_background_task = MagicMock(return_value=bg_task)

            await repl_mod.repl(state_manager)

            # Should show busy message and not process the input
            muted.assert_any_await("Agent is busy, press Ctrl+C to interrupt.")
            assert get_app.return_value.create_background_task.call_count == 0


@pytest.mark.asyncio
async def test_repl_session_restart_and_end():
    """Test that REPL restarts session on 'restart' and ends on 'exit'."""

    state_manager = MagicMock()
    state_manager.session.current_model = "gpt-test"
    state_manager.session.input_sessions = {}
    state_manager.session.show_thoughts = False
    state_manager.session.total_tokens = 100
    state_manager.session.user_config = {"context_window_size": 200000}

    with (
        patch("tunacode.ui.console.muted", new=AsyncMock()),
        patch("tunacode.ui.console.success", new=AsyncMock()),
        patch("tunacode.ui.console.line", new=AsyncMock()),
        patch.object(repl_mod.agent, "get_or_create_agent") as get_agent,
        patch("tunacode.ui.console.info", new=AsyncMock()) as info,
        patch("tunacode.ui.console.warning", new=AsyncMock()),
        patch.object(
            repl_mod, "_handle_command", new=AsyncMock(side_effect=["restart", None])
        ) as handle_cmd,
    ):
        agent_instance = MagicMock()
        mcp_context = AsyncMock()
        mcp_context.__aenter__ = AsyncMock(return_value=None)
        mcp_context.__aexit__ = AsyncMock(return_value=None)
        agent_instance.run_mcp_servers = MagicMock(return_value=mcp_context)
        get_agent.return_value = agent_instance

        # Simulate input: "/restart" (should restart), then "exit"
        inputs = ["/restart", "exit"]

        async def fake_multiline_input(*a, **kw):
            return inputs.pop(0)

        with (
            patch("tunacode.ui.console.multiline_input", new=fake_multiline_input),
            patch("tunacode.cli.repl.get_app") as get_app,
        ):
            bg_task = MagicMock()
            bg_task.done.return_value = True
            get_app.return_value.create_background_task = MagicMock(return_value=bg_task)

            await repl_mod.repl(state_manager)

            # Current behavior: only calls _handle_command once because restart breaks loop
            assert handle_cmd.await_count == 1
            info.assert_awaited_with("Session ended. Happy coding!")
