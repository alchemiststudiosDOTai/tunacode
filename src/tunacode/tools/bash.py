"""Bash command execution tool for agent operations."""

import asyncio

import os
import re
import subprocess

from pydantic_ai.exceptions import ModelRetry

from tunacode.constants import (
    CMD_OUTPUT_TRUNCATED,
    COMMAND_OUTPUT_END_SIZE,
    COMMAND_OUTPUT_START_INDEX,
    COMMAND_OUTPUT_THRESHOLD,
    MAX_COMMAND_OUTPUT,
)
from tunacode.tools.decorators import base_tool


# Enhanced dangerous patterns from run_command.py
DESTRUCTIVE_PATTERNS = ["rm -rf", "rm -r", "rm /", "dd if=", "mkfs", "fdisk"]

# Comprehensive dangerous patterns from security module
DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/",  # Dangerous rm commands
    r"sudo\s+rm",  # Sudo rm commands
    r">\s*/dev/sd[a-z]",  # Writing to disk devices
    r"dd\s+.*of=/dev/",  # DD to devices
    r"mkfs\.",  # Format filesystem
    r"fdisk",  # Partition manipulation
    r":\(\)\{.*\}\;",  # Fork bomb pattern
]


@base_tool
async def bash(
    command: str,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int | None = 30,
    capture_output: bool = True,
) -> str:
    """Execute a bash command with enhanced features.

    Args:
        command: The bash command to execute.
        cwd: Working directory for the command.
        env: Additional environment variables to set.
        timeout: Command timeout in seconds (1-300, default 30).
        capture_output: Whether to capture stdout/stderr.

    Returns:
        Formatted output with exit code, stdout, and stderr.
    """
    _validate_inputs(command, cwd, timeout)
    _validate_command_security(command)

    exec_env = os.environ.copy()
    if env:
        for key, value in env.items():
            if isinstance(key, str) and isinstance(value, str):
                exec_env[key] = value

    exec_cwd = cwd or os.getcwd()

    process = None
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
            raise ModelRetry(
                f"Command timed out after {timeout} seconds: {command}\n"
                "Consider using a longer timeout or breaking the command into smaller parts."
            ) from err

        stdout_text = stdout.decode("utf-8", errors="replace").strip() if stdout else ""
        stderr_text = stderr.decode("utf-8", errors="replace").strip() if stderr else ""

        _check_common_errors(command, process.returncode, stderr_text)

        return _format_output(command, process.returncode, stdout_text, stderr_text, exec_cwd)

    except FileNotFoundError as err:
        raise ModelRetry(
            f"Shell not found. Cannot execute command: {command}\n"
            "This typically indicates a system configuration issue."
        ) from err
    finally:
        await _cleanup_process(process)


def _validate_command_security(command: str) -> None:
    """
    Validate command security using comprehensive validation from run_command.py.

    Args:
        command: The command string to validate

    Raises:
        ModelRetry: If the command fails security validation
    """
    if not command or not command.strip():
        raise ModelRetry("Empty command not allowed")

    # Always check for the most dangerous patterns regardless of shell features
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            raise ModelRetry(f"Command contains dangerous pattern and is blocked: {pattern}")

    # Check for dangerous injection patterns (more selective, before character checks)
    strict_patterns = [
        r";\s*rm\s+",  # Command chaining to rm
        r"&&\s*rm\s+",  # Command chaining to rm
        r"`[^`]*rm[^`]*`",  # Command substitution with rm
        r"\$\([^)]*rm[^)]*\)",  # Command substitution with rm
        r":\(\)\{.*\}\;",  # Fork bomb
    ]

    for pattern in strict_patterns:
        if re.search(pattern, command):
            raise ModelRetry(f"Potentially unsafe pattern detected in command: {pattern}")

    # Check for restricted characters (but allow safe environment variable usage)
    # Allow $ when used for legitimate environment variables or shell variables
    if re.search(r"\$[^({a-zA-Z_]", command):
        # $ followed by something that's not a valid variable start
        raise ModelRetry("Potentially unsafe character '$' in command")

    # Check other restricted characters but allow { } when part of valid variable expansion
    if "{" in command or "}" in command:  # noqa: SIM102
        # Only block braces if they're not part of valid variable expansion
        if not re.search(r"\$\{?\w+\}?", command):
            for char in ["{", "}"]:
                if char in command:
                    raise ModelRetry(f"Potentially unsafe character '{char}' in command")

    # Check remaining restricted characters
    for char in [";", "&", "`"]:
        if char in command:
            raise ModelRetry(f"Potentially unsafe character '{char}' in command")


def _validate_inputs(command: str, cwd: str | None, timeout: int | None) -> None:
    """Validate command inputs."""
    if timeout and (timeout < 1 or timeout > 300):
        raise ModelRetry(
            "Timeout must be between 1 and 300 seconds. "
            "Use shorter timeouts for quick commands, longer for builds/tests."
        )

    if cwd and not os.path.isdir(cwd):
        raise ModelRetry(
            f"Working directory '{cwd}' does not exist. "
            "Please verify the path or create the directory first."
        )

    if any(pattern in command for pattern in DESTRUCTIVE_PATTERNS):
        raise ModelRetry(
            f"Command contains potentially destructive operations: {command}\n"
            "Please confirm this is intentional and safe for your system."
        )


def _check_common_errors(command: str, returncode: int, stderr: str) -> None:
    """Check for common error patterns and provide guidance."""
    if returncode == 0 or not stderr:
        return


async def _cleanup_process(process) -> None:
    """Ensure process cleanup."""
    if process is None or process.returncode is not None:
        return

    try:
        try:
            process.terminate()
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except TimeoutError:
            process.kill()
            await asyncio.wait_for(process.wait(), timeout=1.0)
    except Exception as e:
        pass


def _format_output(command: str, exit_code: int, stdout: str, stderr: str, cwd: str) -> str:
    """Format command output."""
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

    if len(result) > MAX_COMMAND_OUTPUT:
        start_part = result[:COMMAND_OUTPUT_START_INDEX]
        if len(result) > COMMAND_OUTPUT_THRESHOLD:
            end_part = result[-COMMAND_OUTPUT_END_SIZE:]
        else:
            end_part = result[COMMAND_OUTPUT_START_INDEX:]
        result = start_part + CMD_OUTPUT_TRUNCATED + end_part

    return result
