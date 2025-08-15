"""Core types and data structures for slash command system."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    pass


class CommandSource(Enum):
    """Command source with priority ordering (lower value = higher priority)."""

    PROJECT_TUNACODE = 1  # Highest priority
    PROJECT_CLAUDE = 2  # Project fallback
    USER_TUNACODE = 3  # User primary
    USER_CLAUDE = 4  # Lowest priority


class SecurityLevel(Enum):
    """Security validation levels."""

    STRICT = "strict"  # Minimal commands allowed
    MODERATE = "moderate"  # Balanced security (default)
    PERMISSIVE = "permissive"  # More commands allowed


@dataclass
class SlashCommandMetadata:
    """Metadata parsed from YAML frontmatter."""

    description: str
    allowed_tools: Optional[List[str]] = None
    timeout: Optional[int] = None
    parameters: Dict[str, str] = field(default_factory=dict)
    source: CommandSource = CommandSource.PROJECT_TUNACODE


@dataclass
class CommandDiscoveryResult:
    """Result of command discovery process."""

    commands: Dict[str, Any]  # SlashCommand instances
    conflicts: List[Tuple[str, List[Path]]]  # Commands with conflicts
    errors: List[Tuple[Path, Exception]]  # Files that failed to load
    stats: Dict[str, int] = field(default_factory=dict)


@dataclass
class ContextInjectionResult:
    """Result of template processing with context injection."""

    processed_content: str
    included_files: List[Path]
    executed_commands: List[str]
    total_size: int
    warnings: List[str]


@dataclass
class SecurityViolation:
    """Details about a security violation."""

    type: str
    message: str
    command: str
    severity: str  # "error", "warning", "info"


@dataclass
class ValidationResult:
    """Result of security validation."""

    allowed: bool
    violations: List[SecurityViolation]
    sanitized_command: Optional[str] = None


@dataclass
class AuditEntry:
    """Single audit log entry for security monitoring."""

    timestamp: datetime
    command_name: str
    user: str
    command_content: str
    included_files: List[str]
    executed_commands: List[str]
    security_violations: List[Dict]
    success: bool
    error_message: Optional[str] = None
