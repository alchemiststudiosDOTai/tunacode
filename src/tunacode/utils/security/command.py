"""
Security utilities for safe command execution and input validation.
Provides defensive measures against command injection attacks.
"""

import re
import shlex
import subprocess


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
            raise CommandSecurityError("Command contains dangerous pattern and is blocked")

    if not allow_shell_features:
        # Check for dangerous characters (but allow some for CLI tools)
        restricted_chars = [";", "&", "`", "$", "{", "}"]  # More permissive for CLI
        for char in restricted_chars:
            if char in command:
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
                raise CommandSecurityError("Potentially unsafe pattern detected in command")


def sanitize_command_args(args: list[str]) -> list[str]:
    """
    Sanitize command arguments by shell-quoting them.

    Args:
        args: List of command arguments

    Returns:
        List of sanitized arguments
    """
    return [shlex.quote(arg) for arg in args]


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

    if shell:
        # When using shell=True, command should be a string
        return subprocess.Popen(command, shell=True, **kwargs)
    else:
        # When shell=False, command should be a list
        command_list = shlex.split(command) if isinstance(command, str) else command
        return subprocess.Popen(command_list, shell=False, **kwargs)
