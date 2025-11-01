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

    async def _ensure_session(self) -> ShellSession:
        """
        Ensure a shell session exists, creating one if necessary.

        Returns:
            The active ShellSession.

        Raises:
            RuntimeError: If shell process fails to start.
        """
        if self._session is not None and self._session.process.returncode is None:
            # Session exists and process is still alive
            return self._session

        logger.info("Starting new shell session: {executable}", executable=self._config.shell_executable)

        try:
            # Start bash subprocess with pipes for stdin/stdout/stderr
            process = await asyncio.create_subprocess_exec(
                self._config.shell_executable,
                *self._config.shell_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Initialize shell environment
            # Disable command history to prevent pollution
            await self._write_to_stdin(process, "set +o history\n")

            # Disable PS1/PS2 prompts to simplify output parsing
            await self._write_to_stdin(process, 'PS1=""\n')
            await self._write_to_stdin(process, 'PS2=""\n')

            # Get initial working directory
            cwd = "/"  # Default, will be updated by first state capture
            env = {}   # Will be populated by first state capture

            self._session = ShellSession(process=process, cwd=cwd, env=env)
            logger.info("Shell session started successfully, PID: {pid}", pid=process.pid)

            return self._session

        except Exception as e:
            logger.error("Failed to start shell process: {error}", error=e)
            raise RuntimeError(f"Failed to start shell process: {e}") from e

    async def _write_to_stdin(self, process: asyncio.subprocess.Process, data: str):
        """
        Write data to the process stdin.

        Args:
            process: The subprocess to write to.
            data: String data to write.

        Raises:
            RuntimeError: If stdin is not available.
        """
        if process.stdin is None:
            raise RuntimeError("Process stdin is not available")

        process.stdin.write(data.encode())
        await process.stdin.drain()

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
