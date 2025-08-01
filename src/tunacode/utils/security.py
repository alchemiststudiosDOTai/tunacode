"""
Security utilities for safe command execution and input validation.
Provides defensive measures against command injection attacks.
"""

import re
import shlex
import subprocess
from typing import List, Optional

from tunacode.core.logging.logger import get_logger

logger = get_logger(__name__)

# Dangerous shell metacharacters that indicate potential injection
DANGEROUS_CHARS = [
    ";",
    "&",
    "|",
    "`",
    "$",
    "(",
    ")",
    "{",
    "}",
    "<",
    ">",
    "\n",
    "\r",
    "\\",
    '"',
    "'",
]

# Common injection patterns
INJECTION_PATTERNS = [
    r";\s*\w+",  # Command chaining with semicolon
    r"&&\s*\w+",  # Command chaining with &&
    r"\|\s*\w+",  # Piping to another command
    r"`[^`]+`",  # Command substitution with backticks
    r"\$\([^)]+\)",  # Command substitution with $()
    r">\s*[/\w]",  # Output redirection
    r"<\s*[/\w]",  # Input redirection
]


class CommandSecurityError(Exception):
    """Raised when a command fails security validation."""

    pass


def validate_command_safety(command: str, allow_shell_features: bool = False) -> None:
    """
    Validate that a command is safe to execute.

    Args:
        command: The command string to validate
        allow_shell_features: If True, allows some shell features like pipes

    Raises:
        CommandSecurityError: If the command contains potentially dangerous patterns
    """
    if not command or not command.strip():
        raise CommandSecurityError("Empty command not allowed")

    # Log the command being validated
    logger.info(f"Validating command: {command[:100]}...")

    # Always check for the most dangerous patterns regardless of shell features
    dangerous_patterns = [
        r"rm\s+-rf\s+/",  # Dangerous rm commands
        r"sudo\s+rm",  # Sudo rm commands
        r">\s*/dev/sd[a-z]",  # Writing to disk devices
        r"dd\s+.*of=/dev/",  # DD to devices
        r"mkfs\.",  # Format filesystem
        r"fdisk",  # Partition manipulation
        r":\(\)\{.*\}\;",  # Fork bomb pattern
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            logger.error(f"Highly dangerous pattern '{pattern}' detected in command")
            raise CommandSecurityError("Command contains dangerous pattern and is blocked")

    if not allow_shell_features:
        # Check for dangerous characters (but allow some for CLI tools)
        restricted_chars = [";", "&", "`", "$", "{", "}"]  # More permissive for CLI
        for char in restricted_chars:
            if char in command:
                logger.warning(f"Potentially dangerous character '{char}' detected in command")
                raise CommandSecurityError(f"Potentially unsafe character '{char}' in command")

        # Check for injection patterns (more selective)
        strict_patterns = [
            r";\s*rm\s+",  # Command chaining to rm
            r"&&\s*rm\s+",  # Command chaining to rm
            r"`[^`]*rm[^`]*`",  # Command substitution with rm
            r"\$\([^)]*rm[^)]*\)",  # Command substitution with rm
        ]

        for pattern in strict_patterns:
            if re.search(pattern, command):
                logger.warning(f"Dangerous injection pattern '{pattern}' detected in command")
                raise CommandSecurityError("Potentially unsafe pattern detected in command")


def sanitize_command_args(args: List[str]) -> List[str]:
    """
    Sanitize command arguments by shell-quoting them.

    Args:
        args: List of command arguments

    Returns:
        List of sanitized arguments
    """
    return [shlex.quote(arg) for arg in args]


def safe_subprocess_run(
    command: str,
    shell: bool = False,
    validate: bool = True,
    timeout: Optional[int] = None,
    **kwargs,
) -> subprocess.CompletedProcess:
    """
    Safely execute a subprocess with security validation.

    Args:
        command: Command to execute (string if shell=True, list if shell=False)
        shell: Whether to use shell execution (discouraged)
        validate: Whether to validate command safety
        timeout: Timeout in seconds
        **kwargs: Additional subprocess arguments

    Returns:
        CompletedProcess result

    Raises:
        CommandSecurityError: If command fails security validation
    """
    if validate and shell and isinstance(command, str):
        validate_command_safety(command, allow_shell_features=shell)

    # Log the command execution
    logger.info(f"Executing command: {str(command)[:100]}...")

    try:
        if shell:
            # When using shell=True, command should be a string
            result = subprocess.run(command, shell=True, timeout=timeout, **kwargs)
        else:
            # When shell=False, command should be a list
            if isinstance(command, str):
                # Parse the string into a list
                command_list = shlex.split(command)
            else:
                command_list = command

            result = subprocess.run(command_list, shell=False, timeout=timeout, **kwargs)

        logger.info(f"Command completed with return code: {result.returncode}")
        return result

    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout} seconds")
        raise
    except Exception as e:
        logger.error(f"Command execution failed: {str(e)}")
        raise


def safe_subprocess_popen(
    command: str, shell: bool = False, validate: bool = True, **kwargs
) -> subprocess.Popen:
    """
    Safely create a subprocess.Popen with security validation.

    Args:
        command: Command to execute
        shell: Whether to use shell execution (discouraged)
        validate: Whether to validate command safety
        **kwargs: Additional Popen arguments

    Returns:
        Popen process object

    Raises:
        CommandSecurityError: If command fails security validation
    """
    if validate and shell and isinstance(command, str):
        validate_command_safety(command, allow_shell_features=shell)

    # Log the command execution
    logger.info(f"Creating Popen for command: {str(command)[:100]}...")

    if shell:
        # When using shell=True, command should be a string
        return subprocess.Popen(command, shell=True, **kwargs)
    else:
        # When shell=False, command should be a list
        if isinstance(command, str):
            command_list = shlex.split(command)
        else:
            command_list = command

        return subprocess.Popen(command_list, shell=False, **kwargs)
