"""Security validation for slash command execution."""

import logging
import re
from pathlib import Path
from typing import List

from .types import SecurityLevel, SecurityViolation, ValidationResult

logger = logging.getLogger(__name__)


class CommandValidator:
    """Comprehensive security validation system for slash commands."""

    def __init__(self, security_level: SecurityLevel = SecurityLevel.MODERATE):
        self.security_level = security_level
        self._init_security_rules()

    def _init_security_rules(self) -> None:
        """Initialize security rules based on security level."""

        # Always blocked commands (all security levels)
        self.ALWAYS_BLOCKED = {
            "rm",
            "rmdir",
            "del",
            "format",
            "fdisk",
            "mkfs",
            "sudo",
            "su",
            "passwd",
            "useradd",
            "userdel",
            "chmod",
            "chown",
            "chgrp",
            "setfacl",
            "iptables",
            "firewall-cmd",
            "ufw",
            "systemctl",
            "service",
            "initctl",
            "wget",
            "curl",
            "nc",
            "netcat",
            "telnet",
            "dd",
            "mount",
            "umount",
            "fsck",
        }

        # Dangerous patterns (all security levels)
        self.DANGEROUS_PATTERNS = [
            r"rm\s+.*-[rf]",  # Recursive/force delete
            r">\s*/dev/",  # Device access
            r"\|\s*sh\b",  # Pipe to shell
            r"\|\s*bash\b",  # Pipe to bash
            r"`[^`]*`",  # Command substitution
            r"\$\([^)]*\)",  # Command substitution
            r"(?:;|\|\||&&)",  # Command chaining (;, ||, &&)
            r"[|&]+\s*$",  # Trailing pipes
            r"eval\s+",  # Dynamic evaluation
            r"exec\s+",  # Process replacement
            r"source\s+",  # Script sourcing
            r"\.\s+/",  # Script sourcing (dot)
        ]

        # Security level specific rules
        if self.security_level == SecurityLevel.STRICT:
            self.ALLOWED_COMMANDS = {
                "git": ["status", "branch", "log", "show"],
                "ls": ["-la", "-l", "-a"],
                "cat": [],
                "echo": [],
                "date": [],
                "pwd": [],
            }
        elif self.security_level == SecurityLevel.MODERATE:
            self.ALLOWED_COMMANDS = {
                "git": ["status", "branch", "log", "diff", "show", "remote", "config"],
                "npm": ["list", "info", "view", "outdated", "audit", "install"],
                "python": ["-c", "-m", "--version", "-V"],
                "node": ["--version", "-v", "-e"],
                "ls": ["-la", "-l", "-a", "-h", "-R"],
                "cat": [],
                "head": [],
                "tail": [],
                "echo": [],
                "date": [],
                "pwd": [],
                "whoami": [],
                "grep": ["-r", "-n", "-i", "-v"],
                "find": ["-name", "-type", "-size"],
                "wc": ["-l", "-w", "-c"],
                "sort": [],
                "uniq": [],
                "cut": [],
            }
        else:  # PERMISSIVE
            self.ALLOWED_COMMANDS = {
                # All moderate commands plus more
                "git": ["status", "branch", "log", "diff", "show", "remote", "config"],
                "npm": ["list", "info", "view", "outdated", "audit"],
                "python": ["-c", "-m", "--version", "-V"],
                "node": ["--version", "-v", "-e"],
                "ls": ["-la", "-l", "-a", "-h", "-R"],
                "cat": [],
                "head": [],
                "tail": [],
                "echo": [],
                "date": [],
                "pwd": [],
                "whoami": [],
                "grep": ["-r", "-n", "-i", "-v"],
                "find": ["-name", "-type", "-size"],
                "wc": ["-l", "-w", "-c"],
                "sort": [],
                "uniq": [],
                "cut": [],
                "make": ["--version", "-n"],  # Dry run only
                "docker": ["ps", "images", "info", "version"],
                "kubectl": ["get", "describe", "logs", "version"],
                "terraform": ["version", "validate", "plan"],
            }

    def validate_shell_command(self, command: str) -> ValidationResult:
        """Comprehensive command validation with detailed results."""
        command = command.strip()
        violations = []

        if not command:
            violations.append(
                SecurityViolation(
                    type="empty_command",
                    message="Empty command not allowed",
                    command=command,
                    severity="error",
                )
            )
            return ValidationResult(False, violations)

        # Parse command
        parts = command.split()
        base_command = parts[0].lower()

        # Check for always blocked commands
        if base_command in self.ALWAYS_BLOCKED:
            violations.append(
                SecurityViolation(
                    type="blocked_command",
                    message=f"Command '{base_command}' is always blocked",
                    command=command,
                    severity="error",
                )
            )
            return ValidationResult(False, violations)

        # Check dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                violations.append(
                    SecurityViolation(
                        type="dangerous_pattern",
                        message=f"Command matches dangerous pattern: {pattern}",
                        command=command,
                        severity="error",
                    )
                )
                return ValidationResult(False, violations)

        # Check against whitelist
        if base_command not in self.ALLOWED_COMMANDS:
            violations.append(
                SecurityViolation(
                    type="unknown_command",
                    message=f"Command '{base_command}' not in whitelist",
                    command=command,
                    severity="warning"
                    if self.security_level == SecurityLevel.PERMISSIVE
                    else "error",
                )
            )

            if self.security_level != SecurityLevel.PERMISSIVE:
                return ValidationResult(False, violations)
        else:
            # Validate subcommands if specified
            allowed_subcommands = self.ALLOWED_COMMANDS[base_command]
            if allowed_subcommands and len(parts) > 1:
                subcommand = parts[1]
                if subcommand not in allowed_subcommands:
                    # Allow python scripts
                    if base_command == "python" and subcommand.endswith(".py"):
                        pass
                    elif base_command == "grep":
                        pass
                    else:
                        violations.append(
                            SecurityViolation(
                                type="invalid_subcommand",
                                message=f"Subcommand '{subcommand}' not allowed for '{base_command}'",
                                command=command,
                                severity="error",
                            )
                        )
                        return ValidationResult(False, violations)

        # Additional validation checks
        violations.extend(self._check_file_access_patterns(command))
        violations.extend(self._check_network_patterns(command))
        violations.extend(self._check_privilege_escalation(command))

        # Determine if command is allowed
        error_violations = [v for v in violations if v.severity == "error"]
        allowed = len(error_violations) == 0

        return ValidationResult(allowed, violations)

    def _check_file_access_patterns(self, command: str) -> List[SecurityViolation]:
        """Check for suspicious file access patterns."""
        violations = []

        # Sensitive file patterns
        sensitive_patterns = [
            r"/etc/passwd",
            r"/etc/shadow",
            r"/etc/hosts",
            r"/home/[^/]+/\.ssh",
            r"~/.ssh",
            r"/var/log/",
            r"/proc/",
            r"/sys/",
            r"\.env",
            r"\.secret",
            r"\.key",
        ]

        for pattern in sensitive_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                violations.append(
                    SecurityViolation(
                        type="sensitive_file_access",
                        message=f"Potential access to sensitive file: {pattern}",
                        command=command,
                        severity="warning",
                    )
                )

        return violations

    def _check_network_patterns(self, command: str) -> List[SecurityViolation]:
        """Check for network access patterns."""
        violations = []

        network_patterns = [
            r"curl\s+",
            r"wget\s+",
            r"nc\s+",
            r"netcat\s+",
            r"ssh\s+",
            r"scp\s+",
            r"rsync\s+.*:",
            r"ftp\s+",
            r"telnet\s+",
        ]

        for pattern in network_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                violations.append(
                    SecurityViolation(
                        type="network_access",
                        message=f"Network access detected: {pattern}",
                        command=command,
                        severity="error",
                    )
                )

        return violations

    def _check_privilege_escalation(self, command: str) -> List[SecurityViolation]:
        """Check for privilege escalation attempts."""
        violations = []

        privilege_patterns = [
            r"sudo\s+",
            r"su\s+",
            r"doas\s+",
            r"pkexec\s+",
            r"runuser\s+",
        ]

        for pattern in privilege_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                violations.append(
                    SecurityViolation(
                        type="privilege_escalation",
                        message=f"Privilege escalation attempt: {pattern}",
                        command=command,
                        severity="error",
                    )
                )

        return violations

    def validate_file_path(self, file_path: str, base_path: Path) -> ValidationResult:
        """Enhanced file path validation."""
        violations = []

        try:
            # Basic path traversal check
            resolved = (base_path / file_path).resolve()
            base_resolved = base_path.resolve()

            if not str(resolved).startswith(str(base_resolved)):
                violations.append(
                    SecurityViolation(
                        type="path_traversal",
                        message=f"Path traversal detected: {file_path}",
                        command=file_path,
                        severity="error",
                    )
                )
                return ValidationResult(False, violations)

            # Check for sensitive file access
            sensitive_dirs = [".ssh", ".git", ".env", "node_modules"]
            path_parts = Path(file_path).parts

            for sensitive in sensitive_dirs:
                if sensitive in path_parts:
                    violations.append(
                        SecurityViolation(
                            type="sensitive_directory",
                            message=f"Access to sensitive directory: {sensitive}",
                            command=file_path,
                            severity="warning",
                        )
                    )

            return ValidationResult(True, violations)

        except (OSError, ValueError) as e:
            violations.append(
                SecurityViolation(
                    type="invalid_path",
                    message=f"Invalid file path: {str(e)}",
                    command=file_path,
                    severity="error",
                )
            )
            return ValidationResult(False, violations)

    def validate_glob_pattern(self, pattern: str) -> ValidationResult:
        """Enhanced glob pattern validation."""
        violations = []

        # Dangerous glob patterns
        dangerous_globs = [
            r"\.\./.*",  # Parent directory traversal
            r"/etc/.*",
            r"/home/.*",
            r"/root/.*",  # System directories
            r"/var/.*",
            r"/usr/bin/.*",
            r"/bin/.*",
            r".*\.key$",
            r".*\.secret$",
            r".*\.pem$",  # Sensitive files
        ]

        for dangerous in dangerous_globs:
            if re.match(dangerous, pattern, re.IGNORECASE):
                violations.append(
                    SecurityViolation(
                        type="dangerous_glob",
                        message=f"Dangerous glob pattern: {dangerous}",
                        command=pattern,
                        severity="error",
                    )
                )
                return ValidationResult(False, violations)

        # Check for overly broad patterns
        if pattern in ["**/*", "*", "**"]:
            violations.append(
                SecurityViolation(
                    type="broad_glob",
                    message="Overly broad glob pattern",
                    command=pattern,
                    severity="warning",
                )
            )

        return ValidationResult(True, violations)
