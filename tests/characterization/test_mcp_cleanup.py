"""
Tests for MCP server cache cleanup functionality.

Tests: src/tunacode/services/mcp.py
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tunacode.services.mcp import (
    MCPServerStdio,
    cleanup_mcp_servers,
    get_mcp_servers,
    register_mcp_agent,
)
from tunacode.exceptions import MCPError


class TestMCPServerCleanup:
    """Test suite for MCP server cache cleanup."""

    @pytest.fixture
    def mock_state_manager(self):
        """Create a mock state manager with MCP server configuration."""
        mock_sm = MagicMock()
        mock_sm.session.user_config = {
            "mcpServers": {
                "test-server": {
                    "command": "echo",
                    "args": ["test"],
                },
                "another-server": {
                    "command": "cat",
                    "args": ["/dev/null"],
                },
            }
        }
        return mock_sm

    @pytest.fixture
    def empty_state_manager(self):
        """Create a mock state manager with no MCP servers."""
        mock_sm = MagicMock()
        mock_sm.session.user_config = {"mcpServers": {}}
        return mock_sm

    @pytest.mark.asyncio
    async def test_cleanup_mcp_servers_all(self):
        """Test cleanup of all MCP servers."""
        # Setup: Add mock servers to cache
        with patch("tunacode.services.mcp._MCP_SERVER_CACHE", {"test1": MagicMock(), "test2": MagicMock()}):
            with patch("tunacode.services.mcp._MCP_SERVER_AGENTS", {"test1": MagicMock(), "test2": MagicMock()}):
                with patch("tunacode.services.mcp._cleanup_single_server") as mock_cleanup:
                    await cleanup_mcp_servers()

                    # Should call cleanup for both servers
                    assert mock_cleanup.call_count == 2
                    mock_cleanup.assert_any_call("test1")
                    mock_cleanup.assert_any_call("test2")

    @pytest.mark.asyncio
    async def test_cleanup_mcp_servers_specific(self):
        """Test cleanup of specific MCP servers."""
        # Setup: Add mock servers to cache
        with patch("tunacode.services.mcp._MCP_SERVER_CACHE", {"test1": MagicMock(), "test2": MagicMock(), "test3": MagicMock()}):
            with patch("tunacode.services.mcp._MCP_SERVER_AGENTS", {"test1": MagicMock(), "test2": MagicMock(), "test3": MagicMock()}):
                with patch("tunacode.services.mcp._cleanup_single_server") as mock_cleanup:
                    await cleanup_mcp_servers(["test1", "test3"])

                    # Should call cleanup only for specified servers
                    assert mock_cleanup.call_count == 2
                    mock_cleanup.assert_any_call("test1")
                    mock_cleanup.assert_any_call("test3")
                    # Verify test2 was not called by checking all call arguments
                    call_args = [call[0][0] for call in mock_cleanup.call_args_list]
                    assert "test2" not in call_args

    @pytest.mark.asyncio
    async def test_cleanup_single_server_with_agent(self):
        """Test cleanup of a single server that has an associated agent."""
        mock_server = MagicMock()
        mock_agent = MagicMock()

        with patch("tunacode.services.mcp._MCP_SERVER_CACHE", {"test-server": mock_server}):
            with patch("tunacode.services.mcp._MCP_SERVER_AGENTS", {"test-server": mock_agent}):
                await cleanup_mcp_servers(["test-server"])

                # Verify caches are cleared
                from tunacode.services.mcp import _MCP_SERVER_CACHE, _MCP_SERVER_AGENTS
                assert "test-server" not in _MCP_SERVER_CACHE
                assert "test-server" not in _MCP_SERVER_AGENTS

    @pytest.mark.asyncio
    async def test_cleanup_handles_exceptions_gracefully(self):
        """Test that cleanup handles exceptions gracefully."""
        with patch("tunacode.services.mcp._MCP_SERVER_CACHE", {"test1": MagicMock()}):
            with patch("tunacode.services.mcp._MCP_SERVER_AGENTS", {"test1": MagicMock()}):
                with patch("tunacode.services.mcp._cleanup_single_server", side_effect=Exception("Test error")):
                    # Should not raise exception
                    await cleanup_mcp_servers()

                    # Cache should still be cleared despite error
                    from tunacode.services.mcp import _MCP_SERVER_CACHE
                    assert len(_MCP_SERVER_CACHE) == 0

    def test_register_mcp_agent(self):
        """Test registering an agent for MCP cleanup tracking."""
        mock_agent = MagicMock()

        with patch("tunacode.services.mcp._MCP_SERVER_AGENTS", {}):
            register_mcp_agent("test-server", mock_agent)

            from tunacode.services.mcp import _MCP_SERVER_AGENTS
            assert _MCP_SERVER_AGENTS["test-server"] == mock_agent

    def test_get_mcp_servers_caching(self, mock_state_manager):
        """Test that get_mcp_servers properly caches server instances."""
        # Clear any existing cache
        with patch("tunacode.services.mcp._MCP_SERVER_CACHE", {}):
            with patch("tunacode.services.mcp._MCP_CONFIG_HASH", None):
                with patch("tunacode.services.mcp.MCPServerStdio") as mock_server_class:
                    mock_server = MagicMock()
                    mock_server_class.return_value = mock_server

                    # First call should create new instances
                    servers1 = get_mcp_servers(mock_state_manager)
                    assert len(servers1) == 2
                    assert mock_server_class.call_count == 2

                    # Second call should return cached instances
                    servers2 = get_mcp_servers(mock_state_manager)
                    assert len(servers2) == 2
                    assert mock_server_class.call_count == 2  # No new instances created
                    # Should contain the same server instances (not the same list object)
                    assert servers1[0] is servers2[0]
                    assert servers1[1] is servers2[1]

    def test_get_mcp_servers_config_change_cleanup(self, mock_state_manager):
        """Test that configuration changes trigger cleanup of removed servers."""
        # Initial config
        initial_servers = mock_state_manager.session.user_config["mcpServers"]

        with patch("tunacode.services.mcp._MCP_SERVER_CACHE", {"old-server": MagicMock()}):
            with patch("tunacode.services.mcp._MCP_CONFIG_HASH", 12345):  # Different hash
                with patch("tunacode.services.mcp.MCPServerStdio") as mock_server_class:
                    mock_server = MagicMock()
                    mock_server_class.return_value = mock_server
                    with patch("asyncio.get_event_loop") as mock_get_loop:
                        mock_loop = MagicMock()
                        mock_get_loop.return_value = mock_loop

                        # This should detect config change and cleanup old server
                        get_mcp_servers(mock_state_manager)

                        # Should schedule cleanup for removed server
                        mock_loop.create_task.assert_called_once()
                        cleanup_call = mock_loop.create_task.call_args[0][0]

                        # Verify the cleanup call is for the removed server
                        assert asyncio.iscoroutine(cleanup_call)

    def test_get_mcp_servers_handles_creation_error(self, mock_state_manager):
        """Test that get_mcp_servers handles server creation errors properly."""
        with patch("tunacode.services.mcp.MCPServerStdio", side_effect=Exception("Creation failed")):
            with pytest.raises(MCPError) as exc_info:
                get_mcp_servers(mock_state_manager)

            assert "Failed to create MCP server" in str(exc_info.value)
            assert "test-server" in str(exc_info.value.server_name)

    def test_get_mcp_servers_empty_config(self, empty_state_manager):
        """Test get_mcp_servers with empty configuration."""
        with patch("tunacode.services.mcp._MCP_SERVER_CACHE", {}):
            servers = get_mcp_servers(empty_state_manager)
            assert servers == []

    @pytest.mark.asyncio
    async def test_cleanup_integration_with_config_changes(self):
        """Test integration between config changes and cleanup."""
        mock_sm = MagicMock()

        # First configuration
        mock_sm.session.user_config = {
            "mcpServers": {
                "server1": {"command": "echo", "args": ["1"]},
                "server2": {"command": "echo", "args": ["2"]},
            }
        }

        with patch("tunacode.services.mcp._MCP_SERVER_CACHE", {}):
            with patch("tunacode.services.mcp._MCP_CONFIG_HASH", None):
                with patch("tunacode.services.mcp.MCPServerStdio") as mock_server_class:
                    mock_server = MagicMock()
                    mock_server_class.return_value = mock_server

                    # Create initial servers
                    servers1 = get_mcp_servers(mock_sm)
                    assert len(servers1) == 2

                    # Change configuration - remove server2
                    mock_sm.session.user_config = {
                        "mcpServers": {
                            "server1": {"command": "echo", "args": ["1"]},
                        }
                    }

                    with patch("asyncio.get_event_loop") as mock_get_loop:
                        mock_loop = MagicMock()
                        mock_get_loop.return_value = mock_loop

                        # This should detect removal and schedule cleanup
                        servers2 = get_mcp_servers(mock_sm)
                        assert len(servers2) == 1

                        # Should have scheduled cleanup for removed server
                        mock_loop.create_task.assert_called_once()