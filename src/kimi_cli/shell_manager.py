"""
Persistent shell session manager for Kimi CLI.

This module provides the ShellManager class which manages a persistent bash subprocess
that maintains state (working directory, environment variables) across multiple command
executions within an agent session.
"""

import asyncio
from dataclasses import dataclass

from kimi_cli.config import PersistentShellConfig
from kimi_cli.utils.logging import logger


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

        logger.info(
            "Starting new shell session: {executable}",
            executable=self._config.shell_executable
        )

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

    async def execute(
        self,
        command: str,
        timeout: int | None = None,
    ) -> tuple[str, str, int]:
        """
        Execute a command in the persistent shell session.

        The command is executed in the existing shell session, preserving all
        state changes (working directory, environment variables, etc.).

        Args:
            command: The shell command to execute.
            timeout: Optional timeout in seconds. Defaults to config.command_timeout.

        Returns:
            A tuple of (stdout, stderr, exit_code).

        Raises:
            asyncio.TimeoutError: If command execution exceeds timeout.
            RuntimeError: If shell process has died or communication fails.
        """
        session = await self._ensure_session()
        timeout = timeout or self._config.command_timeout

        logger.debug("Executing command in shell session: {command}", command=command)

        try:
            # Generate unique sentinel for this command execution
            import time
            sentinel_id = f"{self._config.exit_code_sentinel}{int(time.time() * 1000000)}"
            # Use double quotes to allow $? expansion
            sentinel_line = f'echo "{sentinel_id}$?"\n'

            # Write command followed by exit code sentinel
            await self._write_to_stdin(session.process, f"{command}\n")
            await self._write_to_stdin(session.process, sentinel_line)

            # Read output until we see the sentinel
            stdout_lines = []
            stderr_lines = []

            async def read_until_sentinel() -> int:
                """Read stdout/stderr until sentinel appears, return exit code."""
                exit_code = 0

                while True:
                    # Check if process died
                    if session.process.returncode is not None:
                        returncode = session.process.returncode
                        raise RuntimeError(f"Shell process died with code {returncode}")

                    # Read from stdout
                    if session.process.stdout is not None:
                        try:
                            line = await asyncio.wait_for(
                                session.process.stdout.readline(),
                                timeout=0.1
                            )
                            if line:
                                line_str = line.decode('utf-8', errors='replace')

                                # Check for sentinel
                                if line_str.startswith(sentinel_id):
                                    # Extract exit code from sentinel line
                                    exit_code_str = line_str[len(sentinel_id):].strip()
                                    try:
                                        exit_code = int(exit_code_str)
                                    except ValueError:
                                        logger.warning(
                                            "Failed to parse exit code: {code}",
                                            code=exit_code_str
                                        )
                                        exit_code = -1
                                    return exit_code
                                else:
                                    stdout_lines.append(line_str)
                        except asyncio.TimeoutError:
                            pass  # No data available, continue

                    # Read from stderr (non-blocking)
                    if session.process.stderr is not None:
                        try:
                            line = await asyncio.wait_for(
                                session.process.stderr.readline(),
                                timeout=0.01
                            )
                            if line:
                                stderr_lines.append(line.decode('utf-8', errors='replace'))
                        except asyncio.TimeoutError:
                            pass  # No data available

            # Execute with timeout
            exit_code = await asyncio.wait_for(read_until_sentinel(), timeout=timeout)

            stdout = ''.join(stdout_lines)
            stderr = ''.join(stderr_lines)

            logger.debug(
                "Command completed: exit_code={code}, stdout_len={out_len}, stderr_len={err_len}",
                code=exit_code,
                out_len=len(stdout),
                err_len=len(stderr)
            )

            return (stdout, stderr, exit_code)

        except asyncio.TimeoutError:
            logger.error(
                "Command timed out after {timeout}s: {command}",
                timeout=timeout,
                command=command
            )
            # Kill the session as it's likely in a bad state
            if self._session is not None:
                try:
                    self._session.process.kill()
                    await self._session.process.wait()
                except Exception:
                    pass
                self._session = None
            raise

        except Exception as e:
            logger.error("Command execution failed: {error}", error=e)
            raise

    async def get_state(self) -> dict[str, str | dict[str, str]]:
        """
        Capture the current state of the shell session.

        Returns:
            A dictionary containing:
                - 'cwd': Current working directory
                - 'env': Dictionary of environment variables

        Raises:
            RuntimeError: If unable to capture state.
        """
        if self._session is None:
            raise RuntimeError("No active shell session")

        logger.debug("Capturing shell session state")

        try:
            # Get current working directory
            cwd_stdout, cwd_stderr, cwd_code = await self.execute("pwd", timeout=5)
            if cwd_code != 0:
                logger.warning("Failed to get cwd: {stderr}", stderr=cwd_stderr)
                cwd = self._session.cwd  # Keep previous value
            else:
                cwd = cwd_stdout.strip()
                self._session.cwd = cwd

            # Get environment variables (use standard env, not null-terminated to avoid readline issues)
            env_stdout, env_stderr, env_code = await self.execute("env", timeout=5)
            if env_code != 0:
                logger.warning("Failed to get env: {stderr}", stderr=env_stderr)
                env = self._session.env  # Keep previous value
            else:
                # Parse line-based env output
                env = {}
                for line in env_stdout.strip().split('\n'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env[key] = value
                self._session.env = env

            logger.debug("State captured: cwd={cwd}, env_vars={count}", cwd=cwd, count=len(env))

            return {
                'cwd': cwd,
                'env': env,
            }

        except Exception as e:
            logger.error("Failed to capture state: {error}", error=e)
            raise RuntimeError(f"Failed to capture shell state: {e}") from e

    async def cleanup(self):
        """
        Cleanup all shell sessions.

        This method gracefully terminates the shell subprocess using a multi-stage
        approach:
        1. Send 'exit' command to stdin (graceful)
        2. If no response after 5s, send SIGTERM (polite force)
        3. If still running after 2s, send SIGKILL (hard force)

        The session is cleared regardless of termination success.
        """
        if self._session is None:
            logger.debug("No active shell session to cleanup")
            return

        process = self._session.process
        logger.info("Cleaning up shell session PID={pid}", pid=process.pid)

        try:
            # Stage 1: Graceful exit via 'exit' command
            if process.returncode is None:
                logger.debug("Sending 'exit' command to shell")
                try:
                    await self._write_to_stdin(process, "exit\n")
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                    logger.info("Shell process exited gracefully")
                    return
                except asyncio.TimeoutError:
                    logger.warning("Shell did not exit gracefully, sending SIGTERM")
                except Exception as e:
                    logger.warning("Error during graceful exit: {error}", error=e)

            # Stage 2: SIGTERM (polite force)
            if process.returncode is None:
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=2.0)
                    logger.info("Shell process terminated with SIGTERM")
                    return
                except asyncio.TimeoutError:
                    logger.warning("Shell did not respond to SIGTERM, sending SIGKILL")
                except Exception as e:
                    logger.warning("Error during SIGTERM: {error}", error=e)

            # Stage 3: SIGKILL (hard force)
            if process.returncode is None:
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=1.0)
                    logger.warning("Shell process killed with SIGKILL")
                except Exception as e:
                    logger.error("Failed to kill shell process: {error}", error=e)

        finally:
            # Always clear the session regardless of cleanup success
            self._session = None
            logger.debug("Shell session cleared")
