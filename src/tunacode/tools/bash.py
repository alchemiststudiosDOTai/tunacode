"""Native tinyagent bash tool."""

from __future__ import annotations

import asyncio
import os
import subprocess
from asyncio.subprocess import Process

from tinyagent.agent_types import (
    AgentTool,
    AgentToolResult,
    AgentToolUpdateCallback,
    JsonObject,
    TextContent,
)

from tunacode.exceptions import ToolExecutionError, ToolRetryError, UserAbortError

COMMAND_OUTPUT_THRESHOLD = 3500
COMMAND_OUTPUT_START_INDEX = 2500
COMMAND_OUTPUT_END_SIZE = 1000
CMD_OUTPUT_TRUNCATED = "\n...\n[truncated]\n...\n"
MIN_TIMEOUT_SECONDS = 1
MAX_TIMEOUT_SECONDS = 600
DEFAULT_TIMEOUT_SECONDS = 120

_BASH_DESCRIPTION = """Execute a bash command with enhanced features.

Args:
    command: The bash command to execute.
    cwd: Working directory for the command.
    env: Additional environment variables to set.
    timeout: Command timeout in seconds (1-600, default 120).
    capture_output: Whether to capture stdout/stderr.

Returns:
    Formatted output with exit code, stdout, and stderr.
"""

_BASH_PARAMETERS: JsonObject = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "command": {
            "type": "string",
            "description": "The bash command to execute.",
        },
        "cwd": {
            "type": "string",
            "description": "Optional working directory.",
        },
        "env": {
            "type": "object",
            "description": "Optional environment variable overrides.",
            "additionalProperties": {"type": "string"},
        },
        "timeout": {
            "type": "integer",
            "description": "Command timeout in seconds between 1 and 600.",
        },
        "capture_output": {
            "type": "boolean",
            "description": "Whether to capture stdout and stderr.",
        },
    },
    "required": ["command"],
}


def _text_result(text: str) -> AgentToolResult:
    return AgentToolResult(content=[TextContent(text=text)], details={})


def _require_string_arg(args: JsonObject, key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str):
        raise ToolRetryError(f"Invalid arguments for tool 'bash': '{key}' must be a string.")
    return value


def _optional_string_arg(args: JsonObject, key: str) -> str | None:
    value = args.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ToolRetryError(f"Invalid arguments for tool 'bash': '{key}' must be a string.")
    return value


def _optional_int_arg(args: JsonObject, key: str, default: int | None) -> int | None:
    value = args.get(key, default)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ToolRetryError(f"Invalid arguments for tool 'bash': '{key}' must be an integer.")
    return value


def _optional_bool_arg(args: JsonObject, key: str, default: bool) -> bool:
    value = args.get(key, default)
    if not isinstance(value, bool):
        raise ToolRetryError(f"Invalid arguments for tool 'bash': '{key}' must be a boolean.")
    return value


def _optional_env_arg(args: JsonObject) -> dict[str, str] | None:
    value = args.get("env")
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ToolRetryError("Invalid arguments for tool 'bash': 'env' must be an object.")
    env: dict[str, str] = {}
    for env_key, env_value in value.items():
        if not isinstance(env_key, str) or not isinstance(env_value, str):
            raise ToolRetryError(
                "Invalid arguments for tool 'bash': 'env' must only contain string pairs."
            )
        env[env_key] = env_value
    return env


async def _run_bash(
    command: str,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int | None = DEFAULT_TIMEOUT_SECONDS,
    capture_output: bool = True,
    *,
    max_command_output: int,
) -> str:
    _validate_inputs(command, cwd, timeout)

    exec_env = os.environ.copy()
    if env:
        exec_env.update(env)

    exec_cwd = cwd or os.getcwd()
    process: Process | None = None
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=subprocess.PIPE if capture_output else None,
            stderr=subprocess.PIPE if capture_output else None,
            cwd=exec_cwd,
            env=exec_env,
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except TimeoutError as err:
            process.kill()
            await process.wait()
            raise ToolRetryError(
                f"Command timed out after {timeout} seconds: {command}\n"
                "Consider using a longer timeout or breaking the command into smaller parts."
            ) from err

        stdout_text = stdout.decode("utf-8", errors="replace").strip() if stdout else ""
        stderr_text = stderr.decode("utf-8", errors="replace").strip() if stderr else ""

        return_code = process.returncode
        assert return_code is not None
        _check_common_errors(command, return_code, stderr_text)
        return _format_output(
            command,
            return_code,
            stdout_text,
            stderr_text,
            exec_cwd,
            max_command_output=max_command_output,
        )
    except FileNotFoundError as err:
        raise ToolRetryError(
            f"Shell not found. Cannot execute command: {command}\n"
            "This typically indicates a system configuration issue."
        ) from err
    finally:
        await _cleanup_process(process)


def build_bash_tool(*, max_command_output: int) -> AgentTool:
    async def _execute_bash(
        tool_call_id: str,
        args: JsonObject,
        signal: asyncio.Event | None,
        on_update: AgentToolUpdateCallback,
    ) -> AgentToolResult:
        _ = (tool_call_id, on_update)
        if signal is not None and signal.is_set():
            raise UserAbortError("Tool execution aborted: bash")

        try:
            result = await _run_bash(
                command=_require_string_arg(args, "command"),
                cwd=_optional_string_arg(args, "cwd"),
                env=_optional_env_arg(args),
                timeout=_optional_int_arg(args, "timeout", DEFAULT_TIMEOUT_SECONDS),
                capture_output=_optional_bool_arg(args, "capture_output", True),
                max_command_output=max_command_output,
            )
        except (ToolRetryError, ToolExecutionError):
            raise
        except Exception as exc:  # noqa: BLE001
            raise ToolExecutionError(
                tool_name="bash", message=str(exc), original_error=exc
            ) from exc

        return _text_result(result)

    return AgentTool(
        name="bash",
        label="bash",
        description=_BASH_DESCRIPTION,
        parameters=_BASH_PARAMETERS,
        execute=_execute_bash,
    )


def _validate_inputs(command: str, cwd: str | None, timeout: int | None) -> None:
    if not command.strip():
        raise ToolRetryError("Empty command not allowed")

    if timeout is not None and (timeout < MIN_TIMEOUT_SECONDS or timeout > MAX_TIMEOUT_SECONDS):
        raise ToolRetryError(
            f"Timeout must be between {MIN_TIMEOUT_SECONDS} and {MAX_TIMEOUT_SECONDS} seconds. "
            "Use shorter timeouts for quick commands, longer for builds/tests."
        )

    if cwd and not os.path.isdir(cwd):
        raise ToolRetryError(
            f"Working directory '{cwd}' does not exist. "
            "Please verify the path or create the directory first."
        )


def _check_common_errors(command: str, returncode: int, stderr: str) -> None:
    _ = command
    if returncode == 0 or not stderr:
        return


async def _cleanup_process(process: Process | None) -> None:
    if process is None or process.returncode is not None:
        return

    try:
        try:
            process.terminate()
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except TimeoutError:
            process.kill()
            await asyncio.wait_for(process.wait(), timeout=1.0)
    except Exception:
        pass


def _format_output(
    command: str,
    exit_code: int,
    stdout: str,
    stderr: str,
    cwd: str,
    *,
    max_command_output: int,
) -> str:
    lines = [
        f"Command: {command}",
        f"Exit Code: {exit_code}",
        f"Working Directory: {cwd}",
        "",
        "STDOUT:",
        stdout or "(no output)",
        "",
        "STDERR:",
        stderr or "(no errors)",
    ]

    result = "\n".join(lines)
    if len(result) > max_command_output:
        start_part = result[:COMMAND_OUTPUT_START_INDEX]
        end_part = (
            result[-COMMAND_OUTPUT_END_SIZE:]
            if len(result) > COMMAND_OUTPUT_THRESHOLD
            else result[COMMAND_OUTPUT_START_INDEX:]
        )
        result = start_part + CMD_OUTPUT_TRUNCATED + end_part

    return result
