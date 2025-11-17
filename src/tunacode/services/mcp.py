"""
Module: sidekick.services.mcp

Provides Model Context Protocol (MCP) server management functionality.
Handles MCP server initialization, configuration validation, and client connections.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator, Dict, List, Optional, Tuple

from pydantic_ai.mcp import MCPServerStdio

from tunacode.exceptions import MCPError
from tunacode.types import MCPServers

if TYPE_CHECKING:
    from mcp.client.stdio import ReadStream, WriteStream
    from pydantic_ai import Agent

    from tunacode.core.state import StateManager

# Module-level cache for MCP server instances
_MCP_SERVER_CACHE: Dict[str, MCPServerStdio] = {}
_MCP_CONFIG_HASH: Optional[int] = None
_MCP_SERVER_AGENTS: Dict[str, "Agent"] = {}

logger = logging.getLogger(__name__)


class QuietMCPServer(MCPServerStdio):
    """A version of ``MCPServerStdio`` that suppresses *all* output coming from the
    MCP server's **stderr** stream.

    We can't just redirect the server's *stdout* because that is where the JSON‑RPC
    protocol messages are sent.  Instead we override ``client_streams`` so we can
    hand our own ``errlog`` (``os.devnull``) to ``mcp.client.stdio.stdio_client``.
    """

    @asynccontextmanager
    async def client_streams(self) -> AsyncIterator[Tuple["ReadStream", "WriteStream"]]:
        """Start the subprocess exactly like the parent class but silence *stderr*."""
        # Local import to avoid cycles
        from mcp.client.stdio import StdioServerParameters, stdio_client

        server_params = StdioServerParameters(
            command=self.command,
            args=list(self.args),
            env=self.env or os.environ,
        )

        # Open ``/dev/null`` for the lifetime of the subprocess so anything the
        # server writes to *stderr* is discarded.
        #
        # This is to help with noisy MCP's that have options for verbosity
        encoding: Optional[str] = getattr(server_params, "encoding", None)
        with open(os.devnull, "w", encoding=encoding) as devnull:
            async with stdio_client(server=server_params, errlog=devnull) as (
                read_stream,
                write_stream,
            ):
                yield read_stream, write_stream


async def cleanup_mcp_servers(server_names: Optional[List[str]] = None) -> None:
    """Clean up MCP server connections and clear cache.

    Args:
        server_names: Optional list of specific server names to clean up.
                     If None, all servers will be cleaned up.
    """
    global _MCP_SERVER_CACHE, _MCP_SERVER_AGENTS

    servers_to_cleanup = server_names or list(_MCP_SERVER_CACHE.keys())

    cleanup_tasks = []
    for server_name in servers_to_cleanup:
        if server_name in _MCP_SERVER_CACHE:
            logger.debug(f"Cleaning up MCP server: {server_name}")
            cleanup_tasks.append(_cleanup_single_server(server_name))

    if cleanup_tasks:
        try:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        except Exception as e:
            logger.warning(f"Error during MCP server cleanup: {e}")

    # Clear caches for cleaned up servers
    if server_names is None:
        # Clear all
        _MCP_SERVER_CACHE.clear()
        _MCP_SERVER_AGENTS.clear()
        logger.debug("Cleared all MCP server caches")
    else:
        # Clear specific servers
        for server_name in server_names:
            _MCP_SERVER_CACHE.pop(server_name, None)
            _MCP_SERVER_AGENTS.pop(server_name, None)
            logger.debug(f"Cleared cache for MCP server: {server_name}")


async def _cleanup_single_server(server_name: str) -> None:
    """Clean up a single MCP server instance.

    Args:
        server_name: Name of the server to clean up
    """
    if server_name not in _MCP_SERVER_CACHE:
        return

    server = _MCP_SERVER_CACHE[server_name]
    agent = _MCP_SERVER_AGENTS.get(server_name)

    try:
        # Use agent's run_mcp_servers context manager if available
        if agent and hasattr(agent, "run_mcp_servers"):
            # The agent should handle proper cleanup via context manager exit
            logger.debug(f"Agent cleanup for {server_name} handled by run_mcp_servers context")
        else:
            # Fallback: try to stop the server subprocess directly
            if hasattr(server, "is_running") and server.is_running:
                # MCPServerStdio doesn't expose direct cleanup, so we log this
                logger.debug(f"MCP server {server_name} is running but no direct cleanup available")
    except Exception as e:
        logger.warning(f"Error cleaning up MCP server {server_name}: {e}")


def register_mcp_agent(server_name: str, agent: "Agent") -> None:
    """Register an agent that manages MCP servers for cleanup tracking.

    Args:
        server_name: Name of the server configuration
        agent: Agent instance that manages the server
    """
    _MCP_SERVER_AGENTS[server_name] = agent
    logger.debug(f"Registered agent for MCP server: {server_name}")


def get_mcp_servers(state_manager: "StateManager") -> List[MCPServerStdio]:
    """Load MCP servers from configuration with caching.

    Args:
        state_manager: The state manager containing user configuration

    Returns:
        List of MCP server instances (cached when possible)

    Raises:
        MCPError: If a server configuration is invalid
    """
    global _MCP_CONFIG_HASH

    mcp_servers: MCPServers = state_manager.session.user_config.get("mcpServers", {})

    # Calculate hash of current config
    current_hash = hash(str(mcp_servers))

    # Check if config has changed
    if _MCP_CONFIG_HASH == current_hash and _MCP_SERVER_CACHE:
        # Return cached servers
        return list(_MCP_SERVER_CACHE.values())

    # Config changed or first load - cleanup old servers and rebuild cache
    if _MCP_CONFIG_HASH is not None and _MCP_SERVER_CACHE:
        # Config changed - schedule cleanup of stale servers
        removed_servers = [name for name in _MCP_SERVER_CACHE.keys() if name not in mcp_servers]
        if removed_servers:
            logger.debug(
                f"Configuration changed, cleaning up removed MCP servers: {removed_servers}"
            )
            # Schedule async cleanup - use asyncio.create_task to avoid blocking
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(cleanup_mcp_servers(removed_servers))
            except RuntimeError:
                # No event loop running, schedule for later
                logger.debug("No event loop available, deferring MCP server cleanup")

    _MCP_SERVER_CACHE.clear()
    _MCP_CONFIG_HASH = current_hash

    loaded_servers: List[MCPServerStdio] = []
    MCPServerStdio.log_level = "critical"

    for server_name, conf in mcp_servers.items():
        try:
            # Check if this server is already cached
            if server_name not in _MCP_SERVER_CACHE:
                # Create new instance
                mcp_instance = MCPServerStdio(**conf)
                _MCP_SERVER_CACHE[server_name] = mcp_instance
                logger.debug(f"Created MCP server instance: {server_name}")

            loaded_servers.append(_MCP_SERVER_CACHE[server_name])
        except Exception as e:
            raise MCPError(
                server_name=server_name,
                message=f"Failed to create MCP server: {str(e)}",
                original_error=e,
            )

    return loaded_servers
