"""Command implementations for TunaCode CLI."""

# Import all command classes for easy access
from .conversation import CompactCommand
from .debug import (
    DumpCommand,
    FixCommand,
    IterationsCommand,
    ParseToolsCommand,
    ThoughtsCommand,
    YoloCommand,
)
from .development import BranchCommand, InitCommand
from .model import ModelCommand
from .system import ClearCommand, HelpCommand, RefreshConfigCommand, StreamingCommand, UpdateCommand
from .todo import TodoCommand

__all__ = [
    # System commands
    "HelpCommand",
    "ClearCommand",
    "RefreshConfigCommand",
    "StreamingCommand",
    "UpdateCommand",
    # Debug commands
    "YoloCommand",
    "DumpCommand",
    "ThoughtsCommand",
    "IterationsCommand",
    "FixCommand",
    "ParseToolsCommand",
    # Development commands
    "BranchCommand",
    "InitCommand",
    # Model commands
    "ModelCommand",
    # Conversation commands
    "CompactCommand",
    # Todo commands
    "TodoCommand",
]
