"""Command registry and factory for TunaCode CLI commands.

CLAUDE_ANCHOR[command-registry]: Central command registration and execution
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from ...exceptions import ValidationError
from ...templates.loader import TemplateLoader
from ...types import CommandArgs, CommandContext, ProcessRequestCallback
from .base import Command, CommandCategory

# Import all command implementations
from .implementations.command_reload import CommandReloadCommand
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
from .implementations.plan import ExitPlanCommand, PlanCommand
from .implementations.quickstart import QuickStartCommand
from .implementations.system import (
    ClearCommand,
    HelpCommand,
    RefreshConfigCommand,
    StreamingCommand,
    UpdateCommand,
)
from .implementations.template import TemplateCommand
from .implementations.todo import TodoCommand
from .template_shortcut import TemplateShortcutCommand

logger = logging.getLogger(__name__)


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
        elif command_class == CommandReloadCommand:
            return CommandReloadCommand(self.dependencies.command_registry)

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
        self._shortcuts_loaded = False

        # Slash command support
        self._slash_loader: Optional[Any] = None  # SlashCommandLoader
        self._slash_discovery_result: Optional[Any] = None  # CommandDiscoveryResult
        self._slash_enabled: bool = True  # Feature flag

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

        # Step 1: Discover built-in commands
        self._discover_builtin_commands()

        # Step 2: Discover slash commands (if enabled)
        if self._slash_enabled:
            self._discover_slash_commands()

        self._discovered = True

    def _discover_builtin_commands(self) -> None:
        """Discover and register built-in command classes."""
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
            TemplateCommand,
            TodoCommand,
            CommandReloadCommand,
            PlanCommand,  # Add plan command
            ExitPlanCommand,  # Add exit plan command
            QuickStartCommand,  # Add quickstart command
        ]

        # Register all discovered commands
        for command_class in command_classes:
            self.register_command_class(command_class)  # type: ignore[arg-type]

    def _discover_slash_commands(self) -> None:
        """Discover and register markdown-based slash commands."""
        try:
            if not self._slash_loader:
                # Dynamic import to avoid circular dependency
                from .slash.loader import SlashCommandLoader

                project_root = Path.cwd()
                user_home = Path.home()
                self._slash_loader = SlashCommandLoader(project_root, user_home)

            self._slash_discovery_result = self._slash_loader.discover_commands()

            # Register all discovered commands
            registered_count = 0
            for command_name, command in self._slash_discovery_result.commands.items():
                try:
                    self.register(command)
                    registered_count += 1
                except Exception as e:
                    logger.warning(f"Failed to register slash command '{command_name}': {e}")

            # Log discovery summary
            if registered_count > 0:
                logger.info(f"Registered {registered_count} slash commands")

            # Report conflicts and errors
            self._report_slash_command_issues()

        except Exception as e:
            logger.error(f"Slash command discovery failed: {e}")
            # Don't fail the entire system if slash commands can't load

    def _report_slash_command_issues(self) -> None:
        """Report conflicts and errors from slash command discovery."""
        if not self._slash_discovery_result:
            return

        # Report conflicts
        if self._slash_discovery_result.conflicts:
            logger.info(f"Resolved {len(self._slash_discovery_result.conflicts)} command conflicts")
            for cmd_name, conflicting_paths in self._slash_discovery_result.conflicts:
                logger.debug(
                    f"  {cmd_name}: {conflicting_paths[1]} overrode {conflicting_paths[0]}"
                )

        # Report errors (limit to first 3 for brevity)
        if self._slash_discovery_result.errors:
            logger.warning(
                f"Failed to load {len(self._slash_discovery_result.errors)} command files"
            )
            for path, error in self._slash_discovery_result.errors[:3]:
                logger.warning(f"  {path}: {str(error)[:100]}...")

    def register_all_default_commands(self) -> None:
        """Register all default commands (backward compatibility)."""
        self.discover_commands()

    def load_template_shortcuts(self) -> None:
        """Load and register template shortcuts dynamically."""
        if self._shortcuts_loaded:
            return

        try:
            loader = TemplateLoader()
            shortcuts = loader.get_templates_with_shortcuts()

            for shortcut, template in shortcuts.items():
                # Create a template shortcut command instance
                shortcut_command = TemplateShortcutCommand(template)
                self.register(shortcut_command)

            self._shortcuts_loaded = True

        except Exception as e:
            # Don't fail if templates can't be loaded
            print(f"Warning: Failed to load template shortcuts: {str(e)}")

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
        # Load template shortcuts
        self.load_template_shortcuts()

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

    # Slash command utilities
    def get_slash_commands(self) -> Dict[str, Command]:
        """Get all registered slash commands."""
        slash_commands = {}
        for name, command in self._commands.items():
            # Duck typing for SlashCommand - check if it has file_path attribute
            if hasattr(command, "file_path") and hasattr(command, "namespace"):
                slash_commands[name] = command
        return slash_commands

    def reload_slash_commands(self) -> int:
        """Reload slash commands (useful for development)."""
        if not self._slash_enabled:
            return 0

        slash_commands = self.get_slash_commands()
        for cmd_name in list(slash_commands.keys()):
            if cmd_name in self._commands:
                del self._commands[cmd_name]
                # Also remove from category
                for category_commands in self._categories.values():
                    category_commands[:] = [
                        cmd
                        for cmd in category_commands
                        if not (hasattr(cmd, "file_path") and cmd.name == cmd_name)
                    ]

        # Rediscover slash commands
        self._slash_loader = None
        self._slash_discovery_result = None
        self._discover_slash_commands()

        return len(self.get_slash_commands())

    def enable_slash_commands(self, enabled: bool = True) -> None:
        """Enable or disable slash command discovery."""
        self._slash_enabled = enabled

    def get_slash_command_stats(self) -> Dict[str, Any]:
        """Get detailed statistics about slash command discovery."""
        if not self._slash_discovery_result:
            return {"enabled": self._slash_enabled, "discovered": False}

        return {
            "enabled": self._slash_enabled,
            "discovered": True,
            "stats": self._slash_discovery_result.stats,
            "conflicts": len(self._slash_discovery_result.conflicts),
            "errors": len(self._slash_discovery_result.errors),
            "registered_commands": len(self.get_slash_commands()),
        }
