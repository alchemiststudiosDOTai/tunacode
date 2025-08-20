"""SlashCommandLoader for discovering and loading markdown-based commands."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .command import SlashCommand
from .types import CommandDiscoveryResult, CommandSource

logger = logging.getLogger(__name__)


class SlashCommandLoader:
    """Discovers and loads markdown-based slash commands with precedence rules."""

    def __init__(self, project_root: Path, user_home: Path):
        self.project_root = project_root
        self.user_home = user_home
        self.directories = self._build_directory_list()
        self._cache: Dict[str, SlashCommand] = {}

    def _build_directory_list(self) -> List[Tuple[Path, CommandSource, str]]:
        """Build prioritized directory list with sources and namespaces."""
        return [
            (
                self.project_root / ".tunacode" / "commands",
                CommandSource.PROJECT_TUNACODE,
                "project",
            ),
            (self.project_root / ".claude" / "commands", CommandSource.PROJECT_CLAUDE, "project"),
            (self.user_home / ".tunacode" / "commands", CommandSource.USER_TUNACODE, "user"),
            (self.user_home / ".claude" / "commands", CommandSource.USER_CLAUDE, "user"),
        ]

    def discover_commands(self) -> CommandDiscoveryResult:
        """Main discovery method with conflict resolution."""
        all_commands: Dict[str, Any] = {}
        conflicts = []
        errors = []
        stats = {"scanned_dirs": 0, "found_files": 0, "loaded_commands": 0}

        for directory, source, namespace in self.directories:
            if not directory.exists():
                continue

            stats["scanned_dirs"] += 1

            try:
                dir_commands = self._scan_directory(directory, source, namespace)
                stats["found_files"] += len(dir_commands)

                # Handle conflicts with precedence
                for cmd_name, cmd in dir_commands.items():
                    if cmd_name in all_commands:
                        existing_cmd = all_commands[cmd_name]
                        # Lower source value = higher priority
                        if (
                            source.value < existing_cmd._metadata.source.value
                            if existing_cmd._metadata
                            else float("inf")
                        ):
                            conflicts.append((cmd_name, [existing_cmd.file_path, cmd.file_path]))
                            all_commands[cmd_name] = cmd
                            logger.info(f"Command '{cmd_name}' overridden by {source.name}")
                    else:
                        all_commands[cmd_name] = cmd

                stats["loaded_commands"] += len(
                    [c for c in dir_commands.values() if c.name in all_commands]
                )

            except Exception as e:
                errors.append((directory, e))
                logger.error(f"Error scanning {directory}: {e}")

        logger.info(
            f"Discovered {len(all_commands)} slash commands from {stats['scanned_dirs']} directories"
        )
        return CommandDiscoveryResult(all_commands, conflicts, errors, stats)

    def _scan_directory(
        self, directory: Path, source: CommandSource, namespace: str
    ) -> Dict[str, SlashCommand]:
        """Recursively scan directory for markdown files."""
        commands = {}

        for md_file in directory.rglob("*.md"):
            try:
                # Calculate command parts from file path
                relative_path = md_file.relative_to(directory)
                command_parts = list(relative_path.parts[:-1])  # Directories
                command_parts.append(relative_path.stem)  # Filename without .md

                # Create command
                command = SlashCommand(md_file, namespace, command_parts)
                # Set source in metadata (will be used for precedence)
                if not hasattr(command, "_metadata") or command._metadata is None:
                    from .types import SlashCommandMetadata

                    command._metadata = SlashCommandMetadata(description="", source=source)
                else:
                    command._metadata.source = source

                command_name = command.name
                commands[command_name] = command

            except Exception as e:
                logger.warning(f"Failed to load command from {md_file}: {e}")

        return commands

    def reload_commands(self) -> CommandDiscoveryResult:
        """Reload all commands (useful for development)."""
        self._cache.clear()
        return self.discover_commands()

    def get_command_by_path(self, file_path: Path) -> SlashCommand:
        """Get command for a specific file path."""
        # Determine namespace and command parts from path
        for directory, source, namespace in self.directories:
            try:
                if file_path.is_relative_to(directory):
                    relative_path = file_path.relative_to(directory)
                    command_parts = list(relative_path.parts[:-1])
                    command_parts.append(relative_path.stem)

                    command = SlashCommand(file_path, namespace, command_parts)
                    return command
            except (ValueError, AttributeError):
                continue

        # Fallback to project namespace if path not in known directories
        parts = file_path.stem.split("_") if file_path.stem else ["unknown"]
        return SlashCommand(file_path, "project", parts)
