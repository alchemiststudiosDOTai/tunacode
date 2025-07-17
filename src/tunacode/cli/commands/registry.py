"""Command registry and factory for TunaCode CLI commands."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type

from ...exceptions import ValidationError
from ...types import CommandArgs, CommandContext, ProcessRequestCallback
from .base import Command, CommandCategory

# Import all command implementations
from .implementations.conversation import CompactCommand
from .implementations.debug import (
    DumpCommand,
    FixCommand,
    IterationsCommand,
    ParseToolsCommand,
    ThoughtsCommand,
    YoloCommand,
)
from .implementations.development import BranchCommand, InitCommand
from .implementations.model import ModelCommand
from .implementations.system import (
    ClearCommand,
    HelpCommand,
    RefreshConfigCommand,
    StreamingCommand,
    UpdateCommand,
)
from .implementations.todo import TodoCommand


@dataclass
class CommandDependencies:
    """Container for command dependencies."""

    process_request_callback: Optional[ProcessRequestCallback] = None
    command_registry: Optional[Any] = None  # Reference to the registry itself


class CommandFactory:
    """Factory for creating commands with proper dependency injection."""

    def __init__(self, dependencies: Optional[CommandDependencies] = None):
        self.dependencies = dependencies or CommandDependencies()

    def create_command(self, command_class: Type[Command]) -> Command:
        """Create a command instance with proper dependencies."""
        # Special handling for commands that need dependencies
        if command_class == CompactCommand:
            return CompactCommand(self.dependencies.process_request_callback)
        elif command_class == HelpCommand:
            return HelpCommand(self.dependencies.command_registry)

        # Default creation for commands without dependencies
        return command_class()

    def update_dependencies(self, **kwargs) -> None:
        """Update factory dependencies."""
        for key, value in kwargs.items():
            if hasattr(self.dependencies, key):
                setattr(self.dependencies, key, value)


class CommandRegistry:
    """Registry for managing commands with auto-discovery and categories."""

    def __init__(self, factory: Optional[CommandFactory] = None):
        self._commands: Dict[str, Command] = {}
        self._categories: Dict[CommandCategory, List[Command]] = {
            category: [] for category in CommandCategory
        }
        self._factory = factory or CommandFactory()
        self._discovered = False

        # Set registry reference in factory dependencies
        self._factory.update_dependencies(command_registry=self)

    def register(self, command: Command) -> None:
        """Register a command and its aliases."""
        # Register by primary name
        self._commands[command.name] = command

        # Register all aliases
        for alias in command.aliases:
            self._commands[alias.lower()] = command

        # Add to category (remove existing instance first to prevent duplicates)
        category_commands = self._categories[command.category]
        # Remove any existing instance of this command class
        self._categories[command.category] = [
            cmd for cmd in category_commands if cmd.__class__ != command.__class__
        ]
        # Add the new instance
        self._categories[command.category].append(command)

    def register_command_class(self, command_class: Type[Command]) -> None:
        """Register a command class using the factory."""
        command = self._factory.create_command(command_class)
        self.register(command)

    def discover_commands(self) -> None:
        """Auto-discover and register all command classes."""
        if self._discovered:
            return

        # List of all command classes to register
        command_classes = [
            YoloCommand,
            DumpCommand,
            ThoughtsCommand,
            IterationsCommand,
            ClearCommand,
            FixCommand,
            ParseToolsCommand,
            RefreshConfigCommand,
            StreamingCommand,
            UpdateCommand,
            HelpCommand,
            BranchCommand,
            CompactCommand,
            ModelCommand,
            InitCommand,
            TodoCommand,
        ]

        # Register all discovered commands
        for command_class in command_classes:
            self.register_command_class(command_class)

        self._discovered = True

    def register_all_default_commands(self) -> None:
        """Register all default commands (backward compatibility)."""
        self.discover_commands()

    def set_process_request_callback(self, callback: ProcessRequestCallback) -> None:
        """Set the process_request callback for commands that need it."""
        # Only update if callback has changed
        if self._factory.dependencies.process_request_callback == callback:
            return

        self._factory.update_dependencies(process_request_callback=callback)

        # Re-register CompactCommand with new dependency if already registered
        if "compact" in self._commands:
            self.register_command_class(CompactCommand)

    async def execute(self, command_text: str, context: CommandContext) -> Any:
        """
        Execute a command.

        Args:
            command_text: The full command text
            context: Execution context

        Returns:
            Command-specific return value, or None if command not found

        Raises:
            ValidationError: If command is not found or empty
        """
        # Ensure commands are discovered
        self.discover_commands()

        parts = command_text.split()
        if not parts:
            raise ValidationError("Empty command")

        command_name = parts[0].lower()
        args = parts[1:]

        # First try exact match
        if command_name in self._commands:
            command = self._commands[command_name]
            return await command.execute(args, context)

        # Try partial matching
        matches = self.find_matching_commands(command_name)

        if not matches:
            raise ValidationError(f"Unknown command: {command_name}")
        elif len(matches) == 1:
            # Unambiguous match
            command = self._commands[matches[0]]
            return await command.execute(args, context)
        else:
            # Ambiguous - show possibilities
            matches_str = ", ".join(sorted(set(matches)))
            raise ValidationError(
                f"Ambiguous command '{command_name}'. Did you mean: {matches_str}?"
            )

    def find_matching_commands(self, partial_command: str) -> List[str]:
        """
        Find all commands that start with the given partial command.

        Args:
            partial_command: The partial command to match

        Returns:
            List of matching command names
        """
        self.discover_commands()
        partial = partial_command.lower()
        return [cmd for cmd in self._commands.keys() if cmd.startswith(partial)]

    def is_command(self, text: str) -> bool:
        """Check if text starts with a registered command (supports partial matching)."""
        if not text:
            return False

        parts = text.split()
        if not parts:
            return False

        command_name = parts[0].lower()

        # Check exact match first
        if command_name in self._commands:
            return True

        # Check partial match
        return len(self.find_matching_commands(command_name)) > 0

    def get_command_names(self) -> CommandArgs:
        """Get all registered command names (including aliases)."""
        self.discover_commands()
        return sorted(self._commands.keys())

    def get_commands_by_category(self, category: CommandCategory) -> List[Command]:
        """Get all commands in a specific category."""
        self.discover_commands()
        return self._categories.get(category, [])

    def get_all_categories(self) -> Dict[CommandCategory, List[Command]]:
        """Get all commands organized by category."""
        self.discover_commands()
        return self._categories.copy()
