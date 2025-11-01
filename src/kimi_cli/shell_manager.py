"""
Persistent shell session manager for Kimi CLI.

This module provides the ShellManager class which manages a persistent bash subprocess
that maintains state (working directory, environment variables) across multiple command
executions within an agent session.
"""

import asyncio
from dataclasses import dataclass

from kimi_cli.utils.logging import logger


@dataclass
class PersistentShellConfig:
    """Configuration for persistent shell sessions."""

    enabled: bool = True
    """Whether persistent shell sessions are enabled."""

    shell_executable: str = "/bin/bash"
    """Path to the shell executable."""

    shell_args: list[str] | None = None
    """Arguments to pass to the shell. Defaults to ['--noprofile', '--norc']."""

    command_timeout: int = 60
    """Default timeout for command execution in seconds."""

    exit_code_sentinel: str = "___KIMI_EXIT_"
    """Sentinel pattern used to detect command exit codes."""

    def __post_init__(self):
        """Set default shell arguments if not provided."""
        if self.shell_args is None:
            self.shell_args = ["--noprofile", "--norc"]


@dataclass
class ShellSession:
    """Represents a single persistent shell session."""

    process: asyncio.subprocess.Process
    """The subprocess running the shell."""

    cwd: str
    """Current working directory of the shell."""

    env: dict[str, str]
    """Environment variables in the shell."""


class ShellManager:
    """
    Manages persistent shell sessions.

    The ShellManager maintains a long-running bash subprocess that persists
    state across multiple command executions. This allows commands to modify
    the environment (cd, export, etc.) and have those changes persist for
    subsequent commands.

    Example:
        ```python
        config = PersistentShellConfig(enabled=True)
        manager = ShellManager(config)

        # Commands persist state
        await manager.execute("cd /tmp")
        await manager.execute("export FOO=bar")
        # Next command sees both changes

        await manager.cleanup()
        ```
    """

    def __init__(self, config: PersistentShellConfig):
        """
        Initialize the ShellManager.

        Args:
            config: Configuration for persistent shell behavior.
        """
        self._config = config
        self._session: ShellSession | None = None
        logger.debug("ShellManager initialized with config: {config}", config=config)

    async def cleanup(self):
        """
        Cleanup all shell sessions.

        This method gracefully terminates the shell subprocess, waiting for
        clean shutdown before forcing termination if necessary.
        """
        if self._session is None:
            logger.debug("No active shell session to cleanup")
            return

        logger.info("Cleaning up shell session")
        # Implementation to be added in Task 1.5
        pass
