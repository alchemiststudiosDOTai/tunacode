from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import tunacode.cli.repl as repl_mod
from tunacode.constants import UI_COLORS


@pytest.mark.asyncio
async def test_repl_initialization_basic(monkeypatch):
    """Test REPL startup: prints model, success, and line, and initializes agent/session."""

    # Mock StateManager and session
    state_manager = MagicMock()
    state_manager.session.current_model = "gpt-test"
    state_manager.session.input_sessions = {}
    state_manager.session.show_thoughts = True  # Enable thoughts to see startup messages
    state_manager.session.total_tokens = 0
    state_manager.session.max_tokens = 200000
    state_manager.session.user_config = {"context_window_size": 200000}

    def mock_update_token_count():
        state_manager.session.total_tokens = 100

    state_manager.session.update_token_count = MagicMock(side_effect=mock_update_token_count)

    # Patch UI methods
    with (
        patch.object(repl_mod.ui, "muted", new=AsyncMock()) as muted,
        patch.object(repl_mod.ui, "success", new=AsyncMock()) as success,
        patch.object(repl_mod.ui, "line", new=AsyncMock()),
        patch.object(repl_mod.agent, "get_or_create_agent") as get_agent,
    ):
        # Mock agent instance and MCP context
        agent_instance = MagicMock()
        mcp_context = AsyncMock()
        mcp_context.__aenter__ = AsyncMock(return_value=None)
        mcp_context.__aexit__ = AsyncMock(return_value=None)
        agent_instance.run_mcp_servers = MagicMock(return_value=mcp_context)
        get_agent.return_value = agent_instance

        # Patch the REPL loop to exit immediately
        async def fake_multiline_input(*a, **kw):
            return "exit"

        with (
            patch.object(repl_mod.ui, "multiline_input", new=fake_multiline_input),
            patch.object(repl_mod.ui, "info", new=AsyncMock()) as info,
        ):
            await repl_mod.repl(state_manager)

    # Check that startup UI was called since show_thoughts is True
    muted.assert_any_await(
        f"• Model: gpt-test • [b]Context:[/] [{UI_COLORS['success']}]100/200,000 (0%)[/]"
    )
    success.assert_awaited()
    get_agent.assert_called_once_with("gpt-test", state_manager)
    info.assert_awaited_with("Session ended. Happy coding!")


@pytest.mark.asyncio
async def test_repl_initialization_no_thoughts_no_startup_messages(monkeypatch):
    """Test REPL startup: no startup messages shown when show_thoughts is False."""

    # Mock StateManager and session
    state_manager = MagicMock()
    state_manager.session.current_model = "gpt-test"
    state_manager.session.input_sessions = {}
    state_manager.session.show_thoughts = False  # Disable thoughts
    state_manager.session.total_tokens = 0
    state_manager.session.max_tokens = 200000
    state_manager.session.user_config = {"context_window_size": 200000}
    state_manager.session._startup_shown = True  # Simulate not first run

    def mock_update_token_count():
        state_manager.session.total_tokens = 100

    state_manager.session.update_token_count = MagicMock(side_effect=mock_update_token_count)

    # Patch UI methods
    with (
        patch.object(repl_mod.ui, "muted", new=AsyncMock()) as muted,
        patch.object(repl_mod.ui, "success", new=AsyncMock()) as success,
        patch.object(repl_mod.ui, "line", new=AsyncMock()),
        patch.object(repl_mod.agent, "get_or_create_agent") as get_agent,
    ):
        # Mock agent instance and MCP context
        agent_instance = MagicMock()
        mcp_context = AsyncMock()
        mcp_context.__aenter__ = AsyncMock(return_value=None)
        mcp_context.__aexit__ = AsyncMock(return_value=None)
        agent_instance.run_mcp_servers = MagicMock(return_value=mcp_context)
        get_agent.return_value = agent_instance

        # Patch the REPL loop to exit immediately
        async def fake_multiline_input(*a, **kw):
            return "exit"

        with (
            patch.object(repl_mod.ui, "multiline_input", new=fake_multiline_input),
            patch.object(repl_mod.ui, "info", new=AsyncMock()) as info,
        ):
            await repl_mod.repl(state_manager)

    # Check that startup UI was NOT called since show_thoughts is False and not first run
    assert not any("Model:" in str(call) for call in muted.await_args_list), (
        "Startup model message should not be shown when show_thoughts is False"
    )
    assert not any("Ready to assist" in str(call) for call in success.await_args_list), (
        "Startup success message should not be shown when show_thoughts is False"
    )

    get_agent.assert_called_once_with("gpt-test", state_manager)
    info.assert_awaited_with("Session ended. Happy coding!")
