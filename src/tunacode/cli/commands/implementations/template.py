"""Template management commands for TunaCode CLI."""

from typing import Optional

from ....templates.loader import TemplateLoader
from ....types import CommandArgs, CommandContext
from ....ui import console as ui
from ..base import CommandCategory, CommandSpec, SimpleCommand


class TemplateCommand(SimpleCommand):
    """Manage and use templates for pre-approved tools."""

    spec = CommandSpec(
        name="template",
        aliases=["/template", "/tpl"],
        description="Manage and use templates",
        category=CommandCategory.SYSTEM,
    )

    async def execute(self, args: CommandArgs, context: CommandContext) -> Optional[str]:
        """Execute template command with subcommands."""
        if not args:
            await self._show_help()
            return None

        subcommand = args[0]

        if subcommand == "list":
            await self._list_templates()
        elif subcommand == "load":
            if len(args) < 2:
                await ui.error("Please specify a template name")
                await ui.muted("Usage: /template load <template-name>")
                return None
            await self._load_template(args[1], context)
        elif subcommand == "create":
            await self._create_template()
        elif subcommand == "clear":
            await self._clear_template(context)
        else:
            await ui.error(f"Unknown subcommand: {subcommand}")
            await self._show_help()

        return None

    async def _show_help(self) -> None:
        """Show help for template command."""
        await ui.info("Template management commands:")
        await ui.muted("  /template list      - List available templates")
        await ui.muted("  /template load <name> - Load and activate a template")
        await ui.muted("  /template create    - Create a new template interactively")
        await ui.muted("  /template clear     - Clear the active template")

    async def _list_templates(self) -> None:
        """List all available templates."""
        loader = TemplateLoader()
        template_names = loader.list_templates()

        if not template_names:
            await ui.info("No templates found.")
            await ui.muted("Create one with: /template create")
            return

        await ui.info("Available templates:")
        for name in template_names:
            template = loader.load_template(name)
            if template:
                tools_count = len(template.allowed_tools) if template.allowed_tools else 0
                shortcut_info = f" ({template.shortcut})" if template.shortcut else ""
                await ui.muted(
                    f"  • {name}{shortcut_info}: {template.description} ({tools_count} tools)"
                )

    async def _load_template(self, name: str, context: CommandContext) -> None:
        """Load and activate a template."""
        loader = TemplateLoader()
        template = loader.load_template(name)

        if not template:
            await ui.error(f"Template '{name}' not found")
            await ui.muted("Use '/template list' to see available templates")
            return

        # Set active template in tool handler
        if hasattr(context.state_manager, "tool_handler") and context.state_manager.tool_handler:
            context.state_manager.tool_handler.set_active_template(template)
        else:
            await ui.error("Tool handler not initialized. Please restart TunaCode.")
            return

        await ui.success(f"Loaded template: {template.name}")
        await ui.muted(f"Description: {template.description}")

        if template.shortcut:
            await ui.muted(f"Shortcut: {template.shortcut}")

        if template.allowed_tools:
            await ui.info(f"Allowed tools ({len(template.allowed_tools)}):")
            tools_str = ", ".join(template.allowed_tools)
            await ui.muted(f"  {tools_str}")

        # Execute the prompt if one is defined
        if template.prompt:
            await ui.info("Template has a default prompt:")
            await ui.muted(f"  {template.prompt}")
            await ui.muted("Submit this prompt to execute it")

    async def _create_template(self) -> None:
        """Create a new template interactively."""
        await ui.info("Interactive template creation is not yet implemented")
        await ui.muted("Please create templates manually as JSON files in:")
        await ui.muted("  ~/.config/tunacode/templates/")
        await ui.muted("")
        await ui.muted("Example template format:")
        await ui.muted("{")
        await ui.muted('  "name": "debug",')
        await ui.muted('  "description": "Debugging and analysis",')
        await ui.muted('  "shortcut": "/debug",')
        await ui.muted('  "prompt": "Debug the following issue: {argument}",')
        await ui.muted('  "allowed_tools": ["read_file", "grep", "list_dir", "run_command"]')
        await ui.muted("}")

    async def _clear_template(self, context: CommandContext) -> None:
        """Clear the currently active template."""
        if hasattr(context.state_manager, "tool_handler") and context.state_manager.tool_handler:
            context.state_manager.tool_handler.set_active_template(None)
            await ui.success("Cleared active template")
        else:
            await ui.error("Unable to clear template - tool handler not found")
