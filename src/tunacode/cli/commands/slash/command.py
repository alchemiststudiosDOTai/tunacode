"""SlashCommand implementation for markdown-based commands."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from ..base import Command, CommandCategory
from .processor import MarkdownTemplateProcessor
from .types import SlashCommandMetadata

if TYPE_CHECKING:
    from ....types import CommandArgs, CommandContext, CommandResult

logger = logging.getLogger(__name__)


class SlashCommand(Command):
    """Markdown-based slash command implementation."""

    def __init__(self, file_path: Path, namespace: str, command_parts: List[str]):
        self.file_path = file_path
        self.namespace = namespace  # "project" or "user"
        self.command_parts = command_parts  # ["test", "unit"] for test:unit
        self._metadata: Optional[SlashCommandMetadata] = None
        self._content: Optional[str] = None
        self._loaded = False

    def _lazy_load(self) -> None:
        """Load content and metadata on first access."""
        if self._loaded:
            return

        try:
            content = self.file_path.read_text(encoding="utf-8")
            processor = MarkdownTemplateProcessor()
            frontmatter, markdown = processor.parse_frontmatter(content)

            self._content = markdown
            self._metadata = SlashCommandMetadata(
                description=frontmatter.get("description", "Custom command")
                if frontmatter
                else "Custom command",
                allowed_tools=frontmatter.get("allowed-tools") if frontmatter else None,
                timeout=frontmatter.get("timeout") if frontmatter else None,
                parameters=frontmatter.get("parameters", {}) if frontmatter else {},
            )
            self._loaded = True

        except Exception as e:
            logger.error(f"Failed to load slash command {self.file_path}: {e}")
            self._metadata = SlashCommandMetadata(description=f"Error loading command: {str(e)}")
            self._content = ""
            self._loaded = True

    @property
    def name(self) -> str:
        """The primary name of the command."""
        return f"{self.namespace}:{':'.join(self.command_parts)}"

    @property
    def aliases(self) -> List[str]:
        """Alternative names/aliases for the command."""
        return [f"/{self.name}"]  # Slash prefix for invocation

    @property
    def description(self) -> str:
        """Description of what the command does."""
        self._lazy_load()
        return self._metadata.description if self._metadata else "Custom command"

    @property
    def category(self) -> CommandCategory:
        """Category this command belongs to."""
        return CommandCategory.SYSTEM  # Could be made configurable

    async def execute(self, args: "CommandArgs", context: "CommandContext") -> "CommandResult":
        """Execute the slash command."""
        self._lazy_load()

        if not self._content:
            return "Error: Could not load command content"

        # Process template with context injection
        max_context_size = 100_000
        max_files = 50
        if self._metadata and self._metadata.parameters:
            max_context_size = int(self._metadata.parameters.get("max_context_size", 100_000))
            max_files = int(self._metadata.parameters.get("max_files", 50))

        processor = MarkdownTemplateProcessor(
            max_context_size=max_context_size, max_files=max_files
        )

        injection_result = processor.process_template_with_context(self._content, args, context)

        # Show warnings if any (import ui dynamically to avoid circular imports)
        if injection_result.warnings:
            try:
                from ....ui import console as ui

                for warning in injection_result.warnings:
                    await ui.warning(f"Context injection: {warning}")
            except ImportError:
                # Fallback to logging if UI not available
                for warning in injection_result.warnings:
                    logger.warning(f"Context injection: {warning}")

        # Show context stats for debugging (if enabled)
        try:
            if context.state_manager.session.show_thoughts:
                from ....ui import console as ui

                await ui.muted(
                    f"Context: {len(injection_result.included_files)} files, "
                    f"{injection_result.total_size} chars, "
                    f"{len(injection_result.executed_commands)} commands"
                )
        except (ImportError, AttributeError):
            pass  # Skip context stats if not available

        # Apply tool restrictions if specified
        if self._metadata and self._metadata.allowed_tools:
            # Set tool handler restrictions similar to template system
            if (
                hasattr(context.state_manager, "tool_handler")
                and context.state_manager.tool_handler
            ):
                # Store current restrictions and apply new ones
                original_restrictions = getattr(
                    context.state_manager.tool_handler, "allowed_tools", None
                )
                context.state_manager.tool_handler.allowed_tools = self._metadata.allowed_tools

                try:
                    # Execute with restrictions
                    if context.process_request:
                        result = await context.process_request(
                            injection_result.processed_content, context.state_manager, True
                        )
                        return result
                    else:
                        return "Error: No process_request callback available"
                finally:
                    # Restore original restrictions
                    context.state_manager.tool_handler.allowed_tools = original_restrictions
        else:
            # Execute without restrictions
            if context.process_request:
                result = await context.process_request(
                    injection_result.processed_content, context.state_manager, True
                )
                return result
            else:
                return "Error: No process_request callback available"

        # Default return if no metadata
        return "Command executed"
