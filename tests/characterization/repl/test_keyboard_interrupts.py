from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import tunacode.cli.repl as repl_mod
from tunacode.exceptions import UserAbortError


@pytest.mark.asyncio
async def test_repl_ctrl_c_behavior():
    """Test REPL Ctrl+C (UserAbortError) handling: first warns, second exits."""

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
        patch.object(repl_mod.ui, "info", new=AsyncMock()) as info,
        patch.object(repl_mod.ui, "warning", new=AsyncMock()) as warning,
    ):
        agent_instance = MagicMock()
        mcp_context = AsyncMock()
        mcp_context.__aenter__ = AsyncMock(return_value=None)
        mcp_context.__aexit__ = AsyncMock(return_value=None)
        agent_instance.run_mcp_servers = MagicMock(return_value=mcp_context)
        get_agent.return_value = agent_instance

        # Simulate multiline_input raising UserAbortError twice
        call_count = {"n": 0}

        async def fake_multiline_input(*a, **kw):
            call_count["n"] += 1
            raise UserAbortError()

        with (
            patch.object(repl_mod.ui, "multiline_input", new=fake_multiline_input),
            patch("tunacode.cli.repl.get_app") as get_app,
        ):
            bg_task = MagicMock()
            bg_task.done.return_value = True
            get_app.return_value.create_background_task = MagicMock(return_value=bg_task)

            await repl_mod.repl(state_manager)

            # First Ctrl+C: warning, second: exit/info
            warning.assert_awaited_with("Hit Ctrl+C again to exit")
            info.assert_awaited_with("Session ended. Happy coding!")
            assert call_count["n"] == 2
