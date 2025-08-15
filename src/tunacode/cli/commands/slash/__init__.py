"""Slash command system for TunaCode.

This module provides extensible markdown-based custom commands that can be
created by users and shared across teams.
"""

# Only export the main classes that external code needs
from .types import (
    CommandDiscoveryResult,
    CommandSource,
    ContextInjectionResult,
    SecurityLevel,
    SecurityViolation,
    SlashCommandMetadata,
    ValidationResult,
)

__all__ = [
    "CommandSource",
    "SlashCommandMetadata",
    "CommandDiscoveryResult",
    "ContextInjectionResult",
    "SecurityLevel",
    "SecurityViolation",
    "ValidationResult",
]

# Other classes can be imported directly when needed:
# from .command import SlashCommand
# from .loader import SlashCommandLoader
# from .processor import MarkdownTemplateProcessor
# from .validator import CommandValidator
