import asyncio
from pathlib import Path
from typing import override

from kosong.tooling import CallableTool2, ToolReturnType
from pydantic import BaseModel, Field

from kimi_cli.shell_manager import ShellManager
from kimi_cli.soul.approval import Approval
from kimi_cli.tools.utils import ToolRejectedError, ToolResultBuilder, load_desc
from kimi_cli.utils.logging import logger

MAX_TIMEOUT = 5 * 60


class Params(BaseModel):
    command: str = Field(description="The bash command to execute.")
    timeout: int = Field(
        description=(
            "The timeout in seconds for the command to execute. "
            "If the command takes longer than this, it will be killed."
        ),
        default=60,
        ge=1,
        le=MAX_TIMEOUT,
    )


class Bash(CallableTool2[Params]):
    name: str = "Bash"
    description: str = load_desc(Path(__file__).parent / "bash.md", {})
    params: type[Params] = Params

    def __init__(
        self,
        approval: Approval,
        shell_manager: ShellManager | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._approval = approval
        self._shell_manager = shell_manager

    @override
    async def __call__(self, params: Params) -> ToolReturnType:
        if not await self._approval.request(
            self.name,
            "run shell command",
            f"Run command `{params.command}`",
        ):
            return ToolRejectedError()

        # Mode selection: use persistent shell if available
        if self._shell_manager is not None:
            try:
                return await self._execute_persistent(params)
            except (RuntimeError, OSError) as e:
                # Persistent shell failed - fall back to ephemeral mode
                logger.warning(
                    "Persistent shell failed, falling back to ephemeral mode: {error}",
                    error=str(e),
                )
                self._shell_manager = None  # Disable for remaining commands
                return await self._execute_ephemeral(params)
        else:
            return await self._execute_ephemeral(params)

    async def _execute_ephemeral(self, params: Params) -> ToolReturnType:
        """Execute command in ephemeral subprocess (original behavior)."""
        builder = ToolResultBuilder()

        def stdout_cb(line: bytes):
            line_str = line.decode(errors="replace")
            builder.write(line_str)

        def stderr_cb(line: bytes):
            line_str = line.decode(errors="replace")
            builder.write(line_str)

        try:
            exitcode = await _stream_subprocess(
                params.command, stdout_cb, stderr_cb, params.timeout
            )

            if exitcode == 0:
                return builder.ok("Command executed successfully.")
            else:
                return builder.error(
                    f"Command failed with exit code: {exitcode}.",
                    brief=f"Failed with exit code: {exitcode}",
                )
        except TimeoutError:
            return builder.error(
                f"Command killed by timeout ({params.timeout}s)",
                brief=f"Killed by timeout ({params.timeout}s)",
            )

    async def _execute_persistent(self, params: Params) -> ToolReturnType:
        """Execute command in persistent shell session."""
        assert self._shell_manager is not None  # Caller ensures this
        builder = ToolResultBuilder()

        try:
            stdout, stderr, exitcode = await self._shell_manager.execute(
                params.command,
                timeout=params.timeout,
            )

            # Write output to builder
            if stdout:
                builder.write(stdout)
            if stderr:
                builder.write(stderr)

            if exitcode == 0:
                return builder.ok("Command executed successfully.")
            else:
                return builder.error(
                    f"Command failed with exit code: {exitcode}.",
                    brief=f"Failed with exit code: {exitcode}",
                )
        except TimeoutError:
            return builder.error(
                f"Command killed by timeout ({params.timeout}s)",
                brief=f"Killed by timeout ({params.timeout}s)",
            )


async def _stream_subprocess(command: str, stdout_cb, stderr_cb, timeout: int) -> int:
    async def _read_stream(stream, cb):
        while True:
            line = await stream.readline()
            if line:
                cb(line)
            else:
                break

    # FIXME: if the event loop is cancelled, an exception may be raised when the process finishes
    process = await asyncio.create_subprocess_shell(
        command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    try:
        await asyncio.wait_for(
            asyncio.gather(
                _read_stream(process.stdout, stdout_cb),
                _read_stream(process.stderr, stderr_cb),
            ),
            timeout,
        )
        return await process.wait()
    except TimeoutError:
        process.kill()
        raise
