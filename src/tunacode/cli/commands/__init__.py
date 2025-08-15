"""Command system for TunaCode CLI.

This package provides a modular command system with:
- Base classes and infrastructure in `base.py`
- Command registry and factory in `registry.py`
- Command implementations organized by category in `implementations/`

The main public API provides backward compatibility with the original
commands.py module while enabling better organization and maintainability.

CLAUDE_ANCHOR[commands-module]: Command registry and dispatch system
"""

# Import base classes and infrastructure
from .base import Command, CommandCategory, CommandSpec, SimpleCommand

# Import all command implementations for backward compatibility
from .implementations import (
    BranchCommand,
    ClearCommand,
    CommandReloadCommand,
    CompactCommand,
    DumpCommand,
    FixCommand,
    HelpCommand,
    InitCommand,
    IterationsCommand,
    ModelCommand,
    ParseToolsCommand,
    RefreshConfigCommand,
    ThoughtsCommand,
    TodoCommand,
    UpdateCommand,
    YoloCommand,
)

# Import registry and factory
from .registry import CommandDependencies, CommandFactory, CommandRegistry

# Maintain backward compatibility by exposing the same public API
__all__ = [
    # Base infrastructure
    "Command",
    "SimpleCommand",
    "CommandSpec",
    "CommandCategory",
    # Registry and factory
    "CommandRegistry",
    "CommandFactory",
    "CommandDependencies",
    # All command classes (imported from implementations)
    "YoloCommand",
    "DumpCommand",
    "ThoughtsCommand",
    "IterationsCommand",
    "ClearCommand",
    "FixCommand",
    "ParseToolsCommand",
    "RefreshConfigCommand",
    "HelpCommand",
    "BranchCommand",
    "CompactCommand",
    "UpdateCommand",
    "ModelCommand",
    "InitCommand",
    "TodoCommand",
    "CommandReloadCommand",
]
